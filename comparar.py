"""EL NUMERO: Nuez contra el baseline, en turnos que nunca vio.

    python comparar.py [n_turnos]

Los dos conjuntos estan en seeds.py y son disjuntos: la tabla de valor y los
barridos de parametros viven en TUNEO, y este numero sale de REPORTE, seeds que
el motor nunca vio. Si no fuera asi estariamos calificandonos con el examen que
ya vimos, y el protocolo topa Results en 3 por eso mismo.
"""

import argparse
import statistics
from functools import partial
from pathlib import Path

import rutas
import seeds
import valor
from baselines import POLITICAS
from contrato import ConfigTurno, Punto
from nuez import politica_nuez
from oracle import simular_oracle
from sim import Politica, politica_greedy, simular


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n_turnos", type=int, nargs="?", default=50)
    parser.add_argument("--duracion", type=int, default=120, help="minutos de turno")
    parser.add_argument("--hora-inicio", type=int, choices=range(24), default=14)
    parser.add_argument("--vehiculo", choices=("moto", "car", "bike"), default="moto")
    parser.add_argument("--tabla", type=Path, help="tabla de valor construida offline")
    parser.add_argument(
        "--rivales",
        action="store_true",
        help="mide cinco agentes online y el Oracle offline en los mismos turnos",
    )
    args = parser.parse_args()
    if args.n_turnos <= 0 or args.duracion <= 0:
        parser.error("el numero de turnos y la duracion deben ser positivos")
    try:
        tabla = valor.para_turno(args.duracion, args.tabla)
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))
    politica = partial(politica_nuez, tabla=tabla)
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    ancla = Punto("Tec", *tec)

    reporte = seeds.de_reporte(args.n_turnos)

    def configuracion(semilla: int) -> ConfigTurno:
        return ConfigTurno(
            duracion_min=args.duracion,
            ancla=ancla,
            margen_min=10,
            vehiculo=args.vehiculo,
            hora_inicio=args.hora_inicio,
            seed=semilla,
        )

    if args.rivales:
        politicas: dict[str, Politica] = {
            **POLITICAS,
            "GreedyRate": politica_greedy,
            "OurAgent": politica,
        }
        resultados = {
            nombre: [simular(configuracion(semilla), rival) for semilla in reporte]
            for nombre, rival in politicas.items()
        }
        resultados["Oracle"] = [
            simular_oracle(configuracion(semilla), tabla=tabla) for semilla in reporte
        ]
        assert not any(seeds.es_de_tuneo(s) for s in reporte), "reportando sobre seeds tuneados"
        print(f"{args.n_turnos} turnos frescos, seeds de REPORTE {reporte[0]}-{reporte[-1]}")
        print(f"duracion: {args.duracion} min; inicio: {args.hora_inicio}:00; {args.vehiculo}\n")
        print(f"  {'politica':<16} {'ganancia media':>16} {'entregas':>10} {'tarde':>8}")
        for nombre, corridas in resultados.items():
            print(
                f"  {nombre:<16} ${statistics.mean(r.ganado for r in corridas):>14.0f} "
                f"{statistics.mean(r.entregas for r in corridas):>10.1f} "
                f"{sum(r.llego_tarde for r in corridas):>8}"
            )
        return

    filas = []
    for semilla in reporte:
        cfg = configuracion(semilla)
        g = simular(cfg, politica_greedy)
        n = simular(cfg, politica)
        filas.append((g, n))

    gre = [g.ganado for g, _ in filas]
    nue = [n.ganado for _, n in filas]
    media_g = statistics.mean(gre)
    delta = (statistics.mean(nue) / media_g - 1) * 100 if media_g else None
    gana = sum(1 for g, n in filas if n.ganado > g.ganado)

    assert not any(seeds.es_de_tuneo(s) for s in reporte), "reportando sobre seeds tuneados"
    print(f"{args.n_turnos} turnos frescos, seeds de REPORTE {reporte[0]}-{reporte[-1]}")
    print(f"duracion: {args.duracion} min; inicio: {args.hora_inicio}:00; {args.vehiculo}")
    print(f"tabla: {args.tabla or ('V.json' if max(tabla) == 120 else 'V_480.json')}")
    print(f"la tabla de valor se tuneo en {seeds.TUNEO.start}-{seeds.TUNEO.stop - 1}, disjuntos\n")
    print(f"  {'':<18} {'greedy':>10} {'NUEZ':>10}")
    print(f"  {'ganancia media':<18} ${statistics.mean(gre):>9.0f} ${statistics.mean(nue):>9.0f}")
    med_g, med_n = statistics.median(gre), statistics.median(nue)
    print(f"  {'ganancia mediana':<18} ${med_g:>9.0f} ${med_n:>9.0f}")
    print(
        f"  {'entregas':<18} {statistics.mean([g.entregas for g, _ in filas]):>10.1f} "
        f"{statistics.mean([n.entregas for _, n in filas]):>10.1f}"
    )
    print(
        f"  {'llegaron tarde':<18} {sum(g.llego_tarde for g, _ in filas):>10} "
        f"{sum(n.llego_tarde for _, n in filas):>10}"
    )
    ocup_g = statistics.mean([g.minutos_ocupado for g, _ in filas]) * 100 / args.duracion
    ocup_n = statistics.mean([n.minutos_ocupado for _, n in filas]) * 100 / args.duracion
    print(f"  {'% turno ocupado':<18} {ocup_g:>9.0f}% {ocup_n:>9.0f}%")

    porcentaje = f"{delta:+.1f}%" if delta is not None else "N/A (baseline sin ingresos)"
    print(f"\n  DELTA: {porcentaje}   ganó en {gana}/{args.n_turnos} turnos")


if __name__ == "__main__":
    main()
