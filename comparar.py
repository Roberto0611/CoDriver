"""EL NUMERO: Nuez contra el baseline, en turnos que nunca vio.

    python comparar.py [n_turnos]

La tabla de valor se construyo con los seeds 0-299. La comparacion corre en los
seeds 1000+, frescos. Si no fuera asi, estariamos calificandonos con el examen
que ya vimos.
"""

import statistics
import sys

import rutas
from contrato import ConfigTurno, Punto
from nuez import politica_nuez
from sim import politica_greedy, simular

SEED_BASE = 1000   # fuera del rango con el que se construyo V.json
N = int(sys.argv[1]) if len(sys.argv) > 1 else 50


def main():
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    base = dict(duracion_min=120, ancla=Punto("Tec", *tec), margen_min=10,
                vehiculo="moto", hora_inicio=14)

    filas = []
    for k in range(N):
        cfg = ConfigTurno(**base, seed=SEED_BASE + k)
        g = simular(cfg, politica_greedy)
        n = simular(cfg, politica_nuez)
        filas.append((g, n))

    gre = [g.ganado for g, _ in filas]
    nue = [n.ganado for _, n in filas]
    delta = (statistics.mean(nue) / statistics.mean(gre) - 1) * 100
    gana = sum(1 for g, n in filas if n.ganado > g.ganado)

    print(f"{N} turnos frescos (seeds {SEED_BASE}-{SEED_BASE + N - 1})\n")
    print(f"  {'':<18} {'greedy':>10} {'NUEZ':>10}")
    print(f"  {'ganancia media':<18} ${statistics.mean(gre):>9.0f} ${statistics.mean(nue):>9.0f}")
    print(f"  {'ganancia mediana':<18} ${statistics.median(gre):>9.0f} ${statistics.median(nue):>9.0f}")
    print(f"  {'entregas':<18} {statistics.mean([g.entregas for g, _ in filas]):>10.1f} "
          f"{statistics.mean([n.entregas for _, n in filas]):>10.1f}")
    print(f"  {'llegaron tarde':<18} {sum(g.llego_tarde for g, _ in filas):>10} "
          f"{sum(n.llego_tarde for _, n in filas):>10}")
    print(f"  {'% turno ocupado':<18} {statistics.mean([g.minutos_ocupado for g, _ in filas]) / 1.2:>9.0f}% "
          f"{statistics.mean([n.minutos_ocupado for _, n in filas]) / 1.2:>9.0f}%")

    print(f"\n  DELTA: {delta:+.1f}%   ganó en {gana}/{N} turnos")

    if delta >= 20:
        print("  -> hay hackathon. De aqui en adelante todo es presentacion.")
    elif delta >= 8:
        print("  -> sirve, pero hay que exprimir el motor antes de adornar nada.")
    else:
        print("  -> insuficiente. Revisar la politica ANTES de construir nada encima.")


if __name__ == "__main__":
    main()
