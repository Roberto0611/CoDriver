"""
shock_injector.py — HackMTY 2026 Track 3: The Courier
Injects predefined disruption events into the team's running simulation via HTTP POST.
Use --list to review the four predefined judge scenarios before the demo begins.

Usage:
    python shock_injector.py --list
    python shock_injector.py --shock surge
    python shock_injector.py --shock surge --zone 11 --duration 25 --multiplier 1.6
    python shock_injector.py --shock closure --road "Av. Constitución" --duration 30
    python shock_injector.py --shock rain --duration 45
    python shock_injector.py --shock delay --order-id ORDER-7821 --slip 15
    python shock_injector.py --host 192.168.1.10 --port 5000 --shock surge

Exit code 0 = shock accepted by server. Exit code 1 = connection or server error.
"""

import argparse
import json
import sys
import time

import requests


# Canonical default durations per shock type, matching Track 3 spec.
DEFAULT_DURATIONS = {
    "surge":   25,
    "closure": 30,
    "rain":    45,
}

PREDEFINED_SCENARIOS = [
    {
        "label":      "A",
        "shock_type": "surge",
        "name":       "Surge 1.6x in Zone 11 (San Pedro) — 25 min",
        "purpose":    (
            "Tests repositioning logic. After injection, watch the LLM strategy agent's next "
            "target_zone field — it should shift toward Zone 11. A system with no repositioning "
            "logic will keep accepting orders away from the surge and miss yield."
        ),
        "params": {"zone": 11, "duration_min": 25, "multiplier": 1.6},
    },
    {
        "label":      "B",
        "shock_type": "closure",
        "name":       "Road closure on Av. Constitución — 30 min",
        "purpose":    (
            "Tests rerouting and order-drop decisions. The edge is removed from the routing graph. "
            "Watch for: recalculated delivery times on in-flight orders, and whether the agent drops "
            "orders that become infeasible due to the detour."
        ),
        "params": {"road": "Av. Constitución", "duration_min": 30},
    },
    {
        "label":      "C",
        "shock_type": "rain",
        "name":       "Rain onset — lambda +40%, speeds -25% — 45 min",
        "purpose":    (
            "Tests simultaneous demand increase with reduced throughput. The reservation_wage should "
            "rise (more orders to pick from, slower completion), and the confidence field in the "
            "LLM strategy JSON should reflect higher uncertainty."
        ),
        "params": {"duration_min": 45},
    },
    {
        "label":      "D",
        "shock_type": "delay",
        "name":       "Restaurant delay 15 min on in-flight order",
        "purpose":    (
            "Tests deadline feasibility recalculation. The pickup_ready_at slips 15 minutes on a "
            "currently-accepted order. Watch explain_decision(order_id) — it should show updated "
            "net $/hr and flag if the order is now infeasible relative to shift end."
        ),
        "params": {"order_id": "<current in-flight order ID>", "slip_min": 15},
    },
]


def print_scenario_list() -> None:
    print("HackMTY 2026 Track 3 — Predefined Judge Shock Scenarios")
    print("=" * 70)
    for s in PREDEFINED_SCENARIOS:
        print(f"\n  Scenario {s['label']}: {s['name']}")
        print(f"  Type    : {s['shock_type']}")
        print(f"  Params  : {json.dumps(s['params'])}")
        print(f"  Purpose : {s['purpose']}")
    print()


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_surge_payload(zone: int, duration_min: int, multiplier: float) -> dict:
    return {
        "type":         "surge",
        "zone":         zone,
        "duration_min": duration_min,
        "multiplier":   multiplier,
        "injected_at":  _utc_now(),
    }


def build_closure_payload(road: str, duration_min: int) -> dict:
    return {
        "type":         "closure",
        "road":         road,
        "duration_min": duration_min,
        "injected_at":  _utc_now(),
    }


def build_rain_payload(duration_min: int) -> dict:
    return {
        "type":               "rain",
        "lambda_increase_pct": 40,
        "speed_decrease_pct":  25,
        "duration_min":       duration_min,
        "injected_at":        _utc_now(),
    }


def build_delay_payload(order_id: str, slip_min: int) -> dict:
    return {
        "type":        "delay",
        "order_id":    order_id,
        "slip_min":    slip_min,
        "injected_at": _utc_now(),
    }


