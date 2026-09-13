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

# Algunos streams externos nombran las zonas en vez de compartir nuestro catálogo
# numérico. Estos alias conservan una traducción geográfica explícita, sin cambiar
# los ids estables que Nuez publica en GET /zones.
ALIAS_POR_NOMBRE = {
    "san pedro": "Valle",
    "valle oriente": "Valle",
    "santa catarina": "SantaCatarina",
}

# Convención documentada del practice pack de Courier: 99 representa una zona
# marcada por la noche. La aterrizamos en la zona marcada real de Nuez.
ALIAS_EXTERNOS = {99: "Escobedo"}


def resolver(zone_id: int, zone_name: str | None = None) -> int:
    """Traduce una zona externa al id local sin alterar el catálogo público.

    Los IDs publicados por GET /zones siempre conservan su significado. Si llega
    un ID externo que no existe en ese catálogo, su nombre es el respaldo para
    traducirlo. La excepción es la convención explícita de la zona 99 del
    practice pack.
    """
    if zone_id in ALIAS_EXTERNOS:
        return ID_POR_NOMBRE[ALIAS_EXTERNOS[zone_id]]
    if 0 <= zone_id < len(NOMBRES):
        return zone_id
    if zone_name:
        normalized = " ".join(zone_name.casefold().split())
        local_name = ALIAS_POR_NOMBRE.get(normalized, zone_name)
        if local_name in ID_POR_NOMBRE:
            return ID_POR_NOMBRE[local_name]
    nombre(zone_id)  # valida el id y conserva el error claro del catálogo
    return zone_id


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
