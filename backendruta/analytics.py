"""Consultas de historial para el front; nunca participan en /decide."""

import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from backendruta import database

router = APIRouter(prefix="/analytics", tags=["analytics"])


def resumir(eventos: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Convierte eventos decision en un payload pequeno y directo para React."""
    decisiones = sorted(eventos, key=lambda evento: evento["sim_time"])
    aceptadas = sum(evento["decision"] == "ACCEPT" for evento in decisiones)
    restricciones = Counter(
        evento.get("binding_constraint") or "opportunity_cost" for evento in decisiones
    )
    timeline = []
    neto_aceptado = 0.0
    for evento in decisiones:
        economics = evento.get("inputs", {}).get("economics", {})
        neto = float(economics.get("net_pay_mxn", 0))
        if evento["decision"] == "ACCEPT":
            neto_aceptado += neto
        timeline.append(
            {
                "sim_time": evento["sim_time"],
                "order_id": evento["order_id"],
                "decision": evento["decision"],
                "reason": evento["reason"],
                "binding_constraint": evento.get("binding_constraint"),
                "net_pay_mxn": neto,
            }
        )
    total = len(decisiones)
    return {
        "total_decisions": total,
        "accepted": aceptadas,
        "skipped": total - aceptadas,
        "accept_rate_pct": round(aceptadas * 100 / total, 2) if total else 0.0,
        "by_constraint": dict(sorted(restricciones.items())),
        "accepted_net_mxn": round(neto_aceptado, 2),
        "timeline": timeline,
    }


def _from_tigerdata(log_path: Path) -> list[dict[str, Any]] | None:
    """Lee la copia de TigerData; None significa que toca usar el JSONL local."""
    engine = database.get_engine()
    if not engine or not database.is_connected():
        return None
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT payload
                    FROM decisiones_courier
                    WHERE log_path = :log_path
                    ORDER BY sim_time
                """),
                {"log_path": str(log_path)},
            ).scalars()
            return [json.loads(row) if isinstance(row, str) else row for row in rows]
    except Exception:
        return None


def _from_jsonl(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    with log_path.open(encoding="utf-8") as stream:
        return [
            event
            for line in stream
            if line.strip()
            for event in (json.loads(line),)
            if event.get("event") == "decision"
        ]


@router.get("/shift")
def shift_analytics() -> dict[str, Any]:
    """Resumen del turno activo, listo para tarjetas, gráficas y una línea de tiempo."""
    # Import local: evita un ciclo cuando main monta ambos routers al arrancar.
    from backendruta.courier_api import service

    eventos = _from_tigerdata(service.log.path)
    source = "tigerdata" if eventos is not None else "jsonl"
    if eventos is None:
        eventos = _from_jsonl(service.log.path)
    return {"source": source, "log_path": str(service.log.path), **resumir(eventos)}