def post_shock(url: str, payload: dict) -> int:
    printable = {k: v for k, v in payload.items() if k != "injected_at"}
    print(f"Endpoint  : {url}")
    print(f"Shock type: {payload['type']}")
    print(f"Parameters: {json.dumps(printable)}")
    print(f"Wall time : {payload['injected_at']}")
    print()

    try:
        resp = requests.post(url, json=payload, timeout=10.0)
        resp.raise_for_status()

        body = {}
        try:
            body = resp.json()
        except Exception:
            pass

        print(f"  Status      : HTTP {resp.status_code} — shock accepted")
        if "sim_time" in body:
            print(f"  Sim time    : {body['sim_time']}")
        if "active_until" in body:
            print(f"  Active until: {body['active_until']}")
        if "affected_orders" in body:
            print(f"  Affected orders: {body['affected_orders']}")
        if "message" in body:
            print(f"  Server msg  : {body['message']}")
        print()
        return 0

    except requests.exceptions.ConnectionError:
        print(f"  ERROR: Cannot reach {url}")
        print(f"  Verify the team's simulation server is running and /shock is registered.")
        print()
        return 1
    except requests.exceptions.Timeout:
        print(f"  ERROR: Request timed out after 10 seconds.")
        print()
        return 1
    except requests.exceptions.HTTPError as exc:
        print(f"  ERROR: HTTP {exc.response.status_code} from server.")
        try:
            body_text = exc.response.text
            if body_text:
                print(f"  Body  : {body_text[:400]}")
        except Exception:
            pass
        print()
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="HackMTY 2026 Track 3 — shock event injector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python shock_injector.py --list\n"
            "  python shock_injector.py --shock surge\n"
            "  python shock_injector.py --shock surge --zone 9 --duration 30 --multiplier 1.4\n"
            '  python shock_injector.py --shock closure --road "Av. Morones Prieto" --duration 20\n'
            "  python shock_injector.py --shock rain\n"
            "  python shock_injector.py --shock delay --order-id ORDER-5512 --slip 20\n"
        ),
    )
    parser.add_argument("--host", default="localhost",
                        help="Server hostname (default: localhost)")
    parser.add_argument("--port", type=int, default=8000,
                        help="Server port (default: 8000)")
    parser.add_argument("--endpoint", default="/shock",
                        help="Shock endpoint path (default: /shock)")
    parser.add_argument("--list", dest="list_scenarios", action="store_true",
                        help="Print predefined judge scenarios and exit")
    parser.add_argument("--shock", choices=["surge", "closure", "rain", "delay"],
                        help="Shock type to inject")

    surge_group = parser.add_argument_group("surge options")
    surge_group.add_argument("--zone", type=int, default=11,
                             help="Zone ID (default: 11 = San Pedro)")
    surge_group.add_argument("--multiplier", type=float, default=1.6,
                             help="Demand multiplier (default: 1.6)")

    shared_group = parser.add_argument_group("surge / closure / rain options")
    shared_group.add_argument(
        "--duration", type=int, default=None,
        help=(
            "Event duration in minutes. "
            "Defaults per type: surge=25, closure=30, rain=45."
        ),
    )

    closure_group = parser.add_argument_group("closure options")
    closure_group.add_argument("--road", default="Av. Constitución",
                               help='Road segment to close (default: "Av. Constitución")')

    delay_group = parser.add_argument_group("delay options")
    delay_group.add_argument("--order-id", dest="order_id",
                             help="Order ID whose pickup_ready_at will slip (required for --shock delay)")
    delay_group.add_argument("--slip", type=int, default=15,
                             help="Slip amount in minutes (default: 15)")

    args = parser.parse_args()

    if args.list_scenarios:
        print_scenario_list()
        sys.exit(0)

    if not args.shock:
        parser.error("Provide --shock <type> or --list.")

    url = f"http://{args.host}:{args.port}{args.endpoint}"
    duration = args.duration if args.duration is not None else DEFAULT_DURATIONS.get(args.shock, 25)

    if args.shock == "surge":
        payload = build_surge_payload(args.zone, duration, args.multiplier)
    elif args.shock == "closure":
        payload = build_closure_payload(args.road, duration)
    elif args.shock == "rain":
        payload = build_rain_payload(duration)
    elif args.shock == "delay":
        if not args.order_id:
            parser.error("--order-id is required when using --shock delay")
        payload = build_delay_payload(args.order_id, args.slip)
    else:
        parser.error(f"Unknown shock type: {args.shock}")

    sys.exit(post_shock(url, payload))


if __name__ == "__main__":
    main()
