"""A3 + A4: el simulador del turno.

    simular(cfg, politica) -> Resultado

Una funcion, dos usos: con la politica greedy es el baseline (B1), con la de
costo de oportunidad es Nuez (B6). Mismo seed = mismo stream de ofertas para
las dos, que es lo unico que hace valida la comparacion.

Corre headless en milisegundos: 300 turnos para la tabla de valor son segundos.
"""

import random
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Literal

import rutas
from contrato import ConfigTurno, Decision, EstadoRepartidor, Oferta, Punto
from mundo import es_segura

# --- A3: parametros del generador -------------------------------------------
# ponytail: numeros a ojo, calibrados para que un turno de 2h de ~$250-400.
# Esta es la perilla de la economia del juego; si el turno se siente falso, es aqui.
OFERTAS_POR_MIN = 0.8      # ~96 pings en una ventana de 2 horas
PAGO_BASE = 22.0           # lo que paga cualquier entrega, por corta que sea
PAGO_POR_KM = 7.0
RUIDO_PAGO = 0.35          # +-35%: SIN esto todos los pedidos rinden igual y no hay que decidir
PREP_MIN, PREP_MAX = 4, 15  # minutos que tarda el restaurante
CAPACIDAD = 3              # pedidos simultaneos en la mochila

# Un estudiante con 2 horas trabaja SU zona. Los pings normales salen cerca;
# la fraccion de trampas son los lejanos bien pagados que el motor debe rechazar.
RADIO_PICKUP = 9.0         # minutos a flujo libre desde el ancla
RADIO_ENTREGA = 11.0       # minutos a flujo libre desde el pickup
PROB_TRAMPA = 0.14         # 1 de cada 7 pings es un viaje largo y tentador
BONO_TRAMPA = 1.25         # y encima paga por arriba de tarifa: por eso tienta
VELOCIDAD = {"moto": 1.0, "scooter": 1.25, "bici": 1.8, "pie": 5.0}
COSTO_KM = {"moto": 1.8, "scooter": 0.9, "bici": 0.0, "pie": 0.0}   # pesos de gasolina


@dataclass(frozen=True)
class Parada:
    tipo: Literal["pickup", "dropoff", "ancla"]
    punto: int
    oferta_id: str | None = None


@dataclass
class Resultado:
    ganado: float = 0.0
    entregas: int = 0
    rechazos: int = 0
    llego_tarde: bool = False
    minutos_ocupado: int = 0
    decisiones: list[Decision] = field(default_factory=list)
    ofertas: list[Oferta] = field(default_factory=list)
    trayecto: list[tuple[int, int, str]] = field(default_factory=list)  # (minuto, punto, tipo)
    # Tramos recorridos, para que el front anime la moto: (t_salida, t_llegada, desde, hasta)
    tramos: list[tuple[int, float, int, int]] = field(default_factory=list)
    cobros: list[tuple[int, float]] = field(default_factory=list)   # (minuto, pesos netos)


# --- A3: generador de ofertas ------------------------------------------------


@lru_cache(maxsize=None)
def _vecinos(origen: int, radio_min: float) -> tuple[int, ...]:
    """Puntos a menos de radio_min a flujo libre. Cacheado: se pide miles de veces."""
    cerca = tuple(j for j in range(len(rutas.PUNTOS))
                  if j != origen and rutas.minutos(j=j, i=origen, hora=3) <= radio_min)
    return cerca or tuple(j for j in range(len(rutas.PUNTOS)) if j != origen)


