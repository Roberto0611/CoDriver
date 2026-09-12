"""B5: la tabla de valor. Cuanto rinden normalmente los minutos que te quedan.

    python valor.py          construye V.json corriendo el baseline 300 veces
    import valor             valor.de(45) -> lo que rinden 45 minutos

No hay modelo ni entrenamiento: se corre el simulador muchas veces, se anota
cuanto faltaba por ganar en cada momento, y se promedia. En la literatura esto
es evaluacion Monte Carlo de la politica (Sutton & Barto, cap. 5), en forma
tabular, que es la que se puede auditar.
"""

import json
import statistics
from pathlib import Path

ARCHIVO = Path(__file__).parent / "V.json"
CUBETA = 10   # minutos por cubeta: 120 min -> 12 cubetas


def construir(n: int = 300, duracion: int = 120, hora_inicio: int = 14) -> dict[int, float]:
    """Corre el baseline n veces y promedia la ganancia futura por cubeta."""
    import rutas
    from contrato import ConfigTurno, Punto
    from sim import politica_greedy, simular

    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    muestras: dict[int, list[float]] = {}

    for seed in range(n):
        cfg = ConfigTurno(duracion_min=duracion, ancla=Punto("Tec", *tec),
                          seed=seed, hora_inicio=hora_inicio)
        res = simular(cfg, politica_greedy)

        for t in range(0, duracion + 1, CUBETA):
            restante = duracion - t
            futuro = sum(monto for minuto, monto in res.cobros if minuto >= t)
            muestras.setdefault(restante, []).append(futuro)

    return {k: round(statistics.mean(v), 2) for k, v in sorted(muestras.items())}


_V: dict[int, float] | None = None


def cargar() -> dict[int, float]:
    global _V
    if _V is None:
        _V = {int(k): v for k, v in json.loads(ARCHIVO.read_text()).items()}
    return _V


def de(minutos_restantes: float) -> float:
    """Lo que rinden esos minutos. Interpola entre cubetas."""
    V = cargar()
    m = max(0.0, min(minutos_restantes, max(V)))
    bajo = int(m // CUBETA) * CUBETA
    alto = min(bajo + CUBETA, max(V))
    if alto == bajo:
        return V[bajo]
    peso = (m - bajo) / (alto - bajo)
    return V[bajo] + (V[alto] - V[bajo]) * peso


def precio_del_tiempo(restante: float, minutos: float) -> float:
    """Cuanto vale gastar `minutos` cuando te quedan `restante`. El costo de oportunidad."""
    return de(restante) - de(restante - minutos)


def main():
    V = construir()
    ARCHIVO.write_text(json.dumps(V, indent=1))

    print(f"tabla de valor  ({len(V)} cubetas de {CUBETA} min)\n")
    print(f"  {'te quedan':>10}  {'rinden':>8}   {'$/min a ese ritmo':>18}")
    for restante, pesos in sorted(V.items(), reverse=True):
        ritmo = f"${pesos / restante:.2f}/min" if restante else ""
        print(f"  {restante:>7} min  ${pesos:>7.0f}   {ritmo:>18}")

    assert V[0] == 0, "con cero minutos no se gana nada"
    assert V[max(V)] > V[60] > V[20], "menos tiempo tiene que valer menos"
    print(f"\n  {ARCHIVO.name} escrito.")
    print(f"  ejemplo: gastar 25 min cuando quedan 90 cuesta "
          f"${precio_del_tiempo(90, 25):.0f}")


if __name__ == "__main__":
    main()
