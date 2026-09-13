# Contexto para Agente: Integración de Oracle en Vivo

**Objetivo de este documento:** Proveer contexto técnico y arquitectónico rápido a otro agente de IA sobre la reciente implementación del algoritmo "Oracle" en el dashboard en vivo (`/sim`).

## 1. El Problema Original
En el componente `LiveBenchmarkRace` (frontend), la fila del algoritmo **Oracle** mostraba un valor fijo hardcodeado (`$259`, un promedio offline). El usuario quería que el Oracle simulara la ruta perfecta **dinámicamente** para el turno actual, tomando en cuenta las disrupciones inyectadas (cierres de calles, picos de demanda, retrasos).

**La limitante técnica:** El Oracle utiliza un *Beam Search* exhaustivo (`ANCHO_HAZ=48`) porque "ve el futuro" completo del turno para tomar las decisiones perfectas. Correr esto toma entre 15 y 30 segundos para un turno de 8 horas, lo cual es inaceptable para correrlo de forma síncrona ("tick by tick") en el loop de `/live/tick` ya que congelaría el frontend y el backend.

## 2. La Solución Arquitectónica
Se diseñó un flujo **asíncrono** al finalizar el turno:
1. Durante el turno, el frontend ignora al Oracle y muestra un estado de espera (`waiting for shift end...`).
2. Cuando el turno finaliza (por agotar el tiempo o forzado por el usuario mediante `/live/end`), el backend lanza un **hilo en background** para calcular el Oracle de ese turno exacto, inyectando las disrupciones conocidas.
3. El frontend entra en un modo de polling (`computing...`) preguntando al backend por el resultado.
4. Cuando el hilo termina, el backend responde con los resultados reales y el frontend actualiza la tabla.

## 3. Archivos Modificados

### Backend (Python / FastAPI)
- **`oracle.py`**
  - **Cambios:** Se actualizó la firma de `planificar`, `resolver`, y `simular_oracle` para recibir el parámetro `disrupciones: tuple[LiveShock]`. 
  - **Razón:** El oráculo necesita predecir exactamente las mismas eventualidades que experimentaron los agentes normales para encontrar el path perfecto real de esa sesión.
- **`backendruta/live_api.py`**
  - **Cambios:** 
    - Se creó un `CalculoOracle` (dataclass) con un `threading.Event` para manejar el estado del hilo.
    - Se modificó `LiveRegistry` para manejar `self._oracles` y lanzar el hilo `_calcular_oracle`.
    - Se inyectó la llamada a `registry.oracle(sesion)` dentro de `@router.post("/end")`.
    - Se creó un nuevo endpoint `@router.get("/oracle/{session_id}")` que devuelve `HTTP 202` si el hilo sigue vivo, y `HTTP 200` con `{"earnings_mxn": X, "deliveries": Y}` cuando termina.

### Frontend (React / TypeScript / Vite)
- **`frontend/src/lib/live.ts`**
  - **Cambios:** Se agregaron las funciones `getOracle` y `esperarOracle`.
  - **Razón:** Funciones de polling que consultan `/live/oracle/{id}` cada 700ms (`COUNTERFACTUAL_POLL_MS`) y manejan el 202 Accepted de forma transparente sin frenar el UI.
- **`frontend/src/sim/LiveBenchmarkRace.tsx`**
  - **Cambios:**
    - Se convirtió la lógica puramente presentacional a una manejada por *Hooks* (`useState` y `useEffect`).
    - **Trigger:** Cuando `snapshot.status === 'ended'` o `'finished'`, el `useEffect` invoca a `esperarOracle`.
    - Se agregaron 4 estados lógicos al componente: `'idle'` (muestra *"waiting for shift end..."*), `'loading'` (muestra *"computing..."*), `'done'` (muestra resultados reales), y `'failed'`.

## 4. Notas para el Agente que lea esto
1. **Concurrencia:** El backend está usando `RLock` de `threading` por sesión. Es importante no adquirir el lock dentro del cómputo pesado del oráculo (`simular_oracle`), solo se adquiere para copiar la configuración al inicio del hilo.
2. **Ciclo de vida de React:** Al inyectar Hooks (`useEffect`) en un componente que antes no los tenía, es vital refrescar la página (full reload) en desarrollo para que Vite limpie su árbol, de lo contrario el cliente puede estancarse en el código viejo (un problema clásico de Hot Module Replacement). El código frontend actual es válido y funciona al refrescar.
