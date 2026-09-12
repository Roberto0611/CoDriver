"""EL NUMERO: Nuez contra el baseline, en turnos que nunca vio.

    python comparar.py [n_turnos]

Los dos conjuntos estan en seeds.py y son disjuntos: la tabla de valor y los
barridos de parametros viven en TUNEO, y este numero sale de REPORTE, seeds que
el motor nunca vio. Si no fuera asi estariamos calificandonos con el examen que
ya vimos, y el protocolo topa Results en 3 por eso mismo.
"""

import statistics
import sys

import rutas
import seeds
from contrato import ConfigTurno, Punto
from nuez import politica_nuez
from sim import politica_greedy, simular

N = int(sys.argv[1]) if len(sys.argv) > 1 else 50


def main():
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    ancla = Punto("Tec", *tec)

    reporte = seeds.de_reporte(N)
    filas = []
    for semilla in reporte:
        cfg = ConfigTurno(
            duracion_min=120,
            ancla=ancla,
            margen_min=10,
            vehiculo="moto",
            hora_inicio=14,
            seed=semilla,
        )
        g = simular(cfg, politica_greedy)
        n = simular(cfg, politica_nuez)
        filas.append((g, n))

    gre = [g.ganado for g, _ in filas]
    nue = [n.ganado for _, n in filas]
    delta = (statistics.mean(nue) / statistics.mean(gre) - 1) * 100
    gana = sum(1 for g, n in filas if n.ganado > g.ganado)

    assert not any(seeds.es_de_tuneo(s) for s in reporte), "reportando sobre seeds tuneados"
    print(f"{N} turnos frescos, seeds de REPORTE {reporte[0]}-{reporte[-1]}")
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
    ocup_g = statistics.mean([g.minutos_ocupado for g, _ in filas]) / 1.2
    ocup_n = statistics.mean([n.minutos_ocupado for _, n in filas]) / 1.2
    print(f"  {'% turno ocupado':<18} {ocup_g:>9.0f}% {ocup_n:>9.0f}%")

    print(f"\n  DELTA: {delta:+.1f}%   ganó en {gana}/{N} turnos")

    if delta >= 20:
        print("  -> hay hackathon. De aqui en adelante todo es presentacion.")
    elif delta >= 8:
        print("  -> sirve, pero hay que exprimir el motor antes de adornar nada.")
    else:
        print("  -> insuficiente. Revisar la politica ANTES de construir nada encima.")


if __name__ == "__main__":
    main()
