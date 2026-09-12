"""Dibuja el grafo a PNG, con una ruta resaltada. Solo para ver que todo esté bien.

Uso:  python data/ver_mapa.py
"""

import pickle
from pathlib import Path

import matplotlib
import networkx as nx
import osmnx as ox

matplotlib.use("Agg")

ORIGEN = (25.6714, -100.3090)  # Macroplaza
DESTINO = (25.6510, -100.3590)  # Valle, San Pedro

AQUI = Path(__file__).parent


def main():
    G = pickle.loads((AQUI / "mty_graph.pkl").read_bytes())
    ruta = nx.shortest_path(
        G,
        ox.nearest_nodes(G, ORIGEN[1], ORIGEN[0]),
        ox.nearest_nodes(G, DESTINO[1], DESTINO[0]),
        weight="travel_time",
    )
    fig, _ = ox.plot_graph_route(
        G,
        ruta,
        node_size=0,
        edge_linewidth=0.12,
        edge_color="#3a3a3a",
        route_color="#ff3b30",
        route_linewidth=3,
        bgcolor="#0b0b0b",
        show=False,
        close=True,
        figsize=(12, 12),
    )
    salida = AQUI / "mapa_mty.png"
    fig.savefig(salida, dpi=110, facecolor="#0b0b0b", bbox_inches="tight")
    print(f"{salida}  ({len(ruta)} nodos en la ruta)")


if __name__ == "__main__":
    main()
