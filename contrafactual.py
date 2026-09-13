"""El reporte contrafactual: ¿y si Nuez hubiera tomado lo que salto?

    python contrafactual.py 2000        resumen legible del turno grabado de ese seed

No se adivina: se vuelve a correr el MISMO turno. El stream de ofertas depende
solo de `cfg.seed` y se escribe completo antes de que nadie decida, asi que la
corrida forzada ve exactamente los mismos pings que la real.

Un salto a la vez. Por cada pedido que Nuez salto POR DINERO (`reservation_wage`)
se corre el turno otra vez con Nuez identica, salvo que ese pedido, en ese
momento, lo acepta. delta = ganado(forzado) - ganado(real).

Con `disrupciones` (los shocks que el juez metio en /live) las corridas llevan los
mismos shocks en los mismos minutos. Inyectar a media jornada da la misma historia
que declararlos desde el inicio (ver reloj.py), asi que el "real" es justo el turno
que se vio en pantalla. Sin ellas es el turno grabado de siempre.

Dos cosas que este reporte NO hace, a proposito:
  1. No simula los saltos por restriccion dura. No se venden, asi que no tienen
     precio que reportar: se cuentan y ya. La capacidad va aparte de la seguridad:
     un vehiculo lleno es un limite fisico, no un riesgo para el repartidor.
  2. No suma los deltas. Cada uno es una corrida aparte; tomar un pedido cambia
     la ruta y los que venian despues. "Si los hubiera tomado todos" es otra
     corrida que nadie hizo, y sumarlos seria inventarla.
"""

import math
import sys
from collections import Counter
from dataclasses import replace
from typing import Any, get_args

from contrato import ConfigTurno, Decision, EstadoRepartidor, Oferta, Restriccion
from estrategia import BASE
from nuez import politica_nuez
from shocks import Shock
from sim import Parada, Politica, Resultado, simular

DINERO = "reservation_wage"
CAPACIDAD = "vehicle_capacity"
# Las cinco duras salen del contrato, no de una lista copiada aqui: si mañana
# aparece una sexta, el reporte la cuenta sin que nadie se acuerde de este archivo.
DURAS: tuple[str, ...] = tuple(r for r in get_args(Restriccion) if r != DINERO)
SEGURIDAD: tuple[str, ...] = tuple(r for r in DURAS if r != CAPACIDAD)
TOP = 3


def forzar(objetivo: str, politica: Politica = politica_nuez) -> Politica:
    """La misma politica, salvo que el pedido `objetivo` no se rechaza por dinero.

    Se logra quitando el piso de dinero SOLO para ese pedido: `margen_mxn = -inf`
    hace que `neto < precio + margen` nunca sea cierto. Todo lo demas es la
    politica de siempre: el mismo ruteo (`ruteo.costo_marginal`) y la misma puerta
    de seguridad (`seguridad.revisar`), que en `politica_nuez` se revisa ANTES que
    el dinero. Si una restriccion dura bloquea, el pedido se sigue saltando.

    No pasa por `estrategia.sanear` porque esto no es un modelo proponiendo
    perillas: es un analisis offline que nunca toca `/decide`.
    """

    def forzada(
        o: Oferta, est: EstadoRepartidor, ruta: list[Parada], cfg: ConfigTurno, **kw: Any
    ) -> tuple[list[Parada] | None, Decision]:
        if o.id == objetivo:
            base = kw.get("estrategia", BASE)
            kw = {**kw, "estrategia": replace(base, margen_mxn=-math.inf)}
        return politica(o, est, ruta, cfg, **kw)

    return forzada


def con_pedido(cfg: ConfigTurno, objetivo: str, disrupciones: tuple[Shock, ...] = ()) -> Resultado:
    """El mismo turno, con Nuez aceptando `objetivo` si la seguridad lo deja."""
    return simular(cfg, forzar(objetivo), disrupciones)


def _decision_de(res: Resultado, oferta_id: str) -> Decision:
    return next(d for d in res.decisiones if d.oferta_id == oferta_id)


