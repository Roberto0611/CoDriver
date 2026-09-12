"""explain_decision: el "por que" de cada pedido, leido de un registro y no re-calculado.

La explicacion se arma en el momento de decidir, con los numeros que el motor ya
tenia a la mano, y viaja dentro del evento `decision` del JSONL. Despues solo se
busca: en memoria mientras corre el turno, o leyendo el archivo si ya termino.

    python -m backendruta.explain ORD-0042 --log cache/courier/current_shift.jsonl
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import seguridad
from mundo import HORA_NOCHE

# Lo que el protocolo exige en la respuesta; el resto de campos es contexto extra.
REQUIRED = ("order_id", "decision", "reason", "inputs", "alternatives_considered")
SAFETY = {
    "flagged_zone_night",
    "mandatory_break",
    "heat_rule",
    "shift_end_infeasible",
    "vehicle_capacity",
}


def build(
    *,
    request: Any,
    response: Any,
    terms: dict[str, float],
    position_zone: int,
    time_remaining_min: int,
    continuous_riding_min: int,
    in_flight_orders: list[str],
    strategy: dict[str, Any],
) -> dict[str, Any]:
    """Arma la explicacion completa. Pura aritmetica sobre datos ya calculados."""
    limits = seguridad.VEHICULOS[request.vehicle]
    inputs = {
        "sim_time": request.sim_time.isoformat(),
        "position_zone": position_zone,
        "time_remaining_min": time_remaining_min,
        "time_to_completion_min": terms.get("minutos_para_terminar"),
        "shift_minutes_available": terms.get("minutos_de_turno"),
        "order_marginal_min": terms.get("minutos"),
        "current_route_min": terms.get("minutos_ruta_actual"),
        "continuous_riding_min": continuous_riding_min,
        "in_flight_orders": in_flight_orders,
        "vehicle": request.vehicle,
        "vehicle_limits": {
            "orders": limits.pedidos,
            "weight_kg": limits.peso_kg,
            "volume_liters": limits.volumen_l,
        },
        "offer": {
            "zone_pickup": request.zone_pickup,
            "zone_dropoff": request.zone_dropoff,
            "base_pay_mxn": request.base_pay_mxn,
            "est_tip_mxn": request.est_tip_mxn,
            "surge_multiplier": request.surge_multiplier,
            "restaurant_prep_min": request.restaurant_prep_min,
            "weight_kg": request.weight_kg,
            "volume_liters": request.volume_liters,
        },
        "economics": response.economics,
        "engine_terms": terms,
        "strategy": strategy,
    }
    return {
        "order_id": response.order_id,
        "decision": response.decision,
        "reason": response.reason,
        "binding_constraint": response.binding_constraint,
        "sim_time": inputs["sim_time"],
        "inputs": inputs,
        "alternatives_considered": alternatives(
            response.decision, response.binding_constraint, inputs
        ),
    }


def alternatives(
    decision: str, constraint: str | None, inputs: dict[str, Any]
) -> list[dict[str, str]]:
    """Lo que tambien estaba sobre la mesa y por que perdio, con sus numeros."""
    terms = inputs["engine_terms"]
    pay = terms.get("pago_neto", 0)
    cost = terms.get("precio_tiempo", 0)
    minutes = terms.get("minutos", 0)
    edge = terms.get("ventaja", pay - cost)

    if decision == "ACCEPT":
        return [
            {
                "option": "SKIP and keep waiting for a better offer",
                "rejected_because": (
                    f"Those {minutes:.0f} min usually earn MXN {cost:.0f}; this order nets "
                    f"MXN {pay:.0f}, MXN {edge:.0f} more."
                ),
            }
        ]

    if constraint not in SAFETY:
        # Con ventaja entre 0 y el minimo, "MXN 0 below" confunde: se dice que no alcanza.
        min_edge = inputs.get("strategy", {}).get("min_edge_mxn", 0)
        gap = f"MXN {-edge:.1f} below" if edge < 0 else f"only MXN {edge:.1f} above"
        return [
            {
                "option": "ACCEPT",
                "rejected_because": (
                    f"MXN {pay:.1f} net is {gap} the MXN {cost:.1f} those {minutes:.0f} min "
                    f"usually earn (reservation wage); accepting needs MXN {min_edge:.1f} above it."
                ),
            }
        ]

    pay_verdict = "ACCEPT" if edge > 0 else "SKIP"
    detail = _constraint_detail(constraint, inputs)
    return [
        {"option": "ACCEPT", "rejected_because": f"Blocked by {constraint}: {detail}"},
        {
            "option": "Decide on pay alone",
            "rejected_because": (
                f"Pay math alone says {pay_verdict} (edge MXN {edge:.0f}), but safety "
                "constraints are checked first and cannot be bought with money."
            ),
        },
    ]


def _constraint_detail(constraint: str, inputs: dict[str, Any]) -> str:
    riding = inputs["continuous_riding_min"]
    if constraint == "heat_rule":
        return (
            f"{riding} continuous riding min reaches the {seguridad.LIMITE_CALOR_MIN}-min "
            "limit between 12:00 and 16:00."
        )
    if constraint == "mandatory_break":
        return (
            f"{riding} continuous riding min reaches the {seguridad.LIMITE_CONTINUO_MIN}-min "
            f"limit; a {seguridad.DESCANSO_MIN}-min break is due."
        )
    if constraint == "shift_end_infeasible":
        return (
            f"delivering and returning needs {inputs['time_to_completion_min']} min, "
            f"only {inputs['shift_minutes_available']} min remain."
        )
    if constraint == "flagged_zone_night":
        return (
            f"drop-off zone {inputs['offer']['zone_dropoff']} is flagged after "
            f"{HORA_NOCHE}:00; offer at {inputs['sim_time'][11:16]}."
        )
    limits = inputs["vehicle_limits"]
    offer = inputs["offer"]
    return (
        f"{inputs['vehicle']} carries {limits['orders']} orders, {limits['weight_kg']:.0f} kg, "
        f"{limits['volume_liters']:.0f} L; this adds {offer['weight_kg']} kg, "
        f"{offer['volume_liters']} L to {len(inputs['in_flight_orders'])} in flight."
    )


class ExplainIndex:
    """order_id -> explicacion. Se llena al escribir el log; nunca vuelve a decidir."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}

    def add(self, record: dict[str, Any]) -> None:
        self._records[record["order_id"]] = record

    def get(self, order_id: str) -> dict[str, Any] | None:
        return self._records.get(order_id)

    def clear(self) -> None:
        self._records.clear()

    @classmethod
    def from_log(cls, path: Path) -> "ExplainIndex":
        """Reconstruye el indice desde un JSONL cerrado, sin red ni motor."""
        index = cls()
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                event = json.loads(line)
                if event.get("event") != "decision":
                    continue
                record = {key: event.get(key) for key in REQUIRED}
                record["binding_constraint"] = event.get("binding_constraint")
                record["sim_time"] = event.get("sim_time")
                record["inputs"] = record["inputs"] or {}
                record["alternatives_considered"] = record["alternatives_considered"] or []
                index.add(record)
        return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explica una decision leyendo el JSONL.")
    parser.add_argument("order_id")
    parser.add_argument("--log", type=Path, default=Path("cache/courier/current_shift.jsonl"))
    args = parser.parse_args(argv)
    record = ExplainIndex.from_log(args.log).get(args.order_id)
    if record is None:
        print(f"{args.order_id} no aparece en {args.log}", file=sys.stderr)
        return 1
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
