"""El contrato no cambia sin que se note.

Si este test falla, alguien toco contrato.py. Eso puede ser correcto: se corre
`python scripts/contract_codegen.py --write`, se revisa el diff y se avisa al equipo.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import contract_codegen as cg  # noqa: E402

SNAPSHOT = RAIZ / "tests" / "contract_snapshot.json"
TURNO = RAIZ / "frontend" / "public" / "turno_greedy_1.json"


def test_el_snapshot_coincide_con_contrato_py():
    guardado = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    vivo = cg.esquema()
    assert vivo == guardado, (
        "contrato.py cambio. Si es a proposito: "
        "python scripts/contract_codegen.py --write y avisa al equipo."
    )


def test_contract_ts_esta_al_dia():
    _, ts = cg.generar()
    assert cg.TS.read_text(encoding="utf-8") == ts, (
        "frontend/src/contract.ts esta desactualizado: python scripts/contract_codegen.py --write"
    )


def test_las_formas_esperadas_existen():
    es = cg.esquema()
    assert set(es["aliases"]) == {"Accion", "Vehiculo", "Restriccion"}
    assert {"Punto", "ConfigTurno", "Oferta", "EstadoRepartidor", "Decision", "EventoMundo"} <= set(
        es["classes"]
    )
    assert es["classes"]["Decision"]["fields"][2]["name"] == "accion"
    assert es["classes"]["Decision"]["fields"][2]["type"] == "Accion"


def test_el_turno_grabado_para_el_front_respeta_el_contrato():
    """Lo que el front reproduce hoy tiene exactamente los campos del contrato."""
    es = cg.esquema()
    campos = {n: [f["name"] for f in c["fields"]] for n, c in es["classes"].items()}
    turno = json.loads(TURNO.read_text(encoding="utf-8"))

    assert list(turno["config"]) == campos["ConfigTurno"]
    assert list(turno["config"]["ancla"]) == campos["Punto"]

    ofertas = [o for fr in turno["frames"] for o in fr["ofertas"]]
    decisiones = [d for fr in turno["frames"] for d in fr["decisiones"]]
    assert ofertas and decisiones
    assert all(list(o) == campos["Oferta"] for o in ofertas)
    assert all(list(d) == campos["Decision"] for d in decisiones)
    assert all(d["accion"] in ("aceptar", "saltar") for d in decisiones)
