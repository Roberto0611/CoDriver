"""Script para poblar TigerData (o fallback en memoria) con telemetría de tráfico
minuto a minuto para Monterrey entre las 14:00 y las 16:00, incluyendo el incidente
crítico a las 14:35 para la demostración del agente.

Las calles salen del grafo real, para cubrir toda la ciudad. Los factores NO se
inventan aquí: salen de `mundo.CURVAS_CORREDOR`, la misma tabla que el motor usa
para decidir. Así el rojo del mapa y el número de una decisión son el mismo dato,
y cuando un juez pregunte "¿por eso se desvió?" la respuesta es sí.
"""

import logging
import pickle
import random
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backendruta.database import clear_traffic, init_db, save_traffic_batch  # noqa: E402
from mundo import CURVAS_CORREDOR, ZONAS  # noqa: E402

logger = logging.getLogger("seed_traffic")
logging.basicConfig(level=logging.INFO)

G_PATH = BASE_DIR / "data" / "mty_graph.pkl"

SEED = 7  # el mapa tiene que verse igual cada vez que el juez repite el turno

LAT_RIO = 25.66  # el Santa Catarina parte la ciudad; cruzarlo es el cuello de botella
CENTRO = ZONAS["Centro"][:2]

# Si no hay grafo a la mano (CI, o una maquina sin los 52 MB), estas bastan.
FALLBACK = {
    "Av. Eugenio Garza Sada": "hacia_centro",
    "Av. Constitución": "cruza_rio",
    "Av. Morones Prieto": "cruza_rio",
    "Av. José Eleuterio González (Gonzalitos)": "hacia_centro",
    "Av. Revolución": "desde_centro",
    "Av. Lázaro Cárdenas": "desde_centro",
}


def _corredor_de(lats: list[float], lons: list[float]) -> str:
    """A que corredor pertenece una calle, segun por donde pasa.

    ponytail: heuristica por geometria, no por aforo real. Una calle que cruza el
    rio sufre las dos horas pico; las pegadas al centro son arterias de entrada;
    las de en medio, salidas; las lejanas son locales y casi no se atoran.
    """
    if min(lats) < LAT_RIO < max(lats):
        return "cruza_rio"

    lat, lon = sum(lats) / len(lats), sum(lons) / len(lons)
    # Grados a km, aproximado a esta latitud.
    km = (((lat - CENTRO[0]) * 111) ** 2 + ((lon - CENTRO[1]) * 100) ** 2) ** 0.5
    if km < 3:
        return "hacia_centro"
    if km < 7:
        return "desde_centro"
    return "local"


def get_calles_principales() -> dict[str, str]:
    """Nombre de calle -> corredor, sacado del grafo real.

    Solo vias principales: las locales son el 84% de las aristas, a este zoom no se
    distinguen, y multiplicarian los registros sin aportar nada.
    """
    if not G_PATH.exists():
        logger.warning("No se encontró mty_graph.pkl. Usando fallback básico.")
        return dict(FALLBACK)

    logger.info("Extrayendo calles del grafo para simulación...")
    G = pickle.loads(G_PATH.read_bytes())

    puntos: dict[str, tuple[list[float], list[float]]] = {}
    for u, _v, d in G.edges(data=True):
        h = d.get("highway", "")
        if isinstance(h, list):
            h = h[0]
        if h not in ("motorway", "trunk", "primary", "secondary", "tertiary"):
            continue

        n = d.get("name")
        if not n:
            continue
        for nombre in n if isinstance(n, list) else [n]:
            lats, lons = puntos.setdefault(nombre, ([], []))
            lats.append(G.nodes[u]["y"])
            lons.append(G.nodes[u]["x"])

    calles = {nombre: _corredor_de(lats, lons) for nombre, (lats, lons) in puntos.items()}
    logger.info(f"Se encontraron {len(calles)} avenidas/calles principales.")
    return calles


def generar_datos_simulacion():
    """Genera 120 minutos de tráfico (14:00 - 16:00) derivado de las curvas del motor."""
    hoy = date.today()
    rng = random.Random(SEED)
    registros: list[dict[str, Any]] = []

    calles = get_calles_principales()

    logger.info("Generando datos de simulación por minuto (esto tomará unos segundos)...")
    for total_minutos in range(14 * 60, 16 * 60 + 1):
        hora = total_minutos // 60
        minuto = total_minutos % 60
        dt = datetime.combine(hoy, time(hora, minuto))
        hora_str = f"{hora:02d}:{minuto:02d}"

        for calle, corredor in calles.items():
            # El mismo numero que usa el motor para decidir, por corredor y hora.
            base_retraso = CURVAS_CORREDOR[corredor][hora]

            # Variacion leve entre minutos, con semilla: mismo seed, mismo mapa.
            factor_retraso = round(base_retraso * rng.uniform(0.95, 1.05), 2)

            velocidad = int(50 / factor_retraso)
            delay = int((factor_retraso - 1.0) * 120)
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
                    "corredor": corredor,
                    "factor_retraso": factor_retraso,
                    "delay_segundos": delay,
                    "velocidad_kmh": velocidad,
                    "motivo": motivo,
                    "coords": [],  # el frontend colorea por nombre, no por geometría
                }
            )

    logger.info(f"Guardando {len(registros)} registros derivados de mundo.CURVAS_CORREDOR...")
    # La consulta filtra por HH:MI sin fecha: sin vaciar, cada arranque duplica el mapa.
    clear_traffic()
    for i in range(0, len(registros), 5000):
        save_traffic_batch(registros[i : i + 5000])

    logger.info(
        "Población de datos base completada exitosamente. (Incidentes se inyectarán vía API)."
    )
    return registros


def seed_all():
    init_db()
    generar_datos_simulacion()


if __name__ == "__main__":
    seed_all()
