# Courier — Data Formats and Judging Rules

This folder specifies the **formats** your project must produce and consume, and the protocol judges will run. It contains no dataset and no worked solution — with one deliberate exception, `practice_pack/`, which gives you expected answers for the five published safety constraints so you can test that yours actually fire.

**You build your own simulator and order stream.** Write a generator, or adapt a dataset supplied with the problem statement. The formats below are the contract; the data is yours.

## Files

| File | What it specifies |
|---|---|
| `event_log_schema.json` | The simulator event format — every event type, its required fields, and illustrative examples |
| `decision_response_schema.json` | The request and response contract for your decision endpoint, plus `explain_decision` |
| `evaluation_protocol.md` | What judges will run: shift configurations, probe categories, safety constraints, replay and failure checks |
| `event_log_example.jsonl` | Field shape only — one of each event type, with placeholder values |
| `order_stream_example.csv` | Field shape only — one order as a CSV row, for the CSV input path |
| `validate_format.py` | Checks your output conforms. Format only; no test cases, no expected answers. |
| `practice_pack/` | 14 orders with known correct answers, covering the five safety constraints. See its README. |
| `run_probe_pack.py` | Feeds an order stream to your `/decide` endpoint and grades it against a key. Judges run this same script. |
| `results_table_template.csv` | The Results table shape |

## Order stream input — JSONL or CSV, your choice

Judges always probe your **live endpoint** with JSON; that contract does not change, and `decision_response_schema.json` remains the thing your `/decide` must satisfy.

For building and replaying shifts offline, you may load the order stream as **either** JSON Lines **or** CSV. Use whichever your simulator prefers — they carry the same fields.

`order_stream_example.csv` shows the shape: one row per offered order, columns matching `order_offered` in `event_log_schema.json` minus the `event` column (every row in an order stream is an offered order, so a constant column carries no information).

Empty cell means the optional field is absent — `zone_pickup_name` and the `estimated_*` columns are blank in the example for exactly that reason. The nine required columns are:

```
order_id, sim_time, zone_pickup, zone_dropoff, distance_pickup_km,
distance_delivery_km, base_pay_mxn, surge_multiplier, vehicle
```

A CSV order stream is still bound by the determinism rule: the same seed must produce a byte-identical stream, whichever format you emit.

## Testing your decisions, not just your formats

`validate_format.py` checks that your output has the right shape. It cannot tell you
whether a decision was correct. `practice_pack/` can:

```bash
python3 run_probe_pack.py \
    --pack practice_pack/practice_pack.csv \
    --key practice_pack/practice_pack_key.json \
    --endpoint http://localhost:8000/decide
```

Fourteen orders, POSTed in `sim_time` order, with courier state carried forward from your
own accept decisions — so the heat-rule case is reached by accumulating riding time
rather than by being handed it. Exits non-zero on a failure. Stdlib only.

Five of the fourteen must be **accepted**: three anchors and three controls that sit just
inside a limit. A safety rule that also refuses those is firing too widely, and judges
probe boundaries from both directions.

Read [practice_pack/README.md](practice_pack/README.md) before you run it, and note what
it does not cover: there are no economic judgment cases, because your reservation wage is
yours to set. Judges grade judgment through consistency between decisions — see §3 of
`evaluation_protocol.md` — not against an answer key.

**Passing the practice pack is a floor, not a score.** Judges run a longer pack you have
not seen, on a seed from the reserved band, using this same runner.

## Using the validator

```bash
# an event log your simulator produced
python3 validate_format.py --event-log my_shift.jsonl

# decision responses your endpoint returned
python3 validate_format.py --responses my_responses.json

# probe a running endpoint and check the response shape
python3 validate_format.py --endpoint http://localhost:8000/decide

# an order stream CSV, before you feed it to your simulator
python3 validate_format.py --order-stream-csv my_orders.csv
```

Exits non-zero on a format error. Wire it into your build.

It checks format only. It does not tell you whether your decisions are correct and does not measure earnings.

## Read `evaluation_protocol.md` next

It lists representative evaluation conditions, the decision categories judges probe, the five safety constraints, and the replay/model-failure checks — without giving exact hidden test payloads or expected answers.

## Rules that decide your score

**Decisions must be deterministic per seed.** A seed must produce a byte-identical order stream every time, and identical fast-path decisions on identical input. Judges may record a shift, replay it, and diff the decisions.

**The fast path has a 50 ms budget.** A courier has roughly 5 seconds to decide in the real app. Any code path that calls a model inside the decision window fails Feasibility.

**Safety constraints must be enforced in code.** Not as instructions in a model prompt. Judges will ask you to open the file where each limit is defined. A constraint that exists but is never demonstrated triggering scores low — rehearse at least two as live demo moments.

**Every decision carries a reason under 40 words** that names the constraint that actually bound. Set `binding_constraint` so a safety refusal is machine-distinguishable from pay criteria. A correct decision with a generic or wrong reason does not earn the Judgment credit.

**Report on seeds you did not tune on.** Name both sets in the pitch. If your numbers come from the seeds you tuned on, **Results caps at 3** regardless of the margin.

**Compare against named baselines.** A single number with nothing beside it is not a result.

**Handle model failure.** When the model is unreachable the fast path keeps deciding on the last known strategy, within budget, and signals that it is degraded. A silent fallback is partial credit; a stall or crash is a hard failure.

**Three vehicle types.** `moto`, `car` and `bike`, with distinct speed profiles and distinct weight and volume limits.

## Questions judges ask

- "What happens if I change this input?"
- "Why should I trust this number?"
- "What does it do when it's wrong?"
- "Could a real courier use this tomorrow?"
- "What did you cut, and why?"
- "Why did you skip that order?"
- "What would it do if a surge hit right now?"
- "What if this order's restaurant is running 15 minutes late?"

Answering from a decision log in under ten seconds is itself scored. Re-deriving the answer live is the wrong answer even when it turns out to be right.