def reporte(
    cfg: ConfigTurno, top: int = TOP, disrupciones: tuple[Shock, ...] = ()
) -> dict[str, Any]:
    """Resumen JSON-serializable del turno de Nuez y de sus saltos por dinero."""
    real = simular(cfg, politica_nuez, disrupciones)
    saltos = [d for d in real.decisiones if d.accion == "saltar"]

    duras_cuenta: Counter[str] = Counter()
    evaluados: list[dict[str, Any]] = []
    infactibles = 0
    for d in saltos:
        if d.restriccion != DINERO:
            if d.restriccion not in DURAS:
                raise ValueError(f"{d.oferta_id}: salto sin restriccion reconocida")
            duras_cuenta[d.restriccion] += 1
            continue

        forzado = con_pedido(cfg, d.oferta_id, disrupciones)
        if _decision_de(forzado, d.oferta_id).accion != "aceptar":
            # Una restriccion dura lo bloqueo al forzarlo: se cuenta aparte, sin precio.
            infactibles += 1
            continue
        evaluados.append(
            {
                "order_id": d.oferta_id,
                "minute": d.t,
                "net_pay_mxn": d.terminos.get("pago_neto"),
                "minutes": d.terminos.get("minutos"),
                "time_value_mxn": d.terminos.get("precio_tiempo"),
                "delta_mxn": round(forzado.ganado - real.ganado, 2),
                "forced_earned_mxn": forzado.ganado,
                "forced_deliveries": forzado.entregas,
                "late": forzado.llego_tarde,
                "cancelled": forzado.cancelados,
            }
        )

    deltas = [e["delta_mxn"] for e in evaluados]
    ganan = [x for x in deltas if x > 0]
    pierden = [x for x in deltas if x < 0]
    # Los mas grandes en valor absoluto primero; empate, el que paso antes.
    orden = sorted(evaluados, key=lambda e: (-abs(e["delta_mxn"]), e["minute"]))

    return {
        "seed": cfg.seed,
        "policy": "nuez",
        "actual": {
            "earned_mxn": real.ganado,
            "deliveries": real.entregas,
            "offers": len(real.ofertas),
            "late": real.llego_tarde,
        },
        "skipped_total": len(saltos),
        "money_skips": {
            "count": len(evaluados) + infactibles,
            "evaluated": len(evaluados),
            "infeasible": infactibles,
            "would_earn_less": len(pierden),
            "would_earn_more": len(ganan),
            "no_change": len(deltas) - len(ganan) - len(pierden),
            "late_runs": sum(1 for e in evaluados if e["late"]),
            "cancelled_runs": sum(1 for e in evaluados if e["cancelled"]),
            # Promedio y extremos de corridas INDEPENDIENTES. No hay "total": no suman.
            "avg_delta_mxn": round(sum(deltas) / len(deltas), 2) if deltas else None,
            "max_gain_mxn": max(ganan) if ganan else None,
            "max_loss_mxn": min(pierden) if pierden else None,
        },
        "safety_skips": {r: duras_cuenta[r] for r in SEGURIDAD},
        "capacity_skips": duras_cuenta[CAPACIDAD],
        "top": orden[:top],
        "note": "Each skipped order is re-simulated on its own. Deltas are not additive.",
    }


def _texto(rep: dict[str, Any]) -> str:
    """El resumen para la terminal. Pesos sin centavos, igual que el front."""
    dinero = rep["money_skips"]
    lineas = [
        f"seed {rep['seed']}: Nuez gano ${rep['actual']['earned_mxn']:.2f} "
        f"con {rep['actual']['deliveries']} entregas, salto {rep['skipped_total']} "
        f"de {rep['actual']['offers']} ofertas",
        "",
        f"por dinero: {dinero['count']} saltos, {dinero['evaluated']} re-simulados, "
        f"{dinero['infeasible']} bloqueados por una restriccion dura al forzarlos",
        f"  tomando UNO solo: {dinero['would_earn_less']} ganan menos, "
        f"{dinero['would_earn_more']} ganan mas, {dinero['no_change']} igual",
    ]
    if dinero["max_gain_mxn"] is not None:
        lineas.append(f"  la mejor: +${dinero['max_gain_mxn']:.2f}")
    if dinero["max_loss_mxn"] is not None:
        lineas.append(f"  la peor:  -${-dinero['max_loss_mxn']:.2f}")
    for e in rep["top"]:
        tarde = "  LLEGA TARDE" if e["late"] else ""
        lineas.append(
            f"    {e['order_id']} min {e['minute']:>3}: paga ${e['net_pay_mxn']:.0f} por "
            f"{e['minutes']:.0f} min (valen ${e['time_value_mxn']:.0f}) -> "
            f"{e['delta_mxn']:+.2f}{tarde}"
        )
    bloqueos = ", ".join(f"{r} {n}" for r, n in rep["safety_skips"].items() if n)
    lineas += ["", f"por seguridad, sin precio: {bloqueos or 'ninguno'}"]
    lineas.append(f"vehiculo lleno, sin precio: {rep['capacity_skips']}")
    lineas.append("los deltas NO se suman: cada uno es una corrida aparte")
    return "\n".join(lineas)


def main(argv: list[str]) -> int:
    # Import tardio: la config de los turnos grabados vive con el exportador, y
    # usarla es lo que hace que estos numeros cuadren con el replay del front.
    from data.export_turno import config

    seeds = [int(a) for a in argv] or [2000]
    for i, seed in enumerate(seeds):
        if i:
            print()
        print(_texto(reporte(config(seed))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
