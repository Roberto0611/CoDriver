"""El simulador: reproducible por seed, coherente consigo mismo, y el greedy llega a clase."""

import pytest

import rutas
import seguridad
from contrato import ConfigTurno, Punto
from sim import generar_ofertas, politica_greedy, simular

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
    llenas = [d for d in res.decisiones if d.restriccion == "vehicle_capacity"]
    assert all(d.accion == "saltar" for d in llenas)
    assert seguridad.VEHICULOS["moto"].pedidos == 3


def test_de_noche_el_greedy_no_entra_a_zonas_inseguras():
    res = simular(cfg(4, hora_inicio=23), politica_greedy)
    inseguras = [d for d in res.decisiones if d.restriccion == "flagged_zone_night"]
    assert inseguras, "a las 11 PM alguna oferta debe caer en zona bloqueada"
    assert all(d.accion == "saltar" for d in inseguras)


# --- el protocolo pide dos cosas del sistema completo, no de una funcion -----


@pytest.mark.parametrize("hora", (8, 14, 21))
def test_cero_violaciones_de_fin_de_turno(hora):
    """ "Safety violations must be zero". Las DOS politicas, no solo la nuestra."""
    import seeds
    from nuez import politica_nuez

    for pol in (politica_greedy, politica_nuez):
        tarde = sum(
            simular(cfg(s, hora_inicio=hora), pol).llego_tarde for s in seeds.de_reporte(30)
        )
        assert tarde == 0, f"{pol.__name__} llego tarde {tarde} veces empezando a las {hora}"


def test_las_cinco_restricciones_se_disparan_de_verdad():
    """ "A constraint that exists in code but is never demonstrated scores low".

    Cada una necesita su escenario: el calor solo entre 12 y 4, el descanso solo
    en turnos largos, la zona marcada solo de noche. Si alguna deja de aparecer es
    que quedo inalcanzable, que es igual de malo que no tenerla.
    """
    import seeds
    from nuez import politica_nuez

    vistas = set()
    escenarios = (
        dict(hora_inicio=14, duracion_min=120),  # calor, capacidad, fin de turno
        dict(hora_inicio=21, duracion_min=120),  # zona marcada despues de las 22
        # 8 horas arrancando a las 6: cruza el calor Y junta 4 h seguidas despues.
        dict(hora_inicio=6, duracion_min=480),
    )
    for extra in escenarios:
        for s in seeds.de_reporte(10):
            res = simular(cfg(s, **extra), politica_nuez)
            vistas |= {d.restriccion for d in res.decisiones if d.restriccion}

    assert vistas == {
        "flagged_zone_night",
        "mandatory_break",
        "heat_rule",
        "shift_end_infeasible",
        "vehicle_capacity",
        "reservation_wage",
    }, f"faltaron por dispararse: {vistas}"


@pytest.mark.parametrize("duracion,hora", [(65, 14), (137, 14), (480, 8), (480, 14), (480, 21)])
@pytest.mark.parametrize("vehiculo", ("moto", "car", "bike"))
def test_ventanas_variables_vehiculos_y_regreso(duracion, hora, vehiculo):
    import seeds
    from nuez import politica_nuez

    for seed in seeds.de_reporte(5):
        config = cfg(seed, duracion_min=duracion, hora_inicio=hora, vehiculo=vehiculo)
        for politica in (politica_greedy, politica_nuez):
            res = simular(config, politica)
            assert not res.llego_tarde, (seed, duracion, hora, vehiculo, politica.__name__)
            # Lo aceptado se entrega O se cancela: una disrupcion puede volver
            # infactible un plan que si era factible al aceptarlo.
            aceptadas = sum(d.accion == "aceptar" for d in res.decisiones)
            assert res.entregas + res.cancelados == aceptadas
            assert all(0 <= d.t < duracion for d in res.decisiones)
            assert 0 <= res.minutos_ocupado <= duracion
            for salida, llegada, origen, destino in res.tramos:
                esperado = rutas.minutos(origen, destino, hora + salida // 60, vehiculo)
                assert llegada - salida == pytest.approx(esperado)


def test_ampliar_turno_conserva_el_stream_inicial_y_no_depende_del_vehiculo():
    corto = generar_ofertas(cfg(7))
    largo = generar_ofertas(cfg(7, duracion_min=480, vehiculo="bike"))
    assert corto == [o for o in largo if o.t_aparece < 120]
    assert largo[-1].t_aparece > 400
