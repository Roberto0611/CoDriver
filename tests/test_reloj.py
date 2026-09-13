"""El reloj paso a paso es el mismo motor que simular(): ni un peso de diferencia."""

import sys
from dataclasses import asdict
from functools import partial
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import engine_baseline as eb  # noqa: E402

import shocks  # noqa: E402
import valor  # noqa: E402
from nuez import politica_nuez  # noqa: E402
from reloj import Turno  # noqa: E402
from sim import generar_ofertas, politica_greedy, simular  # noqa: E402

NUEZ = partial(politica_nuez, tabla=valor.para_turno(120))


def correr(turno: Turno):
    while not turno.terminado:
        turno.paso()
    return turno.cerrar()


def huella(res):
    return (
        res.ganado,
        res.entregas,
        res.rechazos,
        res.cancelados,
        res.llego_tarde,
        [asdict(d) for d in res.decisiones],
        res.tramos,
        res.cobros,
        res.trayecto,
    )


@pytest.mark.parametrize("politica", [politica_greedy, NUEZ], ids=["greedy", "nuez"])
@pytest.mark.parametrize("seed", [1, 7, 2000, 2042])
def test_paso_a_paso_es_simular(politica, seed):
    assert huella(correr(Turno(eb.config(seed), politica))) == huella(
        simular(eb.config(seed), politica)
    )


def test_shock_inyectado_a_media_jornada_es_el_mismo_que_declarado():
    cfg = eb.config(2000)
    cierre = shocks.Shock(
        30, "closure", 40, zona="Tec", calle="Garza Sada"
    )  # any zone works here: this is engine equivalence, not the demo preset
    vivo = Turno(cfg, NUEZ)
    while vivo.t < 30:
        vivo.paso()
    vivo.inyectar(cierre)
    assert huella(correr(vivo)) == huella(simular(cfg, NUEZ, (cierre,)))


def test_ofertas_compartidas_no_se_regeneran():
    cfg = eb.config(2000)
    ofertas = generar_ofertas(cfg)
    turno = Turno(cfg, politica_greedy, ofertas=ofertas)
    assert turno.res.ofertas == ofertas


def test_inyectar_en_el_pasado_falla():
    turno = Turno(eb.config(1), politica_greedy)
    turno.paso()
    with pytest.raises(ValueError):
        turno.inyectar(shocks.Shock(0, "rain", 30))
