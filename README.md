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
```

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
| `valor.py`, `nuez.py` | Tabla de valor y política de costo de oportunidad |
| `tests/` | pytest |
| `backendruta/` | FastAPI: rutas y WebSocket |
| `frontend/` | React + Vite + MapLibre |
| `data/` | Descarga del grafo y exportes para el front |
| `scripts/` | Utilidades sueltas y el check de líneas |
