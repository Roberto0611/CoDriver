"""La referencia Oracle del demo: retrospectiva, no una decisión en vivo."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backendruta import live_api
from backendruta.live_geometry import linea_recta
from sim import Resultado


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(live_api, "registry", live_api.LiveRegistry(tmp_path, linea_recta))
    app = FastAPI()
    app.include_router(live_api.router)
    return TestClient(app)


def _start(api, seed=2000, duracion_min=120):
    response = api.post("/live/start", json={"seed": seed, "duracion_min": duracion_min})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _esperar(api, sid):
    fin = time.monotonic() + 5
    while time.monotonic() < fin:
        response = api.get(f"/live/oracle/{sid}")
        if response.status_code != 202:
            return response
        time.sleep(0.01)
    raise AssertionError("Oracle no terminó")


def test_oracle_es_referencia_post_turno_y_copia_los_shocks(api, monkeypatch):
    llamadas = []

    def resolver(cfg, *, disrupciones=()):
        llamadas.append((cfg, disrupciones))
        return (
            Resultado(ganado=42.5, ingreso_bruto=50, gasto_combustible=7.5, entregas=2),
            "OurAgent",
            None,
        )

    monkeypatch.setattr(live_api, "resolver_oracle", resolver)
    sid = _start(api)
    assert api.get(f"/live/oracle/{sid}").status_code == 409
    shock = {"shock_type": "closure", "zone": 0, "duration_min": 40, "road": "Constitución"}
    assert api.post("/live/shock", json={"session_id": sid, **shock}).status_code == 200
    assert api.post("/live/end", json={"session_id": sid}).status_code == 200

    response = _esperar(api, sid)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "earnings_mxn": 42.5,
        "gross_earnings_mxn": 50,
        "fuel_cost_mxn": 7.5,
        "deliveries": 2,
        "source": "OurAgent",
        "session_id": sid,
        "seed": 2000,
    }
    assert len(llamadas) == 1
    assert llamadas[0][1][0].tipo == "closure"


def test_fin_natural_arranca_oracle_una_vez(api, monkeypatch):
    llamadas = []

    def resolver(*_args, **_kwargs):
        llamadas.append(1)
        return Resultado(), "AgendaOracle", None

    monkeypatch.setattr(live_api, "resolver_oracle", resolver)
    sid = _start(api, duracion_min=30)
    for _ in range(3):
        final = api.post("/live/tick", json={"session_id": sid, "minutes": 10})
        assert final.status_code == 200
    assert final.json()["status"] == "finished"

    assert _esperar(api, sid).status_code == 200
    assert api.get(f"/live/oracle/{sid}").status_code == 200
    assert len(llamadas) == 1
