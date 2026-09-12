"""La referencia del motor: lo que gana hoy, para que nadie lo empeore sin notarlo.

    python scripts/engine_baseline.py            muestra la referencia vs lo actual
    python scripts/engine_baseline.py --write    fija lo actual como nueva referencia

Se escribe tests/engine_baseline.json. Lo lee tests/test_engine_golden.py:
  - el greedy sobre los seeds frescos debe dar EXACTAMENTE lo mismo (si cambia,
    cambio el mundo o el simulador, y hay que decidirlo a proposito);
  - el delta de Nuez no puede bajar de la referencia (ratchet: solo sube).
"""

import json
import statistics
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import rutas  # noqa: E402
import seeds  # noqa: E402
from contrato import ConfigTurno, Punto  # noqa: E402
from nuez import politica_nuez  # noqa: E402
from sim import politica_greedy, simular  # noqa: E402

ARCHIVO = RAIZ / "tests" / "engine_baseline.json"
N = 50
SEEDS = seeds.de_reporte(N)  # de REPORTE: el ratchet mide donde se reporta
SEED_BASE = SEEDS[0]


def config(seed: int) -> ConfigTurno:
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    return ConfigTurno(
        duracion_min=120,
        ancla=Punto("Tec", *tec),
        margen_min=10,
        vehiculo="moto",
        hora_inicio=14,
        seed=seed,
    )


def medir() -> dict:
    greedy = [simular(config(s), politica_greedy) for s in SEEDS]
    nuez = [simular(config(s), politica_nuez) for s in SEEDS]
    g = statistics.mean(r.ganado for r in greedy)
    n = statistics.mean(r.ganado for r in nuez)
    return {
        "seed_base": SEED_BASE,
        "n": N,
        "greedy_mean": round(g, 4),
        "nuez_mean": round(n, 4),
        "delta_pct": round((n / g - 1) * 100, 3),
        "nuez_gana_en": sum(1 for a, b in zip(greedy, nuez, strict=True) if b.ganado > a.ganado),
        "nuez_tarde": sum(r.llego_tarde for r in nuez),
        "greedy_tarde": sum(r.llego_tarde for r in greedy),
    }


def main(argv: list[str]) -> int:
    actual = medir()
    if "--write" in argv:
        ARCHIVO.write_text(json.dumps(actual, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(
            f"referencia escrita en {ARCHIVO.relative_to(RAIZ)}: delta {actual['delta_pct']:+.2f}%"
        )
        return 0
    ref = json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.exists() else {}
    print(f"{'':<14}{'referencia':>12}{'actual':>12}")
    for k in ("greedy_mean", "nuez_mean", "delta_pct", "nuez_gana_en", "nuez_tarde"):
        print(f"{k:<14}{ref.get(k, '-'):>12}{actual[k]:>12}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
