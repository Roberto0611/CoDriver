"""B5: la tabla de valor. Cuanto rinden normalmente los minutos que te quedan.

    python valor.py          construye V.json corriendo el baseline 300 veces
    import valor             valor.de(45) -> lo que rinden 45 minutos

No hay modelo ni entrenamiento: se corre el simulador muchas veces, se anota
cuanto faltaba por ganar en cada momento, y se promedia. En la literatura esto
es evaluacion Monte Carlo de la politica (Sutton & Barto, cap. 5), en forma
tabular, que es la que se puede auditar.
"""

import argparse
import json
import statistics
from bisect import bisect_left
from functools import cache
from pathlib import Path

from contrato import Vehiculo

ARCHIVO = Path(__file__).parent / "V.json"
ARCHIVO_LARGO = ARCHIVO.with_name("V_480.json")
ARCHIVO_510 = ARCHIVO.with_name("V_510.json")
CUBETA = 10  # minutos por cubeta


def construir(
    n: int = 300,
    duracion: int = 120,
    hora_inicio: int = 14,
    politica=None,
    vehiculo: Vehiculo = "moto",
) -> dict[int, float]:
    """Corre una politica n veces y promedia la ganancia futura por cubeta.

    Con politica=None usa el baseline. Las muestras siempre vienen de TUNEO.
    Incluye cero y el horizonte completo aunque no sean multiplos de CUBETA.
    """
    import rutas
    import seeds
    from contrato import ConfigTurno, Punto
    from sim import politica_greedy, simular

    if not 1 <= n <= len(seeds.TUNEO):
        raise ValueError(f"n debe estar entre 1 y {len(seeds.TUNEO)} (solo TUNEO)")
    if duracion <= 0:
        raise ValueError("la duracion debe ser positiva")

    politica = politica or politica_greedy

    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    muestras: dict[int, list[float]] = {}

    for seed in seeds.TUNEO[:n]:
        cfg = ConfigTurno(
            duracion_min=duracion,
            ancla=Punto("Tec", *tec),
            seed=seed,
            hora_inicio=hora_inicio,
            vehiculo=vehiculo,
        )
        res = simular(cfg, politica)

        for restante in sorted({*range(0, duracion + 1, CUBETA), duracion}):
            t = duracion - restante
            futuro = sum(monto for minuto, monto in res.cobros if minuto >= t)
            muestras.setdefault(restante, []).append(futuro)

    # Monte Carlo puede invertir dos cubetas vecinas por ruido (p. ej. 120 min
    # medidos $143 y 110 min $145). Más tiempo no puede valer menos: a esa ruta
    # se le puede dedicar el mismo plan y esperar. Proyectamos la media a una
    # curva monótona antes de que Nuez calcule un costo de oportunidad negativo.
    valores: dict[int, float] = {}
    anterior = 0.0
    for restante, muestras_de_cubeta in sorted(muestras.items()):
        anterior = max(anterior, round(statistics.mean(muestras_de_cubeta), 2))
        valores[restante] = anterior
    return valores


@cache
def cargar(archivo: Path = ARCHIVO) -> dict[int, float]:
    """Lee una vez de disco. Acepta V.json historico y tablas con metadatos."""
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    tabla = {int(k): float(v) for k, v in datos.get("valores", datos).items()}
    llaves = sorted(tabla)
    if len(llaves) < 2 or llaves[0] != 0 or tabla[0] != 0:
        raise ValueError("la tabla debe empezar en cero y cubrir un horizonte positivo")
    if any(tabla[b] < tabla[a] for a, b in zip(llaves, llaves[1:], strict=False)):
        raise ValueError("la tabla debe ser monotona")
    return tabla


def para_turno(duracion: int, archivo: Path | None = None) -> dict[int, float]:
    """Conserva la calibracion corta; usa una tabla que cubra todo el turno.

    Son estimaciones agregadas (moto, inicio 14 h), no tablas por hora/zona.
    Para otra calibracion se puede pasar una tabla construida offline.
    """
    if duracion <= 0:
        raise ValueError("la duracion debe ser positiva")
    if archivo is None:
        if duracion <= max(cargar()):
            archivo = ARCHIVO
        elif duracion <= max(cargar(ARCHIVO_LARGO)):
            archivo = ARCHIVO_LARGO
        else:
            archivo = ARCHIVO_510
    tabla = cargar(archivo)
    if max(tabla) < duracion:
        raise ValueError(
            f"la tabla cubre {max(tabla)} min, el turno pide {duracion}; "
            "construye una con python valor.py --duracion y pasala con --tabla"
        )
    return tabla


def de(minutos_restantes: float, tabla: dict[int, float] | None = None) -> float:
    """Interpola entre puntos reales; nunca recorta silenciosamente el horizonte."""
    V = cargar() if tabla is None else tabla
    m = max(0.0, minutos_restantes)
    llaves = sorted(V)
    if m > llaves[-1]:
        raise ValueError(f"{m} minutos exceden el horizonte de la tabla ({llaves[-1]})")
    indice = bisect_left(llaves, m)
    alto = llaves[indice]
    if alto == m:
        return V[alto]
    bajo = llaves[indice - 1]
    peso = (m - bajo) / (alto - bajo)
    return V[bajo] + (V[alto] - V[bajo]) * peso


def precio_del_tiempo(
    restante: float, minutos: float, tabla: dict[int, float] | None = None
) -> float:
    """Cuanto vale gastar `minutos` cuando te quedan `restante`. El costo de oportunidad."""
    return de(restante, tabla) - de(restante - minutos, tabla)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duracion", type=int, default=120, help="minutos de turno")
    parser.add_argument("--hora-inicio", type=int, choices=range(24), default=14)
    parser.add_argument("--vehiculo", choices=("moto", "car", "bike"), default="moto")
    parser.add_argument("--turnos", type=int, default=300)
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()
    V = construir(args.turnos, args.duracion, args.hora_inicio, vehiculo=args.vehiculo)
    historica = (args.duracion, args.hora_inicio, args.vehiculo) == (120, 14, "moto")
    nombre = f"V_{args.duracion}_{args.hora_inicio}_{args.vehiculo}.json"
    if (args.duracion, args.hora_inicio, args.vehiculo) == (480, 14, "moto"):
        nombre = ARCHIVO_LARGO.name
    if (args.duracion, args.hora_inicio, args.vehiculo) == (510, 14, "moto"):
        nombre = ARCHIVO_510.name
    archivo = args.salida or (ARCHIVO if historica else ARCHIVO.with_name(nombre))
    datos = {
        "calibracion": {
            "duracion_min": args.duracion,
            "hora_inicio": args.hora_inicio,
            "vehiculo": args.vehiculo,
            "seeds": {"conjunto": "TUNEO", "inicio": 0, "cantidad": args.turnos},
        },
        "valores": V,
    }
    archivo.write_text(json.dumps(V if historica else datos, indent=1) + "\n", encoding="utf-8")

    print(f"tabla de valor  ({len(V)} cubetas de {CUBETA} min)\n")
    print(f"  {'te quedan':>10}  {'rinden':>8}   {'$/min a ese ritmo':>18}")
    for restante, pesos in sorted(V.items(), reverse=True):
        ritmo = f"${pesos / restante:.2f}/min" if restante else ""
        print(f"  {restante:>7} min  ${pesos:>7.0f}   {ritmo:>18}")

    assert V[0] == 0, "con cero minutos no se gana nada"
    print(f"\n  {archivo} escrito con {args.turnos} seeds de TUNEO.")


if __name__ == "__main__":
    main()
