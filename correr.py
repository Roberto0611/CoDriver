"""Corre turnos y reporta. Es la regla con la que se mide todo lo demas.

python correr.py            un turno, con el detalle de las decisiones
python correr.py 50         50 seeds, estadisticas del baseline
"""

import statistics
import sys
import time

import rutas
from contrato import ConfigTurno, Punto
from sim import generar_ofertas, politica_greedy, simular

# El estudiante tipico: dos horas entre clases, ancla en el Tec, moto, 2 de la tarde.
TEC = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
CFG = ConfigTurno(
    duracion_min=120,
    ancla=Punto("Tec", *TEC),
    margen_min=10,
    vehiculo="moto",
    seed=1,
    hora_inicio=14,
)


def un_turno(seed: int):
    cfg = ConfigTurno(**{**CFG.__dict__, "seed": seed})
    res = simular(cfg, politica_greedy)

    print(f"turno seed={seed}  {cfg.duracion_min} min desde las {cfg.hora_inicio}:00\n")
    for d in res.decisiones[:14]:
        marca = "OK " if d.accion == "aceptar" else "   "
        motivo = d.restriccion or ""
        print(
            f"  t={d.t:>3}  {marca} {d.oferta_id}  "
            f"${d.terminos['pago_neto']:>6.1f}  {d.terminos['minutos']:>5.1f} min"
            f"  ${d.terminos['por_minuto']:>5.2f}/min  {motivo:<20} {d.razon}"
        )
    if len(res.decisiones) > 14:
        print(f"  ... {len(res.decisiones) - 14} decisiones mas")

    print(f"\n  ofertas: {len(res.ofertas)}   entregas: {res.entregas}   rechazos: {res.rechazos}")
    print(
        f"  ganado: ${res.ganado:.0f}   ocupado: {res.minutos_ocupado}/{cfg.duracion_min} min"
        f"   {'LLEGO TARDE A CLASE' if res.llego_tarde else 'llego a tiempo'}"
    )


def muchos(n: int):
    t0 = time.perf_counter()
    ganancias, tardes, entregas = [], 0, []
    for seed in range(n):
        cfg = ConfigTurno(**{**CFG.__dict__, "seed": seed})
        res = simular(cfg, politica_greedy)
        ganancias.append(res.ganado)
        entregas.append(res.entregas)
        tardes += res.llego_tarde
    dt = time.perf_counter() - t0

    print(f"BASELINE GREEDY sobre {n} turnos de {CFG.duracion_min} min\n")
    print(f"  ganancia mediana : ${statistics.median(ganancias):.0f}")
    print(
        f"  ganancia media   : ${statistics.mean(ganancias):.0f}"
        f"  (min ${min(ganancias):.0f}, max ${max(ganancias):.0f})"
    )
    print(f"  entregas mediana : {statistics.median(entregas):.0f}")
    print(f"  llegaron tarde   : {tardes}/{n}")
    print(f"\n  {dt:.2f} s en total, {dt / n * 1000:.1f} ms por turno")
    print(f"  -> las 300 corridas de la tabla de valor tardarian {dt / n * 300:.1f} s")

    # El seed tiene que ser reproducible o el boton del juez no significa nada.
    assert [o.id for o in generar_ofertas(CFG)] == [o.id for o in generar_ofertas(CFG)]
    print("\n  OK: mismo seed = mismo stream de ofertas")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        muchos(int(sys.argv[1]))
    else:
        un_turno(CFG.seed)
