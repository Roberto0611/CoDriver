"""El contrafactual de una sesion en vivo: re-simula con los shocks que metio el juez."""

import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import contrafactual
from backendruta import live_api, zonas
from backendruta.live_demo import SEED_ENSAYADO, LiveDemoSession
from backendruta.live_geometry import linea_recta
from contrafactual import DINERO, forzar, reporte
from contrato import ConfigTurno
from nuez import politica_nuez
from sim import simular


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
    assert reporte(cfg(2000), disrupciones=()) == reporte(cfg(2000))


def test_con_shocks_re_simula_el_turno_en_vivo(tmp_path):
    s = ensayo(tmp_path)
    disrupciones = tuple(s.shocks)
    rep = reporte(s.cfg, disrupciones=disrupciones)

    # El "real" del reporte es el turno que el juez acaba de ver, no el turno sin shocks.
    assert rep["actual"]["earned_mxn"] == s.turnos["nuez"].res.ganado
    assert rep["actual"]["earned_mxn"] != reporte(s.cfg)["actual"]["earned_mxn"]

    real = simular(s.cfg, politica_nuez, disrupciones)
    assert rep["top"], "el ensayo tiene saltos por dinero que re-simular"
    for fila in rep["top"]:
        forzado = simular(s.cfg, forzar(fila["order_id"]), disrupciones)
        assert fila["delta_mxn"] == round(forzado.ganado - real.ganado, 2)
        assert fila["forced_earned_mxn"] == forzado.ganado
        assert fila["forced_deliveries"] == forzado.entregas

    saltos = [d for d in s.turnos["nuez"].res.decisiones if d.restriccion == DINERO]
    assert rep["money_skips"]["count"] == len(saltos)


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


def test_endpoint_404_409_y_despues_del_end(api):
    assert api.get("/live/counterfactual/nope").status_code == 404
    sid = _start(api)
    api.post("/live/tick", json={"session_id": sid, "minutes": 5})
    corriendo = api.get(f"/live/counterfactual/{sid}")
    assert corriendo.status_code == 409, "sin terminar no hay turno que re-simular"

    cierre = {"shock_type": "closure", "zone": 0, "duration_min": 40, "road": "Constitución"}
    assert api.post("/live/shock", json={"session_id": sid, **cierre}).status_code == 200
    assert api.post("/live/end", json={"session_id": sid}).status_code == 200

    r = api.get(f"/live/counterfactual/{sid}")
    assert r.status_code == 200, r.text
    sesion = live_api.registry.obtener(sid)
    assert r.json() == reporte(sesion.cfg, disrupciones=tuple(sesion.shocks))
    assert r.json()["seed"] == SEED_ENSAYADO


def test_se_calcula_una_vez_por_sesion(api, monkeypatch):
    llamadas = []

    def contando(*args, **kwargs):
        llamadas.append(1)
        return contrafactual.reporte(*args, **kwargs)

    monkeypatch.setattr(live_api, "reporte", contando)
    sid = _start(api, seed=2000)
    api.post("/live/end", json={"session_id": sid})
    primera = api.get(f"/live/counterfactual/{sid}").json()
    assert api.get(f"/live/counterfactual/{sid}").json() == primera
    assert len(llamadas) == 1


def test_calcular_no_detiene_a_las_demas_sesiones(api, monkeypatch):
    """Un turno de 8 h tarda segundos en re-simularse: el candado del registro no se
    queda tomado mientras tanto, y status de otra sesion contesta."""
    entro, soltar = threading.Event(), threading.Event()

    def lento(*args, **kwargs):
        entro.set()
        assert soltar.wait(5)
        return contrafactual.reporte(*args, **kwargs)

    monkeypatch.setattr(live_api, "reporte", lento)
    terminada, otra = _start(api, seed=2000), _start(api, seed=2001)
    api.post("/live/end", json={"session_id": terminada})

    hilo = threading.Thread(target=live_api.counterfactual, args=(terminada,))
    hilo.start()
    try:
        assert entro.wait(5)
        listo = threading.Event()

        def pedir_status():
            live_api.status(otra)
            listo.set()

        threading.Thread(target=pedir_status, daemon=True).start()
        assert listo.wait(2), "status de otra sesion se quedo esperando al contrafactual"
    finally:
        soltar.set()
        hilo.join(10)
