"""Zonas como enteros: el protocolo las numera y el motor las nombra.

Los ids son parte de nuestro stream, no un detalle interno: el orden es estable y se
publica en `GET /zones` para que el juez pueda mandar `zone_pickup: 7` y saber a que
se refiere. Este archivo es la unica traduccion entre los dos mundos.
"""

import rutas
from contrato import Punto
from mundo import ZONAS
from sim import _punto

NOMBRES = tuple(ZONAS)
ID_POR_NOMBRE = {nombre: zone_id for zone_id, nombre in enumerate(NOMBRES)}


def nombre(zone_id: int) -> str:
    if not 0 <= zone_id < len(NOMBRES):
        raise ValueError(f"zona {zone_id} desconocida; usa GET /zones")
    return NOMBRES[zone_id]


def indice(zone_id: int) -> int:
    """El punto del mapa que representa a esa zona."""
    return rutas.puntos_de(nombre(zone_id))[0]


def punto(zone_id: int) -> Punto:
    return _punto(indice(zone_id))


def catalogo() -> list[dict[str, float | int | str]]:
    """Lo que devuelve `GET /zones`."""
    return [
        {"id": zone_id, "name": n, "lat": ZONAS[n][0], "lon": ZONAS[n][1]}
        for zone_id, n in enumerate(NOMBRES)
    ]
