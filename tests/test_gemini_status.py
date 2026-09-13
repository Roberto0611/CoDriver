"""Lo que la pantalla lee de Gemini: el badge y la nota salen de `/shift/status`.

El badge no puede mentir. `degraded` en False no basta para decir "Gemini activo":
antes de la primera respuesta tambien es False. Por eso el estado publico trae la
fuente de la estrategia vigente, y estos tests fijan que cada caso se distinga.
"""

import threading
import time

import pytest

from backendruta.strategy import CapaEstrategia, ModeloNoDisponible


def gemini_doble(_contexto):
    return {"margen_mxn": 3.0, "nota": "llueve en Centro, conviene quedarse cerca"}


def caido(_contexto):
    raise ModeloNoDisponible("sin credencial")


def test_antes_de_la_primera_vuelta_no_hay_nada_que_presumir():
    capa = CapaEstrategia(gemini_doble, fuente="gemini")
    estado = capa.estado_publico()
    assert {clave: estado[clave] for clave in estado if clave != "gemini_usage"} == {
        "degraded": False,
        "strategy_source": "base",
        "strategy_note": None,
        "strategy_running": False,
    }, "sin respuesta todavia: ni degradado ni gemini, y sin nota"
    assert estado["gemini_usage"]["calls"] == 0


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
    estado = capa.estado_publico()
    assert {clave: estado[clave] for clave in estado if clave != "gemini_usage"} == {
        "degraded": False,
        "strategy_source": "base",
        "strategy_note": None,
        "strategy_running": False,
    }
    assert estado["gemini_usage"]["calls"] == 2


def test_una_respuesta_tardia_no_se_cuela_despues_de_detener():
    capa = CapaEstrategia(gemini_doble, fuente="gemini")
    capa.detener()
    capa.refrescar()  # el hilo que no alcanzo a salir del join
    assert capa.estado_publico()["strategy_source"] == "base"
    capa.proveedor = caido
    capa.refrescar()
    assert capa.estado_publico()["degraded"] is False


def _esperar(condicion, segundos: float = 5.0) -> None:
    limite = time.monotonic() + segundos
    while not condicion():
        assert time.monotonic() < limite, "el hilo no llego a tiempo"
        time.sleep(0.01)


def test_un_hilo_atorado_no_le_escribe_encima_al_turno_siguiente():
    """Gemini se atora, el juez arranca otro turno sin cerrar: lo viejo se tira."""
    suelta = threading.Event()
    llamadas: list[int] = []

    def lento(_contexto):
        llamadas.append(1)
        if len(llamadas) == 1:
            suelta.wait(5)  # el turno viejo sigue esperando a Gemini
            return {"margen_mxn": 9.0, "nota": "del turno viejo"}
        return {"margen_mxn": 2.0, "nota": "del turno nuevo"}

    capa = CapaEstrategia(lento, fuente="gemini", intervalo=60)
    capa.arrancar()
    _esperar(lambda: len(llamadas) == 1)
    viejo = capa._hilo
    assert viejo is not None

    capa.arrancar()  # /shift/start otra vez, sin /shift/end
    _esperar(lambda: capa.estado_publico()["strategy_note"] == "del turno nuevo")

    suelta.set()
    viejo.join(5)
    assert not viejo.is_alive(), "el hilo soltado sale en vez de seguir llamando a Gemini"
    assert capa.estado_publico()["strategy_note"] == "del turno nuevo"
    assert len(llamadas) == 2
    capa.detener()


def test_arrancar_otro_turno_sin_cerrar_vuelve_a_base():
    capa = CapaEstrategia(caido, fuente="gemini", intervalo=60)
    capa.arrancar()
    _esperar(lambda: capa.estado_publico()["degraded"])

    def todavia_no(_contexto):
        time.sleep(1)  # el turno nuevo aun no contesta
        return {}

    capa.proveedor = todavia_no
    capa.arrancar()
    estado = capa.estado_publico()
    assert {clave: estado[clave] for clave in estado if clave != "gemini_usage"} == {
        "degraded": False,
        "strategy_source": "base",
        "strategy_note": None,
        "strategy_running": True,
    }
    assert estado["gemini_usage"]["calls"] == 0, "el contador es por turno"
    capa.detener()


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
    # Hilo que sale en seguida: arrancar/detener corren de verdad, pero las vueltas
    # se dan a mano para que el orden sea determinista.
    monkeypatch.setattr(servicio.estrategia, "_ciclo", lambda _alto: None)
    servicio.estrategia.proveedor = gemini_doble
    servicio.estrategia.fuente = "gemini"
    monkeypatch.setattr(courier_api, "service", servicio)
    app = FastAPI()
    app.include_router(courier_api.router)
    return TestClient(app), servicio


def test_status_sin_turno_trae_los_campos_de_gemini(api):
    cliente, _ = api
    estado = cliente.get("/shift/status").json()
    assert {clave: estado[clave] for clave in estado if clave != "gemini_usage"} == {
        "active": False,
        "degraded": False,
        "strategy_source": "base",
        "strategy_note": None,
        "strategy_running": False,
    }
    assert estado["gemini_usage"]["calls"] == 0


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
    assert antes["strategy_running"] is True
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
    assert cerrado["active"] is True, "el adaptador conserva el turno cerrado..."
    assert cerrado["strategy_running"] is False, "...y esto es lo que dice que ya no esta vivo"
