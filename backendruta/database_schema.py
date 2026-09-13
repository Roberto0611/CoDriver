"""El esquema de TigerData: las sentencias que `database.init_db()` corre en orden.

Solo DDL. La conexion, los SAVEPOINT y la extension TimescaleDB viven en database.py.
"""

# En este orden, antes de convertir hypertables.
TABLAS = (
    # 2. Tabla de tráfico por minuto (series de tiempo)
    """
                CREATE TABLE IF NOT EXISTS trafico_calles (
                    tiempo TIMESTAMPTZ NOT NULL,
                    calle_nombre TEXT NOT NULL,
                    factor_retraso FLOAT DEFAULT 1.0,
                    delay_segundos INT DEFAULT 0,
                    velocidad_kmh INT,
                    motivo TEXT,
                    coords JSONB
                );
            """,
    # Índices para consultas instantáneas por minuto
    """
                CREATE INDEX IF NOT EXISTS idx_trafico_calles_tiempo
                ON trafico_calles (tiempo DESC);
            """,
    # 3. Tabla de incidentes y cierres viales
    """
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
            """,
    """
                CREATE INDEX IF NOT EXISTS idx_incidentes_fechas
                ON incidentes_viales (inicio, fin);
            """,
    # 4. Bitacora auditable del motor. El JSONB conserva todo el evento
    # oficial (incluyendo inputs y alternativas) sin inventar un segundo
    # contrato que se pueda desalinear del JSONL de replay.
    """
                CREATE TABLE IF NOT EXISTS decisiones_courier (
                    id BIGSERIAL NOT NULL,
                    sim_time TIMESTAMPTZ NOT NULL,
                    log_path TEXT NOT NULL,
                    order_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    binding_constraint TEXT,
                    payload JSONB NOT NULL,
                    PRIMARY KEY (sim_time, id)
                );
            """,
)

# (tabla, columna de tiempo) que se vuelven hypertable si hay TimescaleDB.
HIPERTABLAS = (
    ("trafico_calles", "tiempo"),
    ("decisiones_courier", "sim_time"),
)

# Despues de las hypertables: el indice se crea sobre la tabla ya convertida.
INDICES_FINALES = (
    """
                CREATE INDEX IF NOT EXISTS idx_decisiones_courier_order
                ON decisiones_courier (log_path, order_id, sim_time DESC);
            """,
)
