"""Graba turnos completos a JSON para que el frontend los reproduzca.

    python data/export_turno.py              graba los seeds por defecto
    python data/export_turno.py 1 7 42       graba esos seeds

Por cada seed salen DOS archivos, uno por politica, con el mismo stream de
ofertas: `turno_greedy_<seed>.json` y `turno_nuez_<seed>.json`. Mismo seed es lo
unico que hace honesta la pantalla partida — los dos enfrentaron los mismos pings.

El formato es EL MISMO que va a viajar por el WebSocket, nada mas grabado en
archivo: el front y la voz se construyen contra esto hoy, y el dia que conectemos
el backend en vivo no cambia una linea.

Tambien es el seguro del demo: con los JSON grabados la pantalla partida funciona
aunque el WebSocket, Tiger o el wifi truenen el domingo.
"""

import json
import pickle
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import networkx as nx

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent))

import rutas  # noqa: E402
from contrato import ConfigTurno, Punto  # noqa: E402
from nuez import politica_nuez  # noqa: E402
from sim import Resultado, politica_greedy, simular  # noqa: E402

PUBLIC = AQUI.parent / "frontend" / "public"

# Tres turnos para que el juez pueda escoger sin que dependamos de la red.
SEEDS_DEFAULT = [1, 7, 42]
POLITICAS = {"greedy": politica_greedy, "nuez": politica_nuez}

_grafo = None


def _cargar_grafo():
    """El grafo pesa 52 MB. Se carga una vez para todos los turnos."""
    global _grafo
    if _grafo is None:
        print("cargando grafo para las rutas por calle...")
        _grafo = pickle.loads((AQUI / "mty_graph.pkl").read_bytes())
    return _grafo


def geometria_de_tramos(tramos, cache: dict, grafo=None) -> dict:
    """La calle real de cada tramo, para que la moto no atraviese edificios.

    El cache se comparte entre turnos: muchos tramos se repiten entre politicas.
    `grafo` lo pasa el demo en vivo, que ya lo tiene cargado en main.py; el export
    grabado lo deja en None y aqui se carga del pickle como siempre.
    """
    if not tramos:
        return {}

    G = grafo if grafo is not None else _cargar_grafo()
    nodo = {i: n for i, (_, n, _, _) in enumerate(rutas.PUNTOS)}

    geo = {}
    for _, _, desde, hasta in tramos:
        clave = f"{desde}-{hasta}"
        if clave not in cache:
            camino = nx.shortest_path(G, nodo[desde], nodo[hasta], weight="travel_time")
            cache[clave] = [[round(G.nodes[n]["x"], 5), round(G.nodes[n]["y"], 5)] for n in camino]
        geo[clave] = cache[clave]
    return geo


def config(seed: int) -> ConfigTurno:
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    return ConfigTurno(
        duracion_min=120,
        ancla=Punto("Tec", *tec),
        margen_min=10,
        vehiculo="moto",
        seed=seed,
        hora_inicio=14,
    )


def a_frames(res: Resultado, duracion: int) -> list[dict[str, Any]]:
    """Un frame por minuto: el front hace replay con frames[t] y ya."""
    llegadas = {t: (p, tipo) for t, p, tipo in res.trayecto}
    # Puede haber gasolina negativa y pago positivo en el mismo minuto. `dict`
    # perdería uno de los dos y el contador dejaría de cuadrar con la utilidad neta.
    cobros: dict[int, float] = {}
    for minuto, monto in res.cobros:
        cobros[minuto] = cobros.get(minuto, 0.0) + monto

    por_minuto: dict[int, list[dict]] = {}
    for d in res.decisiones:
        por_minuto.setdefault(d.t, []).append(asdict(d))
    ofertas_min: dict[int, list[dict]] = {}
    for o in res.ofertas:
        ofertas_min.setdefault(o.t_aparece, []).append(asdict(o))

    acumulado = 0.0
    frames = []
    for t in range(duracion):
        # El contador sube al ENTREGAR, con el monto exacto de esa entrega.
        # Es el numero que el juez ve subir, asi que tiene que ser el de verdad.
        acumulado += cobros.get(t, 0.0)
        frames.append(
            {
                "t": t,
                "ofertas": ofertas_min.get(t, []),
                "decisiones": por_minuto.get(t, []),
                "llegada": (
                    {"punto": llegadas[t][0], "tipo": llegadas[t][1]} if t in llegadas else None
                ),
                "cobro": round(cobros.get(t, 0.0), 2),
                "ganado": round(acumulado, 2),
            }
        )
    return frames


