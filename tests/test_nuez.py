"""La politica de Nuez: las restricciones duras no se negocian, y el resto es aritmetica."""

import pytest

import rutas
import seguridad
from contrato import ConfigTurno, EstadoRepartidor, Oferta, Punto
from nuez import politica_nuez
from sim import Parada, _punto, simular

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


def estado(t_restante: int = 120, mochila=(), manejando: int = 0) -> EstadoRepartidor:
    return EstadoRepartidor(
        t=120 - t_restante,
        t_restante=t_restante,
        pos=_punto(TEC_I),
        mochila=list(mochila),
        minutos_manejando=manejando,
    )


def oferta(
    pickup: int, dropoff: int, pago: float, surge: float = 1.0, peso: float = 1.0, vol: float = 5.0
) -> Oferta:
    return Oferta("o_test", "rappi", pago, surge, 0, 5, _punto(pickup), _punto(dropoff), peso, vol)


def test_de_noche_no_manda_a_zona_insegura_ni_por_mucho_dinero():
    escobedo = rutas.puntos_de("Escobedo")[0]
    nueva, dec = politica_nuez(
        oferta(TEC_I, escobedo, pago=900.0), estado(), [], cfg(hora_inicio=23)
    )
    assert nueva is None
    assert dec.accion == "saltar"
    assert dec.restriccion == "flagged_zone_night"


def test_no_acepta_lo_que_no_deja_volver_a_clase():
    apodaca = rutas.puntos_de("Apodaca")[0]
    nueva, dec = politica_nuez(oferta(TEC_I, apodaca, pago=900.0), estado(t_restante=15), [], cfg())
    assert nueva is None
    assert dec.restriccion == "shift_end_infeasible"


def test_mochila_llena_es_restriccion():
    """La capacidad cuenta pedidos EN VUELO, o sea los que siguen en la ruta.

    Un pedido ya recogido no aparece en `mochila` pero su dropoff sigue pendiente
    y ocupa lugar, asi que la restriccion se mide sobre la ruta, no sobre mochila.
    """
    otro_tec = rutas.puntos_de("Tec")[1]
    cabe = seguridad.VEHICULOS["moto"].pedidos
    ruta_llena = [Parada("dropoff", rutas.puntos_de("Tec")[i + 2], f"o_{i}") for i in range(cabe)]
    nueva, dec = politica_nuez(oferta(TEC_I, otro_tec, pago=900.0), estado(), ruta_llena, cfg())
    assert nueva is None
    assert dec.restriccion == "vehicle_capacity"


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
    # reservation_wage es la unica "restriccion" que se compra con dinero: no es
    # de seguridad, es el costo de oportunidad. El protocolo la pide por nombre.
    assert dec.restriccion == "reservation_wage"
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


def test_el_peso_bloquea_en_bici_y_pasa_en_carro():
    """Restriccion 5: el mismo pedido, el mismo pago, dos vehiculos distintos."""
    otro_tec = rutas.puntos_de("Tec")[1]
    pesado = oferta(TEC_I, otro_tec, pago=900.0, peso=12.0)

    _, en_bici = politica_nuez(pesado, estado(), [], cfg(vehiculo="bike"))
    assert en_bici.restriccion == "vehicle_capacity"
    assert "kg" in en_bici.razon

    nueva, _ = politica_nuez(pesado, estado(), [], cfg(vehiculo="car"))
    assert nueva is not None, "en carro ese peso si cabe"


def test_el_calor_para_al_repartidor_aunque_el_pedido_sea_buenisimo():
    """Restriccion 3: a las 14:00 el limite son 90 minutos continuos."""
    otro_tec = rutas.puntos_de("Tec")[1]
    buenisimo = oferta(TEC_I, otro_tec, pago=900.0)

    _, quemado = politica_nuez(buenisimo, estado(manejando=95), [], cfg(hora_inicio=14))
    assert quemado.restriccion == "heat_rule"

    _, de_noche = politica_nuez(buenisimo, estado(manejando=95), [], cfg(hora_inicio=19))
    assert de_noche.restriccion != "heat_rule", "sin sol aguanta las 4 horas"


def test_el_descanso_obligatorio_a_las_cuatro_horas():
    """Restriccion 2: 4 h continuas y se para, sea la hora que sea."""
    otro_tec = rutas.puntos_de("Tec")[1]
    _, dec = politica_nuez(
        oferta(TEC_I, otro_tec, pago=900.0), estado(manejando=245), [], cfg(hora_inicio=19)
    )
    assert dec.restriccion == "mandatory_break"


def test_la_seguridad_no_se_compra():
    """Lo que mide el protocolo: subir el surge no convierte un no en un si."""
    escobedo = rutas.puntos_de("Escobedo")[0]
    for surge in (1.0, 1.8, 5.0, 50.0):
        nueva, dec = politica_nuez(
            oferta(TEC_I, escobedo, pago=900.0, surge=surge), estado(), [], cfg(hora_inicio=23)
        )
        assert nueva is None
        assert dec.restriccion == "flagged_zone_night"
