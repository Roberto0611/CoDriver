"""El router del demo en vivo: dos agentes, un juez con boton de shock.

Cada sesion vive en `LiveRegistry`, no a nivel de modulo: dos jueces corriendo el
demo en paralelo no comparten nada. El registro guarda como mucho 8 sesiones (se
acaba la RAM antes que las probabilidades de un hackathon) y tira la mas vieja, pero
solo despues de que la nueva se construyo: un start que truena no saca a nadie.

Dos candados. El del registro cuida el dict y se suelta enseguida; el de cada sesion
(`sesion.lock`) lo toman tick, shock, end y status. Asi `/live/end` de un turno de 8 h
no congela a las demas sesiones, y nada mas corre sobre la misma mientras termina.

`LiveDemoSession` habla en espanol (tipo/zona/calle/duracion_min/oferta_id/retraso_min);
el protocolo HTTP que ve el juez habla en ingles (shock_type/zone/road/duration_min/
order_id/slip_min). Este
archivo es el unico lugar donde se traducen, igual que courier_api.py hace con
el protocolo Courier.

El contrafactual (`GET /live/counterfactual/{id}`) va aparte de `/live/end` y se
calcula la primera vez que se pide. Re-simula el turno una vez por salto por dinero:
120 min tarda ~0.1-0.5 s, pero 480 min tarda ~3.5 s, y meterlo en `/live/end` haria
que el boton End se quedara colgado todo ese rato. Se calcula sin el candado del
registro (los shocks y el cfg de una sesion terminada ya no cambian) y se guarda en
la sesion, asi que pedirlo dos veces no re-simula dos veces.
"""

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backendruta import zonas
from backendruta.courier_models import MAX_TURNO_MIN
from backendruta.live_demo import (
    DEMO_DELAY,
    MINUTO_DELAY_ENSAYADO,
    SEED_ENSAYADO,
    LiveDemoSession,
    SesionTerminada,
)
from backendruta.live_geometry import Geometria, linea_recta
from contrafactual import reporte
from contrato import ConfigTurno, Vehiculo
from valor import para_turno

MAX_SESIONES = 8
# El minuto en que se ensayo el cierre de Constitucion con SEED_ENSAYADO.
MINUTO_CIERRE_ENSAYADO = 30


@dataclass
class Contrafactual:
    """El reporte de una sesion terminada. Su candado es solo del calculo: dos pedidos
    al mismo tiempo esperan al primero en vez de re-simular el turno dos veces."""

    lock: Lock = field(default_factory=Lock)
    reporte: dict[str, Any] | None = None


class LiveRegistry:
    """Vivas en memoria, una bitacora JSONL por sesion. Su lock es solo del dict: dos
    ticks del mismo id no corren a la vez por el lock de la sesion, no por este."""

    def __init__(self, log_dir: Path, geometria: Geometria = linea_recta) -> None:
        self.log_dir = Path(log_dir)
        self.geometria = geometria
        self._lock = RLock()
        self._sesiones: dict[str, LiveDemoSession] = {}
        self._contrafactuales: dict[str, Contrafactual] = {}

    def usar_grafo(self, grafo: Any) -> None:
        """`main.py` lo llama una vez con el grafo (o None) recien cargado."""
        from backendruta.live_geometry import por_calles

        self.geometria = por_calles(grafo)

    def crear(self, cfg: ConfigTurno) -> LiveDemoSession:
        with self._lock:
            # 3 bytes son 16 millones de ids por seed: chocar es raro, pero pisar la sesion
            # de otro juez (y truncar su JSONL) no se vale ni una vez.
            session_id = f"live-{cfg.seed}-{secrets.token_hex(3)}"
            while session_id in self._sesiones:
                session_id = f"live-{cfg.seed}-{secrets.token_hex(3)}"
            sesion = LiveDemoSession(
                session_id,
                cfg,
                self.log_dir / f"{session_id}.jsonl",
                geometria=self.geometria,
            )
            while len(self._sesiones) >= MAX_SESIONES:
                viejo = next(iter(self._sesiones))  # el mas viejo por insercion
                self._sesiones.pop(viejo)
                self._contrafactuales.pop(viejo, None)
            self._sesiones[session_id] = sesion
            return sesion

    def obtener(self, session_id: str) -> LiveDemoSession:
        with self._lock:
            sesion = self._sesiones.get(session_id)
            if sesion is None:
                raise KeyError(session_id)
            return sesion

    def contrafactual(self, session_id: str) -> Contrafactual:
        """El lugar del reporte de esa sesion. KeyError si ya salio del registro."""
        with self._lock:
            if session_id not in self._sesiones:
                raise KeyError(session_id)
            return self._contrafactuales.setdefault(session_id, Contrafactual())

    @property
    def lock(self) -> RLock:
        return self._lock