def grabar(seed: int, nombre: str, politica, cache: dict) -> dict:
    cfg = config(seed)
    res = simular(cfg, politica)

    salida: dict[str, Any] = {
        "meta": {
            "politica": nombre,
            "seed": seed,
            "ganado": res.ganado,
            "ingreso_bruto": res.ingreso_bruto,
            "gasto_combustible": res.gasto_combustible,
            "entregas": res.entregas,
            "rechazos": res.rechazos,
            # Dos cosas distintas: `violaciones` es aceptar algo infactible (romper
            # la regla) y `llego_tarde` es no volver antes de duracion - margen, que
            # puede deberse a algo que paso DESPUES de aceptar.
            "violaciones": res.violaciones,
            "llego_tarde": res.llego_tarde,
            "regreso_en": res.regreso_en,
            "cancelados": res.cancelados,
            "ofertas_totales": len(res.ofertas),
        },
        "config": asdict(cfg),
        "tramos": [
            {"t_salida": a, "t_llegada": round(b, 2), "desde": c, "hasta": d, "clave": f"{c}-{d}"}
            for a, b, c, d in res.tramos
        ],
        "geometria": geometria_de_tramos(res.tramos, cache),
        "frames": a_frames(res, cfg.duracion_min),
    }

    ruta = PUBLIC / f"turno_{nombre}_{seed}.json"
    ruta.write_text(json.dumps(salida), encoding="utf-8")

    assert len(salida["frames"]) == cfg.duracion_min
    assert salida["frames"][-1]["ganado"] > 0, "un turno sin dinero significa que algo se rompio"
    if not res.llego_tarde and abs(salida["frames"][-1]["ganado"] - res.ganado) >= 0.05:
        print(
            f"WARNING: contador no cuadra para {nombre} seed {seed}: "
            f"{salida['frames'][-1]['ganado']} vs {res.ganado}"
        )
    assert all(t["clave"] in salida["geometria"] for t in salida["tramos"])

    print(
        f"  {ruta.name:<24} {ruta.stat().st_size / 1e3:>6.0f} KB  "
        f"${res.ganado:>6.0f}  {res.entregas} entregas"
        f"{'  LLEGO TARDE' if res.llego_tarde else ''}"
    )
    return salida["meta"]


def main():
    seeds = [int(a) for a in sys.argv[1:]] or SEEDS_DEFAULT
    PUBLIC.mkdir(parents=True, exist_ok=True)
    cache: dict[str, list] = {}
    indice = []

    for seed in seeds:
        print(f"\nturno seed={seed}")
        metas = {n: grabar(seed, n, pol, cache) for n, pol in POLITICAS.items()}
        delta = (metas["nuez"]["ganado"] / metas["greedy"]["ganado"] - 1) * 100
        print(f"  {'delta':<24} {delta:>+6.1f}%")
        indice.append(
            {"seed": seed, "delta_pct": round(delta, 1), **{k: v for k, v in metas.items()}}
        )

    # Indice para el selector de seeds del juez: que turnos hay grabados.
    (PUBLIC / "turnos.json").write_text(json.dumps({"turnos": indice}), encoding="utf-8")
    print(f"\nturnos.json con {len(indice)} turnos grabados")


if __name__ == "__main__":
    main()
