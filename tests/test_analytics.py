"""El front recibe un resumen de decisiones, no SQL ni eventos crudos."""

from backendruta.analytics import resumir


def evento(order_id, decision, constraint, net_pay, minute):
    return {
        "event": "decision",
        "sim_time": f"2026-03-21T14:{minute:02d}:00",
        "order_id": order_id,
        "decision": decision,
        "reason": f"Reason for {order_id}",
        "binding_constraint": constraint,
        "inputs": {"economics": {"net_pay_mxn": net_pay}},
    }


def test_resumir_arma_metricas_y_linea_de_tiempo_ordenada():
    summary = resumir(
        [
            evento("ORD-2", "SKIP", "heat_rule", 80, 20),
            evento("ORD-1", "ACCEPT", None, 50, 10),
            evento("ORD-3", "ACCEPT", None, 60, 30),
        ]
    )

    assert summary == {
        "total_decisions": 3,
        "accepted": 2,
        "skipped": 1,
        "accept_rate_pct": 66.67,
        "by_constraint": {"heat_rule": 1, "opportunity_cost": 2},
        "accepted_net_mxn": 110.0,
        "timeline": [
            {
                "sim_time": "2026-03-21T14:10:00",
                "order_id": "ORD-1",
                "decision": "ACCEPT",
                "reason": "Reason for ORD-1",
                "binding_constraint": None,
                "net_pay_mxn": 50.0,
            },
            {
                "sim_time": "2026-03-21T14:20:00",
                "order_id": "ORD-2",
                "decision": "SKIP",
                "reason": "Reason for ORD-2",
                "binding_constraint": "heat_rule",
                "net_pay_mxn": 80.0,
            },
            {
                "sim_time": "2026-03-21T14:30:00",
                "order_id": "ORD-3",
                "decision": "ACCEPT",
                "reason": "Reason for ORD-3",
                "binding_constraint": None,
                "net_pay_mxn": 60.0,
            },
        ],
    }


def test_endpoint_usa_jsonl_si_tigerdata_no_esta_disponible(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backendruta import analytics, courier_api
    from backendruta.event_log import EventLog

    path = tmp_path / "shift.jsonl"
    log = EventLog(path)
    log.start({"event": "shift_start", "sim_time": "2026-03-21T14:00:00"})
    log.append(evento("ORD-1", "ACCEPT", None, 50, 10))
    monkeypatch.setattr(courier_api, "service", courier_api.CourierService(path))
    monkeypatch.setattr(analytics, "_from_tigerdata", lambda _: None)
    app = FastAPI()
    app.include_router(analytics.router)

    response = TestClient(app).get("/analytics/shift")
    assert response.status_code == 200
    assert response.json()["source"] == "jsonl"
    assert response.json()["accepted_net_mxn"] == 50.0
