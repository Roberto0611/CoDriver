"""Los dos conjuntos de seeds, disjuntos y con nombre.

El protocolo es explicito: "tuning seeds and reporting seeds must be disjoint,
and you must say which is which. If your reported numbers come from the seeds
you tuned on, Results caps at 3". Este archivo ES el "cual es cual".

  TUNEO    tabla de valor, barridos de parametros, calibracion del mundo.
  REPORTE  el unico numero que se dice en voz alta. Nadie tunea aqui, nunca.

El rango de tuneo es ancho a proposito: sobra espacio para barrer sin acercarse
al de reporte. Si algun dia hace falta mas, se crece hacia abajo, no hacia arriba.
"""

TUNEO = range(0, 2000)
REPORTE = range(2000, 100000)

assert TUNEO.stop <= REPORTE.start, "los conjuntos se traslapan: el numero seria mentira"


def de_reporte(n: int) -> list[int]:
    """Los primeros n seeds de reporte. El unico modo legitimo de sacarlos."""
    return [REPORTE.start + k for k in range(n)]


def es_de_tuneo(seed: int) -> bool:
    return seed in TUNEO
