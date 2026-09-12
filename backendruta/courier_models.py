"""Modelos externos del protocolo Courier y estado privado de una sesion."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from contrato import ConfigTurno, Vehiculo
from shocks import Shock
from sim import Parada


class CourierStateOverrides(BaseModel):
    model_config = ConfigDict(extra="allow")

    continuous_riding_min: float | None = Field(default=None, ge=0)
    shift_elapsed_hours: float | None = Field(default=None, ge=0)
    last_break_end_time: datetime | None = None
    shift_end_time: datetime | None = None
    in_flight_orders: list[dict[str, Any]] | None = None
    position_zone: int | None = None


class ShiftStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int
    shift_hours: float = Field(gt=0, le=8)
    vehicle: Vehiculo
    start_location_zone: int
    sim_time: datetime = datetime(2026, 3, 21, 14, 0)
    shift_end_time: datetime | None = None


class DecideRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    order_id: str = Field(min_length=1)
    platform: Literal["rappi", "didi", "uber"] = "rappi"
    sim_time: datetime
    zone_pickup: int
    zone_dropoff: int
    distance_pickup_km: float = Field(ge=0)
    distance_delivery_km: float = Field(ge=0)
    base_pay_mxn: float = Field(ge=0)
    est_tip_mxn: float = Field(default=0, ge=0)
    surge_multiplier: float = Field(gt=0)
    restaurant_prep_min: float = Field(default=0, ge=0)
    weight_kg: float = Field(default=1, ge=0)
    volume_liters: float = Field(default=5, ge=0)
    vehicle: Vehiculo
    estimated_pickup_min: float | None = Field(default=None, ge=0)
    estimated_delivery_min: float | None = Field(default=None, ge=0)
    courier_state_overrides: CourierStateOverrides | None = None


class DecideResponse(BaseModel):
    order_id: str
    decision: Literal["ACCEPT", "SKIP"]
    reason: str
    binding_constraint: str | None
    latency_ms: float
    tier: Literal["tier1", "tier2"] = "tier1"
    degraded: bool = False
    economics: dict[str, float]


class ShockRequest(BaseModel):
    """Lo que el juez inyecta en vivo. Campos del evento `shock` del protocolo."""

    shock_type: Literal["surge", "closure", "rain", "delay"]
    sim_time: datetime | None = None  # None = ahora mismo
    duration_min: int = Field(default=30, ge=1, le=480)
    zone: int | None = None  # surge y closure
    multiplier: float = Field(default=1.5, ge=1.0, le=3.0)  # surge
    road: str | None = None  # closure: el nombre que se dice en voz alta
    order_id: str | None = None  # delay
    slip_min: int = Field(default=15, ge=0, le=120)  # delay


@dataclass
class ShiftState:
    config: ConfigTurno
    start_time: datetime
    end_time: datetime
    current_minute: int
    position: int
    route: list[Parada] = field(default_factory=list)
    arrival_minute: float | None = None
    continuous_riding_min: int = 0
    idle_min: int = 0
    earnings_mxn: float = 0
    completed: int = 0
    offered: int = 0
    shocks: tuple[Shock, ...] = ()  # disrupciones inyectadas por el juez
    accepted: dict[str, DecideRequest | None] = field(default_factory=dict)
    responses: dict[str, tuple[str, DecideResponse]] = field(default_factory=dict)
