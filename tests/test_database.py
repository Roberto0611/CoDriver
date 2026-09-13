"""TigerData recibe una copia de decisiones sin cambiar el contrato del JSONL."""

from pathlib import Path

from backendruta import database


def decision() -> dict:
    return {
        "event": "decision",
        "sim_time": "2026-03-21T14:30:00",
        "order_id": "ORD-42",
        "decision": "SKIP",
        "binding_constraint": "heat_rule",
        "reason": "Heat limit reached.",
        "inputs": {"time_remaining_min": 90},
    }


def test_decision_record_conserva_el_evento_completo_y_columnas_consultables():
    record = database._decision_record(decision(), Path("cache/courier/shift.jsonl"))

    assert record["order_id"] == "ORD-42"
    assert record["decision"] == "SKIP"
    assert record["binding_constraint"] == "heat_rule"
    assert record["log_path"] == str(Path("cache/courier/shift.jsonl"))
    assert '"time_remaining_min": 90' in record["payload"]


def test_solo_las_decisiones_entran_a_la_cola(monkeypatch):
    records = []
    workers = []
    monkeypatch.setattr(database, "_start_decision_worker", lambda: workers.append(True))
    monkeypatch.setattr(
        database._DECISION_QUEUE, "put_nowait", lambda record: records.append(record)
    )

    database.enqueue_decision({"event": "position_update"}, Path("turno.jsonl"))
    assert records == []
    assert workers == []

    database.enqueue_decision(decision(), Path("turno.jsonl"))
    assert records[0]["order_id"] == "ORD-42"
    assert workers == [True]
