"""Adaptador HTTP entre el protocolo oficial de Infosys y el motor de Nuez.

El protocolo usa fechas ISO, zonas enteras y ACCEPT/SKIP. El motor conserva su
contrato interno en minutos, puntos del mapa y aceptar/saltar. Esta frontera es
el unico lugar donde se traducen ambos formatos.
"""

import math
import os
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import APIRouter, HTTPException

import rutas
import valor
from backendruta import courier_format, explain, strategy
from backendruta.courier_models import DecideRequest, DecideResponse, ShiftStartRequest, ShiftState
from backendruta.event_log import EventLog
from backendruta.strategy import CapaEstrategia
from contrato import ConfigTurno, EstadoRepartidor, Oferta, Punto
from estrategia import Estrategia
from mundo import ZONAS
from nuez import politica_nuez
from sim import Parada, _punto

# Los ids son parte de nuestro stream: el orden es estable y se publica en /zones.
ZONE_NAMES = tuple(ZONAS)
ZONE_ID_BY_NAME = {name: zone_id for zone_id, name in enumerate(ZONE_NAMES)}


def _point_for_zone(zone_id: int) -> Punto:
    if not 0 <= zone_id < len(ZONE_NAMES):
        raise ValueError(f"zona {zone_id} desconocida; usa GET /zones")
    name = ZONE_NAMES[zone_id]
    return _punto(rutas.puntos_de(name)[0])


def _index_for_zone(zone_id: int) -> int:
    return rutas.puntos_de(_zone_name(zone_id))[0]


def _zone_name(zone_id: int) -> str:
    if not 0 <= zone_id < len(ZONE_NAMES):
        raise ValueError(f"zona {zone_id} desconocida; usa GET /zones")
    return ZONE_NAMES[zone_id]


