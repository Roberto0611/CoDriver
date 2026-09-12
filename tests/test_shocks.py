"""Las disrupciones: que volteen una decision, que expiren solas, y que no frenen nada.

El brief exige al menos una en vivo durante el demo. Estos son los dos momentos que
se ensayan: una oferta que se vuelve mala cuando cierran la calle, y una que se
vuelve buena cuando entra el surge. La misma oferta, el mismo minuto, un boton.
"""

import time
from functools import partial

import pytest

import rutas
import seeds
import shocks
import valor
from contrato import ConfigTurno, EstadoRepartidor, Oferta, Punto
from nuez import politica_nuez
from sim import _punto, generar_ofertas, politica_greedy, simular

TEC_I = rutas.puntos_de("Tec")[0]
TEC = rutas.COORD_DE[TEC_I]
TABLA = valor.para_turno(120)


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


def estado(t: int = 0) -> EstadoRepartidor:
    return EstadoRepartidor(t=t, t_restante=120 - t, pos=_punto(TEC_I))


def oferta(destino: int, pago: float) -> Oferta:
    return Oferta("o_test", "rappi", pago, 1.0, 0, 5, _punto(TEC_I), _punto(destino))


def decidir(o: Oferta, activos=shocks.NINGUNO):
    return politica_nuez(o, estado(), [], cfg(), tabla=TABLA, activos=activos)


# --- los dos momentos del demo ----------------------------------------------


def test_un_cierre_voltea_la_decision():
    """El mismo pedido, el mismo minuto. Cierran la calle y deja de salir."""
    fundidora = rutas.puntos_de("Fundidora")[0]
    zona = rutas.ZONA_DE[fundidora]
    # $25 es un pedido apenas rentable: es donde un cierre alcanza a voltearlo.
    o = oferta(fundidora, pago=25.0)

    nueva, antes = decidir(o)
    assert nueva is not None, "sin cierre este pedido si sale"

    cierre = shocks.Shock(0, "closure", 60, zona=zona, calle="Constitucion")
    nueva, despues = decidir(o, shocks.en(0, (cierre,)))

    assert nueva is None, "con el cierre ya no sale"
    assert despues.restriccion == "reservation_wage", "lo mata el dinero, no la seguridad"
    assert "Cerraron Constitucion" in despues.razon, "la razon nombra la disrupcion"
    assert len(despues.razon.split()) < 40
    assert despues.terminos["minutos"] > antes.terminos["minutos"], "el viaje tarda mas de verdad"


def test_un_surge_voltea_la_decision_al_reves():
    """Y al reves: un pedido flojo se vuelve bueno cuando sube el surge."""
    apodaca = rutas.puntos_de("Apodaca")[0]
    o = oferta(apodaca, pago=40.0)

    nueva, _ = decidir(o)
    assert nueva is None, "sin surge este pedido no vale la pena"

    surge = shocks.Shock(0, "surge", 30, zona=rutas.ZONA_DE[TEC_I], multiplicador=1.9)
    nueva, con = decidir(o, shocks.en(0, (surge,)))

    assert nueva is not None, "con el surge si sale"
    assert con.terminos["pago_neto"] > 40.0


def test_la_seguridad_no_se_compra_ni_con_surge():
    """Lo que mide el protocolo: una restriccion dura sigue dura aunque suba el pago."""
    escobedo = rutas.puntos_de("Escobedo")[0]
    surge = shocks.Shock(0, "surge", 60, zona=rutas.ZONA_DE[TEC_I], multiplicador=3.0)
    nueva, dec = politica_nuez(
        oferta(escobedo, pago=900.0),
        estado(),
        [],
        cfg(hora_inicio=23),
        tabla=valor.para_turno(120),
        activos=shocks.en(0, (surge,)),
    )
    assert nueva is None
    assert dec.restriccion == "flagged_zone_night"


# --- propiedades del sistema -------------------------------------------------


def test_las_disrupciones_no_mueven_el_stream_de_ofertas():
    """La razon de que el numero sin shocks siga siendo el mismo: dado aparte."""
    configuracion = cfg(seed=2000)
    antes = generar_ofertas(configuracion)
    shocks.generar(2000, 120, ("Tec", "Centro"), antes)
    assert generar_ofertas(configuracion) == antes


def test_mismos_shocks_mismas_decisiones():
    """Replay: los jueces graban un turno, lo reproducen y comparan decision a decision."""
    configuracion = cfg(seed=2001)
    disr = shocks.generar(2001, 120, ("Tec", "Centro", "Valle"), generar_ofertas(configuracion))
    politica = partial(politica_nuez, tabla=TABLA)

    a = simular(configuracion, politica, disr)
    b = simular(configuracion, politica, disr)
    assert [(d.oferta_id, d.accion, d.razon) for d in a.decisiones] == [
        (d.oferta_id, d.accion, d.razon) for d in b.decisiones
    ]
    assert a.ganado == b.ganado


def test_el_turno_aguanta_la_disrupcion_sin_romperse():
    """No basta con no tronar: tiene que seguir entregando y seguir volviendo."""
    politica = partial(politica_nuez, tabla=TABLA)
    for semilla in seeds.de_reporte(20):
        configuracion = cfg(seed=semilla)
        disr = shocks.generar(
            semilla, 120, ("Tec", "Centro", "Valle"), generar_ofertas(configuracion)
        )
        res = simular(configuracion, politica, disr)
        aceptadas = sum(d.accion == "aceptar" for d in res.decisiones)
        assert res.entregas + res.cancelados == aceptadas, "lo aceptado se entrega o se cancela"
        assert res.ganado >= 0


@pytest.mark.parametrize("politica", (politica_greedy, partial(politica_nuez, tabla=TABLA)))
def test_decidir_con_shocks_sigue_siendo_rapido(politica):
    """El presupuesto de la ruta rapida son 50 ms. Una disrupcion no lo mueve."""
    lluvia = shocks.Shock(0, "rain", 60)
    cierre = shocks.Shock(0, "closure", 60, zona="Centro")
    activos = shocks.en(0, (lluvia, cierre))
    o = oferta(rutas.puntos_de("Fundidora")[0], pago=60.0)

    inicio = time.perf_counter()
    for _ in range(50):
        politica(o, estado(), [], cfg(), activos=activos)
    por_decision = (time.perf_counter() - inicio) / 50 * 1000

    assert por_decision < 50, f"{por_decision:.1f} ms por decision"
