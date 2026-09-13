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
    # `strategy_update` lo escribe el hilo de la capa lenta, que corre entre pings
    # y no se sincroniza con ellos a proposito. Puede caer en cualquier hueco: lo
    # que tiene que estar en orden es la ruta rapida.
    rapida = [event for event in events if event["event"] != "strategy_update"]
    rapidos = [event["event"] for event in rapida]
    assert rapidos[:3] == ["shift_start", "order_offered", "decision"]
    assert rapidos[-1] == "shift_end"
    assert "position_update" in rapidos
    assert "earnings_update" in rapidos
    assert "strategy_update" in event_names, "la capa de estrategia tiene que reportarse"
    assert rapida[1]["sim_time"] == "2026-03-21T14:30:00"
    assert rapida[1]["zone_pickup"] == 4
    assert rapida[2]["inputs"]["time_remaining_min"] == 330
    assert [event["sim_time"] for event in rapida] == sorted(e["sim_time"] for e in rapida)

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


def test_la_decision_se_encola_para_tigerdata_sin_cambiar_el_jsonl(api, monkeypatch):
    client, service = api
    mirrored = []
    service.log._after_append = lambda event, path: mirrored.append((event, path))

    start(client)
    assert client.post("/decide", json=order()).status_code == 200

    decisions = [event for event, _ in mirrored if event["event"] == "decision"]
    assert len(decisions) == 1
    assert decisions[0]["order_id"] == "ORD-0001"
    assert decisions[0]["inputs"]["time_remaining_min"] == 330


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


def test_el_boton_del_juez_inyecta_un_shock_y_no_frena_el_bucle(api):
    """El brief exige una disrupcion en vivo. Tiene que entrar sin detener /decide."""
    client, service = api
    start(client)

    respuesta = client.post(
        "/shock",
        json={"shock_type": "closure", "zone": 2, "duration_min": 40, "road": "Constitucion"},
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["shock_type"] == "closure"
    assert respuesta.json()["active_shocks"] == 1

    decidido = client.post("/decide", json=order()).json()
    assert decidido["decision"] in ("ACCEPT", "SKIP"), "decidio, no se quedo esperando"
    assert decidido["latency_ms"] < 50, "el shock no se come el presupuesto"
    assert decidido["tier"] == "tier1"

    eventos = [
        json.loads(linea)
        for linea in service.log.path.read_text(encoding="utf-8").splitlines()
        if '"shock"' in linea
    ]
    assert eventos, "el shock queda en la bitacora para el replay"
    assert eventos[-1]["zone"] == 2 and eventos[-1]["road"] == "Constitucion"


def test_el_shock_estira_el_viaje_de_verdad(api):
    """La fisica no es opinion: el mismo pedido cuesta mas minutos con la calle cerrada."""
    client, service = api
    start(client)

    # Pagos bajos para que los salte y la ruta siga vacia: asi los dos se miden
    # desde el mismo punto de partida y la unica diferencia es la lluvia.
    sin = client.post("/decide", json=order("ORD-SIN", base_pay_mxn=4.0)).json()
    client.post("/shock", json={"shock_type": "rain", "duration_min": 60})
    con = client.post("/decide", json=order("ORD-CON", base_pay_mxn=4.0)).json()

    assert sin["decision"] == con["decision"] == "SKIP"

    assert con["economics"]["total_time_min"] > sin["economics"]["total_time_min"]
    assert service.state is not None and len(service.state.shocks) == 1


def test_un_shock_sin_turno_es_conflicto(api):
    client, _ = api
    assert client.post("/shock", json={"shock_type": "rain"}).status_code == 409
