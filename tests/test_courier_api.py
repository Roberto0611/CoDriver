"""El adaptador oficial responde rapido, respeta overrides y deja evidencia JSONL."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backendruta import courier_api

RAIZ = Path(__file__).resolve().parents[1]


def order(order_id: str = "ORD-0001", **changes):
    payload = {
        "order_id": order_id,
        "platform": "rappi",
        "sim_time": "2026-03-21T14:30:00",
        "zone_pickup": 4,
        "zone_dropoff": 2,
        "distance_pickup_km": 1.4,
        "distance_delivery_km": 6.5,
        "base_pay_mxn": 58.0,
        "est_tip_mxn": 12.0,
        "surge_multiplier": 1.3,
        "restaurant_prep_min": 9,
        "weight_kg": 2.1,
        "volume_liters": 6.0,
        "vehicle": "moto",
    }
    return {**payload, **changes}


@pytest.fixture
def api(tmp_path, monkeypatch):
    service = courier_api.CourierService(tmp_path / "shift.jsonl")
    monkeypatch.setattr(courier_api, "service", service)
    app = FastAPI()
    app.include_router(courier_api.router)
    return TestClient(app), service


def start(api: TestClient, *, hour=12, vehicle="moto"):
    response = api.post(
        "/shift/start",
        json={
            "seed": 1234,
            "shift_hours": 8,
            "vehicle": vehicle,
            "start_location_zone": 4,
            "sim_time": f"2026-03-21T{hour:02d}:00:00",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_probe_directo_funciona_y_es_idempotente(api):
    client, _ = api
    payload = order(
        sim_time="2026-03-21T18:42:00",
        zone_pickup=7,
        zone_dropoff=11,
    )
    first = client.post("/decide", json=payload)
    second = client.post("/decide", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    body = first.json()
    assert body["order_id"] == payload["order_id"]
    assert body["decision"] in {"ACCEPT", "SKIP"}
    assert body["tier"] == "tier1"
    assert body["degraded"] is False
    assert body["latency_ms"] < 50
    assert 0 < len(body["reason"].split()) <= 40
    assert set(body["economics"]) == {
        "net_pay_mxn",
        "total_time_min",
        "raw_rate_mxn_hr",
        "adjusted_rate_mxn_hr",
        "reservation_wage_mxn_hr",
        "deadhead_km",
    }


def test_mismo_id_con_otro_payload_se_rechaza(api):
    client, _ = api
    assert client.post("/decide", json=order(base_pay_mxn=500)).status_code == 200
    response = client.post("/decide", json=order(base_pay_mxn=999))
    assert response.status_code == 409


@pytest.mark.parametrize(
    "sim_time,overrides,constraint",
    [
        (
            "2026-03-21T14:00:00",
            {"continuous_riding_min": 95},
            "heat_rule",
        ),
        (
            "2026-03-21T19:00:00",
            {"continuous_riding_min": 245},
            "mandatory_break",
        ),
        (
            "2026-03-21T23:00:00",
            {"continuous_riding_min": 0},
            "flagged_zone_night",
        ),
        (
            "2026-03-21T19:55:00",
            {"continuous_riding_min": 0, "shift_end_time": "2026-03-21T20:00:00"},
            "shift_end_infeasible",
        ),
    ],
)
def test_overrides_activan_la_restriccion_real(api, sim_time, overrides, constraint):
    client, _ = api
    start(client)
    dropoff = 11 if constraint == "flagged_zone_night" else 13
    response = client.post(
        "/decide",
        json=order(
            sim_time=sim_time,
            zone_dropoff=dropoff,
            base_pay_mxn=90_000,
            courier_state_overrides=overrides,
        ),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"] == "SKIP"
    assert body["binding_constraint"] == constraint
    assert constraint.split("_")[0] in body["reason"].lower() or constraint in {
        "flagged_zone_night",
        "mandatory_break",
        "shift_end_infeasible",
    }


def test_pedidos_en_vuelo_cuentan_para_capacidad(api):
    client, _ = api
    start(client)
    in_flight = [
        {
            "order_id": f"ACTIVE-{number}",
            "zone_dropoff": number,
            "status": "to_dropoff",
            "weight_kg": 1,
            "volume_liters": 2,
        }
        for number in (1, 2, 3)
    ]
    response = client.post(
        "/decide",
        json=order(
            base_pay_mxn=90_000,
            courier_state_overrides={
                "continuous_riding_min": 0,
                "in_flight_orders": in_flight,
            },
        ),
    )
    assert response.status_code == 200, response.text
    assert response.json()["binding_constraint"] == "vehicle_capacity"


def test_jsonl_pasa_el_validador_oficial_y_guarda_inputs(api):
    client, service = api
    started = start(client)
    assert started["shift_hours"] == 8
    assert started["shift_end_time"] == "2026-03-21T20:00:00"
    assert client.post("/decide", json=order()).status_code == 200
    assert client.post("/shift/end", params={"sim_time": "2026-03-21T20:00:00"}).status_code == 200

    events = [
        json.loads(line) for line in service.log.path.read_text(encoding="utf-8").splitlines()
    ]
    event_names = [event["event"] for event in events]
    assert event_names[:3] == ["shift_start", "order_offered", "decision"]
    assert event_names[-1] == "shift_end"
    assert "position_update" in event_names
    assert "earnings_update" in event_names
    assert events[1]["sim_time"] == "2026-03-21T14:30:00"
    assert events[1]["zone_pickup"] == 4
    assert events[2]["inputs"]["time_remaining_min"] == 330
    assert [event["sim_time"] for event in events] == sorted(event["sim_time"] for event in events)

    validated = subprocess.run(
        [
            sys.executable,
            str(RAIZ / "courier" / "validate_format (2).py"),
            "--event-log",
            str(service.log.path),
        ],
        cwd=RAIZ,
        capture_output=True,
        text=True,
    )
    assert validated.returncode == 0, validated.stdout + validated.stderr
    assert "PASS" in validated.stdout


def test_replay_repite_accept_skip_y_razon(api):
    client, _ = api
    payloads = [
        order("ORD-A", sim_time="2026-03-21T12:05:00", base_pay_mxn=20),
        order("ORD-B", sim_time="2026-03-21T12:25:00", base_pay_mxn=200),
    ]

    def run():
        start(client)
        return [client.post("/decide", json=payload).json() for payload in payloads]

    first, replay = run(), run()
    for left, right in zip(first, replay, strict=True):
        for field in ("decision", "reason", "binding_constraint", "economics"):
            assert left[field] == right[field]


def test_catalogo_publica_ids_estables(api):
    client, _ = api
    zones = client.get("/zones").json()
    assert len(zones) == 14
    assert zones[4]["name"] == "Tec"
    assert zones[11]["name"] == "Escobedo"


def test_tiempos_y_distancia_del_request_entran_a_la_decision(api):
    client, _ = api
    start(client)
    response = client.post(
        "/decide",
        json=order(
            sim_time="2026-03-21T19:50:00",
            base_pay_mxn=90_000,
            distance_delivery_km=100,
            estimated_pickup_min=20,
            estimated_delivery_min=90,
            courier_state_overrides={"shift_end_time": "2026-03-21T20:00:00"},
        ),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["binding_constraint"] == "shift_end_infeasible"
    assert body["economics"]["total_time_min"] == 110
    assert body["economics"]["net_pay_mxn"] == pytest.approx(116_832)
