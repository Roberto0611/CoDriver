"""El mundo estático: zonas de Monterrey, tráfico por hora y riesgo por zona-hora.

No tiene lógica de decisión ni estado del turno. Es lo que no cambia entre corridas.
Lo importan el simulador (A3-A6), el motor (V[t][zona]) y Gemini (multiplicadores).
"""

# Zonas del área metropolitana donde de verdad hay pedidos.
# (lat, lon, radio_m). El radio define de dónde se samplean los puntos de interés.
ZONAS = {
    "Centro": (25.6714, -100.3090, 1800),
    "Obispado": (25.6740, -100.3400, 1500),
    "Valle": (25.6510, -100.3590, 2000),  # San Pedro: paga bien, lejos
    "Contry": (25.6300, -100.2700, 2000),
    "Tec": (25.6515, -100.2895, 1500),  # ancla por defecto del estudiante
    "Fundidora": (25.6790, -100.2840, 1500),
    "Guadalupe": (25.6790, -100.2560, 2200),
    "LindaVista": (25.7300, -100.2600, 2000),
    "SanNicolas": (25.7450, -100.2900, 2200),
    "Cumbres": (25.7290, -100.3890, 2500),
    "Mitras": (25.7100, -100.3600, 1800),
    "Escobedo": (25.7900, -100.3200, 2500),
    "SantaCatarina": (25.6750, -100.4500, 2500),
    "Apodaca": (25.7800, -100.1900, 2500),
}

# ponytail: multiplicadores a ojo de regio, no medidos. Esta es LA perilla de
# calibración del simulador — si los tiempos se sienten falsos, se toca aquí.
# Flujo libre (OSM maxspeed) x este factor = tiempo real de viaje.
# El trafico no es uniforme: depende de PARA DONDE vas y a que hora. En la mañana
# todos entran al centro, en la tarde todos salen, y cruzar el rio Santa Catarina
# sufre las dos. Un solo factor para toda la ciudad es un mundo sin ritmo, y en un
# mundo sin ritmo no hay nada que un agente listo pueda aprender.
#
# ponytail: cuatro curvas a ojo de regio, no medidas. ESTA es la perilla de
# calibracion del mundo. Para volverlas reales: 5 pares de puntos conocidos en
# Google Maps a las 8, 14 y 18 h, y el cociente contra el tiempo a flujo libre.

ZONAS_SUR = {"Valle", "Contry", "Tec"}  # del otro lado del rio
ZONAS_CENTRO = {"Centro", "Obispado"}  # el nucleo de trabajo y comercio

CURVAS_CORREDOR = {
    # Dentro de tu propia zona: casi plano, nunca duele mucho.
    "local": {
        0: 1.0,
        1: 1.0,
        2: 1.0,
        3: 1.0,
        4: 1.0,
        5: 1.05,
        6: 1.15,
        7: 1.30,
        8: 1.35,
        9: 1.25,
        10: 1.20,
        11: 1.20,
        12: 1.25,
        13: 1.30,
        14: 1.30,
        15: 1.35,
        16: 1.40,
        17: 1.45,
        18: 1.50,
        19: 1.40,
        20: 1.25,
        21: 1.15,
        22: 1.05,
        23: 1.0,
    },
    # Entrando al centro: el infierno es en la mañana.
    "hacia_centro": {
        0: 1.0,
        1: 1.0,
        2: 1.0,
        3: 1.0,
        4: 1.0,
        5: 1.10,
        6: 1.60,
        7: 2.40,
        8: 2.70,
        9: 2.10,
        10: 1.50,
        11: 1.40,
        12: 1.50,
        13: 1.60,
        14: 1.60,
        15: 1.70,
        16: 1.90,
        17: 2.00,
        18: 2.00,
        19: 1.80,
        20: 1.40,
        21: 1.20,
        22: 1.10,
        23: 1.0,
    },
    # Saliendo del centro: el infierno es en la tarde, y empieza a las 3.
    "desde_centro": {
        0: 1.0,
        1: 1.0,
        2: 1.0,
        3: 1.0,
        4: 1.0,
        5: 1.05,
        6: 1.20,
        7: 1.50,
        8: 1.60,
        9: 1.50,
        10: 1.40,
        11: 1.40,
        12: 1.50,
        13: 1.60,
        14: 1.70,
        15: 2.00,
        16: 2.40,
        17: 2.80,
        18: 2.90,
        19: 2.50,
        20: 1.80,
        21: 1.40,
        22: 1.10,
        23: 1.0,
    },
    # Cruzar el rio: sufre las dos horas pico y siempre es lo peor.
    "cruza_rio": {
        0: 1.0,
        1: 1.0,
        2: 1.0,
        3: 1.0,
        4: 1.0,
        5: 1.10,
        6: 1.50,
        7: 2.30,
        8: 2.60,
        9: 2.20,
        10: 1.70,
        11: 1.60,
        12: 1.70,
        13: 1.90,
        14: 2.00,
        15: 2.40,
        16: 2.90,
        17: 3.20,
        18: 3.30,
        19: 2.90,
        20: 2.00,
        21: 1.50,
        22: 1.20,
        23: 1.0,
    },
}