def generar_ofertas(cfg: ConfigTurno) -> list[Oferta]:
    """El guion fijo del turno. Depende solo del seed: el agente no puede influirlo."""
    rng = random.Random(cfg.seed)
    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)
    todos = tuple(range(len(rutas.PUNTOS)))

    ofertas = []
    for t in range(cfg.duracion_min):
        # Llegadas Poisson aproximadas: una moneda por minuto.
        if rng.random() > OFERTAS_POR_MIN:
            continue

        hora = (cfg.hora_inicio + t // 60) % 24
        trampa = rng.random() < PROB_TRAMPA

        pickup = rng.choice(_vecinos(ancla, RADIO_PICKUP))
        dropoff = rng.choice(todos if trampa else _vecinos(pickup, RADIO_ENTREGA))
        if dropoff == pickup:
            continue

        pago = (PAGO_BASE + PAGO_POR_KM * rutas.km(pickup, dropoff))
        pago *= rng.uniform(1 - RUIDO_PAGO, 1 + RUIDO_PAGO)
        if trampa:
            pago *= BONO_TRAMPA

        ofertas.append(Oferta(
            id=f"o_{len(ofertas):03d}",
            plataforma=rng.choice(["rappi", "uber", "didi"]),
            pago=round(pago, 1),
            surge=round(rng.choices([1.0, 1.3, 1.8], weights=[80, 15, 5])[0], 2),
            t_aparece=t,
            t_prep=rng.randint(PREP_MIN, PREP_MAX),
            pickup=_punto(pickup),
            dropoff=_punto(dropoff),
        ))
    return ofertas


def _punto(i: int) -> Punto:
    lat, lon = rutas.COORD_DE[i]
    return Punto(nombre=f"{rutas.ZONA_DE[i]}#{i}", lat=lat, lon=lon)


def indice_de(p: Punto) -> int:
    """El indice del punto va en el nombre: 'Valle#147' -> 147."""
    return int(p.nombre.split("#")[1])


# --- A4: el reloj ------------------------------------------------------------

# Una politica recibe la oferta, el estado y la ruta actual; devuelve la ruta
# nueva si acepta (o None si salta) mas la Decision con sus terminos.
Politica = Callable[[Oferta, EstadoRepartidor, list[Parada], ConfigTurno],
                    tuple[list[Parada] | None, Decision]]


def simular(cfg: ConfigTurno, politica: Politica) -> Resultado:
    """Corre un turno completo. Determinista: mismo cfg.seed = mismo resultado."""
    ofertas = generar_ofertas(cfg)
    por_minuto: dict[int, list[Oferta]] = {}
    for o in ofertas:
        por_minuto.setdefault(o.t_aparece, []).append(o)

    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)
    res = Resultado(ofertas=ofertas)

    pos = ancla
    ruta: list[Parada] = []
    t_llegada = 0.0            # minuto en que se llega a la primera parada de la ruta
    listo_en: dict[str, int] = {}   # cuando esta listo cada pedido en el restaurante
    aceptadas: dict[str, Oferta] = {}

    for t in range(cfg.duracion_min):
        hora = (cfg.hora_inicio + t // 60) % 24
        estado = EstadoRepartidor(
            t=t, t_restante=cfg.duracion_min - t, pos=_punto(pos),
            mochila=[p.oferta_id for p in ruta if p.tipo == "pickup" and p.oferta_id],
            ganado=res.ganado,
            fatiga=min(1.0, res.minutos_ocupado / 240 * (1.3 if 12 <= hora <= 17 else 1.0)),
        )

        # 1. Decidir sobre los pings de este minuto.
        for o in por_minuto.get(t, []):
            nueva_ruta, dec = politica(o, estado, ruta, cfg)
            res.decisiones.append(dec)
            if nueva_ruta is None:
                res.rechazos += 1
                continue
            # ponytail: la parada en curso no se reordena (no hay vuelta en U a media
            # avenida). La politica replantea de la siguiente parada en adelante.
            if ruta and nueva_ruta[0] != ruta[0]:
                nueva_ruta = [ruta[0]] + [p for p in nueva_ruta if p != ruta[0]]
            if not ruta and nueva_ruta:
                t_llegada = t + rutas.minutos(pos, nueva_ruta[0].punto, hora)
                res.tramos.append((t, t_llegada, pos, nueva_ruta[0].punto))
            ruta = nueva_ruta
            aceptadas[o.id] = o
            listo_en[o.id] = o.t_aparece + o.t_prep

        # 2. Avanzar: llegar a la parada en curso si toca.
        while ruta and t >= t_llegada:
            parada = ruta[0]
            if parada.tipo == "pickup" and t < listo_en.get(parada.oferta_id, 0):
                break   # esperando a que el restaurante termine
            pos = parada.punto
            ruta = ruta[1:]
            res.trayecto.append((t, pos, parada.tipo))

            if parada.tipo == "dropoff" and parada.oferta_id:
                o = aceptadas[parada.oferta_id]
                dist = rutas.km(indice_de(o.pickup), indice_de(o.dropoff))
                cobro = o.pago * o.surge - dist * COSTO_KM[cfg.vehiculo]
                res.cobros.append((t, round(cobro, 2)))
                res.ganado += cobro
                res.entregas += 1

            if ruta:
                t_llegada = t + rutas.minutos(pos, ruta[0].punto, hora)
                res.tramos.append((t, t_llegada, pos, ruta[0].punto))

        # Regresar al ancla es obligacion de cualquier politica: si ya no queda
        # tiempo mas que para volver, el simulador encamina de regreso.
        if not ruta and pos != ancla:
            if t + rutas.minutos(pos, ancla, hora) >= cfg.duracion_min - cfg.margen_min:
                ruta = [Parada("ancla", ancla)]
                t_llegada = t + rutas.minutos(pos, ancla, hora)
                res.tramos.append((t, t_llegada, pos, ancla))

        if ruta:
            res.minutos_ocupado += 1

    res.ganado = round(res.ganado, 2)
    res.llego_tarde = pos != ancla or bool(ruta)
    return res


# --- B1: el baseline ---------------------------------------------------------


def politica_greedy(o: Oferta, est: EstadoRepartidor, ruta: list[Parada],
                    cfg: ConfigTurno) -> tuple[list[Parada] | None, Decision]:
    """Baseline honesto: acepta lo que se ve bien pagado y entrega en el orden que acepto.

    No es un hombre de paja: respeta capacidad, seguridad y se regresa cuando ya
    no le da el tiempo. Lo que NO hace es preguntarse cuanto valen sus minutos.
    """
    hora = (cfg.hora_inicio + est.t // 60) % 24
    i_pick, i_drop = indice_de(o.pickup), indice_de(o.dropoff)
    pos = indice_de(est.pos)
    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)

    # Lo que ya trae encolado cuenta: el pedido nuevo empieza cuando termine la ruta.
    cola, desde = 0.0, pos
    for p in ruta:
        cola += rutas.minutos(desde, p.punto, hora)
        desde = p.punto

    minutos = cola + rutas.minutos(desde, i_pick, hora) + rutas.minutos(i_pick, i_drop, hora)
    neto = o.pago * o.surge - rutas.km(i_pick, i_drop) * COSTO_KM[cfg.vehiculo]
    propios = minutos - cola      # lo que cuesta ESTE pedido, sin la cola de adelante
    terminos = {"pago_neto": round(neto, 1), "minutos": round(propios, 1),
                "por_minuto": round(neto / max(propios, 1), 2)}

    def no(razon: str, restriccion=None):
        return None, Decision(est.t, o.id, "saltar", terminos, razon, restriccion)

    if len(est.mochila) >= CAPACIDAD:
        return no("Ya traigo la mochila llena.", "mochila_llena")
    if not es_segura(rutas.ZONA_DE[i_drop], hora):
        return no(f"No te mando a {rutas.ZONA_DE[i_drop]} a esta hora.", "zona_insegura")
    # Se regresa cuando ya no da el tiempo, pero sin pensar en el costo de oportunidad.
    if minutos + rutas.minutos(i_drop, ancla, hora) > est.t_restante - cfg.margen_min:
        return no("Ya no alcanzo a volver.", "regreso_infactible")
    if terminos["por_minuto"] < 3.0:
        return no("Paga muy poco por el tiempo.")

    nueva = ruta + [Parada("pickup", i_pick, o.id), Parada("dropoff", i_drop, o.id)]
    return nueva, Decision(est.t, o.id, "aceptar", terminos, f"Van {neto:.0f} pesos.")
