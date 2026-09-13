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

El contrafactual (`GET /live/counterfactual/{id}`) va aparte de `/live/end` y corre en
su propio hilo. Re-simula el turno una vez por salto por dinero: 120 min tarda 0.1-0.5 s,
pero 480 min tarda 3-8 s (hasta ~11 s la primera vez, en frio), y meterlo en `/live/end`
dejaria el boton End colgado todo ese rato. `/live/end` lo arranca al soltar el candado
de la sesion y contesta; el GET devuelve 202 mientras calcula, el reporte cuando esta, o
500 si trono, y el front pregunta hasta tener una de las dos. Ningun candado se queda
tomado durante el calculo: el cfg, los shocks y las estrategias de una sesion terminada
ya no cambian, asi que se copian con el candado de la sesion y se sueltan. Se calcula una
vez por sesion.
"""

import os
import secrets
import threading
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Response
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
from oracle import simular_oracle
from valor import para_turno

MAX_SESIONES = 8
# El minuto en que se ensayo el cierre de Constitucion con SEED_ENSAYADO.
MINUTO_CIERRE_ENSAYADO = 30


@dataclass
class Contrafactual:
    """El calculo del reporte de una sesion terminada. `listo` se prende al acabar,
    con `reporte` o con `error`; mientras no, el GET contesta 202."""

    listo: threading.Event = field(default_factory=threading.Event)
    reporte: dict[str, Any] | None = None
    error: str | None = None


def _calcular(calculo: Contrafactual, sesion: LiveDemoSession) -> None:
    # Se copia con el candado de la sesion y se calcula sin ninguno: terminada, ya no
    # recibe ticks ni shocks, y /status de esta u otra sesion no espera segundos.
    with sesion.lock:
        cfg, disrupciones = sesion.cfg, tuple(sesion.shocks)
        estrategias = dict(sesion.nuez.usadas)
    try:
        calculo.reporte = reporte(cfg, disrupciones=disrupciones, estrategias=estrategias)
    except Exception as exc:
        # Un hilo que truena callado dejaria al front en "calculando" para siempre.
        calculo.error = f"{type(exc).__name__}: {exc}"
    finally:
        calculo.listo.set()


@dataclass
class CalculoOracle:
    listo: threading.Event = field(default_factory=threading.Event)
    reporte: dict[str, Any] | None = None
    error: str | None = None


def _calcular_oracle(calculo: CalculoOracle, sesion: LiveDemoSession) -> None:
    with sesion.lock:
        cfg, disrupciones = sesion.cfg, tuple(sesion.shocks)
    try:
        resultado = simular_oracle(cfg, disrupciones=disrupciones)
        calculo.reporte = {
            "earnings_mxn": resultado.ganado,
            "deliveries": resultado.entregas
        }
    except Exception as exc:
        calculo.error = f"{type(exc).__name__}: {exc}"
    finally:
        calculo.listo.set()


class LiveRegistry:
    """Vivas en memoria, una bitacora JSONL por sesion. Su lock es solo del dict: dos
    ticks del mismo id no corren a la vez por el lock de la sesion, no por este."""

    def __init__(self, log_dir: Path, geometria: Geometria = linea_recta) -> None:
        self.log_dir = Path(log_dir)
        self.geometria = geometria
        self._lock = RLock()
        self._sesiones: dict[str, LiveDemoSession] = {}
        self._contrafactuales: dict[str, Contrafactual] = {}
        self._oracles: dict[str, CalculoOracle] = {}

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
                sacada = self._sesiones.pop(viejo)
                self._contrafactuales.pop(viejo, None)
                self._oracles.pop(viejo, None)
                # Una sesion que sale corriendo dejaria su hilo de Gemini consultando cada
                # cinco minutos sin nadie que lo pare. detener() espera al hilo hasta 26 s:
                # va en otro hilo para no frenar este /live/start.
                threading.Thread(target=sacada.estrategia.detener, daemon=True).start()
            self._sesiones[session_id] = sesion
            return sesion

    def obtener(self, session_id: str) -> LiveDemoSession:
        with self._lock:
            sesion = self._sesiones.get(session_id)
            if sesion is None:
                raise KeyError(session_id)
            return sesion

    def contrafactual(self, sesion: LiveDemoSession) -> Contrafactual:
        """El calculo de una sesion ya terminada; lo arranca la primera vez que se pide.
        KeyError si ya salio del registro."""
        with self._lock:
            if self._sesiones.get(sesion.session_id) is not sesion:
                raise KeyError(sesion.session_id)
            calculo = self._contrafactuales.get(sesion.session_id)
            if calculo is not None:
                return calculo
            calculo = self._contrafactuales[sesion.session_id] = Contrafactual()
        hilo = threading.Thread(
            target=_calcular, args=(calculo, sesion), name="contrafactual", daemon=True
        )
        hilo.start()
        return calculo

    def oracle(self, sesion: LiveDemoSession) -> CalculoOracle:
        with self._lock:
            if self._sesiones.get(sesion.session_id) is not sesion:
                raise KeyError(sesion.session_id)
            calculo = self._oracles.get(sesion.session_id)
            if calculo is not None:
                return calculo
            calculo = self._oracles[sesion.session_id] = CalculoOracle()
        hilo = threading.Thread(
            target=_calcular_oracle, args=(calculo, sesion), name="oracle_calc", daemon=True
        )
        hilo.start()
        return calculo

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
            fin = sesion.end()
        except SesionTerminada as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    # Ya sin candado: el calculo arranca aqui y cuando el front pregunte lleva ventaja.
    try:
        registry.contrafactual(sesion)
        registry.oracle(sesion)
    except KeyError:
        pass  # la saco del registro otro /live/start mientras terminaba: ya no hay a quien
    return fin


@router.get("/counterfactual/{session_id}")
def counterfactual(session_id: str, response: Response) -> dict[str, Any]:
    """El contrafactual de Nuez sobre ESTE turno en vivo: su seed, su config, los shocks
    que se metieron y la estrategia con la que decidio cada pedido. Mismo esquema que los
    `contrafactual_<seed>.json` del replay grabado, mas `session_id`.

    202 `{"status": "computing"}` mientras corre, 200 con el reporte, 500 si trono."""
    sesion = _sesion(session_id)
    with sesion.lock:
        corriendo = sesion.status == "running"
    if corriendo:
        raise HTTPException(
            status_code=409,
            detail=f"la sesion {session_id} sigue corriendo: termina el turno primero",
        )
    try:
        calculo = registry.contrafactual(sesion)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"sesion {session_id!r} no existe") from None
    if not calculo.listo.is_set():
        response.status_code = 202
        return {"status": "computing", "session_id": session_id, "seed": sesion.cfg.seed}
    if calculo.reporte is None:
        # En ingles: el panel de /live lo ensena tal cual despues de "Couldn't compute...".
        raise HTTPException(status_code=500, detail=f"re-simulation failed with {calculo.error}")
    return {**calculo.reporte, "session_id": session_id}


@router.get("/oracle/{session_id}")
def oracle(session_id: str, response: Response) -> dict[str, Any]:
    sesion = _sesion(session_id)
    with sesion.lock:
        corriendo = sesion.status == "running"
    if corriendo:
        raise HTTPException(
            status_code=409,
            detail=f"la sesion {session_id} sigue corriendo: termina el turno primero",
        )
    try:
        calculo = registry.oracle(sesion)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"sesion {session_id!r} no existe") from None
    if not calculo.listo.is_set():
        response.status_code = 202
        return {"status": "computing", "session_id": session_id}
    if calculo.reporte is None:
        raise HTTPException(status_code=500, detail=f"oracle simulation failed with {calculo.error}")
    return {**calculo.reporte, "session_id": session_id}
