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
# Los litros van contra la caja de la moto (20 L, ver seguridad.VEHICULOS): una
# pizza no son 25 litros. Con comida de 1-8 L caben ~3 pedidos en la caja, igual que
# antes con 2-25 L en 60 L, y por eso la economia del turno no se entera del cambio.
# Los paquetes SI desbordan a proposito: es lo que hace que el vehiculo importe.
PESO_KG = (0.3, 6.0)
VOLUMEN_L = (1.0, 8.0)
PROB_PAQUETE = 0.10
PESO_PAQUETE = (5.0, 28.0)
VOLUMEN_PAQUETE = (12.0, 35.0)

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
    """
    ofertas = generar_ofertas(cfg)
    por_minuto: dict[int, list[Oferta]] = {}
    for o in ofertas:
        por_minuto.setdefault(o.t_aparece, []).append(o)

    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)
    res = Resultado(ofertas=ofertas)

    pos = ancla
    ruta: list[Parada] = []
    manejando = 0  # minutos seguidos con trabajo encima
    descansando = 0  # minutos seguidos parado; DESCANSO_MIN de estos resetean
    t_llegada = 0.0  # minuto en que se llega a la primera parada de la ruta
    regreso_en: float = 0.0  # arranca en el ancla, asi que a los 0 minutos ya esta
    listo_en: dict[str, int] = {}  # cuando esta listo cada pedido en el restaurante
    aceptadas: dict[str, Oferta] = {}
    carga_en_mochila: set[str] = set()

    def registrar_tramo(
        salida: float, llegada: float, origen: int, destino: int, *, con_carga: bool
    ) -> None:
        """Registra un tramo y sus km segun la carga al momento de salir."""
        res.tramos.append((salida, llegada, origen, destino))
        if con_carga:
            res.km_con_carga += rutas.km(origen, destino)
        else:
            res.km_sin_carga += rutas.km(origen, destino)

    for t in range(cfg.duracion_min):
        hora = (cfg.hora_inicio + t // 60) % 24
        activos = shocks.en(t, disrupciones)

        def viaje(a: int, b: int, cuando: float, act: shocks.Activos = activos) -> float:
            """Minutos reales de un tramo que SALE en `cuando`: el mapa, mas la disrupcion.

            La hora sale del momento de salida y no del minuto entero del reloj: un
            tramo que arranca en el 59.7 se recorre con el trafico de esa hora, no
            con el de la siguiente.
            """
            h = cfg.hora_inicio + int(cuando) // 60
            return rutas.minutos(a, b, h, cfg.vehiculo) * act.factor_tiempo(
                rutas.ZONA_DE[a], rutas.ZONA_DE[b]
            )

        # Una disrupcion puede volver infactible un plan que SI era factible al
        # aceptarlo: llueve a los 20 min y el regreso que eran 25 ahora son 34. El
        # repartidor no puede tirar comida que ya trae, pero si puede cancelar lo
        # que todavia no recoge. Cancela lo ultimo que acepto hasta que vuelva a
        # caberle el turno. Sin disrupciones esto no se dispara nunca: la politica
        # ya garantizo la factibilidad al aceptar.
        while ruta and ruta[0].tipo != "ancla" and _no_alcanza(ruta, t_llegada, cfg, activos):
            cancelable = [p.oferta_id for p in ruta if p.tipo == "pickup" and p.oferta_id]
            if not cancelable:
                break  # todo lo pendiente ya viene en la mochila: hay que entregarlo
            muerto = cancelable[-1]
            primera = ruta[0]
            ruta = [p for p in ruta if p.oferta_id != muerto]
            res.cancelados += 1
            if ruta and ruta[0] != primera:
                t_llegada = t + viaje(pos, ruta[0].punto, t)
                registrar_tramo(t, t_llegada, pos, ruta[0].punto, con_carga=bool(carga_en_mochila))

        estado = EstadoRepartidor(
            t=t,
            t_restante=cfg.duracion_min - t,
            pos=_punto(pos),
            mochila=[p.oferta_id for p in ruta if p.tipo == "pickup" and p.oferta_id],
            ganado=res.ganado,
            fatiga=min(1.0, res.minutos_ocupado / 240 * (1.3 if 12 <= hora <= 17 else 1.0)),
            minutos_manejando=manejando,
        )

        # 1. Decidir sobre los pings de este minuto.
        for o in por_minuto.get(t, []):
            nueva_ruta, dec = politica(o, estado, ruta, cfg, activos=activos)
            res.decisiones.append(dec)
            if nueva_ruta is not None and _viola_su_propia_cuenta(dec):
                res.violaciones += 1
            if nueva_ruta is None:
                res.rechazos += 1
                continue
            # ponytail: la parada en curso no se reordena (no hay vuelta en U a media
            # avenida). La politica replantea de la siguiente parada en adelante.
            if ruta and nueva_ruta[0] != ruta[0]:
                nueva_ruta = [ruta[0]] + [p for p in nueva_ruta if p != ruta[0]]
            if not ruta and nueva_ruta:
                t_llegada = t + viaje(pos, nueva_ruta[0].punto, t)
                registrar_tramo(
                    t, t_llegada, pos, nueva_ruta[0].punto, con_carga=bool(carga_en_mochila)
                )
            ruta = nueva_ruta
            aceptadas[o.id] = o
            listo_en[o.id] = o.t_aparece + o.t_prep + activos.retraso(o.id)

        # 2. Avanzar: llegar a la parada en curso si toca.
        while ruta and t >= t_llegada:
            parada = ruta[0]
            if parada.tipo == "pickup" and t < listo_en.get(parada.oferta_id or "", 0):
                break  # esperando a que el restaurante termine
            # El momento REAL en que queda libre esta parada. El siguiente tramo
            # arranca de aqui y no del minuto entero del reloj: redondear al alza en
            # cada parada regala hasta un minuto por parada, y esa demora inventada
            # es la que hacia llegar tarde a turnos que si alcanzaban.
            libre_en = max(float(t_llegada), float(parada.listo_en))
            pos = parada.punto
            ruta = ruta[1:]
            res.trayecto.append((t, pos, parada.tipo))
            if pos == ancla:
                regreso_en = t_llegada  # el minuto exacto, no el entero del reloj

            if parada.tipo == "pickup" and parada.oferta_id:
                carga_en_mochila.add(parada.oferta_id)

            if parada.tipo == "dropoff" and parada.oferta_id:
                o = aceptadas[parada.oferta_id]
                dist = rutas.km(indice_de(o.pickup), indice_de(o.dropoff))
                # El surge se cotiza al aparecer el ping, no al entregar: es lo que
                # la app le prometio al repartidor cuando acepto.
                cuando = shocks.en(o.t_aparece, disrupciones)
                pago = o.pago * o.surge * cuando.factor_pago(rutas.ZONA_DE[indice_de(o.pickup)])
                cobro = pago - dist * seguridad.VEHICULOS[cfg.vehiculo].costo_km
                res.cobros.append((t, round(cobro, 2)))
                res.ganado += cobro
                res.entregas += 1
                carga_en_mochila.remove(parada.oferta_id)

            if ruta:
                t_llegada = libre_en + viaje(pos, ruta[0].punto, libre_en)
                # La salida es el momento REAL en que quedo libre, no el minuto
                # entero del reloj: si no, el front anima la moto mas lenta de lo
                # que va y el tramo no cuadra con el mapa.
                registrar_tramo(
                    libre_en,
                    t_llegada,
                    pos,
                    ruta[0].punto,
                    con_carga=bool(carga_en_mochila),
                )

        # Regresar al ancla es obligacion de cualquier politica: si ya no queda
        # tiempo mas que para volver, el simulador encamina de regreso.
        if not ruta and pos != ancla:
            regreso = viaje(pos, ancla, t)
            # Sale cuando esperar UN MINUTO MAS ya no lo dejaria volver a tiempo, no
            # cuando salir ahora apenas alcanza: lo segundo hace que llegue justo
            # ENCIMA del limite siempre. Mirar al minuto siguiente cubre de paso el
            # salto de trafico al cambiar de hora (car, 8 h desde las 8, seed 2000).
            if t + 1 + viaje(pos, ancla, t + 1) > cfg.duracion_min - cfg.margen_min:
                ruta = [Parada("ancla", ancla)]
                t_llegada = t + regreso
                registrar_tramo(t, t_llegada, pos, ancla, con_carga=bool(carga_en_mochila))

        # Restricciones 2 y 3: el contador de minutos continuos. Parar 20 minutos
        # lo resetea, y como la politica rechaza todo mientras el limite este
        # alcanzado, el descanso se toma solo: no hace falta una maquina de estados.
        if ruta:
            res.minutos_ocupado += 1
            manejando += 1
            descansando = 0
        else:
            descansando += 1
            if descansando >= seguridad.DESCANSO_MIN:
                manejando = 0

    res.ganado = round(res.ganado, 2)
    res.km_con_carga = round(res.km_con_carga, 3)
    res.km_sin_carga = round(res.km_sin_carga, 3)
    res.regreso_en = regreso_en if pos == ancla and not ruta else None
    limite = cfg.duracion_min - cfg.margen_min
    res.llego_tarde = res.regreso_en is None or res.regreso_en > limite
    return res


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
