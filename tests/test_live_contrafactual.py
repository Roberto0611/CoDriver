"""El contrafactual de una sesion en vivo: re-simula ESE turno, con sus shocks y su estrategia.

Lo que se prueba es la honestidad del numero: que el "real" del reporte es el turno que el
juez vio, que cada delta sale de correr `simular` otra vez con el pedido forzado, y que sin
shocks da lo mismo que el `contrafactual_<seed>.json` grabado para /sim.
"""

import json
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import contrafactual
from backendruta import live_api, zonas
from backendruta.live_demo import SEED_ENSAYADO, LiveDemoSession
from backendruta.live_geometry import linea_recta
from contrafactual import DINERO, con_estrategias, forzar, reporte
from contrato import ConfigTurno
from estrategia import BASE, Estrategia
from nuez import politica_nuez
from shocks import Shock
from sim import simular

PUBLIC = Path(__file__).resolve().parents[1] / "frontend" / "public"


def cfg(seed: int) -> ConfigTurno:
    # La config de /live/start por defecto: Tec, 120 min desde las 14.
    return ConfigTurno(
        duracion_min=120, ancla=zonas.punto(4), margen_min=10, vehiculo="moto", seed=seed
    )


def correr(s: LiveDemoSession, hasta: int) -> None:
    while s.minute < hasta:
        s.tick()


def ensayo(tmp_path, name="ensayo") -> LiveDemoSession:
    """El guion del pitch: cierre de Constitucion en el 30 y delay de 15 en el 56."""
    s = LiveDemoSession(name, cfg(SEED_ENSAYADO), tmp_path / f"{name}.jsonl")
    correr(s, 30)
    s.shock("closure", 40, zona=0, calle="Constitución")
    correr(s, 56)
    s.shock("delay", retraso_min=15)
    s.end()
    return s


def test_sin_shocks_es_el_reporte_de_siempre():
    """El default no cambia nada: el CLI y los contrafactual_*.json siguen dando lo mismo."""
    assert reporte(cfg(2000), disrupciones=(), estrategias={}) == reporte(cfg(2000))


def test_con_shocks_es_simular_con_los_mismos_shocks_y_el_pedido_forzado(tmp_path):
    s = ensayo(tmp_path)
    # Los mismos shocks, declarados desde el inicio en vez de inyectados a media corrida.
    delay = s.shocks[1].oferta_id
    declarados = (
        Shock(30, "closure", 40, zona=zonas.nombre(0), calle="Constitución"),
        Shock(56, "delay", 120 - 56, oferta_id=delay, retraso_min=15),
    )
    assert tuple(s.shocks) == declarados
    rep = reporte(s.cfg, disrupciones=declarados, estrategias=s.nuez.usadas)

    real = simular(s.cfg, politica_nuez, declarados)
    # El "real" del reporte es el turno que el juez acaba de ver, no el turno sin shocks.
    assert rep["actual"]["earned_mxn"] == real.ganado == s.turnos["nuez"].res.ganado
    # Un shock puede mover una decisión y compensarse después: la igualdad con
    # `real` de arriba es la garantía importante, no forzar una diferencia de MXN.

    # Cada salto por dinero, a mano: una corrida forzada por pedido.
    filas, bloqueados = [], 0
    for d in real.decisiones:
        if d.restriccion != DINERO:
            continue
        forzado = simular(s.cfg, forzar(d.oferta_id), declarados)
        if next(x for x in forzado.decisiones if x.oferta_id == d.oferta_id).accion != "aceptar":
            bloqueados += 1
            continue
        filas.append((d.oferta_id, d.t, round(forzado.ganado - real.ganado, 2), forzado))
    assert filas, "el ensayo tiene saltos por dinero que re-simular"

    dinero = rep["money_skips"]
    assert dinero["count"] == len(filas) + bloqueados and dinero["infeasible"] == bloqueados
    assert dinero["would_earn_more"] == sum(1 for f in filas if f[2] > 0)
    assert dinero["would_earn_less"] == sum(1 for f in filas if f[2] < 0)
    orden = sorted(filas, key=lambda f: (-abs(f[2]), f[1]))[: contrafactual.TOP]
    assert [(t["order_id"], t["delta_mxn"]) for t in rep["top"]] == [(f[0], f[2]) for f in orden]
    for t, (_, _, _, forzado) in zip(rep["top"], orden, strict=True):
        assert t["forced_earned_mxn"] == forzado.ganado
        assert t["forced_deliveries"] == forzado.entregas
        assert t["late"] == forzado.llego_tarde


