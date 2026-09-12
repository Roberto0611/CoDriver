"""El contrato serializa a JSON y regresa igual. Es lo que viaja por el WebSocket."""

import json
from dataclasses import asdict

from contrato import ConfigTurno, Decision, EstadoRepartidor, EventoMundo, Oferta, Punto


def test_decision_round_trip():
    d = Decision(
        t=37,
        oferta_id="o_042",
        accion="saltar",
        terminos={"pago_neto": 67.2, "minutos": 34, "precio_tiempo": 91.0},
        razon="No alcanzas a volver al campus antes de las 4.",
        restriccion="regreso_infactible",
    )
    back = json.loads(json.dumps(asdict(d)))
    assert back["terminos"]["precio_tiempo"] == 91.0
    assert back["restriccion"] == "regreso_infactible"
    assert back["accion"] == "saltar"


def test_decision_sin_restriccion_serializa_null():
    d = Decision(t=0, oferta_id="o_000", accion="aceptar", terminos={}, razon="Van 50 pesos.")
    assert json.loads(json.dumps(asdict(d)))["restriccion"] is None


def test_oferta_round_trip_con_puntos_anidados():
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
    back = json.loads(json.dumps(asdict(o)))
    assert back["pickup"]["nombre"] == "Contry"
    assert back["dropoff"]["lon"] == -100.36


def test_config_turno_defaults():
    cfg = ConfigTurno(duracion_min=120, ancla=Punto("Tec", 25.65, -100.29))
    assert cfg.margen_min == 10
    assert cfg.vehiculo == "moto"
    assert cfg.seed == 0
    assert cfg.hora_inicio == 14


def test_estado_y_evento_serializan():
    est = EstadoRepartidor(t=5, t_restante=115, pos=Punto("Tec", 25.65, -100.29))
    assert json.loads(json.dumps(asdict(est)))["mochila"] == []
    ev = EventoMundo(t=40, tipo="surge", zona="Valle", duracion_min=20, mult_demanda=1.8)
    assert json.loads(json.dumps(asdict(ev)))["mult_tiempo"] == 1.0
