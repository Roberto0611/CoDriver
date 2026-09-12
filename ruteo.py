"""B2: el orden optimo de las paradas, y cuanto cuesta de verdad un pedido mas.

Con 3 pedidos en la mochila son 6 paradas y ~90 ordenes validos (recoger siempre
antes de entregar). Se prueban todos y gana el mas rapido: es la respuesta EXACTA,
no una heuristica, y tarda microsegundos. Por eso no hace falta OR-Tools aqui.

Lo que el motor consulta de verdad es `costo_marginal`: cuantos minutos EXTRA
cuesta meter este pedido a lo que ya traigo. Un pedido que va de paso cuesta 8
minutos, no 25 — y eso un umbral fijo de $/min no lo puede ver.
"""

from itertools import permutations

import rutas
from sim import Parada

MAX_PERMUTAR = 6  # 6! = 720 ordenes; de ahi para arriba se dispara

# La espera en el restaurante SI cuenta: al encadenar pedidos llegas a proposito
# antes de que esten listos, y esa espera es tiempo muerto. Sin contarla, la ruta
# mas corta en el mapa resulta la mas lenta en la vida real.


def _valida(orden: tuple[Parada, ...]) -> bool:
    """No se puede entregar lo que no se ha recogido.

    Ojo: un pedido que YA se recogio deja solo su dropoff en la ruta, sin pickup.
    La precedencia solo aplica a los que todavia traen su pickup pendiente; si no,
    ninguna permutacion es valida y la duracion sale infinita.
    """
    pendientes = {p.oferta_id for p in orden if p.tipo == "pickup"}
    recogidos = set()
    for p in orden:
        if p.tipo == "dropoff" and p.oferta_id in pendientes and p.oferta_id not in recogidos:
            return False
        if p.tipo == "pickup":
            recogidos.add(p.oferta_id)
    return True


def duracion(pos: int, orden, hora: int, t0: float = 0.0) -> float:
    """Minutos que toma la ruta. `hora` es la hora en t0; cada tramo usa la SUYA.

    Una ruta de 70 minutos que empieza a las 14:50 termina a las 16:00, y el ultimo
    tramo es el que se come la hora pico. Estimarla toda a las 14 es como se llega
    tarde con la cuenta cuadrada.
    """
    t, desde = t0, pos
    for p in orden:
        # `hora` ya incluye los minutos de t0, asi que se resta su hora y se suma la de t.
        t += rutas.minutos(desde, p.punto, hora + int(t) // 60 - int(t0) // 60)
        if p.tipo == "pickup":
            t = max(t, p.listo_en)  # esperando a que el restaurante termine
        desde = p.punto
    return t - t0


def mejor_ruta(
    pos: int, paradas: list[Parada], hora: int, t0: float = 0.0
) -> tuple[list[Parada], float]:
    """El orden mas rapido de visitar las paradas. La PRIMERA no se reordena:
    ya vas en camino a ella y no hay vuelta en U a media avenida."""
    if len(paradas) <= 1:
        return paradas, duracion(pos, paradas, hora, t0)

    fija, resto = paradas[0], paradas[1:]
    if not resto:
        return paradas, duracion(pos, paradas, hora, t0)

    if len(resto) > MAX_PERMUTAR:
        # ponytail: con la mochila llena de dropoffs pendientes, insertar en la
        # mejor posicion en vez de permutar todo. Deja de ser exacto, pero un
        # repartidor tampoco replanea 5040 rutas en un semaforo.
        return _por_insercion(pos, fija, resto, hora, t0)

    mejor, mejor_t = None, float("inf")
    for perm in permutations(resto):
        candidato = (fija,) + perm
        if not _valida(candidato):
            continue
        t = duracion(pos, candidato, hora, t0)
        if t < mejor_t:
            mejor, mejor_t = candidato, t

    if mejor is None:  # no deberia pasar; si pasa, mejor una ruta mala que un nan
        return paradas, duracion(pos, paradas, hora, t0)
    return list(mejor), mejor_t


def _por_insercion(pos, fija, resto, hora, t0):
    orden = [fija]
    for nueva in resto:
        mejor, mejor_t = None, float("inf")
        for i in range(len(orden) + 1):
            cand = orden[:i] + [nueva] + orden[i:]
            if not _valida(tuple(cand)):
                continue
            t = duracion(pos, cand, hora, t0)
            if t < mejor_t:
                mejor, mejor_t = cand, t
        orden = mejor or (orden + [nueva])
    return orden, duracion(pos, orden, hora, t0)


def costo_marginal(
    pos: int, ruta: list[Parada], nuevas: list[Parada], hora: int, t0: float = 0.0
) -> tuple[list[Parada], float]:
    """Minutos EXTRA de agregar `nuevas`, y la ruta reordenada que los logra."""
    _, sin = mejor_ruta(pos, ruta, hora, t0)
    con_ruta, con = mejor_ruta(pos, ruta + nuevas, hora, t0)
    return con_ruta, con - sin


def demo():
    """Dos pedidos al mismo rumbo deben salir mas baratos juntos que por separado."""
    tec = rutas.puntos_de("Tec")
    fun = rutas.puntos_de("Fundidora")
    hora = 14

    a = [Parada("pickup", tec[0], "A"), Parada("dropoff", fun[0], "A")]
    b = [Parada("pickup", tec[1], "B"), Parada("dropoff", fun[1], "B")]

    _, solo_b = mejor_ruta(tec[2], b, hora)
    _, marginal = costo_marginal(tec[2], a, b, hora)

    print(f"pedido B por su cuenta : {solo_b:.1f} min")
    print(f"pedido B encadenado a A: {marginal:.1f} min   <- lo que de verdad cuesta")
    assert marginal < solo_b, "encadenar tiene que salir mas barato que ir por separado"

    # Un pedido ya recogido deja su dropoff huerfano: la ruta sigue siendo valida.
    huerfano = [Parada("dropoff", fun[2], "C")] + b
    _, t_huerfano = mejor_ruta(tec[2], huerfano, hora)
    assert t_huerfano < float("inf"), "un dropoff sin su pickup no puede invalidar la ruta"

    ruta, _ = mejor_ruta(tec[2], a + b, hora)
    vistos = set()
    for p in ruta:
        if p.tipo == "dropoff":
            assert p.oferta_id in vistos, "entrego algo que no habia recogido"
        vistos.add(p.oferta_id)
    print(f"orden elegido: {[(p.tipo[:4], p.oferta_id) for p in ruta]}")
    print("OK")


if __name__ == "__main__":
    demo()
