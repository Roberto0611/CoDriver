"""El router /live/*: arranca, avanza, inyecta shocks y cierra dos sesiones."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backendruta import live_api
from backendruta.live_geometry import linea_recta


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(live_api, "registry", live_api.LiveRegistry(tmp_path, linea_recta))
    app = FastAPI()
    app.include_router(live_api.router)
    return TestClient(app)


def start(api, seed=2000):
    r = api.post("/live/start", json={"seed": seed})
    assert r.status_code == 200, r.text
    return r.json()


def test_start_arranca_en_cero_los_dos(api):
    snap = start(api)
    assert snap["minute"] == 0 and snap["status"] == "running"
    assert snap["greedy"]["earnings_mxn"] == snap["nuez"]["earnings_mxn"] == 0


def test_tick_avanza_un_minuto(api):
    sid = start(api)["session_id"]
    snap = api.post("/live/tick", json={"session_id": sid}).json()
    assert snap["minute"] == 1 and len(snap["nuez"]["frames"]) == 1


def test_shock_y_status(api):
    sid = start(api)["session_id"]
    api.post("/live/tick", json={"session_id": sid, "minutes": 5})
    r = api.post(
        "/live/shock",
        json={
            "session_id": sid,
            "shock_type": "closure",
            "zone": 0,
            "duration_min": 40,
            "road": "Constitución",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["shock"]["ends_at_min"] == 45
    assert api.get(f"/live/status/{sid}").json()["active_shocks"][0]["type"] == "closure"


def test_errores(api):
    assert api.post("/live/tick", json={"session_id": "nope"}).status_code == 404
    assert api.post("/live/start", json={"seed": 1, "ancla": 99}).status_code == 422
    sid = start(api)["session_id"]
    assert (
        api.post(
            "/live/shock", json={"session_id": sid, "shock_type": "surge", "duration_min": 30}
        ).status_code
        == 422
    )  # no zone
    fin = api.post("/live/end", json={"session_id": sid})
    assert fin.status_code == 200 and fin.json()["event_log"].endswith(".jsonl")
    assert api.post("/live/tick", json={"session_id": sid}).status_code == 409
    assert (
        api.post(
            "/live/shock",
            json={"session_id": sid, "shock_type": "closure", "zone": 0, "duration_min": 40},
        ).status_code
        == 409
    )