# Promedio de los cuatro corredores. Solo para cuando no se sabe el par de zonas.
TRAFICO_POR_HORA = {
    h: round(sum(c[h] for c in CURVAS_CORREDOR.values()) / len(CURVAS_CORREDOR), 2)
    for h in range(24)
}

# ponytail: capa SINTÉTICA, curada a mano. No hay datos abiertos confiables de
# criminalidad por colonia-hora en MTY. En producción se alimenta de reportes
# municipales + iluminación de OSM. Se declara como sintética en el pitch.
# 0 = tranquilo, 1 = no mandes a un estudiante ahí de noche.
RIESGO_BASE = {
    "Centro": 0.45,
    "Obispado": 0.30,
    "Valle": 0.10,
    "Contry": 0.20,
    "Tec": 0.15,
    "Fundidora": 0.25,
    "Guadalupe": 0.40,
    "LindaVista": 0.35,
    "SanNicolas": 0.30,
    "Cumbres": 0.25,
    "Mitras": 0.40,
    "Escobedo": 0.50,
    "SantaCatarina": 0.35,
    "Apodaca": 0.45,
}

UMBRAL_RIESGO = 0.6  # arriba de esto la zona queda marcada: de noche no se entrega ahí
HORA_NOCHE = 22  # la línea del protocolo: "no dropoff in flagged zones after 22:00"

# Zona marcada = la que de noche pasa el umbral. Se deriva del riesgo en vez de
# escribirse a mano para que mover un número de RIESGO_BASE mueva las dos cosas.
ZONAS_MARCADAS = frozenset(z for z, r in RIESGO_BASE.items() if r * 1.8 >= UMBRAL_RIESGO)


def corredor(origen: str, destino: str) -> str:
    """A que tipo de viaje pertenece ir de una zona a otra.

    Cruzar el rio manda sobre todo lo demas: es el cuello de botella de la ciudad.
    """
    if (origen in ZONAS_SUR) != (destino in ZONAS_SUR):
        return "cruza_rio"
    if destino in ZONAS_CENTRO and origen not in ZONAS_CENTRO:
        return "hacia_centro"
    if origen in ZONAS_CENTRO and destino not in ZONAS_CENTRO:
        return "desde_centro"
    return "local"


def factor_trafico(hora: int, origen: str | None = None, destino: str | None = None) -> float:
    """Cuanto se estira el tiempo a flujo libre.

    Con el par de zonas usa la curva de su corredor; sin el, el promedio de la
    ciudad. LA FUENTE UNICA: tanto el motor (via rutas.minutos) como el mapa
    (via backendruta/seed_traffic) preguntan aqui. Nadie inventa factores aparte.
    """
    h = hora % 24
    if origen is None or destino is None:
        return TRAFICO_POR_HORA[h]
    return CURVAS_CORREDOR[corredor(origen, destino)][h]


def riesgo(zona: str, hora: int) -> float:
    """El riesgo sube de noche. 22:00-05:00 es el rango feo."""
    nocturno = 1.8 if hora >= 22 or hora < 5 else (1.3 if hora >= 20 else 1.0)
    return min(1.0, RIESGO_BASE[zona] * nocturno)


def es_segura(zona: str, hora: int) -> bool:
    """Restricción 1 de 5: nada de entregas en zona marcada después de las 22:00.

    La línea es de reloj, no de promedio: a las 21:59 se puede y a las 22:00 no.
    `riesgo()` sigue existiendo para pintar el mapa, pero la que decide es ésta.
    """
    return not (es_de_noche(hora) and zona in ZONAS_MARCADAS)


def es_de_noche(hora: int) -> bool:
    """De las 22:00 a las 5:00. La misma linea para nuestro mapa y para el protocolo."""
    return hora % 24 >= HORA_NOCHE or hora % 24 < 5


def demo():
    assert factor_trafico(18) > factor_trafico(3), "la hora pico debe ser más lenta"
    assert riesgo("Valle", 14) < riesgo("Valle", 23), "de noche sube el riesgo"
    assert es_segura("Valle", 23), "San Pedro de noche sigue siendo seguro"
    assert not es_segura("Escobedo", 23), "Escobedo a las 11 PM debe bloquearse"
    assert es_segura("Escobedo", 14), "pero de día sí se puede"

    print(f"{'zona':<14} {'riesgo 14h':>10} {'riesgo 23h':>11}  {'de noche?':>10}")
    for z in ZONAS:
        print(
            f"{z:<14} {riesgo(z, 14):>10.2f} {riesgo(z, 23):>11.2f}"
            f"  {'si' if es_segura(z, 23) else 'NO':>10}"
        )
    print(
        f"\ntrafico: 3AM x{factor_trafico(3)}, 14h x{factor_trafico(14)}, 18h x{factor_trafico(18)}"
    )
    print("OK")


if __name__ == "__main__":
    demo()
