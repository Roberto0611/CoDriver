"""La politica de Nuez: las restricciones duras no se negocian, y el resto es aritmetica."""

import pytest

import rutas
from contrato import ConfigTurno, EstadoRepartidor, Oferta, Punto
from nuez import politica_nuez
from sim import CAPACIDAD, Parada, _punto, simular

TEC_I = rutas.puntos_de("Tec")[0]
TEC = rutas.COORD_DE[TEC_I]


def cfg(**kw) -> ConfigTurno:
    base = dict(
        duracion_min=120,
        ancla=Punto("Tec", *TEC),
        margen_min=10,
        vehiculo="moto",
        hora_inicio=14,
        seed=0,
    )
    return ConfigTurno(**{**base, **kw})


def estado(t_restante: int = 120, mochila=()) -> EstadoRepartidor:
    return EstadoRepartidor(
        t=120 - t_restante, t_restante=t_restante, pos=_punto(TEC_I), mochila=list(mochila)
    )


def oferta(pickup: int, dropoff: int, pago: float, surge: float = 1.0) -> Oferta:
    return Oferta("o_test", "rappi", pago, surge, 0, 5, _punto(pickup), _punto(dropoff))


def test_de_noche_no_manda_a_zona_insegura_ni_por_mucho_dinero():
    escobedo = rutas.puntos_de("Escobedo")[0]
    nueva, dec = politica_nuez(
        oferta(TEC_I, escobedo, pago=900.0), estado(), [], cfg(hora_inicio=23)
    )
    assert nueva is None
    assert dec.accion == "saltar"
    assert dec.restriccion == "zona_insegura"


def test_no_acepta_lo_que_no_deja_volver_a_clase():
    apodaca = rutas.puntos_de("Apodaca")[0]
    nueva, dec = politica_nuez(oferta(TEC_I, apodaca, pago=900.0), estado(t_restante=15), [], cfg())
    assert nueva is None
    assert dec.restriccion == "regreso_infactible"


def test_mochila_llena_es_restriccion():
    """La capacidad cuenta pedidos EN VUELO, o sea los que siguen en la ruta.

    Un pedido ya recogido no aparece en `mochila` pero su dropoff sigue pendiente
    y ocupa lugar, asi que la restriccion se mide sobre la ruta, no sobre mochila.
    """
    otro_tec = rutas.puntos_de("Tec")[1]
    ruta_llena = [
        Parada("dropoff", rutas.puntos_de("Tec")[i + 2], f"o_{i}") for i in range(CAPACIDAD)
    ]
    nueva, dec = politica_nuez(oferta(TEC_I, otro_tec, pago=900.0), estado(), ruta_llena, cfg())
    assert nueva is None
    assert dec.restriccion == "mochila_llena"


def test_acepta_lo_que_rinde_mas_que_sus_minutos():
    otro_tec = rutas.puntos_de("Tec")[1]
    nueva, dec = politica_nuez(oferta(TEC_I, otro_tec, pago=500.0), estado(), [], cfg())
    assert dec.accion == "aceptar"
    assert dec.restriccion is None
    assert dec.terminos["ventaja"] > 0
    assert nueva is not None
    # `listo_en` lo pone la politica para que el ruteo cuente la espera del restaurante.
    assert [(p.tipo, p.punto, p.oferta_id) for p in nueva] == [
        ("pickup", TEC_I, "o_test"),
        ("dropoff", otro_tec, "o_test"),
    ]


def test_salta_lo_que_paga_menos_que_sus_minutos():
    otro_tec = rutas.puntos_de("Tec")[1]
    nueva, dec = politica_nuez(oferta(TEC_I, otro_tec, pago=0.5), estado(), [], cfg())
    assert nueva is None
    assert dec.accion == "saltar"
    assert dec.restriccion is None
    assert dec.terminos["ventaja"] < 0
    assert "rinden" in dec.razon


def test_los_terminos_traen_el_costo_de_oportunidad():
    otro_tec = rutas.puntos_de("Tec")[1]
    _, dec = politica_nuez(oferta(TEC_I, otro_tec, pago=100.0), estado(), [], cfg())
    assert {"pago_neto", "minutos", "por_minuto", "precio_tiempo", "ventaja"} <= set(dec.terminos)
    assert (
        abs(dec.terminos["ventaja"] - (dec.terminos["pago_neto"] - dec.terminos["precio_tiempo"]))
        < 0.11
    )


@pytest.mark.parametrize("seed", range(1000, 1010))
def test_nuez_siempre_llega_a_clase_en_turnos_frescos(seed):
    res = simular(cfg(seed=seed), politica_nuez)
    assert not res.llego_tarde
    assert res.ganado >= 0
