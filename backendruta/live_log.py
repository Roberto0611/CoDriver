"""Los eventos del JSONL del demo en vivo, con los nombres del protocolo Courier.

Funciones puras: datos de la sesion entran, un dict sale. Aqui no se escribe nada ni
se lee el reloj de pared; `LiveDemoSession` decide cuando va cada evento y lo manda
al `EventLog`. Estan aparte para que las reglas del formato no se pierdan entre la
logica de los minutos.

El archivo es UNO por sesion y lo comparten los dos agentes. El validador oficial
(`courier/validate_format (2).py`) permite llaves extra y eventos repetidos, asi que:

- `shift_start`, `order_offered` y `shock` pasan una vez para los dos: la oferta y
  el shock son el mismo mundo para ambos, que es justo lo que el demo quiere probar.
- `decision`, `position_update`, `earnings_update` y `shift_end` son de un agente y
  llevan la llave extra `"agent": "greedy" | "nuez"`.

`sim_time` sale de `FECHA_BASE + hora_inicio + minuto`, nunca de la hora real: el
mismo seed con los mismos shocks en los mismos minutos da el mismo archivo byte por
byte, salvo `session_id` y `latency_ms`. `minute` va como extra en cada evento del
turno porque es la unidad en la que piensa el motor y la del snapshot.
"""

from datetime import datetime, timedelta
from typing import Any

import rutas
from backendruta import courier_format, zonas
from backendruta.courier_models import ShockRequest
from contrato import ConfigTurno, Decision, Oferta
from shocks import Shock
from sim import Parada, Resultado, indice_de

# La fecha del ejemplo del protocolo. Fija a proposito: si fuera la de hoy, el mismo
# turno grabado dos dias distintos daria dos logs distintos y el replay no cuadraria.
FECHA_BASE = datetime(2026, 3, 21)
# Como en el ejemplo oficial: la app espera la respuesta 5 segundos.
PLAZO_DECISION = timedelta(seconds=5)

# El vocabulario de `status` del esquema no tiene "regresando". Volver al ancla no
# es llevar ni ir por un pedido, asi que cuenta como idle, igual que la ruta vacia.
ESTADO_HACIA = {"pickup": "to_pickup", "dropoff": "to_dropoff"}


def momento(cfg: ConfigTurno, minuto: int) -> datetime:
    return FECHA_BASE + timedelta(hours=cfg.hora_inicio, minutes=minuto)


def cuando(cfg: ConfigTurno, minuto: int) -> str:
    return courier_format.iso(momento(cfg, minuto))


def zona_de(punto: int) -> int:
    return zonas.ID_POR_NOMBRE[rutas.ZONA_DE[punto]]


def shift_start(session_id: str, cfg: ConfigTurno, ancla: int) -> dict[str, Any]:
    return {
        "event": "shift_start",
        "sim_time": cuando(cfg, 0),
        "seed": cfg.seed,
        "shift_hours": cfg.duracion_min / 60,
        "vehicle": cfg.vehiculo,
        "start_location_zone": zona_de(ancla),
        "shift_end_time": cuando(cfg, cfg.duracion_min),
        "fuel_mxn_per_km": courier_format.fuel_cost(cfg.vehiculo),
        "mode": "live",
        "session_id": session_id,
        "margin_min": cfg.margen_min,
    }


def order_offered(o: Oferta, cfg: ConfigTurno, ancla: int, factor: float) -> dict[str, Any]:
    """`factor` es el surge de los shocks vigentes al aparecer el ping en la zona de
    pickup: el mismo que usa `pay_mxn` del snapshot y el que paga el motor al entregar."""
    pickup, dropoff = indice_de(o.pickup), indice_de(o.dropoff)
    aparece = momento(cfg, o.t_aparece)
    return {
        "event": "order_offered",
        "order_id": o.id,
        "platform": o.plataforma,
        "sim_time": courier_format.iso(aparece),
        "decision_deadline": courier_format.iso(aparece + PLAZO_DECISION),
        "minute": o.t_aparece,
        "zone_pickup": zona_de(pickup),
        "zone_dropoff": zona_de(dropoff),
        "zone_pickup_name": rutas.ZONA_DE[pickup],
        "zone_dropoff_name": rutas.ZONA_DE[dropoff],
        # La oferta es una sola para los dos agentes, y cada uno esta en otro lado:
        # no hay UNA posicion del repartidor desde donde medir. Se mide desde el
        # ancla de la sesion, que es el punto comun; cada politica mide su propio
        # deadhead desde donde va.
        "distance_pickup_km": round(rutas.km(ancla, pickup), 3),
        "distance_delivery_km": round(rutas.km(pickup, dropoff), 3),
        "base_pay_mxn": round(o.pago, 2),
        "est_tip_mxn": 0,
        "surge_multiplier": round(o.surge * factor, 3),
        "restaurant_prep_min": o.t_prep,
        "weight_kg": o.peso_kg,
        "volume_liters": o.volumen_l,
        "vehicle": cfg.vehiculo,
    }


