"""A1: precalcula la matriz de tiempos entre los puntos de interés del simulador.

Dijkstra sobre 268k aristas tarda ~1 segundo. El motor pregunta "cuanto tardo de
aqui a alla" miles de veces por turno (cada oferta x cada permutacion de la mochila).
Con la matriz, esa pregunta es leer una celda.

Se corre UNA vez, despues de download_graph.py.
Uso:  python data/build_matriz.py
"""

import pickle
import random
import sys
from pathlib import Path

import networkx as nx
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from mundo import ZONAS  # noqa: E402

PUNTOS_POR_ZONA = 15  # 14 zonas x 15 = 210 puntos -> matriz de 210x210
SEED = 7  # el muestreo es determinista: todos obtienen los mismos puntos

AQUI = Path(__file__).parent
SALIDA = AQUI / "matriz.pkl"


def muestrear_puntos(G, nodos_validos):
    """Toma PUNTOS_POR_ZONA nodos reales dentro del radio de cada zona."""
    rng = random.Random(SEED)
    puntos = []  # (zona, node_id, lat, lon)
    usados = set()  # zonas vecinas se traslapan; un nodo pertenece a una sola

    for zona, (lat, lon, radio) in ZONAS.items():
        # Grados aproximados que cubre el radio; sobra para filtrar candidatos.
        grados = radio / 111_000 * 1.5
        cerca = [
            n
            for n in nodos_validos
            if n not in usados
            and abs(G.nodes[n]["y"] - lat) < grados
            and abs(G.nodes[n]["x"] - lon) < grados
        ]
        if len(cerca) < PUNTOS_POR_ZONA:
            raise SystemExit(f"zona {zona}: solo {len(cerca)} nodos, revisa coordenadas o radio")

        for n in rng.sample(cerca, PUNTOS_POR_ZONA):
            puntos.append((zona, n, G.nodes[n]["y"], G.nodes[n]["x"]))
            usados.add(n)
    return puntos


def main():
    G = pickle.loads((AQUI / "mty_graph.pkl").read_bytes())

    # Solo la componente fuertemente conexa: garantiza que de cualquier punto
    # se llega a cualquier otro. Sin esto, un nodo en un callejon de un sentido
    # produce distancias infinitas a media simulacion.
    mayor = max(nx.strongly_connected_components(G), key=len)
    print(f"componente conexa: {len(mayor):,} de {G.number_of_nodes():,} nodos")

    puntos = muestrear_puntos(G, mayor)
    ids = [n for _, n, _, _ in puntos]
    indice = {n: i for i, n in enumerate(ids)}
    print(f"puntos de interes: {len(puntos)}")

    # Un Dijkstra por origen devuelve los tiempos a TODOS los destinos de golpe.
    sub = G.subgraph(mayor)
    M = np.full((len(ids), len(ids)), np.inf, dtype=np.float32)
    for i, origen in enumerate(ids):
        largos = nx.single_source_dijkstra_path_length(sub, origen, weight="travel_time")
        for destino, seg in largos.items():
            if destino in indice:
                M[i, indice[destino]] = seg / 60.0  # minutos de flujo libre
        if (i + 1) % 30 == 0:
            print(f"  {i + 1}/{len(ids)}")

    assert np.isfinite(M).all(), "hay pares inalcanzables: revisa la componente conexa"

    SALIDA.write_bytes(pickle.dumps({"puntos": puntos, "matriz": M}))
    print(f"\n{SALIDA.name}: matriz {M.shape}, {SALIDA.stat().st_size / 1e3:.0f} KB")
    print(f"tiempo medio entre puntos: {M[M > 0].mean():.1f} min (flujo libre)")


if __name__ == "__main__":
    main()
