"""Presentacion determinista de respuestas y eventos del protocolo Courier."""

import time
from datetime import datetime
from typing import Any

import seguridad
from backendruta.courier_models import DecideRequest, DecideResponse
from contrato import Decision, EstadoRepartidor, Vehiculo


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
        return "Skip: the order and return route cannot finish before the shift deadline."
    if constraint == "vehicle_capacity":
        return "Skip: this order would exceed the assigned vehicle capacity."
    pay = terms.get("pago_neto", 0)
    cost = terms.get("precio_tiempo", 0)
    minutes = terms.get("minutos", 0)
    if decision.accion == "saltar":
        return (
            f"Skip: MXN {pay:.0f} net is below the MXN {cost:.0f} "
            f"opportunity cost for {minutes:.0f} minutes."
        )
    return (
        f"Accept: MXN {pay:.0f} net exceeds the MXN {cost:.0f} "
        f"opportunity cost for {minutes:.0f} minutes."
    )


def offer_event(request: DecideRequest) -> dict[str, Any]:
    event = request.model_dump(mode="json", exclude_none=True)
    event.pop("courier_state_overrides", None)
    return {"event": "order_offered", **event}


def decision_event(
    request: DecideRequest,
    courier: EstadoRepartidor,
    result: DecideResponse,
    position_zone: int,
    in_flight_orders: list[str],
) -> dict[str, Any]:
    event = result.model_dump(mode="json")
    event.update(
        {
            "event": "decision",
            "sim_time": iso(request.sim_time),
            "inputs": {
                "position_zone": position_zone,
                "time_remaining_min": courier.t_restante,
                "continuous_riding_min": courier.minutos_manejando,
                "in_flight_orders": in_flight_orders,
                "vehicle": request.vehicle,
            },
        }
    )
    return event
