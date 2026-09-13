"""Exporta un practice pack Courier como replay auditable para el frontend.

No pretende ser un turno Greedy-vs-Nuez: el pack solo mide las restricciones de
Nuez. Conserva las 14 pruebas, su minuto dentro de la jornada y, si se entrega
el scorecard del runner, el veredicto real que devolvió el servidor.

Ejemplo:
    python data/export_practice_pack_replay.py \
      --pack courier-update/practice_pack/practice_pack.csv \
      --key courier-update/practice_pack/practice_pack_key.json \
      --scorecard cache/courier/practice_pack_scorecard.json
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
PUBLICO = RAIZ / "frontend" / "public"

NUMERICOS = {
    "zone_pickup",
    "zone_dropoff",
    "distance_pickup_km",
    "distance_delivery_km",
    "base_pay_mxn",
    "est_tip_mxn",
    "surge_multiplier",
    "restaurant_prep_min",
    "weight_kg",
    "volume_liters",
    "estimated_pickup_min",
    "estimated_delivery_min",
}
ENTEROS = {"zone_pickup", "zone_dropoff"}


def leer_csv(path: Path) -> list[dict[str, Any]]:
    """Lee el stream oficial preservando nombres y convirtiendo campos numéricos."""
    filas: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as archivo:
        for original in csv.DictReader(archivo):
            fila: dict[str, Any] = {}
            for campo, valor in original.items():
                if campo is None or not (valor := valor.strip()):
                    continue
                if campo in NUMERICOS:
                    numero = float(valor)
                    fila[campo] = int(numero) if campo in ENTEROS else numero
                else:
                    fila[campo] = valor
            filas.append(fila)
    return sorted(filas, key=lambda fila: str(fila["sim_time"]))


def cargar_resultados(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    scorecard = json.loads(path.read_text(encoding="utf-8"))
    return {str(fila["order_id"]): fila for fila in scorecard["orders"]}


def construir(pack: Path, key: Path, scorecard: Path | None) -> dict[str, Any]:
    clave = json.loads(key.read_text(encoding="utf-8"))
    manifest = clave["manifest"]
    inicio = datetime.fromisoformat(manifest["shift_start_time"])
    fin = datetime.fromisoformat(manifest["shift_end_time"])
    resultados = cargar_resultados(scorecard)
    pruebas = []

    for orden in leer_csv(pack):
        order_id = str(orden["order_id"])
        esperado = clave["orders"][order_id]
        resultado = resultados.get(order_id)
        momento = datetime.fromisoformat(str(orden["sim_time"]))
        actual = None
        if resultado is not None:
            actual = {
                campo: resultado.get(campo)
                for campo in (
                    "decision",
                    "binding_constraint",
                    "reason",
                    "verdict",
                    "error",
                    "graded_mode",
                    "sent_state",
                )
            }
        pruebas.append(
            {
                "order": orden,
                "minute": round((momento - inicio).total_seconds() / 60),
                "expected": {
                    campo: esperado.get(campo)
                    for campo in (
                        "grade",
                        "category",
                        "expected_decision",
                        "expected_binding_constraint",
                        "expected_reason_mentions",
                        "service_min",
                        "state_precondition",
                        "state_neutral",
                        "note",
                    )
                    if esperado.get(campo) is not None
                },
                "actual": actual,
            }
        )

    verdicts = [prueba["actual"].get("verdict") for prueba in pruebas if prueba["actual"]]
    return {
        "kind": "courier_practice_pack_replay",
        "pack_id": clave.get("pack_id", pack.stem),
        "title": "Courier Safety Lab — 8.5-hour practice shift",
        "manifest": manifest,
        "duration_min": round((fin - inicio).total_seconds() / 60),
        "summary": {
            "tests": len(pruebas),
            "passed": sum(verdict == "PASS" for verdict in verdicts),
            "failed": sum(verdict in {"FAIL", "ERROR"} for verdict in verdicts),
            "source": "runner scorecard" if scorecard else "expected outcomes only",
        },
        "tests": pruebas,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--scorecard", type=Path)
    parser.add_argument(
        "--output", type=Path, default=PUBLICO / "courier_practice_pack_replay.json"
    )
    args = parser.parse_args()

    replay = construir(args.pack, args.key, args.scorecard)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(replay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{args.output}: {replay['summary']['tests']} pruebas, "
        f"{replay['summary']['passed']} PASS, {replay['summary']['failed']} FAIL"
    )


if __name__ == "__main__":
    main()
