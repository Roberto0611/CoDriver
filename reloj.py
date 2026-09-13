"""A4: el reloj del turno, minuto a minuto.

    turno = Turno(cfg, politica)
    while not turno.terminado:
        turno.paso()
    res = turno.cerrar()

Es el MISMO cuerpo que `sim.simular()`, solo que aqui cada minuto es una llamada
en vez de una vuelta del for. Eso es lo que necesita el demo en vivo: el browser
llama a `paso()` un minuto a la vez y el juez puede `inyectar()` un shock a media
jornada, en el mismo motor que corre el baseline offline. `simular()` no
desaparece, nomas se vuelve un wrapper que le da vuelta a este reloj de un jalon
(ver sim.py).

Por que inyectar a medio turno da lo mismo que declarar el shock desde el inicio:
cada lectura de la lista de disrupciones pasa por `shocks.en(t, disrupciones)`,
incluido el surge que se cotiza al aparecer el ping. Un shock con t >= ahora que
se agrega despues es invisible para todos los minutos que ya corrieron, asi que
inyectar en el minuto m produce la misma historia que declararlo desde el inicio.
"""

import math

import rutas
import seguridad
import shocks
from contrato import ConfigTurno, EstadoRepartidor, Oferta
from sim import (
    Parada,
    Politica,
    Resultado,
    _no_alcanza,
    _punto,
    _viola_su_propia_cuenta,
    generar_ofertas,
    indice_de,
)


