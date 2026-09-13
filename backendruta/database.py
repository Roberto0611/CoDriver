import json
import logging
import os
from datetime import datetime
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Lock, Thread
from time import monotonic, sleep
from typing import Any

from dotenv import load_dotenv
from psycopg2.extras import execute_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

from backendruta import database_schema as schema

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

# Las decisiones viajan por una cola: /decide solo mete un diccionario en memoria
# y nunca espera a Postgres. El hilo de abajo puede tardar, reintentar o caerse sin
# gastar el presupuesto de 50 ms de la ruta rapida.
_DECISION_QUEUE: Queue[dict[str, Any]] = Queue(maxsize=10_000)
_DECISION_THREAD: Thread | None = None
_DECISION_THREAD_LOCK = Lock()


def get_engine(force_retry: bool = False) -> Engine | None:
    global _engine, _db_connected, _connection_attempted
    if _engine is not None:
        return _engine

    if _connection_attempted and not force_retry:
        return None

    _connection_attempted = True
    try:
        # Timeout corto (1s) para no congelar la app si no hay servidor Postgres levantado
        engine_url: str | URL = DATABASE_URL
        if os.getenv("PGHOST") and not os.getenv("TIGERDATA_DATABASE_URL"):
            engine_url = URL.create(
                "postgresql+psycopg2",
                username=os.getenv("PGUSER"),
                password=os.getenv("PGPASSWORD"),
                host=os.getenv("PGHOST"),
                port=int(os.getenv("PGPORT", "5432")),
                database=os.getenv("PGDATABASE"),
                query={"sslmode": os.getenv("PGSSLMODE", "require")},
            )
        _engine = create_engine(engine_url, pool_pre_ping=True, connect_args={"connect_timeout": 1})
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _db_connected = True
        logger.info(
            f"Conectado exitosamente a TigerData/PostgreSQL en {str(engine_url).split('@')[-1]}"
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
            # 1. Intentar activar la extensión TimescaleDB. Lo opcional va en SAVEPOINT: en
            # Postgres una orden que falla aborta la transacción y tumbaba las tablas de abajo.
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

            # 2-4. Tablas e indices (ver database_schema.py).
            for sentencia in schema.TABLAS:
                conn.execute(text(sentencia))

            # Con TimescaleDB, las dos series de tiempo se vuelven hypertables. Cada una en
            # su SAVEPOINT: si una no se puede convertir, el resto del esquema sigue.
            for tabla, columna in schema.HIPERTABLAS:
                if not has_timescale:
                    break
                try:
                    with conn.begin_nested():
                        conn.execute(
                            text(
                                f"SELECT create_hypertable('{tabla}', '{columna}', "
                                "if_not_exists => TRUE);"
                            )
                        )
                except Exception as e:
                    logger.debug(f"Hipertabla {tabla} ya existente o no requerida: {e}")

            for sentencia in schema.INDICES_FINALES:
                conn.execute(text(sentencia))

        logger.info("Esquema de base de datos TigerData inicializado correctamente.")
        return True
    except Exception as e:
        logger.error(f"Error al inicializar esquema en TigerData: {e}")
        return False


def clear_traffic() -> None:
    """Vacia trafico_calles: solo la llena el seed, que la regenera completa al arrancar."""
    engine = get_engine()
    if engine and is_connected():
        try:
            with engine.begin() as conn:
                conn.execute(text("TRUNCATE trafico_calles"))
        except Exception as e:
            logger.error(f"Error al vaciar trafico_calles en TigerData: {e}")


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
        filas = [
            (
                r["tiempo"],
                r["calle_nombre"],
                r.get("factor_retraso", 1.0),
                r.get("delay_segundos", 0),
                r.get("velocidad_kmh", 50),
                r.get("motivo", "Fluido"),
                json.dumps(r.get("coords", [])),
            )
            for r in records
        ]
        try:
            # Un INSERT multi-fila por pagina: fila por fila eran 155k viajes a la nube.
            with engine.begin() as conn:
                execute_values(
                    conn.connection.cursor(),
                    """
                    INSERT INTO trafico_calles
                        (tiempo, calle_nombre, factor_retraso, delay_segundos,
                         velocidad_kmh, motivo, coords)
                    VALUES %s
                    """,
                    filas,
                    page_size=5000,
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


def enqueue_decision(event: dict[str, Any], log_path: Path) -> None:
    """Encola una decision para TigerData sin bloquear la ruta rapida.

    El JSONL se escribe antes de llegar aqui y sigue siendo la fuente para replay.
    Solo los eventos ``decision`` van a la serie de tiempo; posiciones y ofertas no
    duplican la bitacora porque ya estan anidados en el contexto de la decision.
    """
    if event.get("event") != "decision":
        return
    record = _decision_record(event, log_path)
    try:
        _DECISION_QUEUE.put_nowait(record)
    except Full:
        logger.error("Cola de decisiones TigerData llena; el JSONL local conserva el evento.")
        return
    _start_decision_worker()


def get_decision(log_path: Path, order_id: str) -> dict[str, Any] | None:
    """Lee una explicacion persistida; se usa fuera de la ventana de decision."""
    engine = get_engine()
    if not engine or not is_connected():
        return None
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT payload
                    FROM decisiones_courier
                    WHERE log_path = :log_path AND order_id = :order_id
                    ORDER BY sim_time DESC
                    LIMIT 1
                """),
                {"log_path": str(log_path), "order_id": order_id},
            ).scalar_one_or_none()
    except Exception as exc:
        logger.warning(f"Error consultando decision en TigerData: {exc}")
        return None
    if isinstance(row, str):
        return json.loads(row)
    return row if isinstance(row, dict) else None


def flush_decisions(timeout_s: float = 1.0) -> bool:
    """Da al escritor de fondo una oportunidad acotada de vaciar la cola al cerrar."""
    deadline = monotonic() + timeout_s
    while _DECISION_QUEUE.unfinished_tasks and monotonic() < deadline:
        sleep(0.01)
    return _DECISION_QUEUE.unfinished_tasks == 0


def _decision_record(event: dict[str, Any], log_path: Path) -> dict[str, Any]:
    """Extrae las columnas indexables y conserva el evento oficial completo."""
    return {
        "sim_time": event["sim_time"],
        "log_path": str(log_path),
        "order_id": event["order_id"],
        "decision": event["decision"],
        "binding_constraint": event.get("binding_constraint"),
        "payload": json.dumps(event, ensure_ascii=False, default=str),
    }


def _start_decision_worker() -> None:
    global _DECISION_THREAD
    with _DECISION_THREAD_LOCK:
        if _DECISION_THREAD is not None and _DECISION_THREAD.is_alive():
            return
        _DECISION_THREAD = Thread(target=_write_decisions, name="tigerdata-decisions", daemon=True)
        _DECISION_THREAD.start()


def _write_decisions() -> None:
    """Escritor en segundo plano; una falla de DB nunca propaga a /decide."""
    while True:
        try:
            first = _DECISION_QUEUE.get(timeout=0.2)
        except Empty:
            return
        batch = [first]
        while len(batch) < 100:
            try:
                batch.append(_DECISION_QUEUE.get_nowait())
            except Empty:
                break
        try:
            _save_decision_batch(batch)
        finally:
            for _ in batch:
                _DECISION_QUEUE.task_done()


def _save_decision_batch(records: list[dict[str, Any]]) -> None:
    engine = get_engine()
    if not engine or not is_connected():
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO decisiones_courier
                        (sim_time, log_path, order_id, decision, binding_constraint, payload)
                    VALUES
                        (:sim_time, :log_path, :order_id, :decision, :binding_constraint, :payload)
                """),
                records,
            )
    except Exception as exc:
        logger.error(f"Error al guardar decisiones en TigerData: {exc}")


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
