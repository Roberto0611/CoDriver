"""Script para poblar TigerData (o fallback en memoria) con telemetría de tráfico
minuto a minuto para Monterrey entre las 14:00 y las 16:00, incluyendo el incidente
crítico a las 14:35 para la demostración del agente.
"""

import logging
import random
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backendruta.database import init_db, save_traffic_batch  # noqa: E402
from mundo import CURVAS_CORREDOR  # noqa: E402

logger = logging.getLogger("seed_traffic")
logging.basicConfig(level=logging.INFO)

# Coordenadas reales representativas de avenidas clave en Monterrey [lon, lat]
AVENIDAS_MTY = {
    "Av. Eugenio Garza Sada": [
        [-100.2930, 25.6580],
        [-100.2915, 25.6515],  # Frente a Rectoría Tec
        [-100.2880, 25.6420],
        [-100.2840, 25.6310],
    ],
    "Av. Constitución": [
        [-100.3250, 25.6660],
        [-100.3100, 25.6690],
        [-100.2950, 25.6720],
        [-100.2800, 25.6740],
    ],
    "Av. Morones Prieto": [
        [-100.3300, 25.6620],
        [-100.3100, 25.6650],
        [-100.2920, 25.6680],
        [-100.2780, 25.6700],
    ],
    "Av. José Eleuterio González (Gonzalitos)": [
        [-100.3510, 25.6720],
        [-100.3525, 25.6850],
        [-100.3540, 25.6980],
        [-100.3550, 25.7120],
    ],
    "Av. Revolución": [
        [-100.2810, 25.6680],
        [-100.2800, 25.6550],
        [-100.2790, 25.6420],
        [-100.2780, 25.6320],
    ],
    "Av. Lázaro Cárdenas": [
        [-100.3450, 25.6480],
        [-100.3300, 25.6430],
        [-100.3150, 25.6380],
        [-100.2950, 25.6350],
    ],
}


# A que corredor pertenece cada avenida. Gonzalitos y Garza Sada son los ejes
# que entran al centro; Constitucion y Morones corren junto al rio; Revolucion y
# Lazaro Cardenas son las salidas hacia el sur y el poniente.
CORREDOR_DE_CALLE = {
    "Av. Eugenio Garza Sada": "hacia_centro",
    "Av. Constitución": "cruza_rio",
    "Av. Morones Prieto": "cruza_rio",
    "Av. José Eleuterio González (Gonzalitos)": "hacia_centro",
    "Av. Revolución": "desde_centro",
    "Av. Lázaro Cárdenas": "desde_centro",
}

SEED = 7   # el mapa tiene que verse igual cada vez que el juez repite el turno


def generar_datos_simulacion():
    """Genera 120 minutos de tráfico (14:00 - 16:00) con fluctuaciones aleatorias leves."""
    hoy = date.today()
    rng = random.Random(SEED)
    registros: list[dict[str, Any]] = []

    # Iterar cada minuto de 14:00 a 16:00 (121 minutos)
    for total_minutos in range(14 * 60, 16 * 60 + 1):
        hora = total_minutos // 60
        minuto = total_minutos % 60
        dt = datetime.combine(hoy, time(hora, minuto))
        hora_str = f"{hora:02d}:{minuto:02d}"

        for calle, coords in AVENIDAS_MTY.items():
            # El factor NO se inventa aquí: sale de la misma curva que usa el motor
            # para decidir. Así el rojo del mapa y el número de la decisión son el
            # mismo dato, y un juez puede preguntar "¿por eso se desvió?".
            base_retraso = CURVAS_CORREDOR[CORREDOR_DE_CALLE[calle]][hora]

            # Variación leve entre minutos, con semilla: mismo seed, mismo mapa.
            factor_retraso = round(base_retraso * rng.uniform(0.95, 1.05), 2)

            # Velocidad y delay en base al factor
            velocidad = int(50 / factor_retraso)
            delay = int((factor_retraso - 1.0) * 120)  # Delay base
            motivo = "Tráfico fluido/moderado regular"
            if factor_retraso > 2.2:
                motivo = "Tráfico muy pesado"
            elif factor_retraso > 1.5:
                motivo = "Tráfico pesado"

            registros.append(
                {
                    "tiempo": dt,
                    "hora": hora_str,
                    "calle_nombre": calle,
                    "factor_retraso": factor_retraso,
                    "delay_segundos": delay,
                    "velocidad_kmh": velocidad,
                    "motivo": motivo,
                    "coords": coords,
                }
            )

    # Guardar en lotes de 100 registros
    logger.info(f"Guardando {len(registros)} registros derivados de mundo.CURVAS_CORREDOR...")
    for i in range(0, len(registros), 100):
        save_traffic_batch(registros[i : i + 100])

    logger.info(
        "Población de datos base completada exitosamente. (Incidentes se inyectarán vía API)."
    )
    return registros


def seed_all():
    init_db()
    generar_datos_simulacion()


if __name__ == "__main__":
    seed_all()
