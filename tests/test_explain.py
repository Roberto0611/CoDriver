"""explain_decision responde desde el registro, con numeros y alternativas, sin re-decidir."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backendruta import courier_api, explain
from tests.test_courier_api import order, start


@pytest.fixture
def api(tmp_path, monkeypatch):
    service = courier_api.CourierService(tmp_path / "shift.jsonl")
    monkeypatch.setattr(courier_api, "service", service)
    app = FastAPI()
    app.include_router(courier_api.router)
    return TestClient(app), service


def _turno(client):
    """Tres pedidos: uno por calor, uno bueno y uno que no paga sus minutos."""
    start(client)
    payloads = [
        order(
            "ORD-HEAT",
            sim_time="2026-03-21T12:30:00",
            base_pay_mxn=90_000,
            courier_state_overrides={"continuous_riding_min": 95},
        ),
        order("ORD-RICH", sim_time="2026-03-21T19:00:00", base_pay_mxn=90_000),
        order("ORD-POOR", sim_time="2026-03-21T19:00:00", base_pay_mxn=1, est_tip_mxn=0),
    ]
    return {p["order_id"]: client.post("/decide", json=p).json() for p in payloads}


def test_la_explicacion_trae_lo_que_pide_el_protocolo(api):
    client, _ = api
    decisions = _turno(client)
    for order_id, decided in decisions.items():
        body = client.get(f"/explain/{order_id}").json()
        assert set(explain.REQUIRED) <= set(body)
        assert body["decision"] == decided["decision"]
        assert body["reason"] == decided["reason"]
        assert body["binding_constraint"] == decided["binding_constraint"]
        assert body["alternatives_considered"]
        for alt in body["alternatives_considered"]:
            assert alt["option"] and alt["rejected_because"]
        inputs = body["inputs"]
        for key in ("position_zone", "time_remaining_min", "time_to_completion_min"):
            assert inputs[key] is not None
        assert inputs["strategy"]["policy"] == "nuez_opportunity_cost"
        assert "in_flight_orders" in inputs


def test_cada_tipo_de_decision_nombra_su_alternativa(api):
    client, _ = api
    decisions = _turno(client)
    assert decisions["ORD-HEAT"]["binding_constraint"] == "heat_rule"
    assert decisions["ORD-RICH"]["decision"] == "ACCEPT"
    assert decisions["ORD-POOR"]["binding_constraint"] == "reservation_wage"

    heat = client.get("/explain_decision/ORD-HEAT").json()["alternatives_considered"]
    assert "heat_rule" in heat[0]["rejected_because"]
    assert "95" in heat[0]["rejected_because"]
    assert "cannot be bought" in heat[1]["rejected_because"]

    rich = client.get("/explain/ORD-RICH").json()["alternatives_considered"]
    assert rich[0]["option"].startswith("SKIP")

    poor = client.get("/explain/ORD-POOR").json()["alternatives_considered"]
    assert poor == [poor[0]] and poor[0]["option"] == "ACCEPT"
    assert "reservation wage" in poor[0]["rejected_because"]


def test_leer_del_archivo_da_lo_mismo_que_la_memoria(api):
    client, service = api
    _turno(client)
    from_log = explain.ExplainIndex.from_log(service.log.path)
    for order_id in ("ORD-HEAT", "ORD-RICH", "ORD-POOR"):
        in_memory = json.loads(json.dumps(service.explanations.get(order_id)))
        assert from_log.get(order_id) == in_memory


def test_tras_reiniciar_el_proceso_responde_desde_el_log(api, monkeypatch):
    client, service = api
    _turno(client)
    fresh = courier_api.CourierService(service.log.path)
    monkeypatch.setattr(courier_api, "service", fresh)
    body = client.get("/explain/ORD-HEAT").json()
    assert body["binding_constraint"] == "heat_rule"


def test_pedido_desconocido_da_404(api):
    client, _ = api
    _turno(client)
    assert client.get("/explain/ORD-NOPE").status_code == 404


def test_nuevo_turno_limpia_las_explicaciones(api):
    client, _ = api
    _turno(client)
    start(client)
    assert client.get("/explain/ORD-RICH").status_code == 404


def test_cli_imprime_la_explicacion(api, capsys):
    client, service = api
    _turno(client)
    assert explain.main(["ORD-POOR", "--log", str(service.log.path)]) == 0
    assert json.loads(capsys.readouterr().out)["order_id"] == "ORD-POOR"
    assert explain.main(["ORD-NOPE", "--log", str(service.log.path)]) == 1


def test_fin_de_turno_muestra_la_cuenta():
    inputs = {
        "engine_terms": {"pago_neto": 900.0, "precio_tiempo": 40.0, "minutos": 30.0},
        "continuous_riding_min": 0,
        "time_to_completion_min": 48.5,
        "shift_minutes_available": 10.0,
    }
    alts = explain.alternatives("SKIP", "shift_end_infeasible", inputs)
    assert "48.5 min" in alts[0]["rejected_because"]
    assert "10.0 min remain" in alts[0]["rejected_because"]
    assert "says ACCEPT" in alts[1]["rejected_because"]


def test_ventaja_bajo_el_minimo_no_dice_cero_abajo():
    inputs = {
        "engine_terms": {"pago_neto": 26.3, "precio_tiempo": 25.9, "minutos": 22.0},
        "strategy": {"min_edge_mxn": 1.0},
    }
    text = explain.alternatives("SKIP", "reservation_wage", inputs)[0]["rejected_because"]
    assert "only MXN 0.4 above the MXN 25.9" in text
    assert "needs MXN 1.0 above it" in text
