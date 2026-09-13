"""La forma de cada tramo en el mapa, para el demo en vivo.

El replay grabado trae la calle real de cada tramo porque el exportador carga el
grafo de 52 MB. En vivo no se puede cargar por sesion, y en CI ni existe. Por eso
la geometria es una funcion que se le pasa a la sesion:

    linea_recta          sin grafo: del punto A al punto B, y ya
    por_calles(grafo)    el grafo que `main.py` ya tiene en memoria

Un tramo sin camino en el grafo (nodo suelto, calle de un solo sentido) cae a su
linea recta y los demas siguen por calle. Que una moto cruce un edificio es feo;
que el tick truene a media demo es peor.
"""

from collections.abc import Callable
from typing import Any

import rutas

Tramo = tuple[float, float, int, int]  # (t_salida, t_llegada, desde, hasta), como sim.Resultado
Geometria = Callable[[list[Tramo]], dict[str, list[list[float]]]]


def _recta(desde: int, hasta: int) -> list[list[float]]:
    # COORD_DE es (lat, lon) y GeoJSON quiere [lon, lat]. Aqui se voltea una sola vez.
    (lat_a, lon_a), (lat_b, lon_b) = rutas.COORD_DE[desde], rutas.COORD_DE[hasta]
    return [[round(lon_a, 5), round(lat_a, 5)], [round(lon_b, 5), round(lat_b, 5)]]


def linea_recta(tramos: list[Tramo]) -> dict[str, list[list[float]]]:
    return {f"{desde}-{hasta}": _recta(desde, hasta) for _, _, desde, hasta in tramos}


def por_calles(grafo: Any) -> Geometria:
    """Geometria por calle sobre `grafo`. El cache vive en el closure: si el registro
    crea esta funcion una vez, todas las sesiones comparten los caminos ya calculados."""
    if grafo is None:
        return linea_recta

    # Import tardio: export_turno jala networkx, y linea_recta no lo necesita.
    import networkx as nx

    from data import export_turno

    cache: dict[str, list[list[float]]] = {}

    def geometria(tramos: list[Tramo]) -> dict[str, list[list[float]]]:
        geo: dict[str, list[list[float]]] = {}
        for tramo in tramos:
            try:
                geo.update(export_turno.geometria_de_tramos([tramo], cache, grafo=grafo))
            except (nx.NetworkXException, KeyError):
                # Se guarda la recta en el cache: buscar un camino que no existe
                # recorre medio grafo, y no hay que pagarlo cada tick.
                clave = f"{tramo[2]}-{tramo[3]}"
                cache[clave] = _recta(tramo[2], tramo[3])
                geo[clave] = cache[clave]
        return geo

    return geometria
