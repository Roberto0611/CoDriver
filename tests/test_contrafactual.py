"""El contrafactual: re-simula los saltos por dinero, uno a la vez, y nunca los de reglas duras."""

import json
from pathlib import Path

import pytest

import contrafactual
from contrafactual import CAPACIDAD, DINERO, DURAS, SEGURIDAD, con_pedido, forzar, reporte
from data.export_turno import config
from nuez import politica_nuez
from sim import Resultado, simular

RAIZ = Path(__file__).resolve().parent.parent
PUBLIC = RAIZ / "frontend" / "public"

# Un turno grabado de REPORTE que trae de todo: aceptados, saltos por dinero y por seguridad.
SEED = 2000
CFG = config(SEED)


@pytest.fixture(scope="module")
def real() -> Resultado:
    return simular(CFG, politica_nuez)


@pytest.fixture(scope="module")
def rep() -> dict:
    return reporte(CFG)


def _ids(res: Resultado, pred) -> list[str]:
    return [d.oferta_id for d in res.decisiones if pred(d)]


def _huella(res: Resultado) -> tuple:
    """Lo que tiene que quedar identico si nada cambio de verdad."""
    return (
        res.ganado,
        res.entregas,
        res.llego_tarde,
        res.tramos,
        [(d.oferta_id, d.accion, d.restriccion) for d in res.decisiones],
    )


def test_el_turno_tiene_de_todo(real):
    assert _ids(real, lambda d: d.accion == "aceptar")
    assert _ids(real, lambda d: d.restriccion == DINERO)
    assert _ids(real, lambda d: d.restriccion in DURAS)


def test_forzar_un_pedido_ya_aceptado_reproduce_el_turno(real):
    aceptado = _ids(real, lambda d: d.accion == "aceptar")[0]
    assert _huella(con_pedido(CFG, aceptado)) == _huella(real)


def test_forzar_un_id_que_no_existe_reproduce_el_turno(real):
    assert _huella(con_pedido(CFG, "o_inexistente")) == _huella(real)


def test_forzar_no_salta_la_seguridad(real):
    """Forzar un pedido bloqueado por una restriccion dura no lo vuelve un si."""
    for oid in _ids(real, lambda d: d.restriccion in DURAS)[:5]:
        forzado = simular(CFG, forzar(oid))
        assert _huella(forzado) == _huella(real), f"{oid} se colo por la seguridad"


def test_forzar_un_salto_por_dinero_lo_acepta(real, rep):
    oid = _ids(real, lambda d: d.restriccion == DINERO)[0]
    forzado = con_pedido(CFG, oid)
    dec = next(d for d in forzado.decisiones if d.oferta_id == oid)
    assert dec.accion == "aceptar"
    # Todo lo anterior a ese minuto es el mismo turno.
    antes = [d for d in real.decisiones if d.t < dec.t]
    assert forzado.decisiones[: len(antes)] == antes

    fila = next(e for e in rep["top"] if e["order_id"] == oid)
    assert fila["delta_mxn"] == round(forzado.ganado - real.ganado, 2)
    assert fila["forced_earned_mxn"] == forzado.ganado


def test_los_saltos_de_seguridad_nunca_se_simulan(monkeypatch, real):
    forzados: list[str] = []

    def espia(cfg, objetivo, disrupciones=(), estrategias=None):
        forzados.append(objetivo)
        return con_pedido(cfg, objetivo, disrupciones, estrategias)

    monkeypatch.setattr(contrafactual, "con_pedido", espia)
    rep = reporte(CFG)

    assert forzados == _ids(real, lambda d: d.restriccion == DINERO)
    assert not set(forzados) & set(_ids(real, lambda d: d.restriccion in DURAS))
    assert sum(rep["safety_skips"].values()) == len(
        _ids(real, lambda d: d.restriccion in SEGURIDAD)
    )
    assert rep["capacity_skips"] == len(_ids(real, lambda d: d.restriccion == CAPACIDAD))


def test_la_capacidad_no_es_seguridad(rep):
    """Un vehiculo lleno es un limite fisico: no se cuenta como bloqueo de seguridad."""
    assert CAPACIDAD in DURAS
    assert CAPACIDAD not in SEGURIDAD
    assert CAPACIDAD not in rep["safety_skips"]
    assert rep["capacity_skips"] > 0, (
        "el seed 2000 llena el vehiculo; si no, el test no prueba nada"
    )


def test_esquema(rep, real):
    assert set(rep) == {
        "seed",
        "policy",
        "actual",
        "skipped_total",
        "money_skips",
        "safety_skips",
        "capacity_skips",
        "top",
        "note",
    }
    assert rep["seed"] == SEED
    assert rep["actual"]["earned_mxn"] == real.ganado
    assert rep["actual"]["offers"] == len(real.ofertas)

    dinero = rep["money_skips"]
    assert dinero["count"] == dinero["evaluated"] + dinero["infeasible"]
    assert (
        dinero["would_earn_less"] + dinero["would_earn_more"] + dinero["no_change"]
        == dinero["evaluated"]
    )
    assert (
        rep["skipped_total"]
        == dinero["count"] + sum(rep["safety_skips"].values()) + rep["capacity_skips"]
    )
    assert "total" not in " ".join(dinero), "los deltas no se suman: no hay total"

    assert len(DURAS) == 5
    assert list(rep["safety_skips"]) == list(SEGURIDAD) and len(SEGURIDAD) == 4
    assert DINERO not in rep["safety_skips"]

    assert 0 < len(rep["top"]) <= contrafactual.TOP
    deltas = [abs(e["delta_mxn"]) for e in rep["top"]]
    assert deltas == sorted(deltas, reverse=True)
    for e in rep["top"]:
        assert set(e) == {
            "order_id",
            "minute",
            "net_pay_mxn",
            "minutes",
            "time_value_mxn",
            "delta_mxn",
            "forced_earned_mxn",
            "forced_deliveries",
            "late",
            "cancelled",
        }
        assert isinstance(e["late"], bool)

    # JSON estricto: un -inf o un nan que se colara romperia el fetch del front.
    assert json.loads(json.dumps(rep, allow_nan=False)) == rep


def test_determinista(rep):
    assert reporte(CFG) == rep


def test_los_archivos_grabados_cuadran_con_los_turnos():
    """Si alguien regraba los turnos sin regrabar el contrafactual, aqui se nota."""
    indice = json.loads((PUBLIC / "turnos.json").read_text(encoding="utf-8"))["turnos"]
    revisados = 0
    for turno in indice:
        archivo = PUBLIC / f"contrafactual_{turno['seed']}.json"
        if not archivo.exists():
            continue
        grabado = json.loads(archivo.read_text(encoding="utf-8"))
        assert grabado["seed"] == turno["seed"]
        assert grabado["actual"]["earned_mxn"] == turno["nuez"]["ganado"], (
            f"{archivo.name} no cuadra: python data/export_contrafactual.py"
        )
        # Todo el reporte, no solo el numero: un archivo con el esquema viejo pasaria
        # la cuenta y el front lo tiraria sin avisar (esContrafactual da false).
        vivo = json.loads(json.dumps(reporte(config(turno["seed"]))))
        assert grabado == vivo, f"{archivo.name} esta viejo: python data/export_contrafactual.py"
        revisados += 1
    if not revisados:
        pytest.skip("todavia no hay contrafactual_*.json grabados")
