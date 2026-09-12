"""Graba un turno completo a JSON para que el frontend lo reproduzca.

    python data/export_turno.py [seed]

Genera frontend/public/turno_<politica>.json. El formato es EL MISMO que va a
viajar por el WebSocket, nada mas grabado en archivo: el front se construye
contra esto hoy y el dia que conectemos el backend en vivo no cambia nada.

Tambien es el seguro del demo: con los JSON grabados la pantalla partida
funciona aunque el WebSocket truene el domingo.
"""

import json
import pickle
import sys
from dataclasses import asdict
from pathlib import Path

import networkx as nx

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent))

import rutas  # noqa: E402
from contrato import ConfigTurno, Punto  # noqa: E402
from sim import politica_greedy, simular  # noqa: E402

PUBLIC = AQUI.parent / "frontend" / "public"
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 1


def geometria_de_tramos(tramos):
    """La calle real de cada tramo, para que la moto no atraviese edificios.

    Carga el grafo (52 MB) una sola vez. Es offline, no importa que tarde.
    """
    if not tramos:
        return {}

    print("  cargando grafo para las rutas por calle...")
    G = pickle.loads((AQUI / "mty_graph.pkl").read_bytes())
    nodo = {i: n for i, (_, n, _, _) in enumerate(rutas.PUNTOS)}

    geo = {}
    for _, _, desde, hasta in tramos:
        clave = f"{desde}-{hasta}"
        if clave in geo:
            continue
        camino = nx.shortest_path(G, nodo[desde], nodo[hasta], weight="travel_time")
        geo[clave] = [[round(G.nodes[n]["x"], 5), round(G.nodes[n]["y"], 5)] for n in camino]
    return geo


def main():
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    cfg = ConfigTurno(duracion_min=120, ancla=Punto("Tec", *tec), margen_min=10,
                      vehiculo="moto", seed=SEED, hora_inicio=14)
    res = simular(cfg, politica_greedy)

    # Un frame por minuto: el front hace replay con frames[t] y ya.
    llegadas = {t: (p, tipo) for t, p, tipo in res.trayecto}
    por_minuto = {}
    for d in res.decisiones:
        por_minuto.setdefault(d.t, []).append(asdict(d))
    ofertas_min = {}
    for o in res.ofertas:
        ofertas_min.setdefault(o.t_aparece, []).append(asdict(o))

    # El contador sube al ENTREGAR, no al aceptar. Es lo que ve el juez subir.
    por_entrega = res.ganado / max(res.entregas, 1)
    acumulado, frames = 0.0, []
    for t in range(cfg.duracion_min):
        if t in llegadas and llegadas[t][1] == "dropoff":
            acumulado += por_entrega
        frames.append({
            "t": t,
            "ofertas": ofertas_min.get(t, []),
            "decisiones": por_minuto.get(t, []),
            "llegada": ({"punto": llegadas[t][0], "tipo": llegadas[t][1]}
                        if t in llegadas else None),
            "ganado": round(acumulado, 2),
        })

    salida = {
        "meta": {
            "politica": "greedy",
            "seed": SEED,
            "ganado": res.ganado,
            "entregas": res.entregas,
            "rechazos": res.rechazos,
            "llego_tarde": res.llego_tarde,
            "ofertas_totales": len(res.ofertas),
        },
        "config": asdict(cfg),
        "tramos": [{"t_salida": a, "t_llegada": round(b, 2), "desde": c, "hasta": d,
                    "clave": f"{c}-{d}"} for a, b, c, d in res.tramos],
        "geometria": geometria_de_tramos(res.tramos),
        "frames": frames,
    }

    PUBLIC.mkdir(parents=True, exist_ok=True)
    ruta = PUBLIC / f"turno_greedy_{SEED}.json"
    ruta.write_text(json.dumps(salida), encoding="utf-8")

    assert len(frames) == cfg.duracion_min
    assert frames[-1]["ganado"] > 0, "un turno sin dinero significa que algo se rompio"
    assert all(f"{t['desde']}-{t['hasta']}" in salida["geometria"] for t in salida["tramos"])

    print(f"\n{ruta.name}  ({ruta.stat().st_size / 1e3:.0f} KB)")
    print(f"  {len(frames)} frames, {len(res.tramos)} tramos, ${res.ganado:.0f}, "
          f"{res.entregas} entregas")


if __name__ == "__main__":
    main()