def test_la_estrategia_que_publico_gemini_tambien_se_re_simula(tmp_path):
    """Si Gemini movio una perilla a media corrida, el turno en vivo ya no es el de BASE.
    El reporte usa la estrategia con la que se decidio cada pedido, no BASE."""
    s = LiveDemoSession("g", cfg(2000), tmp_path / "g.jsonl")
    s.estrategia.detener()  # sin hilo: nadie pisa lo que publica el test
    correr(s, 30)
    exigente = Estrategia(margen_mxn=25.0, fuente="doble", nota="solo pedidos muy buenos")
    s.estrategia.actual = exigente
    correr(s, 90)
    s.estrategia.actual = BASE
    s.end()
    assert exigente in s.nuez.usadas.values()

    rep = reporte(s.cfg, estrategias=s.nuez.usadas)
    assert rep["actual"]["earned_mxn"] == s.turnos["nuez"].res.ganado
    assert reporte(s.cfg)["actual"]["earned_mxn"] != rep["actual"]["earned_mxn"], (
        "la estrategia tiene que mover el turno, si no el test no prueba nada"
    )
    real = simular(s.cfg, con_estrategias(politica_nuez, s.nuez.usadas))
    for fila in rep["top"]:
        forzado = simular(s.cfg, con_estrategias(forzar(fila["order_id"]), s.nuez.usadas))
        assert fila["delta_mxn"] == round(forzado.ganado - real.ganado, 2)


# --- el endpoint --------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(live_api, "registry", live_api.LiveRegistry(tmp_path, linea_recta))
    app = FastAPI()
    app.include_router(live_api.router)
    return TestClient(app)


def _start(api, seed=SEED_ENSAYADO):
    r = api.post("/live/start", json={"seed": seed})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _esperar(api, sid, segundos=30.0):
    """Pregunta como el front: hasta que deja de contestar 202."""
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        r = api.get(f"/live/counterfactual/{sid}")
        if r.status_code != 202:
            return r
        assert r.json() == {"status": "computing", "session_id": sid, "seed": r.json()["seed"]}
        time.sleep(0.05)
    raise AssertionError("el contrafactual no termino")


def test_endpoint_404_409_y_despues_del_end(api):
    assert api.get("/live/counterfactual/nope").status_code == 404
    sid = _start(api)
    api.post("/live/tick", json={"session_id": sid, "minutes": 5})
    corriendo = api.get(f"/live/counterfactual/{sid}")
    assert corriendo.status_code == 409, "sin terminar no hay turno que re-simular"

    cierre = {"shock_type": "closure", "zone": 0, "duration_min": 40, "road": "Constitución"}
    assert api.post("/live/shock", json={"session_id": sid, **cierre}).status_code == 200
    fin = api.post("/live/end", json={"session_id": sid})
    assert fin.status_code == 200

    r = _esperar(api, sid)
    assert r.status_code == 200, r.text
    sesion = live_api.registry.obtener(sid)
    esperado = reporte(sesion.cfg, disrupciones=tuple(sesion.shocks))
    assert r.json() == {**esperado, "session_id": sid}
    assert r.json()["seed"] == SEED_ENSAYADO
    assert r.json()["actual"]["earned_mxn"] == fin.json()["nuez"]["earnings_mxn"]


