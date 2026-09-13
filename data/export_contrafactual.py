"""Graba el reporte contrafactual de cada turno grabado, para el final del replay.

    python data/export_contrafactual.py          los seeds de frontend/public/turnos.json
    python data/export_contrafactual.py 2000     solo ese seed (tiene que estar en turnos.json)

Sale un archivo NUEVO por seed, `contrafactual_<seed>.json`. No toca los
`turno_*.json` ni `turnos.json`: esos los graba `export_turno.py` y aqui solo se
leen.

Usa la MISMA config que `export_turno.py`. Si el motor ya no da lo que dice el
turno grabado, revienta en vez de escribir: un contrafactual que no cuadra con
el numero que el juez acaba de ver en pantalla es peor que no tener ninguno.
"""

import json
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent))

from contrafactual import reporte  # noqa: E402
from data.export_turno import PUBLIC, config  # noqa: E402
from seeds import es_de_tuneo  # noqa: E402


def grabados() -> dict[int, float]:
    """seed -> lo que gano Nuez segun turnos.json."""
    indice = json.loads((PUBLIC / "turnos.json").read_text(encoding="utf-8"))
    return {t["seed"]: t["nuez"]["ganado"] for t in indice["turnos"]}


def main() -> None:
    en_disco = grabados()
    seeds = [int(a) for a in sys.argv[1:]] or list(en_disco)

    for seed in seeds:
        # Sin turno grabado no hay replay al que ponerle el reporte, y lo que se
        # enseña al juez sale de REPORTE, nunca de un seed de tuneo.
        if seed not in en_disco:
            raise SystemExit(f"seed {seed} no esta en turnos.json: grabalo con export_turno.py")
        if es_de_tuneo(seed):
            raise SystemExit(f"seed {seed} es de TUNEO: el reporte sale de seeds de REPORTE")

        rep = reporte(config(seed))
        ganado = rep["actual"]["earned_mxn"]
        if ganado != en_disco[seed]:
            raise SystemExit(
                f"seed {seed}: el motor da ${ganado} y turnos.json dice ${en_disco[seed]}. "
                "Regraba los turnos primero (python data/export_turno.py)."
            )

        ruta = PUBLIC / f"contrafactual_{seed}.json"
        ruta.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
        dinero = rep["money_skips"]
        print(
            f"  {ruta.name:<26} {dinero['count']} por dinero "
            f"({dinero['would_earn_less']} menos, {dinero['would_earn_more']} mas), "
            f"{sum(rep['safety_skips'].values())} por seguridad, "
            f"{rep['capacity_skips']} por vehiculo lleno"
        )


if __name__ == "__main__":
    main()
