import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Cargar variables de entorno desde .env en la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger("tigerdata")
logger.setLevel(logging.INFO)

DATABASE_URL = os.getenv(
    "TIGERDATA_DATABASE_URL", "postgresql://postgres:password@localhost:5432/postgres"
)

# Estado de la conexión
_engine: Engine | None = None
_db_connected: bool = False
_connection_attempted: bool = False

# Fallback en memoria si la BD no está disponible aún
_MEMORY_TRAFFIC: dict[str, list[dict[str, Any]]] = {}
_MEMORY_INCIDENTS: list[dict[str, Any]] = []


def get_engine(force_retry: bool = False) -> Engine | None:
    global _engine, _db_connected, _connection_attempted
    if _engine is not None:
        return _engine

    if _connection_attempted and not force_retry:
        return None

    _connection_attempted = True
    try:
        # Timeout corto (1s) para no congelar la app si no hay servidor Postgres levantado
        _engine = create_engine(
            DATABASE_URL, pool_pre_ping=True, connect_args={"connect_timeout": 1}
        )
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _db_connected = True
        logger.info(
            f"Conectado exitosamente a TigerData/PostgreSQL en {DATABASE_URL.split('@')[-1]}"
        )
    except Exception as e:
        logger.warning(
            f"No se pudo conectar a TigerData/PostgreSQL ({e}). "
            "Usando almacén en memoria para simulación."
        )
        _engine = None
        _db_connected = False

    return _engine


def is_connected() -> bool:
    global _db_connected
    if not _connection_attempted:
        get_engine()
    return _db_connected


def init_db() -> bool:
    """Crea las tablas e hipertablas de TimescaleDB si está disponible."""
    engine = get_engine()
    if not engine:
        return False

    try:
        with engine.begin() as conn:
            # 1. Intentar activar la extensión TimescaleDB. Va en un SAVEPOINT: en
            # Postgres una orden que falla aborta la transacción entera, y sin él las
            # tablas de abajo tronaban con "transacción abortada" en un Postgres sin Timescale.
            has_timescale = False
            try:
                with conn.begin_nested():
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
                has_timescale = True
                logger.info("Extensión TimescaleDB detectada y activa.")
            except Exception as e:
                logger.info(
                    f"TimescaleDB no disponible en este servidor ({e}); usando PostgreSQL estándar."
                )

            # 2. Tabla de tráfico por minuto (series de tiempo)
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS trafico_calles (
                    tiempo TIMESTAMPTZ NOT NULL,
                    calle_nombre TEXT NOT NULL,
                    factor_retraso FLOAT DEFAULT 1.0,
                    delay_segundos INT DEFAULT 0,
                    velocidad_kmh INT,
                    motivo TEXT,
                    coords JSONB
                );
            """)
            )

            # Si TimescaleDB está presente, convertirla a hypertable
            if has_timescale:
                try:
                    with conn.begin_nested():  # mismo motivo: un fallo no aborta el resto
                        conn.execute(
                            text(
                                "SELECT create_hypertable("
                                "'trafico_calles', 'tiempo', if_not_exists => TRUE);"
                            )
                        )
                except Exception as e:
                    logger.debug(f"Hipertabla ya existente o no requerida: {e}")

            # Índices para consultas instantáneas por minuto
            conn.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_trafico_calles_tiempo
                ON trafico_calles (tiempo DESC);
            """)
            )

            # 3. Tabla de incidentes y cierres viales
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS incidentes_viales (
                    id TEXT PRIMARY KEY,
                    inicio TIMESTAMPTZ NOT NULL,
                    fin TIMESTAMPTZ NOT NULL,
                    calle TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    factor_penalizacion FLOAT DEFAULT 1000.0,
                    motivo TEXT,
                    alerta_voz TEXT,
                    coords JSONB
                );
            """)
            )

            conn.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_incidentes_fechas
                ON incidentes_viales (inicio, fin);
            """)
            )

        logger.info("Esquema de base de datos TigerData inicializado correctamente.")
        return True
    except Exception as e:
        logger.error(f"Error al inicializar esquema en TigerData: {e}")
        return False


def save_traffic_batch(records: list[dict[str, Any]]) -> None:
    """Guarda un lote de registros de tráfico (tanto en DB como en fallback de memoria)."""
    engine = get_engine()

    # Siempre guardamos en fallback de memoria por seguridad
    for r in records:
        hora_str = r.get("hora", "")
        if not hora_str and isinstance(r.get("tiempo"), datetime):
            hora_str = r["tiempo"].strftime("%H:%M")
        if hora_str:
            _MEMORY_TRAFFIC.setdefault(hora_str, []).append(r)

    if engine and is_connected():
        try:
            with engine.begin() as conn:
                for r in records:
                    conn.execute(
                        text("""
                            INSERT INTO trafico_calles
                                (tiempo, calle_nombre, factor_retraso, delay_segundos,
                                 velocidad_kmh, motivo, coords)
                            VALUES
                                (:tiempo, :calle_nombre, :factor_retraso, :delay_segundos,
                                 :velocidad_kmh, :motivo, :coords)
                        """),
                        {
                            "tiempo": r["tiempo"],
                            "calle_nombre": r["calle_nombre"],
                            "factor_retraso": r.get("factor_retraso", 1.0),
                            "delay_segundos": r.get("delay_segundos", 0),
                            "velocidad_kmh": r.get("velocidad_kmh", 50),
                            "motivo": r.get("motivo", "Fluido"),
                            "coords": json.dumps(r.get("coords", [])),
                        },
                    )
        except Exception as e:
            logger.error(f"Error al guardar lote en TigerData: {e}")


