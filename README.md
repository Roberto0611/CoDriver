# Nuez — HackMTY 2026 · Infosys "The Courier"

Copiloto de turno para repartidores estudiantes: decide qué pedidos aceptar en una ventana
corta entre clases, le gana a un repartidor greedy y explica cada decisión en voz alta.

El contexto completo del proyecto (idea, arquitectura, motor, tracks, plan) está en
[`agents.md`](agents.md). La guía visual del front está en
[`docs/ui-style-guide.md`](docs/ui-style-guide.md).

## Correr

```bash
pip install -r requirements.txt -r requirements-dev.txt
python correr.py          # un turno greedy con el detalle de decisiones
python comparar.py 50     # Nuez vs greedy en 50 turnos frescos: EL NÚMERO
python comparar.py 50 --rivales  # los cinco agentes online con los mismos turnos
```

`--rivales` mide reglas deliberadamente fijas: `AcceptAll` toma todo pedido
factible; `HighestPay` exige pago neto de al menos $80; `NearestFirst` exige
un pickup a 10 minutos o menos; `GreedyRate` y `OurAgent` son las políticas
existentes. Las cinco pasan por `seguridad.revisar`. `Oracle` corre sólo offline:
conoce el stream completo, explora agendas sin pedidos apilados y conserva el
mejor resultado reproducible frente a las políticas online.

## Protocolo de Infosys

El adaptador HTTP conserva el motor en minutos relativos y traduce solamente en
la frontera las fechas ISO, zonas enteras y acciones `ACCEPT`/`SKIP` del protocolo.

```bash
python -m uvicorn backendruta.main:app --host 127.0.0.1 --port 8000
```

Rutas principales:

- `GET /zones`: catálogo estable `id` ↔ zona de Monterrey.
- `POST /shift/start`: inicia o reinicia una sesión con `seed`, `shift_hours`,
  `vehicle` y `start_location_zone`. `sim_time` es opcional.
- `POST /decide`: recibe un `order_offered`, aplica `courier_state_overrides` y
  devuelve la decisión rápida en el esquema oficial.
- `GET /shift/status` y `POST /shift/end`: inspeccionan y cierran la sesión.

Sin `/shift/start`, el primer `/decide` crea una sesión determinista de ocho horas;
esto permite que el probe de formato oficial funcione directamente. Cada sesión
escribe `cache/courier/current_shift.jsonl` por defecto. Puede cambiarse antes de
arrancar el proceso con `NUEZ_EVENT_LOG`.

```bash
python "courier/validate_format (2).py" --endpoint http://localhost:8000/decide
python "courier/validate_format (2).py" --event-log cache/courier/current_shift.jsonl
```

`/decide` no llama a modelos ni a servicios externos. Usa la última estrategia
local, la tabla de valor en disco y las restricciones de `seguridad.py`. Los tiempos
estimados enviados por Infosys tienen prioridad cuando el repartidor está libre;
para trabajo apilado se usa el ruteo interno entre zonas.

Convenciones frente al runner de Infosys (`courier-update/run_probe_pack.py`, el mismo
script que corren los jueces):

- **Zonas marcadas de noche.** En `/decide` solo la zona **99** está marcada, que es la
  convención documentada del practice pack. Se decide con el número que llega, antes de
  traducirlo: los números de zona de otro stream no son los nuestros y el nombre es
  opcional. El simulador conserva su propia capa de riesgo (`mundo.ZONAS_MARCADAS`).
- **Fin de turno.** La regla es terminar la entrega antes del fin del turno. Regresar al
  punto de partida es opcional: `return_to_start` en `/shift/start`, apagado por omisión.
- **Pedidos en vuelo.** Se acepta la forma del runner (`order_id`, `minutes_remaining`,
  `dropoff_zone`), y los minutos que declara mandan sobre el ruteo interno.
- **Latencia.** Medir contra `127.0.0.1`, no `localhost`: en Windows este último intenta
  IPv6 primero y agrega unos 2 segundos por petición.

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173
```

## Antes de subir cambios

CI corre en cada push y PR a `main`. Lo mismo, local:

```bash
python -m ruff check . && python -m ruff format . && python -m mypy && python -m pytest
python scripts/max_lines.py .
```

```bash
cd frontend && npm run check
```

`npm run check` encadena lint, tipos, formato, tests, límite de 500 líneas y build.

## Estructura

| Ruta | Qué |
|---|---|
| `contrato.py` | Formas de `Oferta`, `Decision`, `EstadoRepartidor`, `EventoMundo` |
| `mundo.py`, `rutas.py` | Zonas, tráfico por hora, riesgo, matriz de tiempos |
| `sim.py` | Simulador de turno y baseline greedy |
| `baselines.py` | AcceptAll, HighestPay y NearestFirst, con las mismas restricciones duras |
| `oracle.py` | Planeador offline con stream completo; jamás se expone en `/decide` |
| `valor.py`, `nuez.py` | Tabla de valor y política de costo de oportunidad |
| `tests/` | pytest |
| `backendruta/` | FastAPI: protocolo Courier, rutas, JSONL, voz y WebSocket |
| `frontend/` | React + Vite + MapLibre |
| `data/` | Descarga del grafo y exportes para el front |
| `scripts/` | Utilidades sueltas y el check de líneas |

prueba