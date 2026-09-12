"""El motor es el hackathon. Nadie lo cambia sin que se note.

Dos guardas:
  1. Golden del seed 1 con greedy: cualquier edicion a mundo/rutas/sim que mueva
     un solo peso falla aqui.
  2. Ratchet contra tests/engine_baseline.json: el greedy sobre 50 seeds frescos
     da exactamente lo de la referencia, y el delta de Nuez nunca baja.

Si el cambio es a proposito: `python scripts/engine_baseline.py --write`, y el
diff del JSON en el PR es la conversacion.
"""

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import engine_baseline as eb  # noqa: E402

from nuez import politica_nuez  # noqa: E402
from sim import politica_greedy, simular  # noqa: E402

# Lo que da hoy el turno grabado para el front (frontend/public/turno_greedy_1.json).
GOLDEN_SEED_1 = {"ganado": 253.77, "entregas": 4, "rechazos": 90, "ofertas": 94}


def test_golden_seed_1_greedy():
    res = simular(eb.config(1), politica_greedy)
    actual = {
        "ganado": res.ganado,
        "entregas": res.entregas,
        "rechazos": res.rechazos,
        "ofertas": len(res.ofertas),
    }
    assert actual == GOLDEN_SEED_1, (
        "El simulador cambio de comportamiento. Si es a proposito, actualiza GOLDEN_SEED_1 "
        "y regraba frontend/public/turno_greedy_1.json (python data/export_turno.py 1)."
    )
    assert not res.llego_tarde


def test_el_turno_grabado_coincide_con_el_motor():
    meta = json.loads(
        (RAIZ / "frontend" / "public" / "turno_greedy_1.json").read_text(encoding="utf-8")
    )["meta"]
    assert meta["seed"] == 1 and meta["politica"] == "greedy"
    assert meta["ganado"] == GOLDEN_SEED_1["ganado"]
    assert meta["entregas"] == GOLDEN_SEED_1["entregas"]
    assert meta["ofertas_totales"] == GOLDEN_SEED_1["ofertas"]


def test_ratchet_contra_la_referencia():
    ref = json.loads(eb.ARCHIVO.read_text(encoding="utf-8"))
    actual = eb.medir()

    assert actual["greedy_mean"] == ref["greedy_mean"], (
        "El greedy cambio: se movio el mundo o el simulador. Decidelo a proposito y corre "
        "python scripts/engine_baseline.py --write"
    )
    assert actual["delta_pct"] >= ref["delta_pct"] - 0.05, (
        f"Nuez empeoro: {actual['delta_pct']:+.2f}% vs referencia {ref['delta_pct']:+.2f}%. "
        "El motor solo puede mejorar."
    )
    assert actual["nuez_tarde"] <= ref["nuez_tarde"], "Nuez empezo a llegar tarde a clase"


def test_el_simulador_sigue_siendo_rapido():
    """La tabla de valor corre 300 turnos; si el motor se vuelve lento, se rompe el flujo."""
    t0 = time.perf_counter()
    for seed in range(20):
        simular(eb.config(seed), politica_nuez)
    por_turno = (time.perf_counter() - t0) / 20
    assert por_turno < 0.25, f"{por_turno * 1000:.0f} ms por turno; deberian ser ~5-30 ms"
