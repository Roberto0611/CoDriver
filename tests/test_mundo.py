"""Invariantes del mundo: trafico por hora y riesgo por zona-hora."""

import pytest

from mundo import (
    RIESGO_BASE,
    TRAFICO_POR_HORA,
    UMBRAL_RIESGO,
    ZONAS,
    es_segura,
    factor_trafico,
    riesgo,
)


def test_toda_zona_tiene_riesgo():
    assert set(ZONAS) == set(RIESGO_BASE)


def test_trafico_cubre_las_24_horas_y_da_la_vuelta():
    assert set(TRAFICO_POR_HORA) == set(range(24))
    assert factor_trafico(25) == factor_trafico(1)
    assert all(f >= 1.0 for f in TRAFICO_POR_HORA.values())


def test_hora_pico_es_mas_lenta_que_la_madrugada():
    assert factor_trafico(18) > factor_trafico(3)
    assert factor_trafico(8) > factor_trafico(11)


@pytest.mark.parametrize("zona", list(ZONAS))
def test_de_noche_sube_el_riesgo_y_nunca_pasa_de_uno(zona):
    assert riesgo(zona, 23) >= riesgo(zona, 14)
    assert 0.0 <= riesgo(zona, 23) <= 1.0


def test_restriccion_dura_por_zona_y_hora():
    assert es_segura("Valle", 23), "San Pedro de noche sigue siendo seguro"
    assert not es_segura("Escobedo", 23), "Escobedo a las 11 PM se bloquea"
    assert es_segura("Escobedo", 14), "pero de dia si se puede"


def test_es_segura_coincide_con_el_umbral():
    for zona in ZONAS:
        for hora in (3, 14, 20, 23):
            assert es_segura(zona, hora) == (riesgo(zona, hora) < UMBRAL_RIESGO)