class Turno:
    """El estado de un turno a medio correr, expuesto para que el front lo anime."""

    def __init__(
        self,
        cfg: ConfigTurno,
        politica: Politica,
        disrupciones: tuple[shocks.Shock, ...] = (),
        ofertas: list[Oferta] | None = None,
    ) -> None:
        ofertas = generar_ofertas(cfg) if ofertas is None else ofertas
        por_minuto: dict[int, list[Oferta]] = {}
        for o in ofertas:
            por_minuto.setdefault(o.t_aparece, []).append(o)

        self.cfg = cfg
        self.politica = politica
        self.disrupciones = disrupciones

        self.ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)
        self.res = Resultado(ofertas=ofertas)
        self.por_minuto = por_minuto

        self.t = 0
        self.pos = self.ancla
        self.ruta: list[Parada] = []
        self.manejando = 0  # minutos seguidos con trabajo encima
        self.descansando = 0  # minutos seguidos parado; DESCANSO_MIN de estos resetean
        self.t_llegada = 0.0  # minuto en que se llega a la primera parada de la ruta
        self.regreso_en: float = 0.0  # arranca en el ancla, asi que a los 0 minutos ya esta
        self.termino_en: float = 0.0  # ultima vez que quedo libre; sin regreso, ahi acaba
        self.listo_en: dict[str, int] = {}  # cuando esta listo cada pedido en el restaurante
        self.aceptadas: dict[str, Oferta] = {}
        self.carga_en_mochila: set[str] = set()
        self._cerrado = False

    @property
    def terminado(self) -> bool:
        return self.t >= self.cfg.duracion_min

    def activos(self) -> shocks.Activos:
        return shocks.en(self.t, self.disrupciones)

    def inyectar(self, shock: shocks.Shock) -> None:
        """Agrega una disrupcion a media jornada. No se vale inyectar en el pasado:
        el minuto shock.t ya corrio y nadie lo va a releer."""
        if shock.t < self.t:
            raise ValueError(f"no se puede inyectar un shock en el pasado (t={shock.t} < {self.t})")
        self.disrupciones = (*self.disrupciones, shock)

    def _registrar_tramo(
        self, salida: float, llegada: float, origen: int, destino: int, *, con_carga: bool
    ) -> None:
        """Registra un tramo y sus km segun la carga al momento de salir."""
        self.res.tramos.append((salida, llegada, origen, destino))
        km = rutas.km(origen, destino)
        if con_carga:
            self.res.km_con_carga += km
        else:
            self.res.km_sin_carga += km
        # El conductor paga cada km que recorre: llegar al restaurante y volver al
        # ancla también consumen combustible. Se registra al salir para que el
        # contador live enseñe utilidad neta, incluso antes del primer cobro.
        costo = km * seguridad.VEHICULOS[self.cfg.vehiculo].costo_km
        self.res.gasto_combustible += costo
        self.res.ganado -= costo
        self.res.cobros.append((math.ceil(salida), -round(costo, 2)))

    def _viaje(self, a: int, b: int, cuando: float, act: shocks.Activos) -> float:
        """Minutos reales de un tramo que SALE en `cuando`: el mapa, mas la disrupcion.

        La hora sale del momento de salida y no del minuto entero del reloj: un
        tramo que arranca en el 59.7 se recorre con el trafico de esa hora, no
        con el de la siguiente.
        """
        h = self.cfg.hora_inicio + int(cuando) // 60
        return rutas.minutos(a, b, h, self.cfg.vehiculo) * act.factor_tiempo(
            rutas.ZONA_DE[a], rutas.ZONA_DE[b]
        )

    def paso(self) -> None:
        """Corre el minuto self.t y avanza el reloj."""
        cfg, res = self.cfg, self.res
        t = self.t
        hora = (cfg.hora_inicio + t // 60) % 24
        activos = shocks.en(t, self.disrupciones)

        def viaje(a: int, b: int, cuando: float, act: shocks.Activos = activos) -> float:
            return self._viaje(a, b, cuando, act)

        # Una disrupcion puede volver infactible un plan que SI era factible al
        # aceptarlo: llueve a los 20 min y el regreso que eran 25 ahora son 34. El
        # repartidor no puede tirar comida que ya trae, pero si puede cancelar lo
        # que todavia no recoge. Cancela lo ultimo que acepto hasta que vuelva a
        # caberle el turno. Sin disrupciones esto no se dispara nunca: la politica
        # ya garantizo la factibilidad al aceptar.
        while (
            self.ruta
            and self.ruta[0].tipo != "ancla"
            and _no_alcanza(self.ruta, self.t_llegada, cfg, activos)
        ):
            cancelable = [p.oferta_id for p in self.ruta if p.tipo == "pickup" and p.oferta_id]
            if not cancelable:
                break  # todo lo pendiente ya viene en la mochila: hay que entregarlo
            muerto = cancelable[-1]
            primera = self.ruta[0]
            self.ruta = [p for p in self.ruta if p.oferta_id != muerto]
            res.cancelados += 1
            if self.ruta and self.ruta[0] != primera:
                self.t_llegada = t + viaje(self.pos, self.ruta[0].punto, t)
                self._registrar_tramo(
                    t,
                    self.t_llegada,
                    self.pos,
                    self.ruta[0].punto,
                    con_carga=bool(self.carga_en_mochila),
                )

        estado = EstadoRepartidor(
            t=t,
            t_restante=cfg.duracion_min - t,
            pos=_punto(self.pos),
            mochila=[p.oferta_id for p in self.ruta if p.tipo == "pickup" and p.oferta_id],
            ganado=res.ganado,
            fatiga=min(1.0, res.minutos_ocupado / 240 * (1.3 if 12 <= hora <= 17 else 1.0)),
            minutos_manejando=self.manejando,
        )

        # 1. Decidir sobre los pings de este minuto.
        for o in self.por_minuto.get(t, []):
            nueva_ruta, dec = self.politica(o, estado, self.ruta, cfg, activos=activos)
            res.decisiones.append(dec)
            if nueva_ruta is not None and _viola_su_propia_cuenta(dec):
                res.violaciones += 1
            if nueva_ruta is None:
                res.rechazos += 1
                continue
            # ponytail: la parada en curso no se reordena (no hay vuelta en U a media
            # avenida). La politica replantea de la siguiente parada en adelante.
            if self.ruta and nueva_ruta[0] != self.ruta[0]:
                nueva_ruta = [self.ruta[0]] + [p for p in nueva_ruta if p != self.ruta[0]]
            if not self.ruta and nueva_ruta:
                self.t_llegada = t + viaje(self.pos, nueva_ruta[0].punto, t)
                self._registrar_tramo(
                    t,
                    self.t_llegada,
                    self.pos,
                    nueva_ruta[0].punto,
                    con_carga=bool(self.carga_en_mochila),
                )
            self.ruta = nueva_ruta
            self.aceptadas[o.id] = o
            self.listo_en[o.id] = o.t_aparece + o.t_prep + activos.retraso(o.id)

        # 2. Avanzar: llegar a la parada en curso si toca.
        while self.ruta and t >= self.t_llegada:
            parada = self.ruta[0]
            if parada.tipo == "pickup" and t < self.listo_en.get(parada.oferta_id or "", 0):
                break  # esperando a que el restaurante termine
            # El momento REAL en que queda libre esta parada. El siguiente tramo
            # arranca de aqui y no del minuto entero del reloj: redondear al alza en
            # cada parada regala hasta un minuto por parada, y esa demora inventada
            # es la que hacia llegar tarde a turnos que si alcanzaban.
            libre_en = max(float(self.t_llegada), float(parada.listo_en))
            self.pos = parada.punto
            self.ruta = self.ruta[1:]
            res.trayecto.append((t, self.pos, parada.tipo))
            if self.pos == self.ancla:
                self.regreso_en = self.t_llegada  # el minuto exacto, no el entero del reloj
            if not self.ruta:
                self.termino_en = libre_en

            if parada.tipo == "pickup" and parada.oferta_id:
                self.carga_en_mochila.add(parada.oferta_id)

            if parada.tipo == "dropoff" and parada.oferta_id:
                o = self.aceptadas[parada.oferta_id]
                # El surge se cotiza al aparecer el ping, no al entregar: es lo que
                # la app le prometio al repartidor cuando acepto.
                cuando = shocks.en(o.t_aparece, self.disrupciones)
                pago = o.pago * o.surge * cuando.factor_pago(rutas.ZONA_DE[indice_de(o.pickup)])
                res.ingreso_bruto += pago
                res.cobros.append((t, round(pago, 2)))
                res.ganado += pago
                res.entregas += 1
                self.carga_en_mochila.remove(parada.oferta_id)

            if self.ruta:
                self.t_llegada = libre_en + viaje(self.pos, self.ruta[0].punto, libre_en)
                # La salida es el momento REAL en que quedo libre, no el minuto
                # entero del reloj: si no, el front anima la moto mas lenta de lo
                # que va y el tramo no cuadra con el mapa.
                self._registrar_tramo(
                    libre_en,
                    self.t_llegada,
                    self.pos,
                    self.ruta[0].punto,
                    con_carga=bool(self.carga_en_mochila),
                )

        # Regresar al ancla es obligacion de cualquier politica cuando el turno lo pide
        # (`regresar_al_ancla`): si ya no queda tiempo mas que para volver, el
        # simulador encamina de regreso.
        if cfg.regresar_al_ancla and not self.ruta and self.pos != self.ancla:
            regreso = viaje(self.pos, self.ancla, t)
            # Sale cuando esperar UN MINUTO MAS ya no lo dejaria volver a tiempo, no
            # cuando salir ahora apenas alcanza: lo segundo hace que llegue justo
            # ENCIMA del limite siempre. Mirar al minuto siguiente cubre de paso el
            # salto de trafico al cambiar de hora (car, 8 h desde las 8, seed 2000).
            if t + 1 + viaje(self.pos, self.ancla, t + 1) > cfg.duracion_min - cfg.margen_min:
                self.ruta = [Parada("ancla", self.ancla)]
                self.t_llegada = t + regreso
                self._registrar_tramo(
                    t, self.t_llegada, self.pos, self.ancla, con_carga=bool(self.carga_en_mochila)
                )

        # Restricciones 2 y 3: el contador de minutos continuos. Parar 20 minutos
        # lo resetea, y como la politica rechaza todo mientras el limite este
        # alcanzado, el descanso se toma solo: no hace falta una maquina de estados.
        if self.ruta:
            res.minutos_ocupado += 1
            self.manejando += 1
            self.descansando = 0
        else:
            self.descansando += 1
            if self.descansando >= seguridad.DESCANSO_MIN:
                self.manejando = 0

        self.t += 1

    def cerrar(self) -> Resultado:
        """Redondea y calcula llego_tarde. Idempotente: llamarlo dos veces no cambia nada."""
        if self._cerrado:
            return self.res
        res = self.res
        res.ganado = round(res.ganado, 2)
        res.ingreso_bruto = round(res.ingreso_bruto, 2)
        res.gasto_combustible = round(res.gasto_combustible, 2)
        res.km_con_carga = round(res.km_con_carga, 3)
        res.km_sin_carga = round(res.km_sin_carga, 3)
        limite = self.cfg.duracion_min - self.cfg.margen_min
        if self.cfg.regresar_al_ancla:
            res.regreso_en = self.regreso_en if self.pos == self.ancla and not self.ruta else None
            res.llego_tarde = res.regreso_en is None or res.regreso_en > limite
        else:
            # Sin regreso el turno acaba con la ultima entrega, donde sea que quede.
            res.llego_tarde = bool(self.ruta) or self.termino_en > limite
        self._cerrado = True
        return res
