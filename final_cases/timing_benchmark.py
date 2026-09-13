"""
timing_benchmark.py — HackMTY 2026 Track 3: The Courier
Verifies that the team's Tier 1 fast-policy endpoint responds at p99 under 1000ms.
Fires a configurable number of synthetic order pings and reports latency statistics.

Usage:
    python timing_benchmark.py
    python timing_benchmark.py --host localhost --port 8000 --count 200
    python timing_benchmark.py --host 10.0.1.5 --port 5000 --endpoint /api/decide --count 500

Exit code 0 = PASS (p99 < 1000ms). Exit code 1 = FAIL or connection error.
"""

import argparse
import random
import statistics
import sys
import time

import requests


MONTERREY_ZONES = {
    1: "Centro",
    2: "Barrio Antiguo",
    3: "Obispado",
    5: "Cumbres",
    7: "Tec",
    8: "Mitras",
    9: "Valle Oriente",
    11: "San Pedro",
    14: "Santa Catarina",
    17: "Apodaca",
    22: "García",
    33: "Guadalupe",
    41: "Pesquería",
}

ZONE_IDS = list(MONTERREY_ZONES.keys())

ZONE_COORDS = {
    1:  (25.6714, -100.3085),
    2:  (25.6665, -100.3086),
    3:  (25.6797, -100.3284),
    5:  (25.7513, -100.3666),
    7:  (25.6513, -100.2883),
    8:  (25.6899, -100.3458),
    9:  (25.6529, -100.3672),
    11: (25.6564, -100.4028),
    14: (25.6719, -100.4636),
    17: (25.7777, -100.1888),
    22: (25.8151, -100.6055),
    33: (25.6770, -100.2503),
    41: (25.7832, -100.0512),
}

VEHICLE_TYPES = ["moto", "car", "bike"]

RESTAURANT_NAMES = [
    "Los Norteños Tacos",
    "La Casa del Birria",
    "Sushi Monterrey",
    "Pizza Hut San Pedro",
    "KFC Cumbres",
    "Burger King Tec",
    "McDonald's Centro",
    "La Parroquia Café",
    "El Buen Pastor",
    "Saffron Indian Kitchen",
]

# Realistic surge distribution: most orders have no surge
SURGE_POOL = [1.0, 1.0, 1.0, 1.0, 1.2, 1.4, 1.6]


def build_order_payload(ping_index: int, rng: random.Random) -> dict:
    zone_pickup = rng.choice(ZONE_IDS)
    zone_dropoff = rng.choice([z for z in ZONE_IDS if z != zone_pickup])

    pickup_lat, pickup_lng = ZONE_COORDS[zone_pickup]
    dropoff_lat, dropoff_lng = ZONE_COORDS[zone_dropoff]
    courier_zone = rng.choice(ZONE_IDS)
    courier_lat, courier_lng = ZONE_COORDS[courier_zone]

    # Spread sim times evenly across an 8-hour shift starting at 10:00
    sim_hour_offset = rng.uniform(0.0, 8.0)
    abs_hour = 10 + int(sim_hour_offset)
    sim_minute = int((sim_hour_offset % 1.0) * 60)
    sim_time = f"2026-03-21T{abs_hour:02d}:{sim_minute:02d}:00"

    # Keep continuous_riding_min below 90 so safety constraints don't dominate
    # the timing sample — we want to measure latency, not decision frequency.
    continuous_riding_min = rng.randint(0, 85)

    order = {
        "order_id": f"bench-{ping_index:05d}",
        "restaurant_name": rng.choice(RESTAURANT_NAMES),
        "base_pay_mxn": round(rng.uniform(40.0, 180.0), 2),
        "surge_multiplier": rng.choice(SURGE_POOL),
        "distance_pickup_km": round(rng.uniform(0.3, 5.0), 2),
        "distance_delivery_km": round(rng.uniform(0.5, 8.0), 2),
        "zone_pickup": zone_pickup,
        "zone_dropoff": zone_dropoff,
        "pickup_lat": round(pickup_lat + rng.uniform(-0.008, 0.008), 6),
        "pickup_lng": round(pickup_lng + rng.uniform(-0.008, 0.008), 6),
        "dropoff_lat": round(dropoff_lat + rng.uniform(-0.008, 0.008), 6),
        "dropoff_lng": round(dropoff_lng + rng.uniform(-0.008, 0.008), 6),
        "estimated_pickup_min": rng.randint(3, 20),
        "estimated_delivery_min": rng.randint(8, 35),
        "weight_kg": round(rng.uniform(0.2, 12.0), 1),
        "volume_liters": round(rng.uniform(0.5, 10.0), 1),
        "sim_time": sim_time,
    }

    courier = {
        "courier_id": f"judge-{ping_index % 5:02d}",
        "current_zone": courier_zone,
        "current_lat": round(courier_lat + rng.uniform(-0.005, 0.005), 6),
        "current_lng": round(courier_lng + rng.uniform(-0.005, 0.005), 6),
        "shift_elapsed_hours": round(rng.uniform(0.0, 6.5), 2),
        "continuous_riding_min": continuous_riding_min,
        "vehicle": rng.choice(VEHICLE_TYPES),
        "shift_end_time": "2026-03-21T18:00:00",
        "break_taken_at_hour_4": rng.choice([True, False]),
    }

    return {"order": order, "courier": courier}