def decision(agente: str, d: Decision, cfg: ConfigTurno, latency_ms: float) -> dict[str, Any]:
    """`reason` es la misma razon en ingles del log oficial, la que pasa
    `check_response`. La del motor va entera en `reason_es` para no perder nada."""
    return {
        "event": "decision",
        "agent": agente,
        "order_id": d.oferta_id,
        "sim_time": cuando(cfg, d.t),
        "minute": d.t,
        "decision": "ACCEPT" if d.accion == "aceptar" else "SKIP",
        "reason": courier_format.english_reason(d),
        "reason_es": d.razon,
        "binding_constraint": d.restriccion,
        "latency_ms": round(latency_ms, 3),
        "tier": "tier1",
        "degraded": False,
        "terms": d.terminos,
    }


def position_updates(
    agente: str,
    cfg: ConfigTurno,
    llegadas: list[tuple[int, int, str]],
    ruta: list[Parada],
    cancelados: int,
) -> list[dict[str, Any]]:
    """Un `position_update` por parada a la que llego el agente en este minuto.

    `llegadas` son las entradas nuevas de `res.trayecto` y `ruta` la que le quedo al
    terminar el minuto. El status es hacia donde va DESPUES de cada llegada: para
    las de en medio es la siguiente llegada, para la ultima la cabeza de la ruta.

    `cancelados` son los pedidos que el motor tiro desde el ultimo position_update.
    No hay evento oficial de cancelacion, asi que viajan en la primera llegada que
    sigue; el total del turno queda ademas en `shift_end`.
    """
    if not llegadas:
        return []
    siguientes = [tipo for _, _, tipo in llegadas[1:]] + [ruta[0].tipo if ruta else "idle"]
    eventos = []
    for (t, punto, tipo), sig in zip(llegadas, siguientes, strict=True):
        evento: dict[str, Any] = {
            "event": "position_update",
            "agent": agente,
            "sim_time": cuando(cfg, t),
            "minute": t,
            "zone": zona_de(punto),
            "status": ESTADO_HACIA.get(sig, "idle"),
            "point": punto,
            "stop": tipo,
        }
        eventos.append(evento)
    if eventos and cancelados:
        eventos[0]["cancelled_count"] = cancelados
    return eventos


def earnings_update(
    agente: str, cfg: ConfigTurno, t: int, cobro: float, res: Resultado
) -> dict[str, Any]:
    horas = max(t, 1) / 60  # en el minuto 0 no hay hora trabajada entre la cual dividir
    return {
        "event": "earnings_update",
        "agent": agente,
        "sim_time": cuando(cfg, t),
        "minute": t,
        "earnings_mxn": round(res.ganado, 2),
        "orders_completed": res.entregas,
        "mxn_per_hr": round(res.ganado / horas, 2),
        "payout_mxn": round(cobro, 2),
    }


def shock(s: Shock, cfg: ConfigTurno, zone_id: int | None) -> dict[str, Any]:
    """La misma forma que el `shock` del /shock oficial: se arma con su funcion para
    que un campo que solo aplica a un tipo (road, multiplier) no aparezca en otro."""
    peticion = ShockRequest(
        shock_type=s.tipo,
        duration_min=s.duracion_min,
        zone=zone_id,
        multiplier=s.multiplicador,
        road=s.calle,
    )
    evento = courier_format.shock_event(peticion, momento(cfg, s.t), zone_id)
    evento.update({"minute": s.t, "ends_at_min": s.t + s.duracion_min})
    if s.zona is not None:
        evento["zone_name"] = s.zona
    return evento


def shift_end(
    agente: str, cfg: ConfigTurno, minuto: int, res: Resultado, status: str
) -> dict[str, Any]:
    """`res` ya cerrado: `ganado` redondeado y `llego_tarde` calculado."""
    return {
        "event": "shift_end",
        "agent": agente,
        "sim_time": cuando(cfg, minuto),
        "minute": minuto,
        "orders_offered": len(res.decisiones),
        "orders_completed": res.entregas,
        "earnings_mxn": round(res.ganado, 2),
        "safety_violations": res.violaciones,
        "late_return": res.llego_tarde,
        "cancelled": res.cancelados,
        "skipped": res.rechazos,
        "returned_at_min": None if res.regreso_en is None else round(res.regreso_en, 2),
        "session_status": status,
    }