def test_sin_shocks_da_lo_mismo_que_el_grabado_de_sim(api):
    """/live/start con sus defaults y seed 2000 es el turno de contrafactual_2000.json: el
    ancla es la misma coordenada (Tec) aunque el Punto se llame distinto."""
    grabado = json.loads((PUBLIC / "contrafactual_2000.json").read_text(encoding="utf-8"))
    sid = _start(api, seed=2000)
    assert api.post("/live/end", json={"session_id": sid}).status_code == 200
    r = _esperar(api, sid)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo.pop("session_id") == sid
    assert cuerpo == grabado


def test_end_contesta_sin_esperar_al_calculo_y_el_get_da_202(api, monkeypatch):
    """Un turno de 8 h tarda segundos en re-simularse: ni /live/end, ni el GET, ni otra
    sesion esperan a que acabe."""
    entro, soltar = threading.Event(), threading.Event()

    def lento(*args, **kwargs):
        entro.set()
        assert soltar.wait(10)
        return contrafactual.reporte(*args, **kwargs)

    monkeypatch.setattr(live_api, "reporte", lento)
    terminada, otra = _start(api, seed=2000), _start(api, seed=2001)
    try:
        assert api.post("/live/end", json={"session_id": terminada}).status_code == 200
        assert entro.wait(5), "/live/end no arranco el calculo"
        r = api.get(f"/live/counterfactual/{terminada}")
        assert r.status_code == 202
        assert r.json() == {"status": "computing", "session_id": terminada, "seed": 2000}
        assert api.get(f"/live/status/{otra}").status_code == 200
    finally:
        soltar.set()
    assert _esperar(api, terminada).status_code == 200


def test_se_calcula_una_vez_por_sesion(api, monkeypatch):
    llamadas = []

    def contando(*args, **kwargs):
        llamadas.append(1)
        return contrafactual.reporte(*args, **kwargs)

    monkeypatch.setattr(live_api, "reporte", contando)
    sid = _start(api, seed=2000)
    api.post("/live/end", json={"session_id": sid})
    primera = _esperar(api, sid).json()
    assert api.get(f"/live/counterfactual/{sid}").json() == primera
    assert len(llamadas) == 1


def test_turno_de_ocho_horas_y_media_de_punta_a_punta(api):
    """La jornada de 8.5 h del practice pack por /live: arranca, End la adelanta hasta el
    minuto 510 (22:30 si empieza a las 14) y su contrafactual llega por la ruta de 202,
    porque re-simular 510 min tarda segundos."""
    r = api.post("/live/start", json={"seed": 3141, "duracion_min": 510})
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    assert r.json()["duration_min"] == 510 and r.json()["start_hour"] == 14
    assert api.post("/live/tick", json={"session_id": sid, "minutes": 5}).status_code == 200

    fin = api.post("/live/end", json={"session_id": sid})
    assert fin.status_code == 200, fin.text
    assert fin.json()["status"] == "ended" and fin.json()["minute"] == 510
    assert divmod(14 * 60 + fin.json()["minute"], 60) == (22, 30)
    assert api.get(f"/live/counterfactual/{sid}").status_code == 202, "End no espera al calculo"

    rep = _esperar(api, sid, segundos=120)
    assert rep.status_code == 200, rep.text
    assert rep.json()["seed"] == 3141 and rep.json()["session_id"] == sid
    assert rep.json()["actual"]["earned_mxn"] == fin.json()["nuez"]["earnings_mxn"]


def test_si_el_calculo_truena_es_500_y_no_202_para_siempre(api, monkeypatch):
    def truena(*_args, **_kwargs):
        raise ValueError("salto sin restriccion reconocida")

    monkeypatch.setattr(live_api, "reporte", truena)
    sid = _start(api, seed=2000)
    api.post("/live/end", json={"session_id": sid})
    r = _esperar(api, sid)
    assert r.status_code == 500
    assert r.json()["detail"].startswith("re-simulation failed with ValueError")
    assert "salto sin restriccion reconocida" in r.json()["detail"]
