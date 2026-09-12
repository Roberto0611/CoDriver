"""B6: la politica de Nuez. Costo de oportunidad en vez de umbral fijo.

La diferencia con el greedy es UNA linea: en lugar de comparar contra un umbral
fijo de $3/min, compara contra lo que rinden esos minutos segun la tabla de valor.

Las restricciones duras son las mismas y no se negocian: seguridad de la zona y
alcanzar a volver al ancla antes de clase.
"""

import rutas
import valor
from contrato import ConfigTurno, Decision, EstadoRepartidor, Oferta
from mundo import es_segura
from sim import CAPACIDAD, COSTO_KM, Parada, indice_de

MARGEN = 1.0  # el pedido debe rendir al menos esto por encima del costo de oportunidad


def politica_nuez(
    o: Oferta, est: EstadoRepartidor, ruta: list[Parada], cfg: ConfigTurno
) -> tuple[list[Parada] | None, Decision]:
    hora = (cfg.hora_inicio + est.t // 60) % 24
    i_pick, i_drop = indice_de(o.pickup), indice_de(o.dropoff)
    pos = indice_de(est.pos)
    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)

    # Lo que ya trae encolado: el pedido nuevo empieza cuando termine la ruta.
    cola, desde = 0.0, pos
    for p in ruta:
        cola += rutas.minutos(desde, p.punto, hora)
        desde = p.punto

    # Lo que cuesta ESTE pedido, que es lo unico que se le puede cobrar.
    propios = rutas.minutos(desde, i_pick, hora) + rutas.minutos(i_pick, i_drop, hora)
    neto = o.pago * o.surge - rutas.km(i_pick, i_drop) * COSTO_KM[cfg.vehiculo]

    # El costo de oportunidad: lo que rinden esos minutos normalmente.
    precio = valor.precio_del_tiempo(est.t_restante - cola, propios)

    terminos = {
        "pago_neto": round(neto, 1),
        "minutos": round(propios, 1),
        "por_minuto": round(neto / max(propios, 1), 2),
        "precio_tiempo": round(precio, 1),
        "ventaja": round(neto - precio, 1),
    }

    def no(razon: str, restriccion=None):
        return None, Decision(est.t, o.id, "saltar", terminos, razon, restriccion)

    if len(est.mochila) >= CAPACIDAD:
        return no("Ya traigo la mochila llena.", "mochila_llena")
    if not es_segura(rutas.ZONA_DE[i_drop], hora):
        return no(f"No te mando a {rutas.ZONA_DE[i_drop]} a esta hora.", "zona_insegura")
    if cola + propios + rutas.minutos(i_drop, ancla, hora) > est.t_restante - cfg.margen_min:
        return no("No alcanzas a volver a tiempo para tu clase.", "regreso_infactible")

    # LA linea. Todo lo demas es igual al baseline.
    if neto < precio + MARGEN:
        return no(
            f"Esos {propios:.0f} minutos rinden ${precio:.0f} normalmente, y este paga ${neto:.0f}."
        )

    nueva = ruta + [Parada("pickup", i_pick, o.id), Parada("dropoff", i_drop, o.id)]
    return nueva, Decision(
        est.t, o.id, "aceptar", terminos, f"Te deja ${neto - precio:.0f} por encima de lo normal."
    )
