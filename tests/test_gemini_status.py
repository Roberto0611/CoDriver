"""Lo que la pantalla lee de Gemini: el badge y la nota salen de `/shift/status`.

El badge no puede mentir. `degraded` en False no basta para decir "Gemini activo":
antes de la primera respuesta tambien es False. Por eso el estado publico trae la
fuente de la estrategia vigente, y estos tests fijan que cada caso se distinga.
"""

import pytest

from backendruta.strategy import CapaEstrategia, ModeloNoDisponible


def gemini_doble(_contexto):
    return {"margen_mxn": 3.0, "nota": "llueve en Centro, conviene quedarse cerca"}


def caido(_contexto):
    raise ModeloNoDisponible("sin credencial")


def test_antes_de_la_primera_vuelta_no_hay_nada_que_presumir():
    capa = CapaEstrategia(gemini_doble, fuente="gemini")
    assert capa.estado_publico() == {
        "degraded": False,
        "strategy_source": "base",
        "strategy_note": None,
    }, "sin respuesta todavia: ni degradado ni gemini, y sin nota"


def test_con_respuesta_sale_la_fuente_y_la_nota():
    capa = CapaEstrategia(gemini_doble, fuente="gemini")
    capa.refrescar()
    estado = capa.estado_publico()
    assert estado["degraded"] is False
    assert estado["strategy_source"] == "gemini"
    assert estado["strategy_note"] == "llueve en Centro, conviene quedarse cerca"


def test_caido_conserva_la_ultima_nota_y_lo_marca():
    capa = CapaEstrategia(gemini_doble, fuente="gemini")
    capa.refrescar()
    capa.proveedor = caido
    capa.refrescar()
    estado = capa.estado_publico()
    assert estado["degraded"] is True
    assert estado["strategy_source"] == "gemini_vieja"
    assert estado["strategy_note"] == "llueve en Centro, conviene quedarse cerca", (
        "es la nota de la estrategia con la que el motor sigue decidiendo"
    )


def test_sin_turno_no_hay_nota():
    capa = CapaEstrategia(gemini_doble, fuente="gemini")
    capa.refrescar()
    assert capa.estado_publico(en_turno=False)["strategy_note"] is None


def test_al_detener_vuelve_a_base_y_no_presume_gemini():
    """Sin hilo no hay modelo: ni badge verde, ni nota vieja, ni degradado heredado."""
    capa = CapaEstrategia(gemini_doble, fuente="gemini")
    capa.refrescar()
    capa.proveedor = caido
    capa.refrescar()
    assert capa.estado_publico()["degraded"] is True

    capa.detener()
    assert capa.estado_publico() == {
        "degraded": False,
        "strategy_source": "base",
        "strategy_note": None,
    }


def test_una_respuesta_tardia_no_se_cuela_despues_de_detener():
    capa = CapaEstrategia(gemini_doble, fuente="gemini")
    capa.detener()
    capa.refrescar()  # el hilo que no alcanzo a salir del join
    assert capa.estado_publico()["strategy_source"] == "base"
    capa.proveedor = caido
    capa.refrescar()
    assert capa.estado_publico()["degraded"] is False


def test_una_nota_vacia_sale_como_none():
    capa = CapaEstrategia(lambda _c: {"margen_mxn": 2.0}, fuente="gemini")
    capa.refrescar()
    assert capa.estado_publico()["strategy_note"] is None


# --- de punta a punta: lo que el front recibe ---------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backendruta import courier_api

    servicio = courier_api.CourierService(tmp_path / "shift.jsonl")
    # Sin hilo: las vueltas se dan a mano para que el orden sea determinista.
    monkeypatch.setattr(servicio.estrategia, "arrancar", lambda: None)
    servicio.estrategia.proveedor = gemini_doble
    servicio.estrategia.fuente = "gemini"
    monkeypatch.setattr(courier_api, "service", servicio)
    app = FastAPI()
    app.include_router(courier_api.router)
    return TestClient(app), servicio


def test_status_sin_turno_trae_los_campos_de_gemini(api):
    cliente, _ = api
    assert cliente.get("/shift/status").json() == {
        "active": False,
        "degraded": False,
        "strategy_source": "base",
        "strategy_note": None,
    }


def test_status_en_turno_ensena_la_nota_y_el_degradado(api):
    cliente, servicio = api
    cliente.post(
        "/shift/start",
        json={
            "seed": 1234,
            "shift_hours": 8,
            "vehicle": "moto",
            "start_location_zone": 4,
            "sim_time": "2026-03-21T12:00:00",
        },
    )
    antes = cliente.get("/shift/status").json()
    assert antes["active"] is True
    assert (antes["degraded"], antes["strategy_source"], antes["strategy_note"]) == (
        False,
        "base",
        None,
    )

    servicio.estrategia.refrescar()
    vivo = cliente.get("/shift/status").json()
    assert vivo["strategy_source"] == "gemini"
    assert vivo["strategy_note"] == "llueve en Centro, conviene quedarse cerca"
    assert vivo["elapsed_min"] == 0, "los campos de siempre siguen ahi"

    servicio.estrategia.proveedor = caido
    servicio.estrategia.refrescar()
    abajo = cliente.get("/shift/status").json()
    assert abajo["degraded"] is True
    assert abajo["strategy_note"] == "llueve en Centro, conviene quedarse cerca"

    cliente.post("/shift/end")
    cerrado = cliente.get("/shift/status").json()
    assert (cerrado["degraded"], cerrado["strategy_source"], cerrado["strategy_note"]) == (
        False,
        "base",
        None,
    ), "con el turno cerrado el badge no puede seguir diciendo que Gemini habla"
