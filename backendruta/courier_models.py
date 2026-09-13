"""Modelos externos del protocolo Courier y estado privado de una sesion."""

import math
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from contrato import ConfigTurno, Vehiculo
from shocks import Shock
from sim import Parada

MAX_TURNO_MIN = 510  # el practice pack oficial cubre una jornada de 8.5 h


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
    shift_hours: float = Field(gt=0, le=MAX_TURNO_MIN / 60)
    vehicle: Vehiculo
    start_location_zone: int
    sim_time: datetime = datetime(2026, 3, 21, 14, 0)
    shift_end_time: datetime | None = None
    # Opcion de producto, no del protocolo: el estudiante con clase despues la
    # enciende. Es False por omision porque el runner de los jueces llama /decide sin
    # pasar por aqui, y la regla del spec es terminar la entrega, no regresar.
    return_to_start: bool = False


class DecideRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    order_id: str = Field(min_length=1)
    platform: Literal["rappi", "didi", "uber"] = "rappi"
    sim_time: datetime
    zone_pickup: int
    zone_dropoff: int
    # Opcionales: si un stream usa un ID que Nuez no publica, el nombre humano
    # permite traducirlo sin alterar el catálogo estable de Nuez.
    zone_pickup_name: str | None = None
    zone_dropoff_name: str | None = None
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


def origen_del_turno(momento: datetime) -> tuple[datetime, int]:
    """Ancla el reloj del turno a la hora en punto: (origen, minutos de desfase).

    El motor calcula la hora como `hora_inicio + minuto // 60` con `hora_inicio` entero.
    Un turno que arrancaba a las 15:30 contaba su minuto 0 a las 15:30, y a las 22:00 el
    motor creia que eran las 21: aceptaba entregas en zona marcada y aplicaba la regla
    del calor y el trafico con una hora de atraso. Contando desde las 15:00 sale exacto.
    """
    origen = momento.replace(minute=0, second=0, microsecond=0)
    return origen, math.floor((momento - origen).total_seconds() / 60)


@dataclass
class ShiftState:
    config: ConfigTurno
    start_time: datetime
    end_time: datetime
    current_minute: int
    position: int
    # Minutos entre la hora en punto y el arranque real (15:30 -> 30). El reloj del
    # turno cuenta desde la hora en punto para que `hora_inicio + minuto // 60` sea
    # la hora real; esto permite seguir reportando los minutos reales transcurridos.
    start_offset_min: int = 0
    route: list[Parada] = field(default_factory=list)
    arrival_minute: float | None = None
    continuous_riding_min: int = 0
    idle_min: int = 0
    earnings_mxn: float = 0
    completed: int = 0
    offered: int = 0
    # Lo que el runner declara que le falta a lo que ya viene en vuelo. Manda sobre
    # nuestra matriz: None cuando el ping no lo trae y hay que calcularlo con el mapa.
    in_flight_remaining_min: float | None = None
    shocks: tuple[Shock, ...] = ()  # disrupciones inyectadas por el juez
    accepted: dict[str, DecideRequest | None] = field(default_factory=dict)
    responses: dict[str, tuple[str, DecideResponse]] = field(default_factory=dict)

    @property
    def duracion_real(self) -> int:
        """Minutos del turno real, sin el desfase del reloj anclado a la hora en punto.

        La tabla de valor se escoge con esto. Con `config.duracion_min` (que incluye el
        desfase) un turno de 8 h que arranca a las 18:42 pedia la tabla de 8.5 h, y el
        primer /decide la cargaba del disco y se pasaba de 50 ms.
        """
        return self.config.duracion_min - self.start_offset_min

    def anclar(self, inicio: datetime) -> None:
        """Mueve el arranque del turno a `inicio`, con el reloj anclado a la hora en punto."""
        self.start_time, self.start_offset_min = origen_del_turno(inicio)
        total = round((self.end_time - self.start_time).total_seconds() / 60)
        self.config = replace(self.config, hora_inicio=self.start_time.hour, duracion_min=total)
