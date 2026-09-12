"""El mundo estático: zonas de Monterrey, tráfico por hora y riesgo por zona-hora.

No tiene lógica de decisión ni estado del turno. Es lo que no cambia entre corridas.
Lo importan el simulador (A3-A6), el motor (V[t][zona]) y Gemini (multiplicadores).
"""

# Zonas del área metropolitana donde de verdad hay pedidos.
# (lat, lon, radio_m). El radio define de dónde se samplean los puntos de interés.
ZONAS = {
    "Centro":        (25.6714, -100.3090, 1800),
    "Obispado":      (25.6740, -100.3400, 1500),
    "Valle":         (25.6510, -100.3590, 2000),  # San Pedro: paga bien, lejos
    "Contry":        (25.6300, -100.2700, 2000),
    "Tec":           (25.6515, -100.2895, 1500),  # ancla por defecto del estudiante
    "Fundidora":     (25.6790, -100.2840, 1500),
    "Guadalupe":     (25.6790, -100.2560, 2200),
    "LindaVista":    (25.7300, -100.2600, 2000),
    "SanNicolas":    (25.7450, -100.2900, 2200),
    "Cumbres":       (25.7290, -100.3890, 2500),
    "Mitras":        (25.7100, -100.3600, 1800),
    "Escobedo":      (25.7900, -100.3200, 2500),
    "SantaCatarina": (25.6750, -100.4500, 2500),
    "Apodaca":       (25.7800, -100.1900, 2500),
}

# ponytail: multiplicadores a ojo de regio, no medidos. Esta es LA perilla de
# calibración del simulador — si los tiempos se sienten falsos, se toca aquí.
# Flujo libre (OSM maxspeed) x este factor = tiempo real de viaje.
TRAFICO_POR_HORA = {
    0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.1,
    6: 1.4, 7: 2.2, 8: 2.4, 9: 1.9,          # entrada a escuelas y trabajo
    10: 1.4, 11: 1.4, 12: 1.5,
    13: 1.7, 14: 1.8, 15: 1.6,               # hora de comida
    16: 1.8, 17: 2.3, 18: 2.5, 19: 2.2,      # salida, el peor rato del día
    20: 1.6, 21: 1.3, 22: 1.1, 23: 1.0,
}

# ponytail: capa SINTÉTICA, curada a mano. No hay datos abiertos confiables de
# criminalidad por colonia-hora en MTY. En producción se alimenta de reportes
# municipales + iluminación de OSM. Se declara como sintética en el pitch.
# 0 = tranquilo, 1 = no mandes a un estudiante ahí de noche.
RIESGO_BASE = {
    "Centro": 0.45, "Obispado": 0.30, "Valle": 0.10, "Contry": 0.20,
    "Tec": 0.15, "Fundidora": 0.25, "Guadalupe": 0.40, "LindaVista": 0.35,
    "SanNicolas": 0.30, "Cumbres": 0.25, "Mitras": 0.40, "Escobedo": 0.50,
    "SantaCatarina": 0.35, "Apodaca": 0.45,
}

UMBRAL_RIESGO = 0.6   # arriba de esto, restricción dura: no se acepta, ni por dinero


def factor_trafico(hora: int) -> float:
    return TRAFICO_POR_HORA[hora % 24]


def riesgo(zona: str, hora: int) -> float:
    """El riesgo sube de noche. 22:00-05:00 es el rango feo."""
    nocturno = 1.8 if hora >= 22 or hora < 5 else (1.3 if hora >= 20 else 1.0)
    return min(1.0, RIESGO_BASE[zona] * nocturno)


def es_segura(zona: str, hora: int) -> bool:
    return riesgo(zona, hora) < UMBRAL_RIESGO


def demo():
    assert factor_trafico(18) > factor_trafico(3), "la hora pico debe ser más lenta"
    assert riesgo("Valle", 14) < riesgo("Valle", 23), "de noche sube el riesgo"
    assert es_segura("Valle", 23), "San Pedro de noche sigue siendo seguro"
    assert not es_segura("Escobedo", 23), "Escobedo a las 11 PM debe bloquearse"
    assert es_segura("Escobedo", 14), "pero de día sí se puede"

    print(f"{'zona':<14} {'riesgo 14h':>10} {'riesgo 23h':>11}  {'de noche?':>10}")
    for z in ZONAS:
        print(f"{z:<14} {riesgo(z, 14):>10.2f} {riesgo(z, 23):>11.2f}"
              f"  {'si' if es_segura(z, 23) else 'NO':>10}")
    print(f"\ntrafico: 3AM x{factor_trafico(3)}, 14h x{factor_trafico(14)}, 18h x{factor_trafico(18)}")
    print("OK")


if __name__ == "__main__":
    demo()
