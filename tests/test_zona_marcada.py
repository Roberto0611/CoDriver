"""Zonas marcadas de noche: la convencion del protocolo contra nuestro mapa de riesgo.

Los numeros de zona de un stream externo no son los nuestros (en el practice pack su 8
es Mitras y nuestro 8 es San Nicolas), y el nombre es opcional "for display". Asi que
en /decide la zona marcada se decide con el numero que llega, ANTES de traducirlo, y la
unica convencion documentada es la 99.

Nuestro mapa de riesgo marca 7 de 14 zonas. En /decide eso hacia que un pedido a Santa
Catarina culpara a la zona marcada en vez del fin de turno (PP-013), y que PP-012 y
PP-014 pasaran solo porque traduciamos mal la zona. El simulador conserva su mapa.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import seguridad
from backendruta import courier_api, zonas


@pytest.fixture
def api(tmp_path, monkeypatch):
    servicio = courier_api.CourierService(tmp_path / "shift.jsonl")
    monkeypatch.setattr(courier_api, "service", servicio)
    app = FastAPI()
    app.include_router(courier_api.router)
    cliente = TestClient(app)
    respuesta = cliente.post(
        "/shift/start",
        json={
            "seed": 1234,
            "shift_hours": 8.5,
            "vehicle": "moto",
            "start_location_zone": 4,
            "sim_time": "2026-03-21T15:30:00",
            "shift_end_time": "2026-03-22T00:00:00",
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    return cliente


def decidir(cliente: TestClient, order_id: str, hora: str, dropoff: int) -> dict:
    respuesta = cliente.post(
        "/decide",
        json={
            "order_id": order_id,
            "platform": "didi",
            "sim_time": f"2026-03-21T{hora}:00",
            "zone_pickup": 4,
            "zone_dropoff": dropoff,
            "distance_pickup_km": 0.8,
            "distance_delivery_km": 3.0,
            "base_pay_mxn": 900.0,
            "surge_multiplier": 1.0,
            "restaurant_prep_min": 3,
            "weight_kg": 1.0,
            "volume_liters": 2.0,
            "vehicle": "moto",
            "estimated_pickup_min": 3,
            "estimated_delivery_min": 10,
            "courier_state_overrides": {"continuous_riding_min": 0},
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_la_convencion_del_protocolo_es_la_zona_99():
    assert zonas.MARCADAS_PROTOCOLO == frozenset({99})


def test_la_zona_99_se_bloquea_a_partir_de_las_22_en_punto(api):
    """La linea es de reloj: 21:59 se entrega, 22:00 ya no."""
    antes = decidir(api, "Z-1", "21:59", dropoff=99)
    assert antes["binding_constraint"] != "flagged_zone_night"

    despues = decidir(api, "Z-2", "22:00", dropoff=99)
    assert despues["decision"] == "SKIP"
    assert despues["binding_constraint"] == "flagged_zone_night"


def test_nuestro_mapa_ya_no_marca_zonas_en_el_endpoint(api):
    """Nuestra 12 (Santa Catarina) y nuestra 11 (Escobedo) estan marcadas en el mapa
    del simulador. En /decide son numeros de otro catalogo y no deben bloquear."""
    santa_catarina = decidir(api, "Z-3", "22:12", dropoff=12)
    assert santa_catarina["binding_constraint"] != "flagged_zone_night"
    assert santa_catarina["decision"] == "ACCEPT"

    escobedo = decidir(api, "Z-4", "23:00", dropoff=11)
    assert escobedo["binding_constraint"] != "flagged_zone_night"


@pytest.mark.parametrize(
    "cambios,esperado",
    [
        # Sin decision externa: nuestro mapa de riesgo, lo que corre el simulador.
        ({"zona_dropoff": "Escobedo", "hora": 23}, "flagged_zone_night"),
        ({"zona_dropoff": "Valle", "hora": 23}, None),
        # Con decision externa: manda el protocolo, pero sigue siendo solo de noche.
        ({"zona_dropoff": "Escobedo", "hora": 23, "zona_marcada": False}, None),
        ({"zona_dropoff": "Valle", "hora": 23, "zona_marcada": True}, "flagged_zone_night"),
        ({"zona_dropoff": "Valle", "hora": 14, "zona_marcada": True}, None),
        ({"zona_dropoff": "Valle", "hora": 4, "zona_marcada": True}, "flagged_zone_night"),
    ],
)
def test_revisar_respeta_quien_decide_la_zona_marcada(cambios, esperado):
    resultado = seguridad.caso(**cambios)
    assert (resultado[0] if resultado else None) == esperado


# --- el reloj del turno: un arranque a las 15:30 no puede atrasar la hora -------


def test_sin_shift_start_y_arranque_a_media_hora_la_noche_empieza_a_las_22(tmp_path, monkeypatch):
    """Asi llama el runner oficial: /decide directo, con `shift_elapsed_hours`.

    6.5 h transcurridas a las 22:00 significa que el turno arranco a las 15:30. Antes el
    motor contaba desde las 15:30 y a las 22:00 creia que eran las 21: aceptaba entregas
    en zona marcada. Ahora el reloj se ancla a las 15:00 y la hora sale exacta.
    """
    servicio = courier_api.CourierService(tmp_path / "shift.jsonl")
    monkeypatch.setattr(courier_api, "service", servicio)
    app = FastAPI()
    app.include_router(courier_api.router)
    cliente = TestClient(app)

    respuesta = cliente.post(
        "/decide",
        json={
            "order_id": "RELOJ-1",
            "platform": "didi",
            "sim_time": "2026-03-21T22:00:00",
            "zone_pickup": 4,
            "zone_dropoff": 99,
            "distance_pickup_km": 0.8,
            "distance_delivery_km": 3.0,
            "base_pay_mxn": 900.0,
            "surge_multiplier": 1.0,
            "restaurant_prep_min": 3,
            "weight_kg": 1.0,
            "volume_liters": 2.0,
            "vehicle": "moto",
            "estimated_pickup_min": 3,
            "estimated_delivery_min": 10,
            "courier_state_overrides": {
                "continuous_riding_min": 0,
                "shift_elapsed_hours": 6.5,
                "shift_end_time": "2026-03-21T23:30:00",
            },
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["binding_constraint"] == "flagged_zone_night"

    estado = cliente.get("/shift/status").json()
    assert estado["elapsed_min"] == 390, "se siguen reportando los minutos reales"
    assert estado["remaining_min"] == 90