class CourierService:
    """Una sesion determinista. El lock evita dos pings mutando el turno a la vez."""

    def __init__(self, log_path: Path):
        self.log = EventLog(log_path)
        self.state: ShiftState | None = None
        self.explanations = explain.ExplainIndex()
        self._lock = RLock()
        # La capa lenta. Vive aqui pero NO se llama desde decide(): solo se lee
        # `self.estrategia.actual`, que es leer una variable.
        self.estrategia = CapaEstrategia(al_cambiar=self._log_strategy)
        self.estrategia.contexto = self._contexto_modelo

    @property
    def degraded(self) -> bool:
        """True cuando el motor decide con una estrategia vieja porque el modelo no responde."""
        return self.estrategia.degradado

    def start(self, request: ShiftStartRequest) -> dict[str, Any]:
        with self._lock:
            try:
                position = _index_for_zone(request.start_location_zone)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            duration = round(request.shift_hours * 60)
            end_time = request.shift_end_time or request.sim_time + timedelta(minutes=duration)
            actual_duration = round((end_time - request.sim_time).total_seconds() / 60)
            if actual_duration <= 0 or actual_duration > 480:
                raise HTTPException(status_code=422, detail="el turno debe durar entre 1 y 480 min")
            config = ConfigTurno(
                duracion_min=actual_duration,
                ancla=_point_for_zone(request.start_location_zone),
                margen_min=0,
                vehiculo=request.vehicle,
                seed=request.seed,
                hora_inicio=request.sim_time.hour,
            )
            # Falla al iniciar, no durante el primer ping, si falta una tabla adecuada.
            valor.para_turno(actual_duration)
            self.state = ShiftState(
                config=config,
                start_time=request.sim_time,
                end_time=end_time,
                current_minute=0,
                position=position,
            )
            event = {
                "event": "shift_start",
                "sim_time": courier_format.iso(request.sim_time),
                "seed": request.seed,
                "shift_hours": actual_duration / 60,
                "vehicle": request.vehicle,
                "start_location_zone": request.start_location_zone,
                "shift_end_time": courier_format.iso(end_time),
                "fuel_mxn_per_km": courier_format.fuel_cost(request.vehicle),
            }
            self.log.start(event)
            self.explanations.clear()
            # El hilo del modelo arranca con el turno. Si no hay credencial, la
            # primera vuelta marca `degraded` y el motor sigue con la estrategia base.
            self.estrategia.arrancar()
            return {**event, "event_log": str(self.log.path)}

    def explain(self, order_id: str) -> dict[str, Any]:
        """Busca en memoria; si el proceso se reinicio, lee el JSONL. Nunca re-decide."""
        with self._lock:
            record = self.explanations.get(order_id)
            if record is None and self.log.path.exists():
                record = explain.ExplainIndex.from_log(self.log.path).get(order_id)
            if record is None:
                raise HTTPException(status_code=404, detail=f"{order_id} no tiene decision")
            return record

    def decide(self, request: DecideRequest) -> DecideResponse:
        started = time.perf_counter()
        with self._lock:
            self._ensure_state(request)
            assert self.state is not None
            fingerprint = request.model_dump_json(exclude_none=False)
            cached = self.state.responses.get(request.order_id)
            if cached:
                if cached[0] != fingerprint:
                    raise HTTPException(
                        status_code=409, detail="order_id repetido con otro payload"
                    )
                return cached[1]

            try:
                self._apply_time_and_overrides(request)
                offer, courier = self._to_internal(request)
                table = valor.para_turno(self.state.config.duracion_min)
                direct_minutes = courier_format.direct_minutes(request)
                new_route, decision = politica_nuez(
                    offer,
                    courier,
                    self.state.route,
                    self.state.config,
                    tabla=table,
                    minutos_directos=direct_minutes,
                    km_entrega=request.distance_delivery_km,
                    estrategia=self.estrategia.actual,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            response = courier_format.response(request, decision, started, self.degraded)
            explanation = explain.build(
                request=request,
                response=response,
                terms=decision.terminos,
                position_zone=self._current_zone_id(),
                time_remaining_min=courier.t_restante,
                continuous_riding_min=courier.minutos_manejando,
                in_flight_orders=sorted(self.state.accepted),
                strategy={
                    "policy": "nuez_opportunity_cost",
                    "value_table_horizon_min": max(table),
                    **self.estrategia.actual.resumen(),
                    "degraded": self.degraded,
                },
            )
            self.log.append(courier_format.offer_event(request))
            self.log.append(courier_format.decision_event(request, response, explanation))
            self.explanations.add(explanation)
            self.state.offered += 1
            if new_route is not None:
                was_idle = not self.state.route
                self.state.route = new_route
                self.state.accepted[request.order_id] = request
                if was_idle and new_route:
                    self._schedule_arrival(self.state.current_minute)
            self.state.responses[request.order_id] = (fingerprint, response)
            return response

    def end(self, sim_time: datetime | None = None) -> dict[str, Any]:
        with self._lock:
            if self.state is None:
                raise HTTPException(status_code=409, detail="no hay turno activo")
            when = sim_time or self.state.end_time
            elapsed = math.floor((when - self.state.start_time).total_seconds() / 60)
            if elapsed < self.state.current_minute:
                raise HTTPException(
                    status_code=422, detail="el cierre no puede retroceder el reloj"
                )
            self._advance(elapsed)
            event = {
                "event": "shift_end",
                "sim_time": courier_format.iso(when),
                "orders_offered": self.state.offered,
                "orders_completed": self.state.completed,
                "earnings_mxn": round(self.state.earnings_mxn, 2),
                "safety_violations": 0,
            }
            self.log.append(event)
            self.estrategia.detener()
            return event

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self.state is None:
                return {"active": False, "degraded": self.degraded}
            return {
                "active": True,
                "seed": self.state.config.seed,
                "elapsed_min": self.state.current_minute,
                "remaining_min": max(0, self.state.config.duracion_min - self.state.current_minute),
                "in_flight_orders": sorted(self.state.accepted),
                "event_log": str(self.log.path),
                "degraded": self.degraded,
            }

    def _ensure_state(self, request: DecideRequest) -> None:
        if self.state is not None:
            return
        overrides = request.courier_state_overrides
        elapsed = overrides.shift_elapsed_hours if overrides else None
        elapsed_min = round((elapsed or 0) * 60)
        start = request.sim_time - timedelta(minutes=elapsed_min)
        end = (
            overrides.shift_end_time
            if overrides and overrides.shift_end_time
            else start + timedelta(hours=8)
        )
        duration = round((end - start).total_seconds() / 60)
        if not 0 < duration <= 480:
            raise HTTPException(
                status_code=422, detail="el turno inferido debe durar entre 1 y 480 min"
            )
        self.start(
            ShiftStartRequest(
                seed=0,
                shift_hours=duration / 60,
                vehicle=request.vehicle,
                start_location_zone=request.zone_pickup,
                sim_time=start,
                shift_end_time=end,
            )
        )

    def _apply_time_and_overrides(self, request: DecideRequest) -> None:
        assert self.state is not None
        if request.vehicle != self.state.config.vehiculo:
            raise ValueError(
                f"el turno usa {self.state.config.vehiculo}, la oferta declara {request.vehicle}"
            )
        elapsed = math.floor((request.sim_time - self.state.start_time).total_seconds() / 60)
        overrides = request.courier_state_overrides
        if overrides and overrides.shift_elapsed_hours is not None:
            elapsed = round(overrides.shift_elapsed_hours * 60)
            self.state.start_time = request.sim_time - timedelta(minutes=elapsed)
            self.state.config = replace(self.state.config, hora_inicio=self.state.start_time.hour)
        if elapsed < self.state.current_minute:
            raise ValueError("sim_time retrocede dentro del turno; reinicia para hacer replay")
        self._advance(elapsed)

        if overrides is None:
            return
        if overrides.shift_end_time is not None:
            self.state.end_time = overrides.shift_end_time
            duration = round((self.state.end_time - self.state.start_time).total_seconds() / 60)
            if not 0 < duration <= 480:
                raise ValueError("shift_end_time deja un turno fuera del rango de 1 a 480 min")
            self.state.config = replace(self.state.config, duracion_min=duration)
        if overrides.continuous_riding_min is not None:
            self.state.continuous_riding_min = round(overrides.continuous_riding_min)
        elif overrides.last_break_end_time is not None:
            since_break = (request.sim_time - overrides.last_break_end_time).total_seconds() / 60
            self.state.continuous_riding_min = max(0, round(since_break))
        if overrides.position_zone is not None:
            self.state.position = _index_for_zone(overrides.position_zone)
        if overrides.in_flight_orders is not None:
            self._replace_in_flight(overrides.in_flight_orders)

    def _advance(self, target_minute: int) -> None:
        assert self.state is not None
        state = self.state
        while state.current_minute < target_minute:
            if not state.route:
                idle = target_minute - state.current_minute
                state.idle_min += idle
                if state.idle_min >= 20:
                    state.continuous_riding_min = 0
                state.current_minute = target_minute
                break
            arrival = math.ceil(state.arrival_minute or state.current_minute)
            stop = min(target_minute, arrival)
            busy = max(0, stop - state.current_minute)
            state.continuous_riding_min += busy
            state.idle_min = 0
            state.current_minute = stop
            if stop < arrival:
                break
            destination = state.route.pop(0)
            state.position = destination.punto
            if destination.tipo == "dropoff" and destination.oferta_id:
                order = state.accepted.pop(destination.oferta_id, None)
                if order:
                    state.completed += 1
                    state.earnings_mxn += courier_format.net_pay(order)
                    self._log_earnings(state.current_minute)
            self._log_position(state.current_minute)
            if state.route:
                self._schedule_arrival(state.current_minute)
            else:
                state.arrival_minute = None

    def _replace_in_flight(self, orders: list[dict[str, Any]]) -> None:
        assert self.state is not None
        route: list[Parada] = []
        accepted: dict[str, DecideRequest | None] = {}
        for position, raw in enumerate(orders):
            try:
                order_id = str(raw["order_id"])
                pickup_zone = int(raw.get("zone_pickup", self._current_zone_id()))
                dropoff_zone = int(raw["zone_dropoff"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"in_flight_orders[{position}] incompleto") from exc
            status = str(raw.get("status", "to_pickup"))
            prep = max(0, round(float(raw.get("restaurant_prep_min", 0))))
            if status not in {"picked_up", "to_dropoff"}:
                route.append(
                    Parada(
                        "pickup",
                        _index_for_zone(pickup_zone),
                        order_id,
                        self.state.current_minute + prep,
                    )
                )
            route.append(
                Parada(
                    "dropoff",
                    _index_for_zone(dropoff_zone),
                    order_id,
                    peso_kg=float(raw.get("weight_kg", 1)),
                    volumen_l=float(raw.get("volume_liters", 5)),
                )
            )
            accepted[order_id] = None
        self.state.route = route
        self.state.accepted = accepted
        self.state.arrival_minute = None
        if route:
            self._schedule_arrival(self.state.current_minute)

    def _to_internal(self, request: DecideRequest) -> tuple[Oferta, EstadoRepartidor]:
        assert self.state is not None
        remaining = max(
            0,
            math.floor((self.state.end_time - request.sim_time).total_seconds() / 60),
        )
        surge = request.surge_multiplier
        # Oferta aplica surge a `pago`; así la propina queda fuera del multiplicador.
        pay_before_surge = request.base_pay_mxn + request.est_tip_mxn / surge
        offer = Oferta(
            id=request.order_id,
            plataforma=request.platform,
            pago=pay_before_surge,
            surge=surge,
            t_aparece=self.state.current_minute,
            t_prep=round(request.restaurant_prep_min),
            pickup=_point_for_zone(request.zone_pickup),
            dropoff=_point_for_zone(request.zone_dropoff),
            peso_kg=request.weight_kg,
            volumen_l=request.volume_liters,
        )
        courier = EstadoRepartidor(
            t=self.state.current_minute,
            t_restante=remaining,
            pos=_punto(self.state.position),
            mochila=sorted(self.state.accepted),
            ganado=self.state.earnings_mxn,
            fatiga=min(1, self.state.continuous_riding_min / 240),
            minutos_manejando=self.state.continuous_riding_min,
        )
        return offer, courier

    def _log_position(self, minute: int) -> None:
        assert self.state is not None
        if not self.state.route:
            status = "idle"
        elif self.state.route[0].tipo == "pickup":
            status = "to_pickup"
        else:
            status = "to_dropoff"
        self.log.append(
            {
                "event": "position_update",
                "sim_time": courier_format.iso(self.state.start_time + timedelta(minutes=minute)),
                "zone": self._current_zone_id(),
                "status": status,
            }
        )

    def _log_earnings(self, minute: int) -> None:
        assert self.state is not None
        hours = max(minute / 60, 1 / 60)
        self.log.append(
            {
                "event": "earnings_update",
                "sim_time": courier_format.iso(self.state.start_time + timedelta(minutes=minute)),
                "earnings_mxn": round(self.state.earnings_mxn, 2),
                "orders_completed": self.state.completed,
                "mxn_per_hr": round(self.state.earnings_mxn / hours, 2),
            }
        )

    def _schedule_arrival(self, minute: int) -> None:
        assert self.state is not None and self.state.route
        destination = self.state.route[0]
        hour = self.state.config.hora_inicio + minute // 60
        arrival = minute + rutas.minutos(
            self.state.position, destination.punto, hour, self.state.config.vehiculo
        )
        if destination.tipo == "pickup":
            arrival = max(arrival, destination.listo_en)
        self.state.arrival_minute = arrival

    def _contexto_modelo(self) -> dict[str, Any]:
        return strategy.contexto_del_turno(self.state, ZONE_NAMES)

    def _log_strategy(self, propuesta: Estrategia, degraded: bool) -> None:
        """Lo llama el hilo de la capa lenta, nunca /decide.

        No toma el lock del turno a proposito: si lo tomara, un ping que llegue justo
        en ese instante esperaria al hilo del modelo, que es exactamente lo que el
        presupuesto de 50 ms prohibe. El EventLog ya trae su propio lock.
        """
        evento = strategy.evento_actualizacion(self.state, propuesta, degraded)
        if evento is not None:
            self.log.append(evento)

    def _current_zone_id(self) -> int:
        assert self.state is not None
        return ZONE_ID_BY_NAME[rutas.ZONA_DE[self.state.position]]


DEFAULT_LOG = Path(os.getenv("NUEZ_EVENT_LOG", "cache/courier/current_shift.jsonl"))
service = CourierService(DEFAULT_LOG)
router = APIRouter(tags=["courier-protocol"])


@router.get("/zones")
def zones() -> list[dict[str, Any]]:
    return [
        {"id": zone_id, "name": name, "lat": ZONAS[name][0], "lon": ZONAS[name][1]}
        for zone_id, name in enumerate(ZONE_NAMES)
    ]


@router.post("/shift/start")
def start_shift(request: ShiftStartRequest) -> dict[str, Any]:
    return service.start(request)


@router.post("/decide", response_model=DecideResponse)
async def decide(request: DecideRequest) -> DecideResponse:
    return service.decide(request)


@router.post("/shift/end")
def end_shift(sim_time: datetime | None = None) -> dict[str, Any]:
    return service.end(sim_time)


@router.get("/explain/{order_id}")
@router.get("/explain_decision/{order_id}")
def explain_decision(order_id: str) -> dict[str, Any]:
    return service.explain(order_id)


@router.get("/shift/status")
def shift_status() -> dict[str, Any]:
    return service.status()
