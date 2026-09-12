"""Los rivales son simples, deterministas y tan seguros como Nuez."""

import pytest

import rutas
import seguridad
from baselines import (
    PAGO_ALTO_MIN_MXN,
    PICKUP_CERCANO_MAX_MIN,
    POLITICAS,
    politica_accept_all,
    politica_highest_pay,
    politica_nearest_first,
)
from contrato import ConfigTurno, EstadoRepartidor, Oferta, Punto
from sim import Parada, _punto, simular

TEC_I = rutas.puntos_de("Tec")[0]
TEC = rutas.COORD_DE[TEC_I]
POLITICAS_LISTA = tuple(POLITICAS.values())


def cfg(**changes) -> ConfigTurno:
    base = {
        "duracion_min": 120,
        "ancla": Punto("Tec", *TEC),
        "margen_min": 10,
        "vehiculo": "moto",
        "hora_inicio": 14,
        "seed": 0,
    }
    return ConfigTurno(**{**base, **changes})


def estado(**changes) -> EstadoRepartidor:
    base = {"t": 0, "t_restante": 120, "pos": _punto(TEC_I), "minutos_manejando": 0}
    return EstadoRepartidor(**{**base, **changes})


def oferta(pickup: int, dropoff: int, pago: float) -> Oferta:
    return Oferta("o_test", "rappi", pago, 1.0, 0, 0, _punto(pickup), _punto(dropoff))


def test_las_tres_politicas_estan_registradas():
    assert set(POLITICAS) == {"AcceptAll", "HighestPay", "NearestFirst"}


def test_accept_all_acepta_un_pedido_factible_aunque_pague_poco():
    otro_tec = rutas.puntos_de("Tec")[1]
    ruta, decision = politica_accept_all(oferta(TEC_I, otro_tec, 1.0), estado(), [], cfg())
    assert ruta is not None
    assert decision.accion == "aceptar"


def test_highest_pay_solo_usa_pago_total_fijo():
    otro_tec = rutas.puntos_de("Tec")[1]
    _, bajo = politica_highest_pay(oferta(TEC_I, otro_tec, 1.0), estado(), [], cfg())
    ruta, alto = politica_highest_pay(
        oferta(TEC_I, otro_tec, PAGO_ALTO_MIN_MXN + 100), estado(), [], cfg()
    )
    assert bajo.restriccion == "reservation_wage"
    assert ruta is not None
    assert alto.accion == "aceptar"
    assert "tiempo" in bajo.razon


def test_nearest_first_ignora_pago_pero_rechaza_pickup_lejano():
    otro_tec = rutas.puntos_de("Tec")[1]
    ruta, cerca = politica_nearest_first(oferta(TEC_I, otro_tec, 1.0), estado(), [], cfg())
    assert ruta is not None
    assert cerca.accion == "aceptar"

    apodaca = rutas.puntos_de("Apodaca")[0]
    otro_apodaca = rutas.puntos_de("Apodaca")[1]
    _, lejos = politica_nearest_first(
        oferta(apodaca, otro_apodaca, 9_000),
        estado(t_restante=480),
        [],
        cfg(duracion_min=480),
    )
    assert lejos.restriccion is None
    assert lejos.terminos["minutos_hasta_pickup"] > PICKUP_CERCANO_MAX_MIN
    assert lejos.accion == "saltar"


@pytest.mark.parametrize("politica", POLITICAS_LISTA)
def test_los_rivales_no_venden_seguridad_por_dinero(politica):
    escobedo = rutas.puntos_de("Escobedo")[0]
    nueva, decision = politica(oferta(TEC_I, escobedo, 90_000), estado(), [], cfg(hora_inicio=23))
    assert nueva is None
    assert decision.accion == "saltar"
    assert decision.restriccion == "flagged_zone_night"


@pytest.mark.parametrize("politica", POLITICAS_LISTA)
def test_los_rivales_respetan_calor_y_capacidad(politica):
    otro_tec = rutas.puntos_de("Tec")[1]
    _, quemado = politica(oferta(TEC_I, otro_tec, 90_000), estado(minutos_manejando=95), [], cfg())
    assert quemado.restriccion == "heat_rule"

    llenas = [Parada("dropoff", otro_tec, f"o_{number}") for number in range(3)]
    _, lleno = politica(oferta(TEC_I, otro_tec, 90_000), estado(), llenas, cfg())
    assert lleno.restriccion == "vehicle_capacity"
    assert seguridad.VEHICULOS["moto"].pedidos == 3


@pytest.mark.parametrize("politica", POLITICAS_LISTA)
@pytest.mark.parametrize("seed", range(5))
def test_los_rivales_son_deterministas_y_regresan_a_tiempo(politica, seed):
    uno = simular(cfg(seed=seed), politica)
    dos = simular(cfg(seed=seed), politica)
    assert uno.ganado == dos.ganado
    assert [d.accion for d in uno.decisiones] == [d.accion for d in dos.decisiones]
    assert not uno.llego_tarde
