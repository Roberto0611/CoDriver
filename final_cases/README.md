# HackMTY 2026 — Infosys Challenge
## Judge Toolkit for Student Presentations

This package contains every script and file the judge will run against your system during
your presentation. There are no surprises: the same tools are used to evaluate everyone.

---

## Setup (do this before demo day)

```bash
pip install -r requirements.txt
```

All scripts are pure Python 3 with no compiled extensions. `requests` and the optional
`faker` are the only non-stdlib dependencies; the scripts tell you if they are missing.

---

## What is in this package

```
share-with-students/
├── README.md                    ← this file
├── requirements.txt             ← pip install -r requirements.txt
│
├── forensic-auditor/
│   ├── README.md                ← exactly what judges run for Track 01
│   ├── validate_format.py       ← checks your submission JSON format
│   ├── scheme_injector.py       ← generates a fresh estate + plants a scheme
│   └── cost_tracker.py          ← reads your JSONL call log; reports cost & latency
│
└── courier/
    ├── README.md                ← exactly what judges run for Track 02
    ├── run_probe_pack.py        ← feeds an order stream to /decide and scores it
    ├── shock_injector.py        ← posts disruption events to your simulation
    ├── timing_benchmark.py      ← measures p99 latency of your /decide endpoint
    └── practice_pack/
        ├── README.md            ← read this before running the pack
        ├── practice_pack.csv    ← 14-order stream covering all 5 safety constraints
        └── practice_pack_key.json ← answer key — graded by run_probe_pack.py
```

---

## What judges bring separately (not in this package)

- Their own probe pack CSVs (seeds 900–902) — answer keys stay with the judge
- The pre-generated forensic estates (seeds 1–3) — ground truth files stay with the judge
- Their PDF copy of the scoring rubric

---

## Scoring reminder

Six criteria, 1–5 each, 30 points total. A **3** means "did the thing, no more."
A **5** requires specific, verifiable evidence shown live.

Open `scorecard.html` in a browser to see the full rubric for your track.

---

## Quick-start by track

### Track 01 — Forensic Auditor

```bash
cd forensic-auditor/

# Check your submission format
python3 validate_format.py --submission your_submission.json

# Optionally verify exhibit record IDs against your estate
python3 validate_format.py --submission your_submission.json --estate path/to/estate.db

# Live-cost watch during the judge's demo injection
python3 cost_tracker.py --log-file your_calls.jsonl --watch

# Generate a test estate with a known scheme (to test your own agent)
python3 scheme_injector.py --list
python3 scheme_injector.py --scheme phantom_vendor --amount 900000 --seed 42 --output-dir ./test_estate
```

### Track 02 — The Courier

```bash
cd courier/

# Run the practice pack against your endpoint (do this many times)
python3 run_probe_pack.py \
    --pack practice_pack/practice_pack.csv \
    --key  practice_pack/practice_pack_key.json \
    --endpoint http://localhost:8000/decide

# Measure your Tier 1 fast-path latency
python3 timing_benchmark.py --host localhost --port 8000 --count 200

# Preview the four judge shock scenarios (no server needed)
python3 shock_injector.py --list

# Inject shocks during your own test run
python3 shock_injector.py --shock surge
python3 shock_injector.py --shock closure
python3 shock_injector.py --shock rain
python3 shock_injector.py --shock delay --order-id ORDER-XXX --slip 15
```

---

## Passing the practice pack is necessary but not sufficient

`run_probe_pack.py` on the practice pack confirms your safety constraints are reachable
over HTTP. Judges run a longer, unseen pack from a reserved seed band. That pack includes
categories not in the practice pack. A system that only handles what it has seen before
will not score above a 3 on Results.

Similarly, `validate_format.py` checks that your output has the right **shape**; it does
not check that your findings are **correct**. Correctness is measured by the judge's own
ground-truth verification.
