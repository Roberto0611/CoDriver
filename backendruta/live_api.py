"""El router del demo en vivo: dos agentes, un juez con boton de shock.

Cada sesion vive en `LiveRegistry`, no a nivel de modulo: dos jueces corriendo el
demo en paralelo no comparten nada. El registro guarda como mucho 8 sesiones (se
acaba la RAM antes que las probabilidades de un hackathon) y tira la mas vieja.

`LiveDemoSession` habla en espanol (tipo/zona/calle/duracion_min/oferta_id/retraso_min);
el protocolo HTTP que ve el juez habla en ingles (shock_type/zone/road/duration_min/
order_id/slip_min). Este
archivo es el unico lugar donde se traducen, igual que courier_api.py hace con
el protocolo Courier.
"""

import os
import secrets
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backendruta import zonas
from backendruta.live_demo import DEMO_DELAY, SEED_ENSAYADO, LiveDemoSession, SesionTerminada
from backendruta.live_geometry import Geometria, linea_recta
from contrato import ConfigTurno, Vehiculo
from valor import para_turno

MAX_SESIONES = 8
# El minuto en que se ensayo el cierre de Constitucion con SEED_ENSAYADO.
MINUTO_CIERRE_ENSAYADO = 30


class LiveRegistry:
    """Vivas en memoria, una bitacora JSONL por sesion. El lock cubre lectura y
    escritura: dos ticks del mismo id nunca corren a la vez."""

    def __init__(self, log_dir: Path, geometria: Geometria = linea_recta) -> None:
        self.log_dir = Path(log_dir)
        self.geometria = geometria
        self._lock = RLock()
        self._sesiones: dict[str, LiveDemoSession] = {}

    def usar_grafo(self, grafo: Any) -> None:
        """`main.py` lo llama una vez con el grafo (o None) recien cargado."""
        from backendruta.live_geometry import por_calles

        self.geometria = por_calles(grafo)

    def crear(self, cfg: ConfigTurno) -> LiveDemoSession:
        with self._lock:
            while len(self._sesiones) >= MAX_SESIONES:
                self._sesiones.pop(next(iter(self._sesiones)))  # el mas viejo por insercion
            session_id = f"live-{cfg.seed}-{secrets.token_hex(3)}"
            sesion = LiveDemoSession(
                session_id,
                cfg,
                self.log_dir / f"{session_id}.jsonl",
                geometria=self.geometria,
            )
            self._sesiones[session_id] = sesion
            return sesion

    def obtener(self, session_id: str) -> LiveDemoSession:
        with self._lock:
            sesion = self._sesiones.get(session_id)
            if sesion is None:
                raise KeyError(session_id)
            return sesion

    @property
    def lock(self) -> RLock:
        return self._lock


registry = LiveRegistry(Path(os.getenv("NUEZ_LIVE_DIR", "cache/live")))
router = APIRouter(prefix="/live", tags=["live-demo"])


class StartRequest(BaseModel):
    seed: int = Field(ge=0)
    duracion_min: int = Field(default=120, ge=30, le=480)
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
    road: str | None = None
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
    """El seed y el minuto ensayados para el pitch. Viven en el backend para que el
    boton "Rehearsed seed" del front no se quede con un numero viejo."""
    return {
        "seed": SEED_ENSAYADO,
        "closure_minute": MINUTO_CIERRE_ENSAYADO,
        "delay_slip_min": DEMO_DELAY["slip_min"],
    }


@router.post("/start")
def start(request: StartRequest) -> dict[str, Any]:
    with registry.lock:
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
        return sesion.snapshot()


@router.post("/tick")
def tick(request: TickRequest) -> dict[str, Any]:
    with registry.lock:
        sesion = _sesion(request.session_id)
        try:
            return sesion.tick(request.minutes)
        except SesionTerminada as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/shock")
def shock(request: ShockRequestLive) -> dict[str, Any]:
    with registry.lock:
        sesion = _sesion(request.session_id)
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
    with registry.lock:
        return _sesion(session_id).snapshot()


@router.post("/end")
def end(request: SessionRequest) -> dict[str, Any]:
    with registry.lock:
        sesion = _sesion(request.session_id)
        try:
            return sesion.end()
        except SesionTerminada as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
