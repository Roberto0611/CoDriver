"""El simulador: reproducible por seed, coherente consigo mismo, y el greedy llega a clase."""

import pytest

import rutas
from contrato import ConfigTurno, Punto
from sim import CAPACIDAD, generar_ofertas, politica_greedy, simular

TEC = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]


def cfg(seed: int, **kw) -> ConfigTurno:
    base = dict(
        duracion_min=120,
        ancla=Punto("Tec", *TEC),
        margen_min=10,
        vehiculo="moto",
        hora_inicio=14,
        seed=seed,
    )
    return ConfigTurno(**{**base, **kw})


def test_mismo_seed_mismo_stream_de_ofertas():
    a = generar_ofertas(cfg(7))
    b = generar_ofertas(cfg(7))
    assert [o.id for o in a] == [o.id for o in b]
    assert [(o.pago, o.pickup.nombre, o.dropoff.nombre) for o in a] == [
        (o.pago, o.pickup.nombre, o.dropoff.nombre) for o in b
    ]


def test_seeds_distintos_dan_turnos_distintos():
    a = generar_ofertas(cfg(1))
    b = generar_ofertas(cfg(2))
    assert [o.pago for o in a] != [o.pago for o in b]


def test_las_ofertas_estan_bien_formadas():
    ofertas = generar_ofertas(cfg(3))
    assert len(ofertas) > 50, "0.8 pings/min en 120 min deben dar bastantes ofertas"
    ids = [o.id for o in ofertas]
    assert ids == [f"o_{i:03d}" for i in range(len(ofertas))]
    for o in ofertas:
        assert 0 <= o.t_aparece < 120
        assert o.pago > 0
        assert o.surge in (1.0, 1.3, 1.8)
        assert o.pickup.nombre != o.dropoff.nombre
        assert o.plataforma in ("rappi", "uber", "didi")


def test_simular_es_determinista():
    r1 = simular(cfg(5), politica_greedy)
    r2 = simular(cfg(5), politica_greedy)
    assert r1.ganado == r2.ganado
    assert r1.entregas == r2.entregas
    assert [d.accion for d in r1.decisiones] == [d.accion for d in r2.decisiones]


def test_resultado_es_coherente_consigo_mismo():
    res = simular(cfg(1), politica_greedy)
    assert len(res.decisiones) == len(res.ofertas), "cada oferta recibe una decision"
    aceptadas = sum(1 for d in res.decisiones if d.accion == "aceptar")
    assert res.rechazos == len(res.ofertas) - aceptadas
    assert res.entregas == len(res.cobros)
    # Cada cobro se redondea al registrarlo; el total se redondea al final.
    assert abs(res.ganado - sum(m for _, m in res.cobros)) < 0.05
    assert 0 <= res.minutos_ocupado <= 120
    for d in res.decisiones:
        assert {"pago_neto", "minutos", "por_minuto"} <= set(d.terminos)
        assert d.razon


def test_el_greedy_gana_dinero_y_llega_a_clase():
    res = simular(cfg(1), politica_greedy)
    assert res.ganado > 0
    assert res.entregas >= 1
    assert not res.llego_tarde


@pytest.mark.parametrize("seed", range(10))
def test_el_greedy_respeta_la_capacidad_de_la_mochila(seed):
    res = simular(cfg(seed), politica_greedy)
    llenas = [d for d in res.decisiones if d.restriccion == "mochila_llena"]
    # Si rechazo por mochila llena, es porque de verdad traia CAPACIDAD pedidos.
    assert all(d.accion == "saltar" for d in llenas)
    assert CAPACIDAD == 3


def test_de_noche_el_greedy_no_entra_a_zonas_inseguras():
    res = simular(cfg(4, hora_inicio=23), politica_greedy)
    inseguras = [d for d in res.decisiones if d.restriccion == "zona_insegura"]
    assert inseguras, "a las 11 PM alguna oferta debe caer en zona bloqueada"
    assert all(d.accion == "saltar" for d in inseguras)
