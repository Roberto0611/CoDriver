"""Sanity check del grafo: distancias y tiempos entre puntos conocidos de MTY.

Los tiempos son de flujo libre (maxspeed de OSM). El simulador les aplica encima
un factor de tráfico por hora del día — sin eso, MTY se ve 3x más rápido de lo real.
"""

import pickle
from pathlib import Path

import networkx as nx
import osmnx as ox

PUNTOS = {
    "Macroplaza": (25.6714, -100.3090),
    "SanPedro/Valle": (25.6510, -100.3590),
    "Fundidora": (25.6790, -100.2840),
    "Cumbres": (25.7290, -100.3890),
}

# Distancias en línea de calle que sabemos por experiencia local, en km.
ESPERADO_KM = {("Macroplaza", "SanPedro/Valle"): 7, ("Fundidora", "Macroplaza"): 4}


def main():
    G = pickle.loads((Path(__file__).parent / "mty_graph.pkl").read_bytes())
    nodos = {k: ox.nearest_nodes(G, lon, lat) for k, (lat, lon) in PUNTOS.items()}

    for a in PUNTOS:
        for b in PUNTOS:
            if a >= b:
                continue
            km = nx.shortest_path_length(G, nodos[a], nodos[b], weight="length") / 1000
            minutos = nx.shortest_path_length(G, nodos[a], nodos[b], weight="travel_time") / 60
            print(f"{a:>16} -> {b:<16} {km:5.1f} km {minutos:5.1f} min")

            esperado = ESPERADO_KM.get((a, b))
            assert esperado is None or abs(km - esperado) < 3, f"{a}->{b}: {km:.1f} km, esperaba ~{esperado}"

    assert nx.is_strongly_connected(G.subgraph(max(nx.strongly_connected_components(G), key=len)))
    print("\nOK: grafo conectado y distancias coherentes.")


if __name__ == "__main__":
    main()