def save_incident(incident: dict[str, Any]) -> None:
    """Guarda un incidente/cierre vial."""
    # Guardar en memoria
    _MEMORY_INCIDENTS.append(incident)

    engine = get_engine()
    if engine and is_connected():
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO incidentes_viales
                            (id, inicio, fin, calle, tipo, factor_penalizacion,
                             motivo, alerta_voz, coords)
                        VALUES
                            (:id, :inicio, :fin, :calle, :tipo, :factor_penalizacion,
                             :motivo, :alerta_voz, :coords)
                        ON CONFLICT (id) DO UPDATE SET
                            inicio = EXCLUDED.inicio,
                            fin = EXCLUDED.fin,
                            factor_penalizacion = EXCLUDED.factor_penalizacion,
                            motivo = EXCLUDED.motivo,
                            alerta_voz = EXCLUDED.alerta_voz,
                            coords = EXCLUDED.coords;
                    """),
                    {
                        "id": incident["id"],
                        "inicio": incident["inicio"],
                        "fin": incident["fin"],
                        "calle": incident["calle"],
                        "tipo": incident.get("tipo", "CIERRE"),
                        "factor_penalizacion": incident.get("factor_penalizacion", 1000.0),
                        "motivo": incident.get("motivo", ""),
                        "alerta_voz": incident.get("alerta_voz", ""),
                        "coords": json.dumps(incident.get("coords", [])),
                    },
                )
        except Exception as e:
            logger.error(f"Error al guardar incidente en TigerData: {e}")


def get_traffic_at_time(hora_str: str) -> list[dict[str, Any]]:
    """
    Retorna el estado de tráfico en una hora específica (ej. '14:35').
    Devuelve lista de objetos con calle, factor_retraso, coords, etc.
    """
    engine = get_engine()
    if engine and is_connected():
        try:
            # Consultar registros que coincidan con la hora y minuto
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT calle_nombre, factor_retraso, delay_segundos,
                               velocidad_kmh, motivo, coords
                        FROM trafico_calles
                        WHERE TO_CHAR(tiempo, 'HH24:MI') = :hora
                        ORDER BY factor_retraso DESC
                    """),
                    {"hora": hora_str},
                )
                rows = []
                for row in result:
                    coords = json.loads(row[5]) if isinstance(row[5], str) else row[5]
                    rows.append(
                        {
                            "calle_nombre": row[0],
                            "factor_retraso": float(row[1]),
                            "delay_segundos": int(row[2]),
                            "velocidad_kmh": int(row[3]),
                            "motivo": row[4],
                            "coords": coords,
                        }
                    )
                if rows:
                    return rows
        except Exception as e:
            logger.warning(f"Error consultando TigerData: {e}. Usando fallback de memoria.")

    # Fallback de memoria
    return _MEMORY_TRAFFIC.get(hora_str, [])


def get_active_incidents(hora_str: str) -> list[dict[str, Any]]:
    """
    Retorna incidentes activos a la hora dada (ej. '14:35').
    """
    engine = get_engine()
    if engine and is_connected():
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT id, calle, tipo, factor_penalizacion, motivo, alerta_voz, coords
                        FROM incidentes_viales
                        WHERE TO_CHAR(inicio, 'HH24:MI') <= :hora
                          AND TO_CHAR(fin, 'HH24:MI') >= :hora
                    """),
                    {"hora": hora_str},
                )
                incidents = []
                for row in result:
                    coords = json.loads(row[6]) if isinstance(row[6], str) else row[6]
                    incidents.append(
                        {
                            "id": row[0],
                            "calle": row[1],
                            "tipo": row[2],
                            "factor_penalizacion": float(row[3]),
                            "motivo": row[4],
                            "alerta_voz": row[5],
                            "coords": coords,
                        }
                    )
                if incidents:
                    return incidents
        except Exception as e:
            logger.warning(
                f"Error consultando incidentes en TigerData: {e}. Usando fallback de memoria."
            )

    # Fallback de memoria
    active = []
    for inc in _MEMORY_INCIDENTS:
        h_inicio = (
            inc["inicio"].strftime("%H:%M")
            if isinstance(inc["inicio"], datetime)
            else str(inc["inicio"])[-5:]
        )
        h_fin = (
            inc["fin"].strftime("%H:%M")
            if isinstance(inc["fin"], datetime)
            else str(inc["fin"])[-5:]
        )
        if h_inicio <= hora_str <= h_fin:
            active.append(inc)
    return active