def interpolated_percentile(sorted_data: list, pct: float) -> float:
    n = len(sorted_data)
    if n == 0:
        return 0.0
    idx = pct / 100.0 * (n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return float(sorted_data[-1])
    frac = idx - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


def compute_histogram(latencies_ms: list) -> list:
    buckets = [
        (0,    100,         "   0–100ms"),
        (100,  250,         " 100–250ms"),
        (250,  500,         " 250–500ms"),
        (500,  750,         " 500–750ms"),
        (750,  1000,        "750–1000ms"),
        (1000, float("inf"), "   >1000ms"),
    ]
    rows = []
    for lo, hi, label in buckets:
        count = sum(1 for ms in latencies_ms if lo <= ms < hi)
        rows.append((label, count))
    return rows


def run_benchmark(host: str, port: int, count: int, endpoint: str) -> int:
    url = f"http://{host}:{port}{endpoint}"
    print(f"HackMTY 2026 Track 3 — Tier 1 Timing Benchmark")
    print(f"Target   : {url}")
    print(f"Pings    : {count}  (seed=42, reproducible)")
    print("─" * 64)

    rng = random.Random(42)
    latencies_ms = []
    error_count = 0

    session = requests.Session()

    for i in range(count):
        payload = build_order_payload(i, rng)
        try:
            t0 = time.perf_counter()
            resp = session.post(url, json=payload, timeout=5.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            resp.raise_for_status()
            latencies_ms.append(elapsed_ms)
            if i == 0 or (i + 1) % 25 == 0:
                print(f"  [{i + 1:>4}/{count}]  {elapsed_ms:7.2f}ms")
        except requests.exceptions.ConnectionError:
            print()
            print(f"  ERROR: Connection refused at {url}")
            print(f"  Make sure the team's system is running before benchmarking.")
            return 1
        except requests.exceptions.Timeout:
            print(f"  [{i + 1:>4}/{count}]  TIMEOUT — recorded as 5000ms")
            latencies_ms.append(5000.0)
        except requests.exceptions.HTTPError as exc:
            print(f"  [{i + 1:>4}/{count}]  HTTP {exc.response.status_code}")
            error_count += 1

    if not latencies_ms:
        print("\n  No successful responses — cannot compute statistics.")
        return 1

    sorted_lat = sorted(latencies_ms)
    p99 = interpolated_percentile(sorted_lat, 99)
    p95 = interpolated_percentile(sorted_lat, 95)
    med = statistics.median(latencies_ms)
    passed = p99 < 1000.0

    print()
    print("═" * 64)
    print(f"  Results  ({len(latencies_ms)} ok / {count} sent, {error_count} HTTP error(s))")
    print("═" * 64)
    print(f"  min    {min(latencies_ms):>9.2f} ms")
    print(f"  median {med:>9.2f} ms")
    print(f"  p95    {p95:>9.2f} ms")
    verdict_tag = "PASS" if passed else "FAIL"
    print(f"  p99    {p99:>9.2f} ms   <- {verdict_tag}")
    print(f"  max    {max(latencies_ms):>9.2f} ms")
    print()

    total = len(latencies_ms)
    bar_scale = 36
    print("  Latency distribution:")
    for label, bucket_count in compute_histogram(latencies_ms):
        bar = "█" * int(bucket_count / total * bar_scale) if total else ""
        pct = bucket_count / total * 100 if total else 0
        print(f"    {label}  {bar:<36}  {bucket_count:>4}  ({pct:5.1f}%)")

    print()
    if passed:
        print(f"  VERDICT: PASS — p99 {p99:.1f}ms is under the 1000ms threshold.")
        print(f"  Tier 1 fast policy meets the HackMTY latency requirement.")
    else:
        print(f"  VERDICT: FAIL — p99 {p99:.1f}ms exceeds the 1000ms threshold.")
        print(f"  Tier 1 must be pure Python with no blocking I/O or LLM calls.")
    print()

    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(
        description="HackMTY 2026 Track 3 — Tier 1 fast-policy latency benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python timing_benchmark.py\n"
            "  python timing_benchmark.py --count 500\n"
            "  python timing_benchmark.py --host 10.0.1.5 --port 5000\n"
            "  python timing_benchmark.py --endpoint /api/decide --count 200\n"
        ),
    )
    parser.add_argument(
        "--host", default="localhost",
        help="Hostname of the team's running system (default: localhost)",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port of the team's running system (default: 8000)",
    )
    parser.add_argument(
        "--count", type=int, default=100,
        help="Number of synthetic order pings to fire (default: 100, min: 10)",
    )
    parser.add_argument(
        "--endpoint", default="/decide",
        help="Decision endpoint path (default: /decide)",
    )
    args = parser.parse_args()

    if args.count < 10:
        parser.error("--count must be at least 10 for meaningful percentile statistics")

    sys.exit(run_benchmark(args.host, args.port, args.count, args.endpoint))


if __name__ == "__main__":
    main()
