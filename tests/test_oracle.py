"""El Oracle es offline, determinista y nunca rebasa las restricciones."""

from functools import partial

import rutas
from contrato import ConfigTurno, Punto
from nuez import politica_nuez
from oracle import planificar, resolver, simular_oracle
from sim import generar_ofertas, simular


def cfg(**changes) -> ConfigTurno:
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    base = {
        "duracion_min": 120,
        "ancla": Punto("Tec", *tec),
        "margen_min": 10,
        "vehiculo": "moto",
        "hora_inicio": 14,
        "seed": 2_000,
    }
    return ConfigTurno(**{**base, **changes})


def test_el_plan_del_oracle_solo_contiene_ofertas_del_stream_completo():
    turno = cfg()
    stream = generar_ofertas(turno)
    plan = planificar(turno, stream)
    assert plan.oferta_ids
    assert set(plan.oferta_ids).issubset({oferta.id for oferta in stream})
    assert plan.ganancia_estimada > 0


def test_oracle_es_determinista_y_no_peor_que_nuez_en_el_mismo_turno():
    turno = cfg()
    uno, ganador, plan = resolver(turno)
    dos = simular_oracle(turno)
    nuez = simular(turno, partial(politica_nuez))

    assert ganador in {
        "AgendaOracle",
        "AcceptAll",
        "HighestPay",
        "NearestFirst",
        "GreedyRate",
        "OurAgent",
    }
    assert plan.oferta_ids
    assert uno.ganado == dos.ganado
    assert uno.ganado >= nuez.ganado
    assert not uno.llego_tarde
    assert all(
        decision.restriccion is None for decision in uno.decisiones if decision.accion == "aceptar"
    )


def test_oracle_soporta_turno_de_ocho_horas():
    resultado = simular_oracle(cfg(duracion_min=480, seed=2_001))
    assert resultado.ganado >= 0
    assert not resultado.llego_tarde
