"""Genera la evidencia de Results en los seeds de REPORTE.

    python scripts/results_table.py
    python scripts/results_table.py --turnos 200 --salida results_table.csv

La tabla se escribe fuera de ``courier/`` porque ese directorio es el material
oficial del reto. Conserva exactamente sus columnas y documenta los conjuntos
de TUNEO y REPORTE para que la diapositiva no oculte el holdout.
"""

import argparse
import csv
import statistics
import sys
from collections.abc import Sequence
from functools import partial
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import rutas  # noqa: E402
import seeds  # noqa: E402
import valor  # noqa: E402
from baselines import POLITICAS  # noqa: E402
from contrato import ConfigTurno, Punto  # noqa: E402
from nuez import politica_nuez  # noqa: E402
from oracle import simular_oracle  # noqa: E402
from sim import Politica, Resultado, politica_greedy, simular  # noqa: E402

COLUMNAS = (
    "policy",
    "mean_earnings_mxn",
    "median_earnings_mxn",
    "mean_mxn_per_hr",
    "accept_rate_pct",
    "orders_completed",
    "deadhead_pct_of_km",
    "deadline_misses",
    "safety_violations",
)


def metricas(corridas: Sequence[Resultado], duracion_min: int) -> dict[str, str | int]:
    """Resume corridas homogeneas con las unidades que pide Results."""
    assert corridas, "se necesita al menos un turno"
    decisiones = [decision for corrida in corridas for decision in corrida.decisiones]
    km_con_carga = sum(corrida.km_con_carga for corrida in corridas)
    km_sin_carga = sum(corrida.km_sin_carga for corrida in corridas)
    km_totales = km_con_carga + km_sin_carga
    ganancias = [corrida.ganado for corrida in corridas]
    tasa_aceptacion = (
        sum(d.accion == "aceptar" for d in decisiones) * 100 / len(decisiones)
        if decisiones
        else 0.0
    )

    return {
        "mean_earnings_mxn": f"{statistics.mean(ganancias):.2f}",
        "median_earnings_mxn": f"{statistics.median(ganancias):.2f}",
        "mean_mxn_per_hr": f"{statistics.mean(ganancias) * 60 / duracion_min:.2f}",
        "accept_rate_pct": f"{tasa_aceptacion:.2f}",
        "orders_completed": f"{statistics.mean(corrida.entregas for corrida in corridas):.2f}",
        "deadhead_pct_of_km": f"{km_sin_carga * 100 / km_totales:.2f}" if km_totales else "0.00",
        "deadline_misses": sum(corrida.llego_tarde for corrida in corridas),
        "safety_violations": sum(corrida.violaciones for corrida in corridas),
    }


def configuracion(args: argparse.Namespace, seed: int) -> ConfigTurno:
    """Construye la configuracion comun a todos los rivales."""
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    return ConfigTurno(
        duracion_min=args.duracion,
        ancla=Punto("Tec", *tec),
        margen_min=10,
        vehiculo=args.vehiculo,
        hora_inicio=args.hora_inicio,
        seed=seed,
    )


def generar_tabla(args: argparse.Namespace) -> list[dict[str, str | int]]:
    """Corre los seis agentes en el mismo holdout, incluido el techo offline."""
    tabla = valor.para_turno(args.duracion, args.tabla)
    politica_nuez_tabla = partial(politica_nuez, tabla=tabla)
    reporte = seeds.de_reporte(args.turnos)
    assert not any(seeds.es_de_tuneo(seed) for seed in reporte), "reportando sobre seeds tuneados"

    politicas: dict[str, Politica] = {
        **POLITICAS,
        "GreedyRate": politica_greedy,
        "OurAgent": politica_nuez_tabla,
    }
    resultados = {
        nombre: [simular(configuracion(args, seed), politica) for seed in reporte]
        for nombre, politica in politicas.items()
    }
    resultados["Oracle"] = [
        simular_oracle(configuracion(args, seed), tabla=tabla) for seed in reporte
    ]

    return [
        {"policy": nombre, **metricas(corridas, args.duracion)}
        for nombre, corridas in resultados.items()
    ]


def escribir_tabla(filas: Sequence[dict[str, str | int]], args: argparse.Namespace) -> None:
    """Escribe CSV listo para la diapositiva y con procedencia auditable."""
    reporte = seeds.de_reporte(args.turnos)
    with args.salida.open("w", encoding="utf-8", newline="") as archivo:
        archivo.write("# Results criterion, Courier. Generated; do not hand-edit.\n")
        archivo.write(f"# TUNEO: {seeds.TUNEO.start}-{seeds.TUNEO.stop - 1} (tabla de valor).\n")
        archivo.write(f"# REPORTE: {reporte[0]}-{reporte[-1]} ({args.turnos} turnos, holdout).\n")
        archivo.write(
            f"# Config: {args.duracion} min, {args.hora_inicio}:00, {args.vehiculo}, "
            "ancla Tec, margen 10 min.\n"
        )
        writer = csv.DictWriter(archivo, fieldnames=COLUMNAS)
        writer.writeheader()
        writer.writerows(filas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--turnos", type=int, default=50, help="turnos frescos de REPORTE")
    parser.add_argument("--duracion", type=int, default=120, help="minutos de turno")
    parser.add_argument("--hora-inicio", type=int, choices=range(24), default=14)
    parser.add_argument("--vehiculo", choices=("moto", "car", "bike"), default="moto")
    parser.add_argument("--tabla", type=Path, help="tabla de valor construida offline")
    parser.add_argument("--salida", type=Path, default=RAIZ / "results_table.csv")
    args = parser.parse_args()
    if args.turnos <= 0 or args.duracion <= 0:
        parser.error("el numero de turnos y la duracion deben ser positivos")

    try:
        filas = generar_tabla(args)
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))
    escribir_tabla(filas, args)
    print(f"tabla escrita en {args.salida}")
    for fila in filas:
        print(
            f"  {fila['policy']:<12} ${fila['mean_earnings_mxn']:>7} "
            f"{fila['orders_completed']:>5} entregas  "
            f"{fila['deadhead_pct_of_km']:>5}% vacio"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
