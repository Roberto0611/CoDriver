"""Contrato de eventos: la forma de todo lo que viaja entre piezas.

    Simulador  --Oferta-->  Motor  --Decision-->  Front / Voz

Esto se congela en la hora 1. Si alguien necesita cambiarlo, avisa a los otros
tres ANTES de cambiarlo. Cada carril mockea lo que le falta contra estas formas
y así los cuatro avanzan sin esperarse.

El tiempo SIEMPRE es "minutos desde que empezó el turno" (int). Nunca datetime:
el turno es simulado, corre a 60x, y los datetimes solo traen bugs de zona horaria.
"""

from dataclasses import asdict, dataclass, field
from typing import Literal

Accion = Literal["aceptar", "saltar"]
Vehiculo = Literal["moto", "car", "bike"]  # los tres que exige el protocolo

# `binding_constraint` del protocolo, con sus nombres exactos: es lo que deja al
# juez distinguir un rechazo por seguridad de uno por dinero sin leer la frase.
# Los limites de cada una viven en seguridad.py. `reservation_wage` no es una
# restriccion dura: es el costo de oportunidad, la unica que SI se compra con dinero.
Restriccion = Literal[
    "flagged_zone_night",
    "mandatory_break",
    "heat_rule",
    "shift_end_infeasible",
    "vehicle_capacity",
    "reservation_wage",
]


@dataclass(frozen=True)
class Punto:
    nombre: str
    lat: float
    lon: float


@dataclass(frozen=True)
class ConfigTurno:
    """Lo que el estudiante llena antes de arrancar."""

    duracion_min: int  # la ventana entre clases, ej. 120
    ancla: Punto  # a dónde tiene que volver
    margen_min: int = 10  # colchón antes de que empiece la clase
    vehiculo: Vehiculo = "moto"
    seed: int = 0  # mismo seed = mismo turno, siempre
    hora_inicio: int = 14  # hora del día: afecta tráfico, surge y riesgo


@dataclass(frozen=True)
class Oferta:
    """Un ping de la app. El simulador las emite, el motor las juzga."""

    id: str
    plataforma: str  # rappi | uber | didi
    pago: float  # pesos, antes de surge
    surge: float  # multiplicador, 1.0 = normal
    t_aparece: int  # minuto del turno en que entra el ping
    t_prep: int  # minutos que falta para que esté listo en el restaurante
    pickup: Punto
    dropoff: Punto
    peso_kg: float = 1.0  # una bici no carga lo mismo que un carro
    volumen_l: float = 5.0


@dataclass
class EstadoRepartidor:
    """Dónde va y cómo va. Lo lee el front para pintar, y el motor para decidir."""

    t: int  # minuto actual del turno
    t_restante: int
    pos: Punto
    mochila: list[str] = field(default_factory=list)  # ids de ofertas aceptadas
    ganado: float = 0.0
    fatiga: float = 0.0  # 0..1, sube con horas y con calor
    minutos_manejando: int = 0  # seguidos, sin descanso: manda el descanso y el calor


@dataclass(frozen=True)
class Decision:
    """Por qué el motor hizo lo que hizo. Alimenta el front, la voz y el contrafactual.

    `terminos` lleva TODOS los números que entraron a la decisión, no solo el
    resultado: de ahí sale la explicación al juez y el reporte contrafactual.
    """

    t: int
    oferta_id: str
    accion: Accion
    terminos: dict[str, float]  # pago_neto, minutos, precio_tiempo, gasolina, fatiga
    razon: str  # una frase, lista para la voz
    restriccion: Restriccion | None = None  # si mandó una restricción dura


@dataclass(frozen=True)
class EventoMundo:
    """Surge, cierre vial o lluvia. Lo dispara el simulador o el botón del juez."""

    t: int
    tipo: Literal["surge", "cierre", "lluvia", "evento_masivo"]
    zona: str
    duracion_min: int
    mult_demanda: float = 1.0  # cuántos más pings
    mult_tiempo: float = 1.0  # cuánto más tardado moverse ahí


def demo():
    """Round-trip a JSON: lo que se manda por el WebSocket es exactamente esto."""
    import json

    d = Decision(
        t=37,
        oferta_id="o_042",
        accion="saltar",
        terminos={"pago_neto": 67.2, "minutos": 34, "precio_tiempo": 91.0},
        razon="No alcanzas a volver al campus antes de las 4.",
        restriccion="shift_end_infeasible",
    )
    crudo = json.dumps(asdict(d))
    assert json.loads(crudo)["terminos"]["precio_tiempo"] == 91.0
    assert json.loads(crudo)["restriccion"] == "shift_end_infeasible"

    o = Oferta(
        "o_042",
        "rappi",
        48.0,
        1.4,
        37,
        8,
        Punto("Contry", 25.66, -100.28),
        Punto("Valle", 25.65, -100.36),
    )
    assert json.loads(json.dumps(asdict(o)))["pickup"]["nombre"] == "Contry"

    print(json.dumps(asdict(d), indent=2, ensure_ascii=False))
    print("OK: el contrato serializa y regresa igual.")


if __name__ == "__main__":
    demo()
