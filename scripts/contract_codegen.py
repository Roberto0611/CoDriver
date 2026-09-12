"""El contrato (contrato.py) es la costura entre los cuatro carriles. De aqui salen:

    tests/contract_snapshot.json   foto de las formas; el test falla si cambian sin avisar
    frontend/src/contract.ts       los mismos tipos en TypeScript, para el front

    python scripts/contract_codegen.py --write    regenera los dos archivos
    python scripts/contract_codegen.py --check    falla si estan desactualizados (CI)

Cambiar un campo de contrato.py es legitimo. Lo que no es legitimo es hacerlo sin
que se note: se corre --write, se revisa el diff en el PR, y todos se enteran.
"""

import dataclasses
import json
import sys
import types
import typing
from pathlib import Path
from typing import Any, Literal, get_args, get_origin, get_type_hints

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import contrato  # noqa: E402

SNAPSHOT = RAIZ / "tests" / "contract_snapshot.json"
TS = RAIZ / "frontend" / "src" / "contract.ts"

PRIMITIVOS = {str: "string", int: "number", float: "number", bool: "boolean", type(None): "null"}


def ts_type(tp: Any) -> str:
    """Un tipo de Python en notacion TypeScript. Tambien es la forma canonica del snapshot."""
    if tp in PRIMITIVOS:
        return PRIMITIVOS[tp]
    origin = get_origin(tp)
    if origin is Literal:
        return " | ".join(json.dumps(v) for v in get_args(tp))
    if origin in (types.UnionType, typing.Union):
        return " | ".join(ts_type(a) for a in get_args(tp))
    if origin in (list, tuple):
        (inner, *_rest) = get_args(tp) or (Any,)
        return f"{ts_type(inner)}[]"
    if origin is dict:
        k, v = get_args(tp)
        return f"Record<{ts_type(k)}, {ts_type(v)}>"
    if dataclasses.is_dataclass(tp) and isinstance(tp, type):
        return tp.__name__
    if tp is Any:
        return "unknown"
    raise TypeError(f"no se como traducir {tp!r}")


def aliases() -> dict[str, str]:
    """Los Literal de nivel de modulo: Accion, Vehiculo, Restriccion."""
    return {
        name: ts_type(val)
        for name, val in vars(contrato).items()
        if not name.startswith("_") and get_origin(val) is Literal
    }


def clases() -> list[type]:
    return [
        v for v in vars(contrato).values() if dataclasses.is_dataclass(v) and isinstance(v, type)
    ]


def esquema() -> dict[str, Any]:
    """La foto completa: aliases y cada dataclass con sus campos en orden."""
    alias = aliases()

    def con_alias(t: str) -> str:
        # Un campo tipado con un alias se reporta con el nombre del alias, no expandido,
        # tambien dentro de una union (`Restriccion | null`).
        for name, val in sorted(alias.items(), key=lambda kv: -len(kv[1])):
            t = t.replace(val, name)
        return t

    out: dict[str, Any] = {"aliases": alias, "classes": {}}
    for cls in clases():
        hints = get_type_hints(cls)
        campos = []
        for f in dataclasses.fields(cls):
            t = ts_type(hints[f.name])
            campos.append(
                {
                    "name": f.name,
                    "type": con_alias(t),
                    "required": f.default is dataclasses.MISSING
                    and f.default_factory is dataclasses.MISSING,
                }
            )
        doc = (cls.__doc__ or "").strip()
        if doc.startswith(cls.__name__ + "("):
            doc = ""  # sin docstring, dataclass pone la firma; no aporta
        out["classes"][cls.__name__] = {"doc": doc, "fields": campos}
    return out


def render_ts(es: dict[str, Any]) -> str:
    lineas = [
        "// GENERADO por scripts/contract_codegen.py a partir de contrato.py. NO EDITAR A MANO.",
        "// Regenerar: python scripts/contract_codegen.py --write",
        "//",
        "// El tiempo SIEMPRE es minutos desde que empezo el turno (entero). Nunca fechas.",
        "",
    ]
    for name, t in es["aliases"].items():
        lineas.append(f"export type {name} = {t.replace(chr(34), chr(39))}")
    lineas.append("")
    for name, cls in es["classes"].items():
        doc = cls["doc"].splitlines()[0] if cls["doc"] else ""
        if doc:
            lineas.append(f"/** {doc} */")
        lineas.append(f"export interface {name} {{")
        for f in cls["fields"]:
            # En el JSON que viaja, los defaults SIEMPRE van (asdict los incluye): sin `?`.
            lineas.append(f"  {f['name']}: {f['type'].replace(chr(34), chr(39))}")
        lineas.append("}")
        lineas.append("")
    return "\n".join(lineas)


def generar() -> tuple[str, str]:
    es = esquema()
    return json.dumps(es, indent=2, ensure_ascii=False) + "\n", render_ts(es)


def main(argv: list[str]) -> int:
    snap, ts = generar()
    if "--write" in argv:
        SNAPSHOT.write_text(snap, encoding="utf-8")
        TS.write_text(ts, encoding="utf-8")
        print(f"escritos {SNAPSHOT.relative_to(RAIZ)} y {TS.relative_to(RAIZ)}")
        return 0
    if "--check" in argv:
        desfasados = [
            p.relative_to(RAIZ)
            for p, esperado in ((SNAPSHOT, snap), (TS, ts))
            if not p.exists() or p.read_text(encoding="utf-8") != esperado
        ]
        if desfasados:
            print("contrato.py cambio y estos archivos no se regeneraron:")
            for p in desfasados:
                print(f"  {p}")
            print("corre: python scripts/contract_codegen.py --write")
            return 1
        print("OK: snapshot y contract.ts al dia con contrato.py")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
