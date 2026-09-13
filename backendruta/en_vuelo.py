"""Pedidos en vuelo: de lo que manda el protocolo a paradas del motor.

El runner oficial de Infosys (`run_probe_pack.py`, el mismo que corren los jueces) los
manda como `{"order_id", "minutes_remaining", "dropoff_zone"}`. Nuestro formato usa
`zone_dropoff` y `status`. Se aceptan los dos: tronar aqui con un 422 es una falla dura
de Feasibility, no un problema de formato.
"""

from collections.abc import Callable
from typing import Any

from backendruta import zonas
from sim import Parada


def traducir(
    orders: list[dict[str, Any]],
    *,
    resolver: Callable[[int], int],
    zona_actual: int,
    minuto: int,
) -> tuple[list[Parada], list[str], float | None]:
    """La ruta, los ids en vuelo y lo que el runner declaro que les falta.

    Lo declarado es el MAXIMO de `minutes_remaining`: cada pedido termina a su hora,
    independiente de los demas, y el repartidor queda libre cuando acaba el ultimo.
    Es None si alguno no lo trae, porque entonces hay que calcularlo con el mapa.
    """
    ruta: list[Parada] = []
    ids: list[str] = []
    restantes: list[float] = []
    for posicion, raw in enumerate(orders):
        try:
            order_id = str(raw["order_id"])
            pickup_raw = raw.get("zone_pickup", raw.get("pickup_zone"))
            pickup = resolver(int(pickup_raw) if pickup_raw is not None else zona_actual)
            dropoff_raw = raw["zone_dropoff"] if "zone_dropoff" in raw else raw["dropoff_zone"]
            dropoff = resolver(int(dropoff_raw))
            if "minutes_remaining" in raw:
                restantes.append(max(0.0, float(raw["minutes_remaining"])))
            prep = max(0, round(float(raw.get("restaurant_prep_min", 0))))
            peso = float(raw.get("weight_kg", 1))
            volumen = float(raw.get("volume_liters", 5))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"in_flight_orders[{posicion}] incompleto") from exc

        # Con `minutes_remaining` el pedido ya esta en marcha: solo ocupa lugar en el
        # vehiculo hasta entregarse.
        por_omision = "to_dropoff" if "minutes_remaining" in raw else "to_pickup"
        if str(raw.get("status", por_omision)) not in {"picked_up", "to_dropoff"}:
            ruta.append(Parada("pickup", zonas.indice(pickup), order_id, minuto + prep))
        ruta.append(
            Parada("dropoff", zonas.indice(dropoff), order_id, peso_kg=peso, volumen_l=volumen)
        )
        ids.append(order_id)

    declarado = max(restantes) if restantes and len(restantes) == len(orders) else None
    return ruta, ids, declarado


def demo():
    identidad = int
    del_runner = [{"order_id": "PP-012", "minutes_remaining": 7.0, "dropoff_zone": 2}]
    ruta, ids, declarado = traducir(del_runner, resolver=identidad, zona_actual=4, minuto=0)
    assert ids == ["PP-012"] and declarado == 7.0
    assert [p.tipo for p in ruta] == ["dropoff"], "ya en marcha: solo ocupa lugar"

    nuestro = [{"order_id": "A", "zone_pickup": 4, "zone_dropoff": 2, "restaurant_prep_min": 5}]
    ruta, _, declarado = traducir(nuestro, resolver=identidad, zona_actual=4, minuto=10)
    assert [p.tipo for p in ruta] == ["pickup", "dropoff"] and declarado is None
    assert ruta[0].listo_en == 15

    mixto = del_runner + nuestro
    assert traducir(mixto, resolver=identidad, zona_actual=4, minuto=0)[2] is None, (
        "si uno no declara, se calcula con el mapa"
    )

    try:
        traducir([{"order_id": "X"}], resolver=identidad, zona_actual=4, minuto=0)
    except ValueError as exc:
        assert "incompleto" in str(exc)
    else:
        raise AssertionError("sin zona de entrega tiene que fallar claro")
    print("OK: acepta la forma del runner y la nuestra")


if __name__ == "__main__":
    demo()
