"""B6: la politica de Nuez. Costo de oportunidad en vez de umbral fijo.

Dos diferencias con el greedy:
  1. El costo del pedido es MARGINAL (ruteo.py): lo que cuesta encima de lo que ya
     trae, con las paradas reordenadas. Un pedido de paso cuesta 3 min, no 25.
  2. El umbral no es fijo: compara contra lo que rinden esos minutos segun la
     tabla de valor, que depende de cuanto turno queda y de como esta el trafico.

Las restricciones duras son las mismas y no se negocian: seguridad de la zona y
alcanzar a volver al ancla antes de clase.
"""

import rutas
import ruteo
import seguridad
import valor
from contrato import ConfigTurno, Decision, EstadoRepartidor, Oferta
from estrategia import BASE, Estrategia
from sim import Parada, indice_de

MARGEN = BASE.margen_mxn  # el pedido debe rendir al menos esto sobre el costo de oportunidad

# Cuando la ruta esta vacia, un minuto rinde EXACTAMENTE cero. La tabla de valor
# dice lo que rinde un repartidor promedio, pero el promedio incluye a los que ya
# traen trabajo encima; el que esta parado y lejos no puede aspirar a eso, y si se
# lo cobra rechaza todo y termina el turno en ceros (era el caso del seed 1007).
# ponytail: 0.5 salio de barrer el parametro; medido en 300 seeds contra x1.0 da
# +$8.9 por turno, 3.4 veces el error. Si se recalibra el mundo, volver a barrerlo.
DESCUENTO_PARADO = BASE.descuento_parado

# Los dos de arriba son los valores BASE. El modelo puede moverlos pasando otra
# `Estrategia`, pero el default es el de siempre: sin capa de estrategia encima,
# el agente se comporta identico a cuando se midio el numero.


def politica_nuez(
    o: Oferta,
    est: EstadoRepartidor,
    ruta: list[Parada],
    cfg: ConfigTurno,
    *,
    tabla: dict[int, float] | None = None,
    minutos_directos: float | None = None,
    km_entrega: float | None = None,
    estrategia: Estrategia = BASE,
) -> tuple[list[Parada] | None, Decision]:
    hora = (cfg.hora_inicio + est.t // 60) % 24
    i_pick, i_drop = indice_de(o.pickup), indice_de(o.dropoff)
    pos = indice_de(est.pos)
    ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)

    # B2: cuantos minutos EXTRA cuesta meter este pedido, con las paradas
    # reordenadas de la mejor forma. Si va de paso, casi nada.
    nuevas = [
        Parada("pickup", i_pick, o.id, o.t_aparece + o.t_prep),
        Parada("dropoff", i_drop, o.id, peso_kg=o.peso_kg, volumen_l=o.volumen_l),
    ]
    nueva_ruta, propios = ruteo.costo_marginal(pos, ruta, nuevas, hora, est.t, cfg.vehiculo)
    _, cola = ruteo.mejor_ruta(pos, ruta, hora, est.t, cfg.vehiculo)
    # En /decide Infosys puede mandar tiempos y distancias observados. Cuando el
    # repartidor esta libre, esos datos mandan sobre nuestra matriz sintetica.
    # Con trabajo en vuelo se conserva el ruteo exacto para calcular la insercion.
    if not ruta and minutos_directos is not None:
        propios = minutos_directos
    distancia = rutas.km(i_pick, i_drop) if km_entrega is None else km_entrega
    neto = o.pago * o.surge - distancia * seguridad.VEHICULOS[cfg.vehiculo].costo_km

    # El costo de oportunidad: lo que rinden esos minutos normalmente.
    if tabla is None:
        tabla = valor.para_turno(cfg.duracion_min)
    precio = valor.precio_del_tiempo(est.t_restante - cola, propios, tabla)
    if not ruta:
        precio *= estrategia.descuento_parado
    # Encarecer el tiempo hacia una zona es como el modelo dice "hoy no por ahi":
    # no la prohibe (eso solo lo hace seguridad.py), la vuelve mas cara de aceptar.
    precio *= estrategia.precio_de_zona(rutas.ZONA_DE[i_drop])

    terminos = {
        "pago_neto": round(neto, 1),
        "minutos": round(propios, 1),
        "por_minuto": round(neto / max(propios, 1), 2),
        "precio_tiempo": round(precio, 1),
        "ventaja": round(neto - precio, 1),
        "parado": float(not ruta),
        "margen_exigido": estrategia.margen_mxn,
        "multiplicador_zona": estrategia.precio_de_zona(rutas.ZONA_DE[i_drop]),
    }

    def no(razon: str, restriccion=None):
        return None, Decision(est.t, o.id, "saltar", terminos, razon, restriccion)

    # LAS CINCO RESTRICCIONES, todas en seguridad.py. Un pedido ya recogido sigue
    # ocupando lugar en la ruta hasta entregarlo, por eso la carga se mide sobre
    # los dropoff pendientes y no sobre la mochila. El regreso se mide desde la
    # ULTIMA parada de la ruta reordenada: al agrupar, este destino puede quedar
    # a media ruta y medirlo desde el suyo rechazaria pedidos que si se alcanzan.
    fin = nueva_ruta[-1].punto if nueva_ruta else i_drop
    # El regreso se recorre AL FINAL, no ahora: a las 14:00 el mapa miente sobre
    # como estara a las 15:10. Medirlo con la hora actual es como llega tarde el
    # repartidor con la cuenta cuadrada.
    hora_fin = (cfg.hora_inicio + int(est.t + cola + propios) // 60) % 24
    para_terminar = cola + propios + rutas.minutos(fin, ancla, hora_fin, cfg.vehiculo)
    # Quedan en los terminos para que explain_decision muestre la cuenta del fin de turno.
    terminos["minutos_ruta_actual"] = round(cola, 1)
    terminos["minutos_para_terminar"] = round(para_terminar, 1)
    terminos["minutos_de_turno"] = round(est.t_restante - cfg.margen_min, 1)
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

    # LA linea. Lo unico que se compra con dinero, y por eso lleva reservation_wage.
    if neto < precio + estrategia.margen_mxn:
        return no(
            f"Esos {propios:.0f} minutos rinden ${precio:.0f} normalmente, "
            f"y este paga ${neto:.0f}.",
            "reservation_wage",
        )

    return nueva_ruta, Decision(
        est.t, o.id, "aceptar", terminos, f"Te deja ${neto - precio:.0f} por encima de lo normal."
    )
