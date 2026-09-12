"""Descarga el grafo vial del área metropolitana de Monterrey y lo cachea a disco.

Uso:  python data/download_graph.py [radio_metros]

Se corre UNA vez. El simulador nunca toca la red: lee mty_graph.pkl de disco.
"""

import pickle
import sys
from pathlib import Path

import osmnx as ox

# Centro de Monterrey. 20 km de radio cubren San Pedro, Guadalupe, San Nicolás,
# Santa Catarina y Escobedo — el área donde de verdad hay pedidos.
CENTRO = (25.6866, -100.3161)
RADIO_M = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000

SALIDA = Path(__file__).parent / "mty_graph.pkl"


def main():
    if SALIDA.exists() and "--force" not in sys.argv:
        print(f"Ya existe {SALIDA.name} ({SALIDA.stat().st_size / 1e6:.0f} MB). --force para rehacer.")
        return

    print(f"Descargando red vial: {RADIO_M / 1000:.0f} km alrededor de {CENTRO}...")
    G = ox.graph_from_point(CENTRO, dist=RADIO_M, network_type="drive")

    # Velocidades por tipo de vía -> tiempo de viaje por arista, en segundos.
    G = ox.add_edge_speeds(G)
    G = ox.add_edge_travel_times(G)

    SALIDA.write_bytes(pickle.dumps(G))

    print(f"OK: {G.number_of_nodes():,} nodos, {G.number_of_edges():,} aristas")
    print(f"    {SALIDA} ({SALIDA.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
