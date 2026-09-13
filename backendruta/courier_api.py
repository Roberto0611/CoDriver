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

import shocks
import valor
from backendruta import courier_clock, courier_format, en_vuelo, explain, strategy, zonas
from backendruta import database as db
from backendruta.courier_models import (
    MAX_TURNO_MIN,
    DecideRequest,
    DecideResponse,
    ShiftStartRequest,
    ShiftState,
    ShockRequest,
    origen_del_turno,
)
from backendruta.event_log import EventLog
from backendruta.strategy import CapaEstrategia
from backendruta.zonas import NOMBRES as ZONE_NAMES
from contrato import ConfigTurno, EstadoRepartidor, Oferta
from estrategia import Estrategia
from nuez import politica_nuez
from sim import _punto


class CourierService:
    """Una sesion determinista. El lock evita dos pings mutando el turno a la vez."""

    def __init__(self, log_path: Path):
        self.log = EventLog(log_path, after_append=db.enqueue_decision)
        self.state: ShiftState | None = None
        self.explanations = explain.ExplainIndex()
        self._lock = RLock()
        # Mapa aprendido por sesión para IDs externos no publicados que vienen
        # acompañados de un nombre de zona. El API normal conserva GET /zones.
        self._external_zone_ids: dict[int, int] = {}
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
            # Un nuevo turno no hereda la numeración externa de un stream previo.
            self._external_zone_ids.clear()
            try:
                start_zone = self._resolve_zone(request.start_location_zone)
                position = zonas.indice(start_zone)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            duration = round(request.shift_hours * 60)
            end_time = request.shift_end_time or request.sim_time + timedelta(minutes=duration)
            actual_duration = round((end_time - request.sim_time).total_seconds() / 60)
            if actual_duration <= 0 or actual_duration > MAX_TURNO_MIN:
                raise HTTPException(
                    status_code=422,
                    detail=f"el turno debe durar entre 1 y {MAX_TURNO_MIN} min",
                )
            origen, desfase = origen_del_turno(request.sim_time)
            config = ConfigTurno(
                duracion_min=actual_duration + desfase,
                ancla=zonas.punto(start_zone),
                margen_min=0,
                vehiculo=request.vehicle,
                seed=request.seed,
                hora_inicio=origen.hour,
                regresar_al_ancla=request.return_to_start,
            )
            # Falla al iniciar, no durante el primer ping, si falta una tabla adecuada.
            valor.para_turno(actual_duration)
            self.state = ShiftState(
                config=config,
                start_time=origen,
                end_time=end_time,
                current_minute=desfase,
                position=position,
                start_offset_min=desfase,
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
                "return_to_start": request.return_to_start,
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
            record = self.explanations.get(order_id) or db.get_decision(self.log.path, order_id)
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
                table = valor.para_turno(min(self.state.duracion_real, MAX_TURNO_MIN))
                direct_minutes = courier_format.direct_minutes(request)
                new_route, decision = politica_nuez(
                    offer,
                    courier,
                    self.state.route,
                    self.state.config,
                    tabla=table,
                    minutos_directos=direct_minutes,
                    minutos_en_vuelo=self.state.in_flight_remaining_min,
                    km_entrega=request.distance_delivery_km,
                    estrategia=self.estrategia.actual,
                    activos=self._activos(),
                    zona_marcada=request.zone_dropoff in zonas.MARCADAS_PROTOCOLO,
                )
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            response = courier_format.response(request, decision, started, self.degraded)
            explanation = explain.build(
                request=request,
                response=response,
                terms=decision.terminos,
                position_zone=courier_clock.zone_id(self.state),
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
                    courier_clock.schedule_arrival(self.state, self.state.current_minute)
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
            courier_clock.advance(self.state, self.log, elapsed)
            state = self.state
            event = courier_format.shift_end_event(
                when, state.offered, state.completed, state.earnings_mxn
            )
            self.log.append(event)
            self.estrategia.detener()
            return event

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self.state is None:
                return {"active": False, **self.estrategia.estado_publico(en_turno=False)}
            return {
                "active": True,
                "seed": self.state.config.seed,
                "elapsed_min": self.state.current_minute - self.state.start_offset_min,
                "remaining_min": max(0, self.state.config.duracion_min - self.state.current_minute),
                "in_flight_orders": sorted(self.state.accepted),
                "event_log": str(self.log.path),
                **self.estrategia.estado_publico(),
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
        if not 0 < duration <= MAX_TURNO_MIN:
            raise HTTPException(
                status_code=422,
                detail=f"el turno inferido debe durar entre 1 y {MAX_TURNO_MIN} min",
            )
        self.start(
            ShiftStartRequest(
                seed=0,
                shift_hours=duration / 60,
                vehicle=request.vehicle,
                start_location_zone=self._resolve_zone(
                    request.zone_pickup, request.zone_pickup_name
                ),
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
            horas = overrides.shift_elapsed_hours
            self.state.anclar(request.sim_time - timedelta(minutes=round(horas * 60)))
            elapsed = math.floor((request.sim_time - self.state.start_time).total_seconds() / 60)
        if elapsed < self.state.current_minute:
            raise ValueError("sim_time retrocede dentro del turno; reinicia para hacer replay")
        courier_clock.advance(self.state, self.log, elapsed)
        self.state.in_flight_remaining_min = None

        if overrides is None:
            # La ruta rapida solo despierta al hilo ya existente al cruzar treinta
            # minutos simulados. Nunca espera a Gemini ni hace una llamada de red.
            self.estrategia.notificar_minuto_simulado(self.state.current_minute)
            return
        if overrides.shift_end_time is not None:
            self.state.end_time = overrides.shift_end_time
            duration = round((self.state.end_time - self.state.start_time).total_seconds() / 60)
            if not 0 < duration - self.state.start_offset_min <= MAX_TURNO_MIN:
                raise ValueError(
                    f"shift_end_time deja un turno fuera del rango de 1 a {MAX_TURNO_MIN} min"
                )
            self.state.config = replace(self.state.config, duracion_min=duration)
        if overrides.continuous_riding_min is not None:
            self.state.continuous_riding_min = round(overrides.continuous_riding_min)
        elif overrides.last_break_end_time is not None:
            since_break = (request.sim_time - overrides.last_break_end_time).total_seconds() / 60
            self.state.continuous_riding_min = max(0, round(since_break))
        if overrides.position_zone is not None:
            self.state.position = zonas.indice(self._resolve_zone(overrides.position_zone))
        if overrides.in_flight_orders is not None:
            self._replace_in_flight(overrides.in_flight_orders)
        self.estrategia.notificar_minuto_simulado(self.state.current_minute)

    def _replace_in_flight(self, orders: list[dict[str, Any]]) -> None:
        assert self.state is not None
        route, ids, declarado = en_vuelo.traducir(
            orders,
            resolver=self._resolve_zone,
            zona_actual=courier_clock.zone_id(self.state),
            minuto=self.state.current_minute,
        )
        accepted: dict[str, DecideRequest | None] = {order_id: None for order_id in ids}
        self.state.route = route
        self.state.accepted = accepted
        self.state.arrival_minute = None
        if declarado is not None:
            self.state.in_flight_remaining_min = declarado
        if route:
            courier_clock.schedule_arrival(self.state, self.state.current_minute)

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
            pickup=zonas.punto(self._resolve_zone(request.zone_pickup, request.zone_pickup_name)),
            dropoff=zonas.punto(
                self._resolve_zone(request.zone_dropoff, request.zone_dropoff_name)
            ),
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

    def _activos(self) -> shocks.Activos:
        """La foto de las disrupciones vigentes en el minuto actual del turno."""
        if self.state is None:
            return shocks.NINGUNO
        return shocks.en(self.state.current_minute, self.state.shocks)

    def shock(self, request: ShockRequest) -> dict[str, Any]:
        """El boton del juez. Entra por la puerta de siempre y NO frena el bucle."""
        with self._lock:
            if self.state is None:
                raise HTTPException(status_code=409, detail="no hay turno activo")
            cuando = request.sim_time or (
                self.state.start_time + timedelta(minutes=self.state.current_minute)
            )
            minuto = math.floor((cuando - self.state.start_time).total_seconds() / 60)
            try:
                zona = zonas.nombre(request.zone) if request.zone is not None else None
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            self.state.shocks = (*self.state.shocks, courier_format.to_shock(request, minuto, zona))
            evento = courier_format.shock_event(request, cuando, request.zone)
            self.log.append(evento)
            return {**evento, "active_shocks": len(self._activos().shocks)}

    def _contexto_modelo(self) -> dict[str, Any]:
        return strategy.contexto_del_turno(self.state, ZONE_NAMES, self._activos())

    def _log_strategy(self, propuesta: Estrategia, degraded: bool) -> None:
        """Lo llama el hilo de la capa lenta, nunca /decide.

        No toma el lock del turno a proposito: si lo tomara, un ping que llegue justo
        en ese instante esperaria al hilo del modelo, que es exactamente lo que el
        presupuesto de 50 ms prohibe. El EventLog ya trae su propio lock.
        """
        evento = strategy.evento_actualizacion(self.state, propuesta, degraded)
        if evento is not None:
            self.log.append(evento)

    def _resolve_zone(self, zone_id: int, zone_name: str | None = None) -> int:
        """Resuelve IDs propios y catálogos externos etiquetados por nombre."""
        if zone_name:
            resolved = zonas.resolver(zone_id, zone_name)
            self._external_zone_ids[zone_id] = resolved
            return resolved
        if zone_id in self._external_zone_ids:
            return self._external_zone_ids[zone_id]
        return zonas.resolver(zone_id)


DEFAULT_LOG = Path(os.getenv("NUEZ_EVENT_LOG", "cache/courier/current_shift.jsonl"))
service = CourierService(DEFAULT_LOG)
router = APIRouter(tags=["courier-protocol"])


@router.get("/zones")
def zones() -> list[dict[str, float | int | str]]:
    return zonas.catalogo()


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


@router.post("/shock")
def inject_shock(request: ShockRequest) -> dict[str, Any]:
    return service.shock(request)


@router.get("/shift/status")
def shift_status() -> dict[str, Any]:
    return service.status()
