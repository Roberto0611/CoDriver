"""Probe-pack runner — feed a known-outcome order stream to a decision endpoint.

A probe pack is two files:

    pack.csv       the order stream, in the order_stream CSV format
                   (same columns as order_stream_example.csv)
    pack_key.json  the answer key: per-order expectations and the
                   cross-order consistency rules

The CSV alone is harmless. The key is what makes it gradeable, which is why
the two are separate files — the same split as the Forensic Auditor's
estate.db / ground_truth.json.

Usage:
    python3 run_probe_pack.py --pack pack.csv --key pack_key.json \
                              --endpoint http://localhost:8000/decide
    python3 run_probe_pack.py ... --report scorecard.json   # machine-readable
    python3 run_probe_pack.py ... --explain                 # also probe explain_decision

Stdlib only. Exits non-zero on any forced-case failure or consistency failure.

---------------------------------------------------------------------------
How the runner models courier state
---------------------------------------------------------------------------
Orders are POSTed in sim_time order. The runner always supplies
`courier_state_overrides`, so neither side has to guess what the other
believes the courier state to be. That state is computed from the pack's own
declared numbers, never from a travel-time model of our own:

  shift_elapsed_hours   (row sim_time - manifest shift_start_time)
  continuous_riding_min sum of `service_min` over accepted orders since the
                        last row marked `break_before`. Rows marked
                        `state_neutral` never contribute — they are
                        counterfactual variants of one decision moment
                        (a pay ladder, an A/B pair), not sequential work.
  in_flight_orders      accepted, non-neutral orders whose
                        sim_time + service_min is still in the future
  shift_end_time        from the manifest

Because accepted work drives the state, a team that skips the anchor orders
never accumulates the riding time that the heat and break probes need. Rather
than let those probes silently pass, a key entry may declare a
`state_precondition`. When the carried state does not satisfy it, the runner
substitutes the precondition and marks that probe `override` instead of
`carried`. Every probe is therefore always graded; the mode says whether the
team reached the state on its own.

---------------------------------------------------------------------------
Grades
---------------------------------------------------------------------------
anchor      Must be ACCEPTed. Priced far above any plausible reservation
            wage with no constraint binding. Exists to build state and to
            catch a system that refuses everything.
forced      Exactly one correct answer whatever the team's tuning: a safety
            or feasibility rule, or a control proving that rule is not
            over-broad. Graded on decision and on `binding_constraint`.
consistent  No single correct answer — the team's reservation wage is theirs
            to set. Graded only against the other members of its rule.

Consistency rule types:
  pay_invariant     all members must return the same decision and the same
                    binding_constraint. A safety block cannot be bought.
  dominance         accept(worse) implies accept(better), where the two rows
                    have identical route cost and differ only in where the
                    courier ends up. Reports DISCRIMINATES / FLAT / INVERTED.
  monotone_ladder   rungs differ only in pay. Decisions must be non-decreasing
                    with pay. Reports the implied reservation-wage bracket.
  no_gain_from_load accept(loaded) implies accept(clear): adding in-flight
                    work must not make an order more attractive.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

TOLERANCE_MIN_DEFAULT = 5.0

# CSV columns that are numbers, when non-empty. Everything else stays a string.
_NUMERIC = {
    "zone_pickup", "zone_dropoff", "distance_pickup_km", "distance_delivery_km",
    "base_pay_mxn", "est_tip_mxn", "surge_multiplier", "restaurant_prep_min",
    "weight_kg", "volume_liters", "estimated_pickup_min", "estimated_delivery_min",
}
_INT = {"zone_pickup", "zone_dropoff"}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.strip())


def load_pack(path: str) -> list[dict[str, Any]]:
    """Read the order stream CSV into decide-request bodies, in sim_time order."""
    rows: list[dict[str, Any]] = []
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for raw in csv.DictReader(fh):
            row: dict[str, Any] = {}
            for key, val in raw.items():
                if key is None:
                    continue
                val = (val or "").strip()
                if not val:
                    continue            # empty cell means the field is absent
                if key in _NUMERIC:
                    row[key] = int(float(val)) if key in _INT else float(val)
                else:
                    row[key] = val
            rows.append(row)
    rows.sort(key=lambda r: _parse_time(r["sim_time"]))
    return rows


def load_key(path: str) -> dict[str, Any]:
    key = json.loads(Path(path).read_text(encoding="utf-8"))
    for required in ("manifest", "orders"):
        if required not in key:
            raise SystemExit(f"key file is missing {required!r}")
    return key


# ---------------------------------------------------------------------------
# Courier state carried across the stream
# ---------------------------------------------------------------------------

class CarriedState:
    """Courier state derived from the pack's declared numbers and the team's
    own accept decisions. See the module docstring for the model."""

    def __init__(self, manifest: dict[str, Any]) -> None:
        self.shift_start = _parse_time(manifest["shift_start_time"])
        self.shift_end = _parse_time(manifest["shift_end_time"])
        self.last_break_at: datetime | None = None
        # accepted, non-neutral work: (start, end, dropoff_zone, order_id)
        self._work: list[tuple[datetime, datetime, int, str]] = []

    def mark_break(self, at: datetime) -> None:
        self.last_break_at = at

    def record_accept(self, order_id: str, at: datetime,
                      service_min: float, dropoff_zone: int) -> None:
        self._work.append((at, at + timedelta(minutes=service_min),
                           dropoff_zone, order_id))

    def snapshot(self, now: datetime) -> dict[str, Any]:
        since = self.last_break_at or self.shift_start
        continuous = sum((end - start).total_seconds() / 60.0
                         for start, end, _z, _o in self._work if start >= since)
        in_flight = [
            {"order_id": oid,
             "minutes_remaining": round((end - now).total_seconds() / 60.0, 1),
             "dropoff_zone": zone}
            for start, end, zone, oid in self._work if end > now
        ]
        return {
            "continuous_riding_min": round(continuous, 1),
            "shift_elapsed_hours": round(
                (now - self.shift_start).total_seconds() / 3600.0, 3),
            "last_break_end_time": (self.last_break_at.isoformat()
                                    if self.last_break_at else None),
            "shift_end_time": self.shift_end.isoformat(),
            "in_flight_orders": in_flight,
        }


def satisfies(carried: dict[str, Any], precondition: dict[str, Any],
              tolerance_min: float) -> bool:
    """True when the carried state already puts the courier where the probe
    needs them, so no override is required."""
    for field in ("continuous_riding_min", "shift_elapsed_hours"):
        if field not in precondition:
            continue
        want = float(precondition[field])
        got = float(carried[field])
        slack = tolerance_min if field.endswith("_min") else tolerance_min / 60.0
        if abs(want - got) > slack:
            return False
    if "in_flight_orders" in precondition:
        want_flight = precondition["in_flight_orders"]
        got_flight = carried["in_flight_orders"]
        if len(want_flight) != len(got_flight):
            return False
        for want_one, got_one in zip(want_flight, got_flight):
            if abs(float(want_one.get("minutes_remaining", 0.0))
                   - float(got_one["minutes_remaining"])) > tolerance_min:
                return False
    return True


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

def post_decide(url: str, body: dict[str, Any], timeout: float
                ) -> tuple[dict[str, Any] | None, float, str | None]:
    """POST one order. Returns (response, wall_clock_ms, error)."""
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data, (time.perf_counter() - started) * 1000.0, None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        return None, (time.perf_counter() - started) * 1000.0, f"HTTP {exc.code}: {detail}"
    except Exception as exc:                         # noqa: BLE001 - report, never crash
        return None, (time.perf_counter() - started) * 1000.0, f"{type(exc).__name__}: {exc}"


def get_explain(base: str, order_id: str, timeout: float) -> dict[str, Any] | None:
    url = f"{base.rstrip('/')}/explain_decision/{order_id}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:                                # noqa: BLE001 - optional probe
        return None


# ---------------------------------------------------------------------------
# Running the stream
# ---------------------------------------------------------------------------

def run_stream(rows: list[dict[str, Any]], key: dict[str, Any],
               endpoint: str, timeout: float) -> list[dict[str, Any]]:
    manifest = key["manifest"]
    entries = key["orders"]
    tolerance = float(key.get("grading", {}).get("tolerance_min", TOLERANCE_MIN_DEFAULT))
    state = CarriedState(manifest)
    results: list[dict[str, Any]] = []

    for row in rows:
        order_id = row["order_id"]
        entry = entries.get(order_id, {})
        now = _parse_time(row["sim_time"])

        if entry.get("break_before"):
            state.mark_break(now)

        carried = state.snapshot(now)
        precondition = entry.get("state_precondition")
        if precondition and not satisfies(carried, precondition, tolerance):
            overrides = dict(carried)
            overrides.update(precondition)
            mode = "override"
        else:
            overrides = carried
            mode = "carried"

        body = {k: v for k, v in row.items()}
        body["courier_state_overrides"] = overrides

        data, wall_ms, error = post_decide(endpoint, body, timeout)
        decision = (data or {}).get("decision")
        result = {
            "order_id": order_id,
            "sim_time": row["sim_time"],
            "grade": entry.get("grade", "unscored"),
            "category": entry.get("category"),
            "graded_mode": mode,
            "decision": decision,
            "binding_constraint": (data or {}).get("binding_constraint"),
            "reason": (data or {}).get("reason", ""),
            "reported_latency_ms": (data or {}).get("latency_ms"),
            "wall_clock_ms": round(wall_ms, 1),
            "degraded": (data or {}).get("degraded"),
            "tier": (data or {}).get("tier"),
            "error": error,
            "sent_state": overrides,
        }
        results.append(result)

        if decision == "ACCEPT" and not entry.get("state_neutral"):
            state.record_accept(order_id, now,
                                float(entry.get("service_min", 0.0)),
                                int(row.get("zone_dropoff", 0)))

    return results


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

def grade_orders(results: list[dict[str, Any]], key: dict[str, Any]
                 ) -> list[dict[str, Any]]:
    """Grade anchor and forced rows. Consistent rows are left to the rules."""
    entries = key["orders"]
    graded: list[dict[str, Any]] = []

    for res in results:
        entry = entries.get(res["order_id"], {})
        grade = entry.get("grade", "unscored")
        if grade not in ("anchor", "forced"):
            continue

        want_decision = entry.get("expected_decision")
        want_constraint = entry.get("expected_binding_constraint")
        notes: list[str] = []

        if res["error"]:
            verdict = "ERROR"
            notes.append(res["error"])
        elif res["decision"] != want_decision:
            verdict = "FAIL"
            notes.append(f"decision {res['decision']} != {want_decision}")
        elif want_constraint and res["binding_constraint"] != want_constraint:
            verdict = "FAIL"
            notes.append(f"binding_constraint {res['binding_constraint']!r} "
                         f"!= {want_constraint!r}")
        else:
            verdict = "PASS"
            if want_decision == "ACCEPT" and res["binding_constraint"]:
                notes.append(f"ACCEPT reported binding_constraint "
                             f"{res['binding_constraint']!r} — incoherent")

        mentions = [m.lower() for m in entry.get("expected_reason_mentions", [])]
        reason_ok = (not mentions
                     or any(m in (res["reason"] or "").lower() for m in mentions))

        graded.append({**res, "verdict": verdict,
                       "expected_decision": want_decision,
                       "expected_binding_constraint": want_constraint,
                       "reason_ok": reason_ok,
                       "reason_should_mention": mentions,
                       "notes": notes})
    return graded


def _decision_of(results: list[dict[str, Any]], order_id: str) -> str | None:
    for res in results:
        if res["order_id"] == order_id:
            return res["decision"]
    return None


def _constraint_of(results: list[dict[str, Any]], order_id: str) -> str | None:
    for res in results:
        if res["order_id"] == order_id:
            return res["binding_constraint"]
    return None


def grade_rules(results: list[dict[str, Any]], key: dict[str, Any]
                ) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    for rule in key.get("consistency_rules", []):
        rtype = rule["type"]
        record = {"rule_id": rule["rule_id"], "type": rtype,
                  "category": rule.get("category"), "note": rule.get("note", "")}

        if rtype == "pay_invariant":
            members = rule["members"]
            decisions = {m: _decision_of(results, m) for m in members}
            constraints = {m: _constraint_of(results, m) for m in members}
            same_decision = len(set(decisions.values())) == 1
            same_constraint = len(set(constraints.values())) == 1
            # Every member of a pay-invariance pair is a safety refusal that
            # higher pay must not unlock. If nothing was refused there is no
            # block to be invariant about, and calling that a pass would read
            # as credit for a rule the system does not have. The matching
            # forced cases carry the failure; this rule abstains.
            if set(decisions.values()) == {"ACCEPT"}:
                record.update(
                    verdict="N/A", outcome="NO BLOCK",
                    detail=f"decisions={decisions}",
                    explanation="every member was accepted — no safety block was "
                                "present to test for pay-invariance; see the forced "
                                "cases for these order ids")
            else:
                record.update(
                    verdict="PASS" if (same_decision and same_constraint) else "FAIL",
                    detail=f"decisions={decisions} constraints={constraints}",
                    explanation=("the block held as pay rose" if same_decision
                                 else "the decision changed when only pay changed"))

        elif rtype == "dominance":
            worse, better = rule["worse"], rule["better"]
            d_worse, d_better = _decision_of(results, worse), _decision_of(results, better)
            if d_worse == "ACCEPT" and d_better == "SKIP":
                verdict, outcome = "FAIL", "INVERTED"
                explanation = (f"took {worse} (poor dropoff) but refused {better}, "
                               f"which costs the same and ends somewhere better")
            elif d_worse == "SKIP" and d_better == "ACCEPT":
                verdict, outcome = "PASS", "DISCRIMINATES"
                explanation = "priced the dropoff location, not just the fare"
            else:
                verdict, outcome = "PASS", "FLAT"
                explanation = (f"treated both identically ({d_worse}) — no evidence "
                               f"the dropoff zone entered the decision")
            record.update(verdict=verdict, outcome=outcome,
                          detail=f"{worse}={d_worse} {better}={d_better}",
                          explanation=explanation)

        elif rtype == "monotone_ladder":
            rungs = sorted(rule["rungs"], key=lambda r: r["reference_rate_mxn_hr"])
            seq = [(r["order_id"], r["reference_rate_mxn_hr"],
                    _decision_of(results, r["order_id"])) for r in rungs]
            violations = [
                f"{seq[i][0]} ACCEPT at {seq[i][1]:.0f} but {seq[j][0]} SKIP at {seq[j][1]:.0f}"
                for i in range(len(seq)) for j in range(i + 1, len(seq))
                if seq[i][2] == "ACCEPT" and seq[j][2] == "SKIP"
            ]
            accepted = [rate for _o, rate, d in seq if d == "ACCEPT"]
            skipped = [rate for _o, rate, d in seq if d == "SKIP"]
            lower = max(skipped) if skipped else None
            upper = min(accepted) if accepted else None
            if accepted and skipped:
                bracket = f"{lower:.0f}–{upper:.0f} MXN/hr"
            elif accepted:
                bracket = f"below {min(accepted):.0f} MXN/hr"
            elif skipped:
                bracket = f"above {max(skipped):.0f} MXN/hr"
            else:
                bracket = "not determined"
            record.update(
                verdict="FAIL" if violations else "PASS",
                detail="; ".join(f"{o}@{rate:.0f}={d}" for o, rate, d in seq),
                implied_reservation_wage=bracket,
                explanation=("; ".join(violations) if violations
                             else f"monotone in pay; implied threshold {bracket}"))

        elif rtype == "no_gain_from_load":
            clear, loaded = rule["clear"], rule["loaded"]
            d_clear, d_loaded = _decision_of(results, clear), _decision_of(results, loaded)
            ok = not (d_loaded == "ACCEPT" and d_clear == "SKIP")
            record.update(
                verdict="PASS" if ok else "FAIL",
                detail=f"{clear}(clear)={d_clear} {loaded}(loaded)={d_loaded}",
                explanation=("in-flight work did not make the order more attractive"
                             if ok else
                             "accepted while loaded but refused the same order clear"))
        else:
            record.update(verdict="ERROR", detail=f"unknown rule type {rtype!r}")

        out.append(record)
    return out


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(int(round(pct / 100.0 * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[idx]


def report(results: list[dict[str, Any]], graded: list[dict[str, Any]],
           rules: list[dict[str, Any]], key: dict[str, Any]) -> dict[str, Any]:
    budget = float(key.get("grading", {}).get("latency_budget_ms", 50))
    bar = "=" * 74

    print(bar)
    print(f"  COURIER PROBE PACK — {key.get('pack_id', '?')}")
    print(bar)
    m = key["manifest"]
    print(f"  shift    {m['shift_start_time']} → {m['shift_end_time']}  "
          f"({m['shift_hours']} h, {m['vehicle']}, start zone {m['start_location_zone']})")
    print(f"  orders   {len(results)}")

    errors = [r for r in results if r["error"]]
    if errors:
        print(f"\n  TRANSPORT ERRORS ({len(errors)})")
        for res in errors[:10]:
            print(f"    {res['order_id']}: {res['error']}")

    # --- forced and anchor cases ------------------------------------------
    print(f"\n{'-' * 74}\n  FORCED CASES — one correct answer, whatever the tuning\n{'-' * 74}")
    print(f"  {'order':<10} {'grade':<7} {'mode':<9} {'got':<7} {'want':<7} "
          f"{'constraint':<21} {'':<4}")
    for g in graded:
        flag = {"PASS": "ok", "FAIL": "FAIL", "ERROR": "ERR"}[g["verdict"]]
        got_c = g["binding_constraint"] or "-"
        print(f"  {g['order_id']:<10} {g['grade']:<7} {g['graded_mode']:<9} "
              f"{str(g['decision'] or '-'):<7} {str(g['expected_decision']):<7} "
              f"{got_c:<21} {flag:<4}")
        for note in g["notes"]:
            print(f"             ↳ {note}")

    failed = [g for g in graded if g["verdict"] != "PASS"]
    anchors = [g for g in graded if g["grade"] == "anchor"]
    anchors_failed = [g for g in anchors if g["verdict"] != "PASS"]
    overridden = [g for g in graded if g["graded_mode"] == "override"]

    print(f"\n  {len(graded) - len(failed)}/{len(graded)} forced cases passed")
    if anchors_failed:
        print(f"  {len(anchors_failed)}/{len(anchors)} anchor orders were refused — a system "
              f"that skips work\n  it should take is not merely cautious; it also never "
              f"reaches the states\n  the state-dependent probes test.")
    if overridden:
        print(f"  {len(overridden)} probe(s) graded in override mode "
              f"(state supplied, not reached): "
              f"{', '.join(g['order_id'] for g in overridden)}")

    # --- reason strings ---------------------------------------------------
    checked = [g for g in graded if g["reason_should_mention"]]
    weak = [g for g in checked if not g["reason_ok"]]
    if checked:
        print(f"\n  Reason strings naming the right constraint: "
              f"{len(checked) - len(weak)}/{len(checked)}")
        for g in weak:
            print(f"    {g['order_id']}: expected one of {g['reason_should_mention']}")
            print(f"      got: {g['reason'][:80]!r}")
        print("  (evaluation_protocol.md §3: a correct decision with a generic reason")
        print("   earns no Judgment credit — this is reported, not counted as a failure.)")

    # --- consistency rules ------------------------------------------------
    print(f"\n{'-' * 74}\n  CONSISTENCY RULES — no fixed answer; graded against themselves\n{'-' * 74}")
    for r in rules:
        head = r["verdict"] + (f" [{r['outcome']}]" if "outcome" in r else "")
        print(f"  {r['rule_id']:<22} {head}")
        print(f"    {r['detail']}")
        print(f"    {r['explanation']}")
    # N/A means the rule could not bite (nothing was blocked); the matching
    # forced case carries that failure, so it is not double-counted here.
    rules_failed = [r for r in rules if r["verdict"] == "FAIL"]

    # --- per-category rollup ---------------------------------------------
    print(f"\n{'-' * 74}\n  BY PROBE CATEGORY (evaluation_protocol.md §3)\n{'-' * 74}")
    categories: dict[str, list[str]] = {}
    for g in graded:
        if g["category"]:
            categories.setdefault(g["category"], []).append(g["verdict"])
    for r in rules:
        if r.get("category"):
            categories.setdefault(r["category"], []).append(r["verdict"])
    for name in sorted(categories):
        verdicts = [v for v in categories[name] if v != "N/A"]
        if not verdicts:
            print(f"  {name:<34} not exercised")
            continue
        passed = sum(1 for v in verdicts if v == "PASS")
        mark = "ok" if passed == len(verdicts) else "FAIL"
        print(f"  {name:<34} {passed}/{len(verdicts)}  {mark}")

    # --- latency ----------------------------------------------------------
    reported = [r["reported_latency_ms"] for r in results
                if isinstance(r["reported_latency_ms"], (int, float))]
    wall = [r["wall_clock_ms"] for r in results if not r["error"]]
    print(f"\n{'-' * 74}\n  LATENCY (budget {budget:.0f} ms, fast path)\n{'-' * 74}")
    if reported:
        print(f"  self-reported   p50 {statistics.median(reported):7.1f}   "
              f"p95 {_percentile(reported, 95):7.1f}   p99 {_percentile(reported, 99):7.1f} ms")
        over = [r for r in results
                if isinstance(r["reported_latency_ms"], (int, float))
                and r["reported_latency_ms"] > budget]
        if over:
            print(f"  {len(over)} response(s) over budget: "
                  f"{', '.join(r['order_id'] for r in over[:8])}")
    else:
        print("  no latency_ms field in any response — required by "
              "decision_response_schema.json")
    if wall:
        print(f"  wall clock      p50 {statistics.median(wall):7.1f}   "
              f"p95 {_percentile(wall, 95):7.1f}   p99 {_percentile(wall, 99):7.1f} ms "
              f"(includes network)")
    # A large gap between the two is worth a question: it usually means the
    # timer starts after the work, or an LLM sits inside the decision window.
    if reported and wall:
        gap = statistics.median(wall) - statistics.median(reported)
        if gap > 200:
            print(f"  NOTE: wall clock exceeds self-reported latency by "
                  f"{gap:.0f} ms at the median.")
            print("        Ask what happens between the request arriving and the timer "
                  "starting.")

    degraded = [r for r in results if r["degraded"]]
    if degraded:
        print(f"\n  {len(degraded)} response(s) flagged degraded "
              f"(stale strategy): {', '.join(r['order_id'] for r in degraded[:8])}")

    ok = not failed and not rules_failed
    print(f"\n{bar}")
    print(f"  RESULT: {'PASS' if ok else 'FAIL'} — "
          f"{len(failed)} forced failure(s), {len(rules_failed)} consistency failure(s)")
    print(bar)

    return {
        "pack_id": key.get("pack_id"),
        "passed": ok,
        "forced": {"total": len(graded), "failed": len(failed)},
        "anchors": {"total": len(anchors), "refused": len(anchors_failed)},
        "overridden_probes": [g["order_id"] for g in overridden],
        "reason_quality": {"checked": len(checked), "weak": len(weak)},
        "consistency_rules": rules,
        "categories": {k: v for k, v in categories.items()},
        "latency_ms": {
            "reported_p50": statistics.median(reported) if reported else None,
            "reported_p99": _percentile(reported, 99) if reported else None,
            "wall_p50": statistics.median(wall) if wall else None,
            "wall_p99": _percentile(wall, 99) if wall else None,
            "budget": budget,
        },
        "orders": graded,
        "raw": results,
    }


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pack", required=True, help="order stream CSV")
    ap.add_argument("--key", required=True, help="answer key JSON")
    ap.add_argument("--endpoint", required=True,
                    help="full decide URL, e.g. http://localhost:8000/decide")
    ap.add_argument("--report", help="write the scorecard as JSON to this path")
    ap.add_argument("--explain", action="store_true",
                    help="also call explain_decision for each forced SKIP")
    ap.add_argument("--explain-base",
                    help="base URL for explain_decision (default: --endpoint "
                         "with its last path segment removed)")
    ap.add_argument("--timeout", type=float, default=5.0)
    args = ap.parse_args()

    rows = load_pack(args.pack)
    key = load_key(args.key)

    missing = [r["order_id"] for r in rows if r["order_id"] not in key["orders"]]
    if missing:
        print(f"warning: {len(missing)} order(s) in the pack have no key entry: "
              f"{', '.join(missing[:5])}", file=sys.stderr)

    results = run_stream(rows, key, args.endpoint, args.timeout)
    graded = grade_orders(results, key)
    rules = grade_rules(results, key)
    scorecard = report(results, graded, rules, key)

    if args.explain:
        base = args.explain_base or args.endpoint.rsplit("/", 1)[0]
        print(f"\n{'-' * 74}\n  EXPLAIN_DECISION spot check\n{'-' * 74}")
        targets = [g for g in graded
                   if g["expected_decision"] == "SKIP" and g["verdict"] == "PASS"]
        for g in targets:
            data = get_explain(base, g["order_id"], args.timeout)
            if data is None:
                print(f"  {g['order_id']}: no response")
            elif data.get("decision") != g["decision"]:
                print(f"  {g['order_id']}: MISMATCH — decide said {g['decision']}, "
                      f"explain says {data.get('decision')}")
            else:
                alts = len(data.get("alternatives_considered", []))
                print(f"  {g['order_id']}: ok, {alts} alternative(s) recorded")

    if args.report:
        Path(args.report).write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
        print(f"\nscorecard written to {args.report}")

    return 0 if scorecard["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
