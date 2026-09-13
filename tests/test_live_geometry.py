"""La geometría de las rutas del demo en vivo."""

import pytest

import rutas
from backendruta.live_geometry import linea_recta, por_calles


def test_sin_grafo_la_geometria_es_linea_recta():
    assert por_calles(None) is linea_recta
    (lat_a, lon_a), (lat_b, lon_b) = rutas.COORD_DE[3], rutas.COORD_DE[7]
    geo = linea_recta([(0, 4.5, 3, 7)])
    assert geo == {
        "3-7": [
            [pytest.approx(lon_a, abs=1e-5), pytest.approx(lat_a, abs=1e-5)],
            [pytest.approx(lon_b, abs=1e-5), pytest.approx(lat_b, abs=1e-5)],
        ]
    }


def test_por_calles_usa_el_grafo_que_le_dan_y_cae_a_recta_por_tramo():
    nx = pytest.importorskip("networkx")
    n0, n1 = rutas.PUNTOS[0][1], rutas.PUNTOS[1][1]
    grafo = nx.MultiDiGraph()
    grafo.add_node(n0, x=-100.1, y=25.1)
    grafo.add_node("medio", x=-100.2, y=25.2)
    grafo.add_node(n1, x=-100.3, y=25.3)
    grafo.add_edge(n0, "medio", travel_time=1.0)
    grafo.add_edge("medio", n1, travel_time=1.0)

    geo = por_calles(grafo)([(0, 3, 0, 1), (3, 6, 1, 0), (6, 9, 0, 2)])
    assert geo["0-1"] == [[-100.1, 25.1], [-100.2, 25.2], [-100.3, 25.3]], "uso el grafo dado"
    assert geo["1-0"] == linea_recta([(3, 6, 1, 0)])["1-0"]
    assert geo["0-2"] == linea_recta([(6, 9, 0, 2)])["0-2"]
