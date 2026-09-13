"""Oracle offline: resuelve un turno con el stream completo antes de empezarlo.

Nunca se expone en /decide. Planea con búsqueda en haz una secuencia sin pedidos
apilados y compara ese plan contra las cinco
políticas online ya reproducidas sobre el mismo seed. Así es un techo reproducible
para esta familia de estrategias, nunca una promesa de que un repartidor conoce
el futuro.
"""

from dataclasses import dataclass
from functools import partial
from math import ceil

import rutas
import seguridad
import shocks
from baselines import POLITICAS, politica_accept_all
from contrato import ConfigTurno, Decision, EstadoRepartidor, Oferta
from mundo import es_segura
from nuez import politica_nuez
from sim import Parada, Politica, Resultado, generar_ofertas, indice_de, politica_greedy, simular


@dataclass(frozen=True)
class PlanOracle:
    """Mejor secuencia encontrada si se toma un pedido a la vez, sin apilar."""

    oferta_ids: tuple[str, ...]
    ganancia_estimada: float


def _pago_neto(
    oferta: Oferta, cfg: ConfigTurno, disrupciones: tuple[shocks.Shock, ...] = ()
) -> float:
    pickup, dropoff = indice_de(oferta.pickup), indice_de(oferta.dropoff)
    activos = shocks.en(oferta.t_aparece, disrupciones)
    return (
        oferta.pago * oferta.surge * activos.factor_pago(rutas.ZONA_DE[pickup])
        - rutas.km(pickup, dropoff) * seguridad.VEHICULOS[cfg.vehiculo].costo_km
    )


