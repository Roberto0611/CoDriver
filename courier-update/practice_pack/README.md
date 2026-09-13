# Courier — Practice Pack

Fourteen orders with a known correct answer, and a runner that feeds them to your
`/decide` endpoint and tells you which ones you got wrong.

```bash
python3 ../run_probe_pack.py \
    --pack practice_pack.csv --key practice_pack_key.json \
    --endpoint http://localhost:8000/decide
```

Stdlib only, exits non-zero on a failure, runs in about a second. Wire it into your build
next to `validate_format.py` — that one checks that your output has the right *shape*,
this one checks that your decisions are *right*.

## What is in it, and what is not

Every case here tests one of the five safety constraints in `evaluation_protocol.md` §4,
or proves that constraint is not over-broad. That is the whole scope.

There are **no economic judgment cases**. Your reservation wage is yours to set, there is
no single correct value, and a pack that graded you against ours would be teaching you to
match our tuning instead of building your own. Judges do test judgment — §3 lists the
categories — but they test it with rules about *consistency* between decisions, not with
an answer key. Two of those rules are in this pack so you can see the shape:
`heat-pay-invariance` and `flagged-zone-pay-invariance` each offer the same blocked route
twice, once at ordinary pay and once at roughly five times that. A refusal that changes
its mind when the money improves was never a safety rule.

**Passing this pack does not mean you will score well.** It means your safety constraints
are wired up and reachable over HTTP. Judges run a longer pack you have not seen, on a
seed from the reserved band, including categories that are not represented here at all.

## Five of the fourteen must be ACCEPTED

`PP-001` through `PP-003` are anchors: well-paid ordinary orders with nothing binding.
`PP-009`, `PP-012` and `PP-014` are controls, and they are the interesting ones:

- `PP-009` — 19.0 kg and 18.5 L, just inside the moto limits
- `PP-012` — 22:07, an ordinary dropoff zone, well inside the shift
- `PP-014` — 22:16, a 5-minute order with 14 minutes of shift left

A system that refuses these has a safety rule firing too widely. That is not caution; it
is a bug that costs the courier real money, and judges probe boundaries from both sides.
`if hour >= 22: return SKIP` passes `PP-010` and fails `PP-012`.

## Carried state, and why some cases say "override"

The runner POSTs orders in `sim_time` order and carries courier state forward from *your*
accept decisions — continuous riding time, elapsed shift hours, in-flight orders — then
sends that state as `courier_state_overrides` on the next ping. Service times come from
the key, so neither of us has to guess at the other's travel model.

That is what makes `PP-004` work. It needs 92 minutes of continuous riding behind it, and
you get there by accepting the three anchors. If the runner reports `PP-004` as `carried`,
you accumulated that state yourself. If it reports `override`, the runner had to hand you
the state because your accept pattern never produced it — the probe still gets graded,
but you have learned something about your system.

`PP-006` is always `override`. It needs four unbroken hours of riding, and a shift that
obeys the heat rule never gets there, which is exactly why that constraint needs a test of
its own rather than an expectation that a normal shift will exercise it.

## Adjust it to your model

Two conventions the pack has to assume, both flagged in the key:

- **Zone 99 is treated as flagged.** Your simulator picks its own flagged set. If 99 is
  not in yours, add it or repoint `PP-010` and `PP-011` at a zone that is.
- **Moto limits are 20 kg and 20 L.** If your profile differs, move `PP-007`, `PP-008` and
  `PP-009` so two rows sit outside your limits and one sits just inside. Keep the one just
  inside.

## Write your own

The format is worth learning, because the fastest way to find out whether your system
handles a situation is to write the situation down. The key's `_about` fields and the
runner's module docstring document both files. A case needs a `grade`, a `service_min`,
an `expected_decision`, and — for a safety refusal — an `expected_binding_constraint`.

Add cases for the situations you are least sure about. The ones you avoid writing are
usually the ones that break on stage.
