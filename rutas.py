"""A2: tiempos de viaje reales = matriz de flujo libre x factor de trafico por hora.

Esta es la unica puerta por donde el simulador y el motor preguntan "cuanto tardo".
No toca el grafo ni la red: lee matriz.pkl (183 KB) y multiplica.

    >>> import rutas
    >>> rutas.minutos(0, 100, hora=18)   # hora pico
"""

import pickle
from functools import cache
from pathlib import Path

from mundo import factor_trafico

_datos = pickle.loads((Path(__file__).parent / "data" / "matriz.pkl").read_bytes())

PUNTOS = _datos["puntos"]  # [(zona, node_id, lat, lon), ...]
_M = _datos["matriz"]  # minutos de flujo libre, float32

ZONA_DE = [z for z, _, _, _ in PUNTOS]
COORD_DE = [(lat, lon) for _, _, lat, lon in PUNTOS]


def minutos(i: int, j: int, hora: int) -> float:
    """Minutos reales del punto i al j a esa hora del dia."""
    return float(_M[i, j]) * factor_trafico(hora)


def km(i: int, j: int) -> float:
    """Distancia aproximada, SIN trafico.

    El trafico te hace tardar mas, no recorrer mas kilometros. Si esto se
    calculara desde minutos(i, j, hora) la gasolina y el pago se inflarian
    solos en hora pico.
    """
    return float(_M[i, j]) / 60 * 30  # ~30 km/h promedio a flujo libre


@cache
def puntos_de(zona: str) -> tuple[int, ...]:
    """Indices de los puntos de interes que caen en una zona."""
    return tuple(i for i, z in enumerate(ZONA_DE) if z == zona)


def indice_mas_cercano(lat: float, lon: float) -> int:
    """El punto de interes mas cercano a una coordenada. Para resolver el ancla."""
    return min(
        range(len(COORD_DE)),
        key=lambda i: (COORD_DE[i][0] - lat) ** 2 + (COORD_DE[i][1] - lon) ** 2,
    )


def demo():
    import statistics

    centro = puntos_de("Centro")[0]
    valle = puntos_de("Valle")[0]

    libre = minutos(centro, valle, hora=3)
    pico = minutos(centro, valle, hora=18)

    assert pico > libre * 2, "la hora pico debe doler"
    assert minutos(centro, centro, 12) == 0.0, "de un punto a si mismo son 0 min"
    assert len(puntos_de("Tec")) == 15

    # El regreso no siempre tarda lo mismo que la ida: hay calles de un sentido.
    ida, vuelta = minutos(centro, valle, 12), minutos(valle, centro, 12)
    assert ida > 0 and vuelta > 0

    print(f"Centro -> Valle   3 AM: {libre:5.1f} min")
    print(f"Centro -> Valle  18 h : {pico:5.1f} min   <- hora pico")
    print(f"ida {ida:.1f} / vuelta {vuelta:.1f} min a las 12 h")

    todos = [minutos(i, j, 18) for i in range(0, 210, 20) for j in range(0, 210, 20) if i != j]
    print(f"\nmediana entre puntos en hora pico: {statistics.median(todos):.1f} min")
    print("OK")


if __name__ == "__main__":
    demo()