def _viaje(
    a: int, b: int, minuto: int, cfg: ConfigTurno, disrupciones: tuple[shocks.Shock, ...]
) -> float:
    """El tramo offline usa la misma física de shocks que el reloj del turno."""
    activos = shocks.en(minuto, disrupciones)
    base = rutas.minutos(a, b, cfg.hora_inicio + minuto // 60, cfg.vehiculo)
    return base * activos.factor_tiempo(rutas.ZONA_DE[a], rutas.ZONA_DE[b])


def _fin_de_pedido(
    pos: int, desde: int, oferta: Oferta, cfg: ConfigTurno, disrupciones: tuple[shocks.Shock, ...]
) -> int | None:
    """Minuto posterior a entregar ``oferta`` desde un repartidor libre."""
    pickup, dropoff = indice_de(oferta.pickup), indice_de(oferta.dropoff)
    salida = max(desde, oferta.t_aparece)
    llega_pickup = ceil(salida + _viaje(pos, pickup, salida, cfg, disrupciones))
    retraso = shocks.en(oferta.t_aparece, disrupciones).retraso(oferta.id)
    recoge = max(llega_pickup, oferta.t_aparece + oferta.t_prep + retraso)
    entrega = ceil(recoge + _viaje(pickup, dropoff, recoge, cfg, disrupciones))
    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)
    regreso = (
        ceil(_viaje(dropoff, ancla, entrega, cfg, disrupciones)) if cfg.regresar_al_ancla else 0
    )
    limite = cfg.duracion_min - cfg.margen_min
    if entrega + regreso >= limite:
        return None
    if not es_segura(rutas.ZONA_DE[dropoff], (cfg.hora_inicio + salida // 60) % 24):
        return None
    vehiculo = seguridad.VEHICULOS[cfg.vehiculo]
    if oferta.peso_kg > vehiculo.peso_kg or oferta.volumen_l > vehiculo.volumen_l:
        return None
    return entrega + 1


@dataclass(frozen=True)
class _EstadoPlan:
    disponible: int
    pos: int
    ganado: float
    oferta_ids: tuple[str, ...]


ANCHO_HAZ = 48
SIGUIENTES_POR_ESTADO = 18


def planificar(
    cfg: ConfigTurno,
    ofertas: list[Oferta] | None = None,
    *,
    disrupciones: tuple[shocks.Shock, ...] = (),
) -> PlanOracle:
    """Busca una agenda offline de pedidos individuales con el stream completo.

    Conserva las 48 agendas más rentables en cada ronda y expande las 18 ofertas
    factibles de mayor pago por minuto. El estado carga la hora y posición reales;
    por eso cada ruta se calcula desde donde terminó la agenda anterior.
    """
    stream = generar_ofertas(cfg) if ofertas is None else ofertas
    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)
    frontera = [_EstadoPlan(0, ancla, 0.0, ())]
    mejor = frontera[0]

    for _ in stream:
        expansiones: list[_EstadoPlan] = []
        for estado in frontera:
            candidatas = []
            for oferta in stream:
                if oferta.t_aparece < estado.disponible or oferta.id in estado.oferta_ids:
                    continue
                fin = _fin_de_pedido(estado.pos, estado.disponible, oferta, cfg, disrupciones)
                if fin is None:
                    continue
                pago = _pago_neto(oferta, cfg, disrupciones)
                puntaje = pago / max(fin - estado.disponible, 1)
                candidatas.append((puntaje, oferta, fin, pago))
            for _, oferta, fin, pago in sorted(
                candidatas, key=lambda candidata: candidata[0], reverse=True
            )[:SIGUIENTES_POR_ESTADO]:
                candidata = _EstadoPlan(
                    fin,
                    indice_de(oferta.dropoff),
                    estado.ganado + pago,
                    estado.oferta_ids + (oferta.id,),
                )
                expansiones.append(candidata)
                if candidata.ganado > mejor.ganado:
                    mejor = candidata
        if not expansiones:
            break

        por_estado: dict[tuple[int, int], _EstadoPlan] = {}
        for candidata in expansiones:
            llave = (candidata.pos, candidata.disponible // 10)
            previa = por_estado.get(llave)
            if previa is None or candidata.ganado > previa.ganado:
                por_estado[llave] = candidata
        frontera = sorted(por_estado.values(), key=lambda estado: estado.ganado, reverse=True)[
            :ANCHO_HAZ
        ]

    return PlanOracle(mejor.oferta_ids, round(mejor.ganado, 2))


def politica_del_plan(plan: PlanOracle) -> Politica:
    """Convierte el plan offline en decisiones que el simulador puede reproducir."""
    siguiente = 0

    def politica(
        oferta: Oferta,
        est: EstadoRepartidor,
        ruta: list[Parada],
        cfg: ConfigTurno,
        **_,
    ) -> tuple[list[Parada] | None, Decision]:
        nonlocal siguiente
        esperado = plan.oferta_ids[siguiente] if siguiente < len(plan.oferta_ids) else None
        if oferta.id != esperado:
            return None, Decision(
                est.t,
                oferta.id,
                "saltar",
                {"pago_neto": round(_pago_neto(oferta, cfg), 1)},
                "El Oracle reserva el tiempo para una oferta futura mejor.",
                "reservation_wage",
            )
        siguiente += 1
        if ruta:
            return None, Decision(
                est.t,
                oferta.id,
                "saltar",
                {"pago_neto": round(_pago_neto(oferta, cfg), 1)},
                "La agenda perdió factibilidad; conserva la ruta en curso.",
                "shift_end_infeasible",
            )
        return politica_accept_all(oferta, est, ruta, cfg)

    return politica


def resolver(
    cfg: ConfigTurno,
    *,
    tabla: dict[int, float] | None = None,
    disrupciones: tuple[shocks.Shock, ...] = (),
) -> tuple[Resultado, str, PlanOracle]:
    """Corre el plan y las políticas online; devuelve el mejor resultado reproducible."""
    plan = planificar(cfg, disrupciones=disrupciones)
    candidatos: dict[str, Politica] = {
        "AgendaOracle": politica_del_plan(plan),
        **POLITICAS,
        "GreedyRate": politica_greedy,
        "OurAgent": partial(politica_nuez, tabla=tabla),
    }
    resultados = {
        nombre: simular(cfg, politica, disrupciones=disrupciones)
        for nombre, politica in candidatos.items()
    }
    nombre = max(
        resultados,
        key=lambda candidato: (
            resultados[candidato].ganado,
            resultados[candidato].entregas,
            -resultados[candidato].rechazos,
        ),
    )
    return resultados[nombre], nombre, plan


def simular_oracle(
    cfg: ConfigTurno,
    *,
    tabla: dict[int, float] | None = None,
    disrupciones: tuple[shocks.Shock, ...] = (),
) -> Resultado:
    """Punto de entrada para la tabla de resultados; sólo debe usarse offline."""
    return resolver(cfg, tabla=tabla, disrupciones=disrupciones)[0]
