"""Presentacion determinista de respuestas y eventos del protocolo Courier."""

import time
from datetime import datetime, timedelta
from typing import Any

import seguridad
import shocks
from backendruta.courier_models import DecideRequest, DecideResponse, ShockRequest
from contrato import Decision, Vehiculo
from nuez import MARGEN
from sim import Parada


def iso(value: datetime) -> str:
    return value.isoformat()


def net_pay(request: DecideRequest) -> float:
    gross = request.base_pay_mxn * request.surge_multiplier + request.est_tip_mxn
    fuel = request.distance_delivery_km * seguridad.VEHICULOS[request.vehicle].costo_km
    return gross - fuel


def direct_minutes(request: DecideRequest) -> float:
    speed_factor = seguridad.VEHICULOS[request.vehicle].velocidad
    pickup = request.estimated_pickup_min
    if pickup is None:
        pickup = request.distance_pickup_km * 2 * speed_factor
    delivery = request.estimated_delivery_min
    if delivery is None:
        delivery = request.distance_delivery_km * 2 * speed_factor
    return max(pickup, request.restaurant_prep_min) + delivery


def fuel_cost(vehicle: Vehiculo) -> float:
    return seguridad.VEHICULOS[vehicle].costo_km


def response(
    request: DecideRequest, decision: Decision, started: float, degraded: bool
) -> DecideResponse:
    terms = decision.terminos
    minutes = terms.get("minutos", 0)
    pay = terms.get("pago_neto", net_pay(request))
    raw_rate = pay * 60 / max(minutes, 1)
    opportunity = terms.get("precio_tiempo", 0)
    result = DecideResponse(
        order_id=request.order_id,
        decision="ACCEPT" if decision.accion == "aceptar" else "SKIP",
        reason=english_reason(decision),
        binding_constraint=decision.restriccion,
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
        degraded=degraded,
        economics={
            "net_pay_mxn": round(pay, 2),
            "total_time_min": round(minutes, 2),
            "raw_rate_mxn_hr": round(raw_rate, 2),
            "adjusted_rate_mxn_hr": round((pay - opportunity) * 60 / max(minutes, 1), 2),
            "reservation_wage_mxn_hr": round(opportunity * 60 / max(minutes, 1), 2),
            "deadhead_km": request.distance_pickup_km,
        },
    )
    if len(result.reason.split()) > 40:
        raise RuntimeError("la razon del motor excede 40 palabras")
    return result


def english_reason(decision: Decision) -> str:
    terms = decision.terminos
    constraint = decision.restriccion
    if constraint == "flagged_zone_night":
        return "Skip: the drop-off zone is flagged after 22:00. Safety overrides pay."
    if constraint == "mandatory_break":
        return "Skip: the mandatory 20-minute break is due after four continuous riding hours."
    if constraint == "heat_rule":
        return "Skip: continuous riding reached the 90-minute heat limit between 12:00 and 16:00."
    if constraint == "shift_end_infeasible":
        if terms.get("minutos_regreso", 0) > 0:
            return "Skip: the order and return route cannot finish before the shift deadline."
        return "Skip: not enough time remaining to deliver this order before the shift end."
    if constraint == "vehicle_capacity":
        return "Skip: this order would exceed the assigned vehicle capacity."
    pay = terms.get("pago_neto", 0)
    cost = terms.get("precio_tiempo", 0)
    minutes = terms.get("minutos", 0)
    # Con decimales: redondeado a pesos, "MXN 26 is below MXN 26" suena a error.
    if decision.accion == "saltar" and pay >= cost:
        return (
            f"Skip: MXN {pay:.1f} net is only MXN {pay - cost:.1f} above the MXN {cost:.1f} "
            f"opportunity cost for {minutes:.0f} minutes; the minimum edge is MXN {MARGEN:.1f}."
        )
    if decision.accion == "saltar":
        return (
            f"Skip: MXN {pay:.1f} net is below the MXN {cost:.1f} "
            f"opportunity cost for {minutes:.0f} minutes."
        )
    return (
        f"Accept: MXN {pay:.1f} net exceeds the MXN {cost:.1f} "
        f"opportunity cost for {minutes:.0f} minutes."
    )


def offer_event(request: DecideRequest) -> dict[str, Any]:
    event = request.model_dump(mode="json", exclude_none=True)
    event.pop("courier_state_overrides", None)
    return {"event": "order_offered", **event}


def decision_event(
    request: DecideRequest, result: DecideResponse, explanation: dict[str, Any]
) -> dict[str, Any]:
    """El evento lleva la explicacion completa: explain_decision solo la vuelve a leer."""
    event = result.model_dump(mode="json")
    event.update(
        {
            "event": "decision",
            "sim_time": iso(request.sim_time),
            "inputs": explanation["inputs"],
            "alternatives_considered": explanation["alternatives_considered"],
        }
    )
    return event


def shock_event(request: ShockRequest, cuando: datetime, zone_id: int | None) -> dict[str, Any]:
    """El evento `shock` del protocolo. Solo lleva los campos que aplican a su tipo."""
    evento: dict[str, Any] = {
        "event": "shock",
        "sim_time": iso(cuando),
        "shock_type": request.shock_type,
        "duration_min": request.duration_min,
    }
    if zone_id is not None:
        evento["zone"] = zone_id
    if request.shock_type == "surge":
        evento["multiplier"] = request.multiplier
    if request.shock_type == "closure" and request.road:
        evento["road"] = request.road
    if request.shock_type == "delay":
        evento["order_id"] = request.order_id
        evento["slip_min"] = request.slip_min
    return evento


def to_shock(request: ShockRequest, minuto: int, zona: str | None) -> shocks.Shock:
    """La forma interna: minutos desde que empezo el turno y zona por nombre."""
    return shocks.Shock(
        t=max(0, minuto),
        tipo=request.shock_type,
        duracion_min=request.duration_min,
        zona=zona,
        multiplicador=request.multiplier,
        calle=request.road,
        oferta_id=request.order_id,
        retraso_min=request.slip_min,
    )


def position_event(
    start: datetime, minute: int, zone_id: int, route: list[Parada]
) -> dict[str, Any]:
    """El `position_update` del protocolo: donde va y hacia que tipo de parada."""
    if not route:
        status = "idle"
    elif route[0].tipo == "pickup":
        status = "to_pickup"
    else:
        status = "to_dropoff"
    return {
        "event": "position_update",
        "sim_time": iso(start + timedelta(minutes=minute)),
        "zone": zone_id,
        "status": status,
    }


def earnings_event(
    start: datetime, minute: int, earnings_mxn: float, completed: int
) -> dict[str, Any]:
    """El `earnings_update` del protocolo, con el ritmo por hora del turno hasta ahora."""
    hours = max(minute / 60, 1 / 60)
    return {
        "event": "earnings_update",
        "sim_time": iso(start + timedelta(minutes=minute)),
        "earnings_mxn": round(earnings_mxn, 2),
        "orders_completed": completed,
        "mxn_per_hr": round(earnings_mxn / hours, 2),
    }


def shift_end_event(
    when: datetime, offered: int, completed: int, earnings_mxn: float
) -> dict[str, Any]:
    """El `shift_end` del protocolo."""
    return {
        "event": "shift_end",
        "sim_time": iso(when),
        "orders_offered": offered,
        "orders_completed": completed,
        "earnings_mxn": round(earnings_mxn, 2),
        "safety_violations": 0,
    }
