"""Los tres rivales simples que pide la tabla de resultados de Infosys.

No conocen la tabla de valor, no reordenan para buscar oportunidad y respetan
exactamente las mismas restricciones duras que Nuez. Sus umbrales son reglas
fijas, declaradas aqui; no se ajustan contra los seeds de REPORTE.
"""

from dataclasses import dataclass

import rutas
import seguridad
import shocks
from contrato import ConfigTurno, Decision, EstadoRepartidor, Oferta
from sim import Parada, indice_de

# Reglas deliberadamente simples y estables, no parámetros aprendidos.
PAGO_ALTO_MIN_MXN = 80.0
PICKUP_CERCANO_MAX_MIN = 10.0


@dataclass(frozen=True)
class Evaluacion:
    nueva_ruta: list[Parada]
    terminos: dict[str, float]
    bloqueo: tuple[str, str] | None
    minutos_hasta_pickup: float


def evaluar(
    o: Oferta,
    est: EstadoRepartidor,
    ruta: list[Parada],
    cfg: ConfigTurno,
    activos: shocks.Activos = shocks.NINGUNO,
) -> Evaluacion:
    """Calcula una oferta sin aplicar preferencia de dinero, distancia o valor futuro."""
    hora = (cfg.hora_inicio + est.t // 60) % 24
    i_pick, i_drop = indice_de(o.pickup), indice_de(o.dropoff)
    pos = indice_de(est.pos)
    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)

    def tramo(origen: int, destino: int, desde_min: float) -> float:
        return rutas.minutos(
            origen,
            destino,
            cfg.hora_inicio + int(est.t + desde_min) // 60,
            cfg.vehiculo,
        )

    cola, desde = 0.0, pos
    for parada in ruta:
        cola += tramo(desde, parada.punto, cola)
        if parada.tipo == "pickup":
            cola = max(cola, parada.listo_en - est.t)
        desde = parada.punto

    minutos_hasta_pickup = cola + tramo(desde, i_pick, cola)
    minutos_hasta_pickup = max(minutos_hasta_pickup, o.t_aparece + o.t_prep - est.t)
    minutos_totales = minutos_hasta_pickup + tramo(i_pick, i_drop, minutos_hasta_pickup)
    propios = minutos_totales - cola
    neto = o.pago * o.surge - rutas.km(i_pick, i_drop) * seguridad.VEHICULOS[cfg.vehiculo].costo_km
    terminos = {
        "pago_neto": round(neto, 1),
        "minutos": round(propios, 1),
        "por_minuto": round(neto / max(propios, 1), 2),
        "minutos_hasta_pickup": round(minutos_hasta_pickup, 1),
    }
    bloqueo = seguridad.revisar(
        vehiculo=cfg.vehiculo,
        hora=hora,
        zona_dropoff=rutas.ZONA_DE[i_drop],
        minutos_manejando=est.minutos_manejando,
        carga_kg=sum(parada.peso_kg for parada in ruta if parada.tipo == "dropoff") + o.peso_kg,
        carga_l=sum(parada.volumen_l for parada in ruta if parada.tipo == "dropoff") + o.volumen_l,
        pedidos_en_vuelo=len({parada.oferta_id for parada in ruta if parada.oferta_id}) + 1,
        minutos_para_terminar=minutos_totales
        + (tramo(i_drop, ancla, minutos_totales) if cfg.regresar_al_ancla else 0.0),
        minutos_de_turno=est.t_restante - cfg.margen_min,
    )
    nueva_ruta = ruta + [
        Parada("pickup", i_pick, o.id, o.t_aparece + o.t_prep),
        Parada("dropoff", i_drop, o.id, peso_kg=o.peso_kg, volumen_l=o.volumen_l),
    ]
    return Evaluacion(nueva_ruta, terminos, bloqueo, minutos_hasta_pickup)


def _salta(
    est: EstadoRepartidor, o: Oferta, terminos: dict[str, float], razon: str, restriccion=None
):
    return None, Decision(est.t, o.id, "saltar", terminos, razon, restriccion)


def politica_accept_all(
    o: Oferta,
    est: EstadoRepartidor,
    ruta: list[Parada],
    cfg: ConfigTurno,
    *,
    activos: shocks.Activos = shocks.NINGUNO,
    **_,
) -> tuple[list[Parada] | None, Decision]:
    """AcceptAll: todo pedido que sea seguro y factible entra, sin mirar su valor."""
    eva = evaluar(o, est, ruta, cfg, activos)
    if eva.bloqueo:
        return _salta(est, o, eva.terminos, eva.bloqueo[1], eva.bloqueo[0])
    return eva.nueva_ruta, Decision(
        est.t, o.id, "aceptar", eva.terminos, "Acepta todo pedido factible."
    )


def politica_highest_pay(
    o: Oferta,
    est: EstadoRepartidor,
    ruta: list[Parada],
    cfg: ConfigTurno,
    *,
    activos: shocks.Activos = shocks.NINGUNO,
    **_,
) -> tuple[list[Parada] | None, Decision]:
    """HighestPay: persigue pago total; no considera distancia ni costo de oportunidad."""
    eva = evaluar(o, est, ruta, cfg, activos)
    if eva.bloqueo:
        return _salta(est, o, eva.terminos, eva.bloqueo[1], eva.bloqueo[0])
    if eva.terminos["pago_neto"] < PAGO_ALTO_MIN_MXN:
        return _salta(
            est,
            o,
            eva.terminos,
            f"Busca pagos de al menos ${PAGO_ALTO_MIN_MXN:.0f}, sin mirar el tiempo.",
            "reservation_wage",
        )
    return eva.nueva_ruta, Decision(
        est.t,
        o.id,
        "aceptar",
        eva.terminos,
        f"Paga ${eva.terminos['pago_neto']:.0f}, suficiente para HighestPay.",
    )


def politica_nearest_first(
    o: Oferta,
    est: EstadoRepartidor,
    ruta: list[Parada],
    cfg: ConfigTurno,
    *,
    activos: shocks.Activos = shocks.NINGUNO,
    **_,
) -> tuple[list[Parada] | None, Decision]:
    """NearestFirst: persigue pickups cercanos; no considera pago ni destino final."""
    eva = evaluar(o, est, ruta, cfg, activos)
    if eva.bloqueo:
        return _salta(est, o, eva.terminos, eva.bloqueo[1], eva.bloqueo[0])
    if eva.minutos_hasta_pickup > PICKUP_CERCANO_MAX_MIN:
        return _salta(
            est,
            o,
            eva.terminos,
            f"El pickup queda a {eva.minutos_hasta_pickup:.0f} min; busca uno de hasta "
            f"{PICKUP_CERCANO_MAX_MIN:.0f} min.",
        )
    return eva.nueva_ruta, Decision(
        est.t,
        o.id,
        "aceptar",
        eva.terminos,
        f"El pickup está a {eva.minutos_hasta_pickup:.0f} min, el más cercano permitido.",
    )


POLITICAS = {
    "AcceptAll": politica_accept_all,
    "HighestPay": politica_highest_pay,
    "NearestFirst": politica_nearest_first,
}
