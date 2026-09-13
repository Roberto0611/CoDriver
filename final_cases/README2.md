# Track 02 — The Courier
## What the judge will run during your demo

This directory contains the exact scripts a judge runs against your system.
No surprises: test against these before demo day.

---

## Scripts at a glance

| Script | What it does | Requires network? |
|--------|-------------|:-----------------:|
| `run_probe_pack.py` | Feeds an order stream to `/decide`, grades decisions | Yes — your endpoint |
| `shock_injector.py` | Posts a disruption event to your simulation | Yes — your endpoint |
| `timing_benchmark.py` | Measures p99 latency of `/decide` | Yes — your endpoint |

---

## run_probe_pack.py

Feeds an order stream (CSV) to your `/decide` endpoint in `sim_time` order, then scores
each decision against an answer key. The runner manages courier state between orders so
neither side guesses what the other believes the courier state to be.

```bash
# Run the practice pack (key included — explicitly for students)
python3 run_probe_pack.py \
    --pack  practice_pack/practice_pack.csv \
    --key   practice_pack/practice_pack_key.json \
    --endpoint http://localhost:8000/decide

# Machine-readable output (for CI)
python3 run_probe_pack.py --pack ... --key ... --endpoint ... --report scorecard.json

# Also probe explain_decision for each skipped order
python3 run_probe_pack.py --pack ... --key ... --endpoint ... --explain
```

**Three decision grades:**
- `anchor` — must be ACCEPTED; priced well above any plausible reservation wage
- `forced` — exactly one correct answer (a safety constraint, or its control)
- `consistent` — no single correct answer; graded against consistency rules across orders

**During demo:** The judge runs their own probe pack (seed from the reserved band, not the
practice pack). Passing the practice pack means your safety constraints are wired up over
HTTP. It does not mean you will pass the judge's pack.

---

## shock_injector.py

Posts a disruption event to your simulation's `/shock` endpoint. The judge uses four
predefined scenarios. Run `--list` to see them and understand what to implement.

```bash
# Print the four judge scenarios (read these before building)
python3 shock_injector.py --list

# Inject each scenario (your simulation must be running)
python3 shock_injector.py --shock surge                                    # Scenario A
python3 shock_injector.py --shock closure                                  # Scenario B
python3 shock_injector.py --shock rain                                     # Scenario C
python3 shock_injector.py --shock delay --order-id ORDER-XXX --slip 15    # Scenario D

# Non-default host/port
python3 shock_injector.py --host 10.0.1.5 --port 5000 --shock surge
```

**Four predefined judge scenarios:**
- **A — Surge 1.6× Zone 11 (San Pedro), 25 min** — tests repositioning. After injection,
  your Tier 2 strategy agent's next `target_zone` should shift toward Zone 11.
- **B — Road closure on Av. Constitución, 30 min** — tests rerouting. In-flight orders
  that become infeasible due to the detour should be re-evaluated.
- **C — Rain: λ +40%, speeds −25%, 45 min** — tests simultaneous demand rise + slowdown.
  `reservation_wage` should rise; confidence may reflect higher uncertainty.
- **D — Restaurant delay 15 min on in-flight order** — tests deadline feasibility.
  `explain_decision` should show updated net MXN/hr and flag if infeasible.

**Your `/shock` endpoint must:**
- Accept `POST application/json` with `{"type": "surge"|"closure"|"rain"|"delay", ...}`
- Return HTTP 200 with a JSON body (fields: `sim_time`, `active_until`, `message`)
- Return promptly — the injector times out at 10 s

---

## timing_benchmark.py

Fires 100+ synthetic order pings at your `/decide` endpoint and reports p99 latency.
Reproducible: uses seed 42 so the same orders are sent every run.

```bash
python3 timing_benchmark.py                                        # 100 pings, localhost:8000
python3 timing_benchmark.py --count 200                            # more pings
python3 timing_benchmark.py --host 10.0.1.5 --port 5000           # remote endpoint
python3 timing_benchmark.py --endpoint /api/decide --count 500     # custom path
```

**Pass criteria:** p99 < 1000 ms.

The benchmark does not test the 50 ms contract from the evaluation protocol directly — that
contract applies to your `courier_state_overrides`-bearing pings from the simulator. The
benchmark measures raw HTTP round-trip latency with synthetic payloads. If your p99 here
is >100 ms, you are already far outside the 50 ms contract.

**What the judge looks for:**
- Fast-path decisions never block on an in-progress LLM call
- Tier 2 (LLM strategy) runs between pings, not during them
- Degraded mode: Tier 1 still answers within 50 ms even when Tier 2 is unavailable

---

## practice_pack/

Fourteen orders covering all five safety constraints, plus two consistency rules. Run this
repeatedly until you pass reliably. Read `practice_pack/README.md` first — it explains
the anchor/forced/consistent grading model and how to interpret the results.

---

## Checklist — what the judge will verify

**Before demo:**
- [ ] `run_probe_pack.py` on the practice pack exits 0
- [ ] `timing_benchmark.py` reports p99 < 100 ms (well inside the 50 ms contract)
- [ ] Replay: `python3 courier/replay.py --log eventlog.json` (network off) matches live run

**During demo (probe pack run):**
- [ ] Judge runs their own pack — `latency_ms` ≤ 50 on forced/anchor rows
- [ ] `binding_constraint` field is set correctly on refused orders

**Shock event tests:**
- [ ] Surge injected → Tier 2 agent sets new `target_zone` toward Zone 11
- [ ] Road closure → agent recalculates feasibility of in-flight orders
- [ ] Rain injected → `reservation_wage` increases, confidence reflects uncertainty
- [ ] Restaurant delay → `explain_decision` shows updated net MXN/hr

**Safety constraint tests (hard constraints in code, not in prompt text):**
- [ ] Order: dropoff in flagged colonia after 22:00 → REFUSE with `binding_constraint`
- [ ] Scenario: 4 h continuous riding → mandatory 20-min break triggers
- [ ] Scenario: 12:00–16:00 heat window, 90+ min riding → heat rule triggers
- [ ] Order: infeasible before shift end → REFUSE with `binding_constraint`
- [ ] Order: 40 kg to moto courier → REFUSE citing vehicle weight limit

**LLM failure test:**
- [ ] Judge disables network mid-demo → Tier 1 keeps answering on last-known strategy
- [ ] Judge asks: "What is the fallback reservation_wage?" — answer: last LLM-set value

**Surprise questions the judge will ask from these:**
- "Why did you skip that order?" → decision log: net MXN, km, MXN/hr, reservation wage, continuation delta
- "What would it do if a surge hit right now?" → inject live; Tier 2 responds in ≤40 words
- "What if the restaurant is running 15 minutes late?" → updated feasibility calculation shown
- "Show a shift where it made a counterintuitive call that paid off." → continuation-value skip example
- "What's your Oracle gap?" → specific percentage, computed figure, not an estimate
