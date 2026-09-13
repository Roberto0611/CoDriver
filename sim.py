"""A3 + A4: el simulador del turno.

    simular(cfg, politica) -> Resultado

Una funcion, dos usos: con la politica greedy es el baseline (B1), con la de
costo de oportunidad es Nuez (B6). Mismo seed = mismo stream de ofertas para
las dos, que es lo unico que hace valida la comparacion.

Corre headless en milisegundos: 300 turnos para la tabla de valor son segundos.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from typing import Literal

import rutas
import seguridad
import shocks
from contrato import ConfigTurno, Decision, EstadoRepartidor, Oferta, Punto

# --- A3: parametros del generador -------------------------------------------
# ponytail: numeros a ojo, calibrados para que un turno de 2h de ~$250-400.
# Esta es la perilla de la economia del juego; si el turno se siente falso, es aqui.
OFERTAS_POR_MIN = 0.8  # ~96 pings en una ventana de 2 horas
PAGO_BASE = 22.0  # lo que paga cualquier entrega, por corta que sea
PAGO_POR_KM = 7.0
RUIDO_PAGO = 0.35  # +-35%: SIN esto todos los pedidos rinden igual y no hay que decidir
PREP_MIN, PREP_MAX = 4, 15  # minutos que tarda el restaurante

# Que tan grande viene el pedido. Casi todo es comida y no pesa nada; la cola son
# los paquetes, que es donde el vehiculo empieza a importar (en bici no caben).
PESO_KG = (0.3, 6.0)
VOLUMEN_L = (2.0, 25.0)
PROB_PAQUETE = 0.10
PESO_PAQUETE = (5.0, 28.0)
VOLUMEN_PAQUETE = (20.0, 90.0)

# Un estudiante con 2 horas trabaja SU zona. Los pings normales salen cerca;
# la fraccion de trampas son los lejanos bien pagados que el motor debe rechazar.
RADIO_PICKUP = 9.0  # minutos a flujo libre desde el ancla
RADIO_ENTREGA = 11.0  # minutos a flujo libre desde el pickup
PROB_TRAMPA = 0.14  # 1 de cada 7 pings es un viaje largo y tentador
BONO_TRAMPA = 1.25  # y encima paga por arriba de tarifa: por eso tienta


@dataclass(frozen=True)
class Parada:
    tipo: Literal["pickup", "dropoff", "ancla"]
    punto: int
    oferta_id: str | None = None
    listo_en: int = 0  # minuto en que el restaurante termina; 0 = sin espera
    # El pedido ocupa el vehiculo hasta que se entrega, asi que la carga se suma
    # sobre los dropoff pendientes. Va aqui y no en el estado para que no se quede
    # viejo cuando entran dos ofertas en el mismo minuto.
    peso_kg: float = 0.0
    volumen_l: float = 0.0


@dataclass
class Resultado:
    ganado: float = 0.0
    entregas: int = 0
    rechazos: int = 0
    # LA linea es el ancla MENOS el margen, no el fin del turno: los 10 minutos de
    # colchon antes de clase son parte de la restriccion, no una cortesia. Un turno
    # que vuelve en el minuto 115 de 120 con margen 10 llego tarde.
    llego_tarde: bool = False
    regreso_en: float | None = None  # minuto exacto en que quedo de vuelta en el ancla
    # Dos cosas distintas, y solo la primera es romper una regla:
    #   violaciones     acepto algo que su propia cuenta decia que no alcanzaba
    #   llego_tarde     no volvio a tiempo (puede ser por algo posterior a aceptar)
    violaciones: int = 0
    minutos_ocupado: int = 0
    decisiones: list[Decision] = field(default_factory=list)
    ofertas: list[Oferta] = field(default_factory=list)
    trayecto: list[tuple[int, int, str]] = field(default_factory=list)  # (minuto, punto, tipo)
    # Tramos recorridos, para que el front anime la moto: (t_salida, t_llegada, desde, hasta)
    tramos: list[tuple[float, float, int, int]] = field(default_factory=list)
    cobros: list[tuple[int, float]] = field(default_factory=list)  # (minuto, pesos netos)
    cancelados: int = 0  # pedidos soltados porque una disrupcion los volvio infactibles
    # Distancia recorrida con y sin pedidos ya recogidos. La segunda es el
    # deadhead que pide la tabla de Results; ir al pickup y volver al ancla sin
    # carga cuentan, moverse con al menos un pedido en la mochila no.
    km_con_carga: float = 0.0
    km_sin_carga: float = 0.0


# --- A3: generador de ofertas ------------------------------------------------


@cache
def _vecinos(origen: int, radio_min: float) -> tuple[int, ...]:
    """Puntos a menos de radio_min a flujo libre. Cacheado: se pide miles de veces."""
    cerca = tuple(
        j
        for j in range(len(rutas.PUNTOS))
        if j != origen and rutas.minutos(j=j, i=origen, hora=3) <= radio_min
    )
    return cerca or tuple(j for j in range(len(rutas.PUNTOS)) if j != origen)


def generar_ofertas(cfg: ConfigTurno) -> list[Oferta]:
    """El guion fijo del turno. Depende solo del seed: el agente no puede influirlo."""
    rng = random.Random(cfg.seed)
    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)
    todos = tuple(range(len(rutas.PUNTOS)))

    ofertas: list[Oferta] = []
    for t in range(cfg.duracion_min):
        # Llegadas Poisson aproximadas: una moneda por minuto.
        if rng.random() > OFERTAS_POR_MIN:
            continue

        trampa = rng.random() < PROB_TRAMPA

        pickup = rng.choice(_vecinos(ancla, RADIO_PICKUP))
        dropoff = rng.choice(todos if trampa else _vecinos(pickup, RADIO_ENTREGA))
        if dropoff == pickup:
            continue

        paquete = rng.random() < PROB_PAQUETE
        peso = rng.uniform(*(PESO_PAQUETE if paquete else PESO_KG))
        volumen = rng.uniform(*(VOLUMEN_PAQUETE if paquete else VOLUMEN_L))

        pago = PAGO_BASE + PAGO_POR_KM * rutas.km(pickup, dropoff)
        pago *= rng.uniform(1 - RUIDO_PAGO, 1 + RUIDO_PAGO)
        if trampa:
            pago *= BONO_TRAMPA

        ofertas.append(
            Oferta(
                id=f"o_{len(ofertas):03d}",
                plataforma=rng.choice(["rappi", "uber", "didi"]),
                pago=round(pago, 1),
                surge=round(rng.choices([1.0, 1.3, 1.8], weights=[80, 15, 5])[0], 2),
                t_aparece=t,
                t_prep=rng.randint(PREP_MIN, PREP_MAX),
                pickup=_punto(pickup),
                dropoff=_punto(dropoff),
                peso_kg=round(peso, 1),
                volumen_l=round(volumen, 1),
            )
        )
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
#
# `activos` son las disrupciones vigentes en este minuto. Va como argumento y no
# como estado global a proposito: si el mundo cambia por debajo, el replay deja de
# reproducirse y no hay forma de auditar por que. Las politicas que no lo miran lo
# aceptan y lo ignoran; por eso el Protocol lleva **kwargs.


# ponytail: `Callable[...]` y no un Protocol. Cada politica trae sus propios
# kwargs opcionales (tabla, estrategia, activos) y un Protocol obligaria a que
# todas acepten todos. El tipo de retorno si se verifica, que es lo que importa.
Politica = Callable[..., tuple[list[Parada] | None, Decision]]


def _viola_su_propia_cuenta(dec: Decision) -> bool:
    """¿Acepto algo que sus propios numeros decian que no alcanzaba a terminar?

    Esto SI es romper la restriccion de fin de turno. Llegar tarde porque empezo a
    llover despues de aceptar es otra cosa, y se cuenta aparte.
    """
    falta = dec.terminos.get("minutos_para_terminar")
    cabe = dec.terminos.get("minutos_de_turno")
    return falta is not None and cabe is not None and falta > cabe


def _no_alcanza(
    ruta: list[Parada],
    t_llegada: float,
    cfg: ConfigTurno,
    activos: shocks.Activos,
) -> bool:
    """Con las condiciones de AHORA, ¿ya no da tiempo de terminar la ruta y volver?

    Arranca desde `t_llegada` en la PRIMERA parada, no desde la posicion actual: el
    repartidor ya va a media calle hacia ella. Recalcular ese tramo completo cada
    minuto suma un minuto de castigo por cada minuto en transito, y el chequeo
    termina cancelando pedidos que si se alcanzaban.

    Cada tramo se estima a SU hora, igual que `ruteo.duracion`; con una sola hora
    para toda la ruta tambien discrepa de la politica.
    """
    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)

    def tramo(a: int, b: int, cuando: float) -> float:
        minutos = rutas.minutos(a, b, cfg.hora_inicio + int(cuando) // 60, cfg.vehiculo)
        return minutos * activos.factor_tiempo(rutas.ZONA_DE[a], rutas.ZONA_DE[b])

    reloj, desde = t_llegada, ruta[0].punto
    if ruta[0].tipo == "pickup":
        reloj = max(reloj, ruta[0].listo_en)
    for parada in ruta[1:]:
        reloj += tramo(desde, parada.punto, reloj)
        if parada.tipo == "pickup":
            reloj = max(reloj, parada.listo_en)
        desde = parada.punto
    return reloj + tramo(desde, ancla, reloj) > cfg.duracion_min - cfg.margen_min


def simular(
    cfg: ConfigTurno, politica: Politica, disrupciones: tuple[shocks.Shock, ...] = ()
) -> Resultado:
    """Corre un turno completo. Determinista: mismo cfg.seed = mismo resultado.

    `disrupciones` viene de `shocks.generar`, que usa su PROPIO dado: el stream de
    ofertas no se mueve un byte, asi que el numero sin shocks sigue siendo el mismo.

    El reloj vive en `reloj.Turno` para que el demo en vivo avance minuto a minuto
    con el MISMO motor. Import tardio: reloj importa de sim.
    """
    from reloj import Turno

    turno = Turno(cfg, politica, disrupciones)
    while not turno.terminado:
        turno.paso()
    return turno.cerrar()


# --- B1: el baseline ---------------------------------------------------------


def politica_greedy(
    o: Oferta,
    est: EstadoRepartidor,
    ruta: list[Parada],
    cfg: ConfigTurno,
    *,
    activos: shocks.Activos = shocks.NINGUNO,
    **_,
) -> tuple[list[Parada] | None, Decision]:
    """Baseline honesto: acepta lo que se ve bien pagado y entrega en el orden que acepto.

    No es un hombre de paja: respeta capacidad, seguridad y se regresa cuando ya
    no le da el tiempo. Lo que NO hace es preguntarse cuanto valen sus minutos.
    """
    hora = (cfg.hora_inicio + est.t // 60) % 24
    i_pick, i_drop = indice_de(o.pickup), indice_de(o.dropoff)
    pos = indice_de(est.pos)
    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)

    # Lo que ya trae encolado cuenta: el pedido nuevo empieza cuando termine la ruta.
    # Cada tramo se estima a SU hora: la cola de hoy se recorre en el futuro.
    def leg(a: int, b: int, desde_min: float) -> float:
        """El tramo se recorre en `desde_min` minutos mas, y para entonces puede
        ser otra hora con otro trafico. La hora sale del minuto ABSOLUTO del turno."""
        minutos = rutas.minutos(a, b, cfg.hora_inicio + int(est.t + desde_min) // 60, cfg.vehiculo)
        return minutos * activos.factor_tiempo(rutas.ZONA_DE[a], rutas.ZONA_DE[b])

    cola, desde = 0.0, pos
    for p in ruta:
        cola += leg(desde, p.punto, cola)
        if p.tipo == "pickup":
            cola = max(cola, p.listo_en - est.t)  # esperando al restaurante
        desde = p.punto

    listo = o.t_aparece + o.t_prep + activos.retraso(o.id)
    minutos = cola + leg(desde, i_pick, cola)
    minutos = max(minutos, listo - est.t)
    minutos += leg(i_pick, i_drop, minutos)
    pago = o.pago * o.surge * activos.factor_pago(rutas.ZONA_DE[i_pick])
    neto = pago - rutas.km(i_pick, i_drop) * seguridad.VEHICULOS[cfg.vehiculo].costo_km
    propios = minutos - cola  # lo que cuesta ESTE pedido, sin la cola de adelante
    para_terminar = minutos + leg(i_drop, ancla, minutos)
    terminos = {
        "pago_neto": round(neto, 1),
        "minutos": round(propios, 1),
        "por_minuto": round(neto / max(propios, 1), 2),
        # La cuenta del fin de turno, para que se pueda auditar despues.
        "minutos_para_terminar": round(para_terminar, 1),
        "minutos_de_turno": round(est.t_restante - cfg.margen_min, 1),
    }

    def no(razon: str, restriccion=None):
        return None, Decision(est.t, o.id, "saltar", terminos, razon, restriccion)

    # El baseline es tonto con el dinero, NO con la seguridad: entra por la misma
    # puerta que Nuez. Un baseline que atropella restricciones no seria comparable.
    bloqueo = seguridad.revisar(
        vehiculo=cfg.vehiculo,
        hora=hora,
        zona_dropoff=rutas.ZONA_DE[i_drop],
        minutos_manejando=est.minutos_manejando,
        carga_kg=sum(p.peso_kg for p in ruta if p.tipo == "dropoff") + o.peso_kg,
        carga_l=sum(p.volumen_l for p in ruta if p.tipo == "dropoff") + o.volumen_l,
        pedidos_en_vuelo=len({p.oferta_id for p in ruta if p.oferta_id}) + 1,
        minutos_para_terminar=para_terminar,
        minutos_de_turno=est.t_restante - cfg.margen_min,
    )
    if bloqueo:
        return no(bloqueo[1], bloqueo[0])

    # Lo unico que SI se compra con dinero: el umbral fijo de $/min.
    if terminos["por_minuto"] < 3.0:
        return no("Paga muy poco por el tiempo.", "reservation_wage")

    nueva = ruta + [
        Parada("pickup", i_pick, o.id, listo),
        Parada("dropoff", i_drop, o.id, peso_kg=o.peso_kg, volumen_l=o.volumen_l),
    ]
    return nueva, Decision(est.t, o.id, "aceptar", terminos, f"Van {neto:.0f} pesos.")
