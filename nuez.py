"""B6: la politica de Nuez. Costo de oportunidad en vez de umbral fijo.

Dos diferencias con el greedy:
  1. El costo del pedido es MARGINAL (ruteo.py): lo que cuesta encima de lo que ya
     trae, con las paradas reordenadas. Un pedido de paso cuesta 3 min, no 25.
  2. El umbral no es fijo: compara contra lo que rinden esos minutos segun la
     tabla de valor, que depende de cuanto turno queda y de como esta el trafico.

Las restricciones duras son las mismas y no se negocian: seguridad de la zona y
alcanzar a volver al ancla antes de clase.
"""

import ruteo
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

    # B2: cuantos minutos EXTRA cuesta meter este pedido, con las paradas
    # reordenadas de la mejor forma. Si va de paso, casi nada.
    nuevas = [Parada("pickup", i_pick, o.id, o.t_aparece + o.t_prep),
              Parada("dropoff", i_drop, o.id)]
    nueva_ruta, propios = ruteo.costo_marginal(pos, ruta, nuevas, hora, est.t)
    _, cola = ruteo.mejor_ruta(pos, ruta, hora, est.t)
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

    # Un pedido ya recogido sigue ocupando lugar en la ruta hasta entregarlo.
    en_vuelo = {p.oferta_id for p in ruta if p.oferta_id}
    if len(en_vuelo) >= CAPACIDAD:
        return no("Ya traigo la mochila llena.", "mochila_llena")
    if not es_segura(rutas.ZONA_DE[i_drop], hora):
        return no(f"No te mando a {rutas.ZONA_DE[i_drop]} a esta hora.", "zona_insegura")
    # El regreso se mide desde la ULTIMA parada de la ruta reordenada, no desde
    # este pedido: al agrupar, el destino de este puede quedar a media ruta.
    if nueva_ruta:
        regreso = rutas.minutos(nueva_ruta[-1].punto, ancla, hora)
        if cola + propios + regreso > est.t_restante - cfg.margen_min:
            return no("No alcanzas a volver a tiempo para tu clase.", "regreso_infactible")

    # LA linea. Todo lo demas es igual al baseline.
    if neto < precio + MARGEN:
        return no(
            f"Esos {propios:.0f} minutos rinden ${precio:.0f} normalmente, y este paga ${neto:.0f}."
        )

    return nueva_ruta, Decision(
        est.t, o.id, "aceptar", terminos, f"Te deja ${neto - precio:.0f} por encima de lo normal."
    )