registry = LiveRegistry(Path(os.getenv("NUEZ_LIVE_DIR", "cache/live")))
router = APIRouter(prefix="/live", tags=["live-demo"])


class StartRequest(BaseModel):
    # El seed va en el nombre del JSONL: sin tope, uno de 400 digitos tronaba el filesystem.
    seed: int = Field(ge=0, le=2**31 - 1)
    # El mismo tope que /shift/start: la jornada de 8.5 h del practice pack.
    duracion_min: int = Field(default=120, ge=30, le=MAX_TURNO_MIN)
    hora_inicio: int = Field(default=14, ge=0, le=23)
    vehiculo: Vehiculo = "moto"
    ancla: int = 4
    margen_min: int = Field(default=10, ge=0, le=30)


class TickRequest(BaseModel):
    session_id: str
    minutes: int = Field(default=1, ge=1, le=10)


class ShockRequestLive(BaseModel):
    session_id: str
    shock_type: Literal["closure", "surge", "rain", "delay"]
    zone: int | None = None
    # Opcional solo por el delay, que dura hasta el final del turno. Para los demas
    # la sesion la exige y la falta sale como 422, igual que antes.
    duration_min: int | None = Field(default=None, ge=1, le=240)
    multiplier: float = Field(default=1.5, ge=1.0, le=3.0)
    road: str | None = Field(default=None, max_length=60)  # la teclea el juez
    order_id: str | None = None  # delay: None = el siguiente pedido por aparecer
    slip_min: int | None = Field(default=None, ge=1, le=60)  # delay


class SessionRequest(BaseModel):
    session_id: str


def _sesion(session_id: str) -> LiveDemoSession:
    try:
        return registry.obtener(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"sesion {session_id!r} no existe") from None


@router.get("/rehearsal")
def rehearsal() -> dict[str, int]:
    """El seed y los minutos ensayados para el pitch. Viven en el backend para que el
    boton "Rehearsed seed" del front no se quede con un numero viejo."""
    return {
        "seed": SEED_ENSAYADO,
        "closure_minute": MINUTO_CIERRE_ENSAYADO,
        "delay_minute": MINUTO_DELAY_ENSAYADO,
        "delay_slip_min": DEMO_DELAY["slip_min"],
    }


@router.post("/start")
def start(request: StartRequest) -> dict[str, Any]:
    try:
        ancla = zonas.punto(request.ancla)
        para_turno(request.duracion_min)  # ValueError si ninguna tabla la cubre
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    cfg = ConfigTurno(
        duracion_min=request.duracion_min,
        ancla=ancla,
        margen_min=request.margen_min,
        vehiculo=request.vehiculo,
        seed=request.seed,
        hora_inicio=request.hora_inicio,
    )
    sesion = registry.crear(cfg)
    with sesion.lock:
        return sesion.snapshot()


@router.post("/tick")
def tick(request: TickRequest) -> dict[str, Any]:
    sesion = _sesion(request.session_id)
    with sesion.lock:
        try:
            return sesion.tick(request.minutes)
        except SesionTerminada as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/shock")
def shock(request: ShockRequestLive) -> dict[str, Any]:
    sesion = _sesion(request.session_id)
    with sesion.lock:
        try:
            return sesion.shock(
                request.shock_type,
                request.duration_min,
                zona=request.zone,
                multiplicador=request.multiplier,
                calle=request.road,
                oferta_id=request.order_id,
                retraso_min=request.slip_min,
            )
        except SesionTerminada as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/status/{session_id}")
def status(session_id: str) -> dict[str, Any]:
    sesion = _sesion(session_id)
    with sesion.lock:
        return sesion.snapshot()


@router.post("/end")
def end(request: SessionRequest) -> dict[str, Any]:
    sesion = _sesion(request.session_id)
    with sesion.lock:
        try:
            return sesion.end()
        except SesionTerminada as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/counterfactual/{session_id}")
def counterfactual(session_id: str) -> dict[str, Any]:
    """El contrafactual de Nuez sobre el turno en vivo, con los shocks que se metieron.
    Mismo esquema que los `contrafactual_<seed>.json` del replay grabado."""
    sesion = _sesion(session_id)
    with sesion.lock:
        if sesion.status == "running":
            raise HTTPException(
                status_code=409,
                detail=f"la sesion {session_id} sigue corriendo: termina el turno primero",
            )
        # Terminada ya no acepta ticks ni shocks: esto no cambia al soltar el candado.
        cfg, disrupciones = sesion.cfg, tuple(sesion.shocks)
    try:
        calculo = registry.contrafactual(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"sesion {session_id!r} no existe") from None
    with calculo.lock:
        if calculo.reporte is None:
            calculo.reporte = reporte(cfg, disrupciones=disrupciones)
        return calculo.reporte
