"""Script para poblar TigerData (o fallback en memoria) con telemetría de tráfico
minuto a minuto para Monterrey entre las 14:00 y las 16:00, incluyendo el incidente
crítico a las 14:35 para la demostración del agente.
"""

import logging
import random
from datetime import date, datetime, time
from typing import Any

from backendruta.database import init_db, save_traffic_batch

logger = logging.getLogger("seed_traffic")
logging.basicConfig(level=logging.INFO)

# Extraeremos nombres de avenidas directamente del grafo para cubrir toda la ciudad.
# Solo consideramos vías principales para mantener el rendimiento de la simulación.
import pickle
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
G_path = BASE_DIR / "data" / "mty_graph.pkl"

def get_calles_principales() -> List[str]:
    calles = set()
    if not G_path.exists():
        logger.warning("No se encontró mty_graph.pkl. Usando fallback básico.")
        return ["Eugenio Garza Sada", "Constitución", "Morones Prieto", "Gonzalitos"]
        
    logger.info("Extrayendo calles del grafo para simulación...")
    G = pickle.loads(G_path.read_bytes())
    for u, v, d in G.edges(data=True):
        n = d.get("name")
        h = d.get("highway", "")
        if isinstance(h, list): h = h[0]
        
        # Filtrar solo vías importantes para no sobrecargar de ruido el mapa
        if n and h in ("motorway", "trunk", "primary", "secondary", "tertiary"):
            if isinstance(n, list):
                calles.update(n)
            else:
                calles.add(n)
    
    logger.info(f"Se encontraron {len(calles)} avenidas/calles principales.")
    return list(calles)


def generar_datos_simulacion():
    """Genera 120 minutos de tráfico (14:00 - 16:00) con fluctuaciones aleatorias leves."""
    hoy = date.today()
    registros: list[dict[str, Any]] = []
    
    avenidas_reales = get_calles_principales()

    logger.info("Generando datos de simulación por minuto (esto tomará unos segundos)...")
    # Iterar cada minuto de 14:00 a 16:00 (121 minutos)
    for total_minutos in range(14 * 60, 16 * 60 + 1):
        hora = total_minutos // 60
        minuto = total_minutos % 60
        dt = datetime.combine(hoy, time(hora, minuto))
        hora_str = f"{hora:02d}:{minuto:02d}"

        for calle in avenidas_reales:
            # Tráfico base fluido a moderado
            base_retraso = 1.0 if "Gonzalitos" not in calle and "Constitución" not in calle else 1.2
            
            # Ruido aleatorio (baja sensibilidad)
            ruido = random.uniform(0.0, 0.4)
            factor_retraso = round(base_retraso + ruido, 2)

            # Velocidad y delay en base al factor
            velocidad = int(50 / factor_retraso)
            delay = int((factor_retraso - 1.0) * 120)  # Delay base
            motivo = "Tráfico fluido/moderado regular"

            if factor_retraso > 1.5:
                motivo = "Tráfico pesado"

            registros.append({
                "tiempo": dt,
                "hora": hora_str,
                "calle_nombre": calle,
                "factor_retraso": factor_retraso,
                "delay_segundos": delay,
                "velocidad_kmh": velocidad,
                "motivo": motivo,
                "coords": []  # Ya no usamos coords estáticas, el frontend colorea por nombre
            })

    # Guardar en lotes de 5000 registros
    logger.info(f"Guardando {len(registros)} registros de tráfico base (random)...")
    for i in range(0, len(registros), 5000):
        save_traffic_batch(registros[i:i + 5000])

    logger.info(
        "Población de datos base completada exitosamente. (Incidentes se inyectarán vía API)."
    )


def seed_all():
    init_db()
    generar_datos_simulacion()


if __name__ == "__main__":
    seed_all()
