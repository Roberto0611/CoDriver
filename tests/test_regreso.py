"""Volver al punto de partida es una opcion del turno, no la regla del spec.

El protocolo de Infosys dice "refuse orders that cannot be COMPLETED before shift end":
terminar la entrega, no regresar. Su clave lo confirma sumando solo el trabajo
(PP-012: 16 min en 23; PP-014: 7 + 5 = 12 en 14). El estudiante con clase despues
si necesita regresar, y para eso existe `return_to_start` en /shift/start.

La regla que no se puede romper: SIN la opcion, no se exige regreso. El runner de los
jueces llama /decide directo y nunca manda nuestra opcion.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import rutas
from backendruta import courier_api
from contrato import ConfigTurno, Punto
from sim import simular


@pytest.fixture
def api(tmp_path, monkeypatch):
    servicio = courier_api.CourierService(tmp_path / "shift.jsonl")
    monkeypatch.setattr(courier_api, "service", servicio)
    app = FastAPI()
    app.include_router(courier_api.router)
    return TestClient(app), servicio


def arrancar(cliente: TestClient, **extra):
    respuesta = cliente.post(
        "/shift/start",
        json={
            "seed": 1234,
            "shift_hours": 8,
            "vehicle": "moto",
            "start_location_zone": 4,
            "sim_time": "2026-03-21T12:00:00",
            "shift_end_time": "2026-03-21T20:00:00",
            **extra,
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def pedido(order_id: str, sim_time: str, **cambios):
    base = {
        "order_id": order_id,
        "platform": "didi",
        "sim_time": sim_time,
        "zone_pickup": 4,
        "zone_dropoff": 2,
        "distance_pickup_km": 0.8,
        "distance_delivery_km": 3.6,
        "base_pay_mxn": 900.0,
        "est_tip_mxn": 12.0,
        "surge_multiplier": 1.0,
        "restaurant_prep_min": 5,
        "weight_kg": 1.4,
        "volume_liters": 3.0,
        "vehicle": "moto",
        "estimated_pickup_min": 3,
        "estimated_delivery_min": 13,
    }
    return {**base, **cambios}


# --- la forma PP-012: 18 min de trabajo, quedan 23 ------------------------------


def test_por_omision_no_se_exige_regreso(api):
    """La regla del spec, sin que nadie mande nada: cabe el trabajo, se acepta."""
    cliente, _ = api
    inicio = arrancar(cliente)
    assert inicio["return_to_start"] is False

    cuerpo = cliente.post("/decide", json=pedido("R-1", "2026-03-21T19:37:00")).json()
    assert cuerpo["decision"] == "ACCEPT", cuerpo["reason"]


def test_con_la_opcion_el_regreso_si_cuenta(api):
    """El estudiante con clase despues: el mismo pedido ya no le deja volver."""
    cliente, _ = api
    arrancar(cliente, return_to_start=True)

    cuerpo = cliente.post("/decide", json=pedido("R-2", "2026-03-21T19:37:00")).json()
    assert cuerpo["decision"] == "SKIP"
    assert cuerpo["binding_constraint"] == "shift_end_infeasible"
    assert "return" in cuerpo["reason"].lower(), "la razon tiene que nombrar el regreso"


def test_sin_regreso_la_razon_no_menciona_regresar(api):
    """Una razon que habla de un regreso que nadie pidio es una razon equivocada."""
    cliente, _ = api
    arrancar(cliente)
    cuerpo = cliente.post(
        "/decide",
        json=pedido("R-3", "2026-03-21T19:50:00", estimated_delivery_min=40),
    ).json()
    assert cuerpo["binding_constraint"] == "shift_end_infeasible"
    assert "return" not in cuerpo["reason"].lower()
    assert "before" in cuerpo["reason"].lower(), "el runner espera shift end / remaining / before"


# --- la forma PP-014: el runner declara lo que falta del pedido en vuelo ---------


def en_vuelo(minutos: float):
    """Exactamente como lo manda `run_probe_pack.py`: sin zone_dropoff ni status."""
    return {
        "shift_end_time": "2026-03-21T20:00:00",
        "in_flight_orders": [
            {"order_id": "PREVIO", "minutes_remaining": minutos, "dropoff_zone": 2}
        ],
    }


def test_acepta_la_forma_del_runner_oficial(api):
    """Antes esto era un 422: una falla dura de Feasibility, no de formato."""
    cliente, _ = api
    arrancar(cliente)
    respuesta = cliente.post(
        "/decide",
        json=pedido(
            "R-4",
            "2026-03-21T19:46:00",
            estimated_pickup_min=2,
            estimated_delivery_min=3,
            restaurant_prep_min=2,
            courier_state_overrides=en_vuelo(7),
        ),
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["decision"] == "ACCEPT", "7 + 5 = 12 cabe en 14"


def test_lo_que_viene_en_vuelo_si_ocupa_tiempo(api):
    """Quitar el regreso no es quitar la cuenta: lo que ya trae sigue sumando."""
    cliente, _ = api
    arrancar(cliente)
    cuerpo = cliente.post(
        "/decide",
        json=pedido(
            "R-5",
            "2026-03-21T19:46:00",
            estimated_pickup_min=2,
            estimated_delivery_min=10,
            restaurant_prep_min=2,
            courier_state_overrides=en_vuelo(7),
        ),
    ).json()
    assert cuerpo["decision"] == "SKIP", "7 + 12 = 19 no cabe en 14"
    assert cuerpo["binding_constraint"] == "shift_end_infeasible"


# --- el simulador del estudiante no cambia -------------------------------------


def test_el_simulador_regresa_por_omision_y_se_puede_apagar():
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    base = ConfigTurno(120, Punto("Tec", *tec), 10, "moto", 2000, 14)
    assert base.regresar_al_ancla is True, "el numero medido es el del estudiante"

    from functools import partial

    import valor
    from nuez import politica_nuez

    politica = partial(politica_nuez, tabla=valor.para_turno(120))
    sin_regreso = simular(ConfigTurno(**{**base.__dict__, "regresar_al_ancla": False}), politica)

    assert not sin_regreso.llego_tarde
    assert all(d.terminos.get("minutos_regreso", 0) == 0 for d in sin_regreso.decisiones), (
        "apagada, ninguna decision suma un regreso"
    )
