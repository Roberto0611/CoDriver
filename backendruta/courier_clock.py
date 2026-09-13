"""El reloj de una sesion /decide: avanzar minutos, llegar a paradas y anotarlo.

`CourierService` no corre un `reloj.Turno`: el runner manda pings sueltos y entre uno
y otro el repartidor sigue manejando. Esto adelanta el estado hasta el minuto del
ping, cobra lo que se entrego en el camino y deja los `position_update` y
`earnings_update` del protocolo en el log.
"""

import math

import rutas
from backendruta import courier_format
from backendruta.courier_models import ShiftState
from backendruta.event_log import EventLog
from backendruta.zonas import ID_POR_NOMBRE


def zone_id(state: ShiftState) -> int:
    """El id publico (GET /zones) de la zona donde esta el repartidor."""
    return ID_POR_NOMBRE[rutas.ZONA_DE[state.position]]


def schedule_arrival(state: ShiftState, minute: int) -> None:
    assert state.route
    destination = state.route[0]
    hour = state.config.hora_inicio + minute // 60
    arrival = minute + rutas.minutos(state.position, destination.punto, hour, state.config.vehiculo)
    if destination.tipo == "pickup":
        arrival = max(arrival, destination.listo_en)
    state.arrival_minute = arrival


def advance(state: ShiftState, log: EventLog, target_minute: int) -> None:
    while state.current_minute < target_minute:
        if not state.route:
            idle = target_minute - state.current_minute
            state.idle_min += idle
            if state.idle_min >= 20:
                state.continuous_riding_min = 0
            state.current_minute = target_minute
            break
        arrival = math.ceil(state.arrival_minute or state.current_minute)
        stop = min(target_minute, arrival)
        busy = max(0, stop - state.current_minute)
        state.continuous_riding_min += busy
        state.idle_min = 0
        state.current_minute = stop
        if stop < arrival:
            break
        destination = state.route.pop(0)
        state.position = destination.punto
        if destination.tipo == "dropoff" and destination.oferta_id:
            order = state.accepted.pop(destination.oferta_id, None)
            if order:
                state.completed += 1
                state.earnings_mxn += courier_format.net_pay(order)
                log.append(
                    courier_format.earnings_event(
                        state.start_time, state.current_minute, state.earnings_mxn, state.completed
                    )
                )
        log.append(
            courier_format.position_event(
                state.start_time, state.current_minute, zone_id(state), state.route
            )
        )
        if state.route:
            schedule_arrival(state, state.current_minute)
        else:
            state.arrival_minute = None
