# Nuez — HackMTY 2026 / Reto Infosys "The Courier"

Documento de contexto del proyecto. Lo que decidimos, por qué, y cómo se trabaja aquí.

---

## 1. El reto

> Dado un flujo de ofertas de entrega, tráfico y un turno limitado, ¿puede un agente de IA
> ganar lo máximo para un repartidor, como lo haría un conductor experimentado?

**Criterios de evaluación (solo dos):**

| Criterio | Qué miden |
|---|---|
| **Results** | En un turno fresco que no vimos, cuánto gana el agente vs un baseline simple |
| **Judgment** | ¿Toma decisiones seguras y sensatas bajo surge/tráfico, y puede explicárselas a un juez? |

**Lectura estratégica:** la mitad del puntaje no es el algoritmo, es que el agente
**sepa defender su decisión**. Casi todos los equipos van a construir un optimizador y una
gráfica. Gana el que construya un optimizador **que hable**.

Entregable pedido explícitamente por el reto: código funcionando + demo en vivo donde
**dos agentes corren el mismo turno fresco lado a lado**, con un contador de ganancias
corriendo, y un **surge o un cierre vial** a mitad del turno al que deben reaccionar.

---

## 2. La idea

**Nuez** — el copiloto del repartidor estudiante. Un agente que corre tu ventana libre entre
clases y te dice al oído, en voz alta y en español regio, qué aceptar y por qué.

```
[ping] "Rappi, Contry a San Pedro, $48."
Nuez: "Salta. Son 22 minutos contra tráfico y no alcanzas a volver
       para tu clase de las 4. En 6 minutos entra el surge aquí cerca."
```

Un repartidor en moto a 40°C **no lee una pantalla**. La voz no es un add-on para ganar un
track: es la única UI honesta para este caso de uso.

**Frase de pitch:** *no optimizamos las entregas de la plataforma, optimizamos el ingreso del
repartidor — y le explicamos cada decisión en voz alta, porque él es el que va manejando.*

### Enfoque estudiantil (input de la sesión con Infosys)

El usuario no es un repartidor de tiempo completo: es un universitario con **dos horas libres
entre clases** que quiere sacar dinero sin alejarse del campus.

**Esto no es solo narrativa — refuerza el motor.** Un turno de 8 horas perdona errores: aceptas
una mala, pierdes 40 minutos, te recuperas. Dos horas no perdonan nada: un pedido malo se come
el 30% de la ventana. **Mientras más corto el turno, más vale el costo de oportunidad** y más
ridículo se ve el greedy. El delta contra el baseline se dispara.

Y el demo le pega mucho más a jueces que están parados en un campus.

### Configuración antes del turno

| Input | Efecto |
|---|---|
| Ventana horaria (ej. hoy 14:00–16:00) | Duración del turno → `V[t]` arranca en t=120, no 480 |
| Ancla (campus, biblioteca, casa) | Restricción de regreso factible |
| Margen de seguridad (default 10 min) | Colchón antes de que empiece la clase |
| Vehículo (moto / bici / scooter / a pie) | Velocidades y costo de combustible |

### La restricción de distancia NO es un radio

El instinto es "geocerca de 3 km alrededor de la uni". **Está mal:** un pedido que te aleja 3 km
en el minuto 20 es perfecto; el mismo en el minuto 100 te deja sin llegar a clase.

Lo correcto es **regreso factible**, como filtro duro junto al de seguridad:

```
aceptar  <=>  t_recoger + t_entregar + t_regreso_al_ancla(destino) <= t_restante − margen
```

**Comportamiento emergente:** conforme se acaba la ventana, el conjunto de pedidos válidos se
encoge hacia el campus. El agente "se va regresando" solo, sin que nadie lo programe — igual que
el pedido de $90 que cambia de malo a bueno. Dos emergencias explicables en una frase cada una,
ambas en el mismo demo.

No requiere motor nuevo: `V[tiempo][zona]` ya existe, esto es un filtro encima.

### La mascota: Nuez, y no es decoración

**El algoritmo ya es teoría de forrajeo óptimo.** El teorema del valor marginal de Charnov (1976)
—cuándo abandonar un parche de comida— dice exactamente lo que dice nuestro motor: *te vas cuando
el rendimiento local cae por debajo del promedio del ambiente*. Es la misma matemática, publicada
estudiando animales que juntan comida.

El animal del ejemplo clásico —el que junta, hace caché y **siempre regresa a su árbol**— es la
ardilla. Que además es la mascota no oficial del campus del Tec.

| | |
|---|---|
| **Nombre** | Nuez — es de aquí, es corta, es marca |
| **Mascota** | Ardilla regia con casco de moto |
| **Promesa** | "Junta más nueces entre clases" |
| **La voz** | La mascota **es** ElevenLabs. Nuez es quien te habla |

Eso amarra todo: mascota, voz y explicabilidad dejan de ser tres cosas y son una. Si un juez
pregunta por qué una ardilla: *"porque el algoritmo es literalmente forrajeo óptimo, y las
ardillas siempre vuelven a su árbol — como tú a tu clase de las 4."*

**Timebox del branding: 3 horas, una persona, en paralelo.** Nombre, un SVG, paleta, y el prompt
de personalidad de la voz. **NO:** personaje 3D, animaciones, landing, deck de 20 slides.
Si a la hora 10 no corre el baseline, la ardilla no nos salva.

### Encuadre de startup

El lado del trabajador en la economía gig: las plataformas optimizan sus entregas, nadie optimiza
tu ingreso por hora. Primer mercado: ~200k universitarios del área metropolitana que ya manejan
para Uber/Rappi/DiDi entre clases.

Con este encuadre **Solana deja de estar pegado con cinta**: la reputación portable entre
plataformas es producto, no track.

---

## 3. Arquitectura: dos capas

**Regla de oro: el LLM NUNCA hace las matemáticas.** Ese es el error que mata hackathons —
el LLM alucina un número, pierdes contra el baseline y no hay demo.

| Capa | Qué hace | Con qué |
|---|---|---|
| **Motor** (determinista) | Acepta/rechaza, agrupa, rutea. **Gana el dinero.** | Tabla de valor + enumeración exacta |
| **Juicio** (Gemini) | Explica, maneja excepciones, ajusta pesos de la política | Gemini Flash, salida estructurada |

Gemini **no elige la orden**. Gemini decide cosas como *"cerraron Constitución → sube la
penalización de cruce de río durante 20 min"* y emite el JSON con el que el motor recalcula.
Determinista, auditable, sin alucinación de dinero.

### Diagrama

```mermaid
flowchart TB
    subgraph OFF["OFFLINE — antes del demo"]
        SIM["Simulador de turnos<br/>seeds 1..300"] --> LOG[("TigerData<br/>tabla decisiones")]
        LOG --> AGG["time_bucket 15 min<br/>AVG ganancia futura"]
        AGG --> V[["V.json<br/>tabla de valor"]]
    end

    subgraph LIVE["EN VIVO — la ventana entre clases"]
        CFG["Config del turno:<br/>ventana, ancla, vehiculo, margen"] --> ENG
        STREAM["Stream de ofertas<br/>seed del juez"] --> ENG
        GRAFO[("Grafo OSMnx + matrices<br/>precacheadas a disco")] --> ENG
        ENG{{"MOTOR<br/>costo de oportunidad<br/>+ batching exacto"}} --> DEC["Aceptar / Saltar / Agrupar"]
        DEC --> UI["UI side-by-side<br/>MapLibre + contadores"]
        DEC --> VOZ["Nuez / ElevenLabs<br/>voz bidireccional"]
        VOZ -.->|preferencias del repartidor| ENG
        DEC --> TEL[("TigerData<br/>telemetría del turno")]
    end

    subgraph JUI["CAPA DE JUICIO — Gemini"]
        MUNDO["Clima, eventos masivos,<br/>cierres viales"] --> GEM["Gemini Flash<br/>salida estructurada"]
        GEM -.->|JSON de pesos y multiplicadores| ENG
        TEL --> REP["Reporte contrafactual<br/>al cierre del turno"]
        GEM --> REP
    end

    V ==> ENG
    REP --> SOL["Solana devnet<br/>reputación portable"]
```

**Lo que el diagrama tiene que dejar claro:** la flecha gruesa (`V.json → MOTOR`) es de disco, no
de red. Gemini y el mundo exterior solo entran por líneas punteadas — **ajustan pesos, nunca
deciden dinero**. Si Gemini se cae a media demo, el agente sigue corriendo.

---

## 4. El motor: costo de oportunidad

### La intuición

**El turno no es una lista de pedidos. Es un presupuesto de minutos.** Cada pedido que aceptas
es una compra: pagas minutos, recibes pesos.

La pregunta no es *"¿este pedido paga bien?"* sino
**"¿este pedido paga mejor de lo que normalmente rinden esos minutos?"**

### Paso 1: la tabla de valor (offline, una vez)

Corres el simulador ~300 veces con el baseline greedy. En cada momento del turno anotas
cuánto dinero **faltaba por ganar de ahí en adelante**. Promedias.

| Minutos restantes | Ganancia esperada de aquí al final |
|---|---|
| 480 (turno completo) | $900 |
| 420 | $790 |
| 300 | $560 |
| 120 | $210 |
| 60 | $95 |
| 30 | $40 |
| 0 | $0 |

Son ~32 números en un JSON. No es un modelo, no hay entrenamiento.
Versión refinada: `V[minutos_restantes][zona]` — terminar en San Pedro no vale lo mismo que
terminar en Escobedo. Sigue siendo promediar.

### Paso 2: la decisión (en vivo, microsegundos)

```
Quedan 480 min. Pedido: paga $120, cuesta 60 min.
  V(480) = $900,  V(420) = $790  ->  esos 60 min rinden $110 normalmente.
  $120 > $110  ->  ACEPTAR (ganas $10 sobre tu promedio)

Mismo momento. Pedido: paga $90, cuesta 60 min.
  $90 < $110  ->  SALTAR
```

### El flujo completo de una oferta

```mermaid
flowchart TD
    A["Llega una oferta"] --> Z{"¿alcanzo a volver<br/>al ancla antes de clase?"}
    Z -->|no| R
    Z -->|si| B{"¿zona segura<br/>a esta hora?"}
    B -->|no| R["SALTAR<br/>restricción dura, no se negocia"]
    B -->|si| C["Costo marginal en minutos:<br/>ruta CON el pedido − ruta SIN él"]
    C --> D["Precio de esos minutos:<br/>V(restante) − V(restante − costo)"]
    D --> E["Pago neto:<br/>pago × surge − gasolina − fatiga"]
    E --> F{"¿pago neto ><br/>precio del tiempo?"}
    F -->|si| G["ACEPTAR<br/>y recalcular la ruta"]
    F -->|no| H["SALTAR<br/>esos minutos rinden más esperando"]
    G --> L[("log de la decisión<br/>con todos sus términos")]
    H --> L
    R --> L
```

El log de cada decisión guarda **todos los términos**, no solo el resultado. De ahí salen las
tres cosas que importan: lo que dice la voz, el reporte contrafactual, y la respuesta cuando un
juez pregunta "¿por qué?".

### La parte bonita (va en el demo)

Quedan **30 minutos** → la tabla dice que valen **$40**. Llega el mismo pedido de $90 que
rechazó en la mañana... **y ahora lo acepta**.

> **El mismo pedido es malo a las 10 AM y bueno a las 9 PM.**

Es exactamente lo que hace un repartidor con años de experiencia: temprano es exigente porque
sabe que va a llegar algo mejor; al final agarra lo que sea. **El agente hace eso solo**, nadie
lo programó como regla — sale de la aritmética. Y cuando el juez pregunte por qué, la respuesta
es una oración: *"porque a esa hora sus minutos valían $110 y el pedido pagaba $90."*

### Nombre técnico honesto

Si un juez pregunta dónde está el ML: **evaluación Monte Carlo de la política, aprendizaje por
refuerzo sin modelo** (Sutton & Barto, cap. 5). No es marketing — construir una función de valor
promediando retornos de episodios es literalmente eso. Está implementado en forma tabular, que
es la que se puede auditar.

### Dónde NO meter ML

- Predecir demanda por zona → promedio histórico por hora del día
- Predecir tiempos de viaje → OSMnx ya los da, con factor de tráfico por hora
- Predecir surge → **lo generamos nosotros en el simulador**, no se predice lo que uno escribió

Nadie pierde este hackathon por no tener ML. Varios lo van a perder por entrenar algo que un
`statistics.mean` resolvía.

---

## 5. Batching y ruteo

La única pregunta que importa, y la que alimenta la tabla:

```python
costo_marginal = dur(mejor_ruta(paradas + nuevo)) - dur(mejor_ruta(paradas))
```

*"¿Cuántos minutos EXTRA me cuesta meter este pedido a lo que ya traigo?"*

Si ya vas al norte y el nuevo va de paso, el costo real es 12 min, no 60. Comparas **12** contra
la tabla y el pedido que se veía malo resulta excelente.

**Implementación por defecto: enumeración exacta.** Un repartidor carga 2–4 pedidos = 4–8
paradas. Con precedencia (recoger antes de entregar) son ~2,520 rutas válidas para 4 pedidos →
milisegundos, y es **óptimo exacto**, no heurístico.

```python
from itertools import permutations

def mejor_ruta(paradas, t):
    def valida(orden):
        vistos = set()
        for tipo, oid in orden:
            if tipo == "dropoff" and oid not in vistos:
                return False
            vistos.add(oid)
        return True
    return min((p for p in permutations(paradas) if valida(p)),
               key=lambda p: duracion(p, t))
```

**Rol acotado de OR-Tools:** solver de respaldo cuando la mochila pasa de 5 pedidos (>10
paradas), donde la enumeración deja de ser instantánea. Misma firma, se activa por umbral.
No se usa en ninguna otra parte del proyecto.

```python
def mejor_ruta(paradas, t):
    return _enumerar(paradas, t) if len(paradas) <= 10 else _ortools(paradas, t)
```

**Ruteo:** OSMnx/OSRM da el camino más rápido. No se decide nada ahí, solo se consulta.

---

## 6. Factores humanos

Es donde se gana **Judgment**. Trampa a evitar: si metes 15 factores, queda una sopa que nadie
puede explicar — y explicar es la mitad del puntaje.

**Regla: una sola función de utilidad, pocos términos, todos visibles en pantalla.** Si el juez
pregunta "¿por qué rechazó esa?", la UI debe poder señalar el término que mandó.

```
valor = pago × surge
      − costo_tiempo(tráfico, clima)
      − costo_gasolina
      − fatiga(horas, calor)
      − costo_oportunidad(dónde te deja)

sujeto a:   zona_riesgo(hora) < umbral                    <- RESTRICCIÓN DURA
            t_pedido + t_regreso_ancla <= t_restante − margen   <- RESTRICCIÓN DURA
```

Las dos restricciones duras son del mismo tipo y por la misma razón: **no se compran con dinero.**
Ninguna cantidad te manda a una zona insegura a las 11 PM, y ninguna cantidad te hace llegar
tarde a tu clase.

### Seguridad = restricción, no precio

Si la seguridad es un término que se resta, el agente **la vende**: con suficiente dinero entra
a cualquier lado. Como restricción dura, el agente dice:

> *"Rechacé esa de $210. No es por el dinero — a las 11 PM no te mando a esa colonia. Punto."*

Dicho en voz alta frente a un juez, eso vale más que $300 extra en el contador.

**Honestidad de datos:** no hay datos abiertos y confiables de criminalidad por colonia-hora en
Monterrey. Construimos una capa de riesgo curada (iluminación, tipo de vialidad, hora, densidad)
y **lo decimos en el pitch**: *"esta capa es sintética; en producción se alimenta de X e Y."*
Los jueces castigan el dato inventado y premian la honestidad metodológica.

### Clima y eventos

Un evento masivo **no es solo más demanda, es una trampa**: sube el pago y te deja atorado 40
minutos. El agente que sabe **posicionarse en el borde, no en el centro** es el que "piensa como
un repartidor con experiencia" — que es textualmente lo que pide el reto.

Fuentes:
- **Clima:** Open-Meteo (sin API key, histórico + forecast). Lluvia = surge real y riesgo real.
- **Eventos:** lista curada a mano de 10–15 (Arena Monterrey, Estadio BBVA, Auditorio Pabellón M,
  Parque Fundidora). Con eso basta para el demo.
- **Calor:** el reto lo menciona explícito ("40-degree heat"). Fatiga por calor acumulado es un
  término que nadie más va a tener y es puro driver-side.

---

## 7. Tracks adicionales

### Gemini — capa de juicio + reporte contrafactual

1. **Texto desestructurado del mundo real → multiplicadores de demanda.** Esto es lo que un
   heurístico no puede hacer y un LLM sí. Es el argumento del track.

   ```json
   {"zona": "Fundidora/Obispado", "ventana": "18:00-20:30",
    "demanda": 2.4, "movilidad": 0.5,
    "razon": "salida masiva bloquea Av. Madero; entrar antes de las 18:00 o no entrar"}
   ```

2. **Reporte contrafactual al cierre del turno:** *"rechacé 34 órdenes; de haberlas tomado
   habrías ganado $180 menos."* Los jueces aman el contrafactual: es la prueba de que el agente
   pensó, no de que tuvo suerte.

3. **Multimodal (bonus):** leer el screenshot del ping de la app, como lo lee el humano — así no
   asumimos una API que no existe.

### ElevenLabs — manos libres bidireccional

No es TTS decorativo. El repartidor **contesta**: *"no, esa colonia no"* → el agente aprende esa
preferencia y la mete en la función objetivo. Voz como canal de **entrada**, no solo de salida.
Streaming de baja latencia para que se sienta vivo. Que suene a norteño, no a locutor de
aeropuerto.

### TigerData (Timescale) — el store operacional

Postgres con series de tiempo. El proyecto **es** una serie de tiempo: eventos del turno,
decisiones, ganancia acumulada, surge por hora y zona. `time_bucket('15 minutes')` es
literalmente la cubeta que ya diseñamos — el fit no está forzado.

```sql
-- La tabla de valor, mantenida sola conforme corre el simulador.
CREATE MATERIALIZED VIEW valor_por_cubeta
WITH (timescaledb.continuous) AS
SELECT time_bucket('15 minutes', t_restante) AS cubeta,
       zona,
       AVG(ganancia_futura) AS valor_esperado
FROM decisiones
GROUP BY 1, 2;
```

**Base única del proyecto.** Es Postgres: ya la necesitamos para el estado del demo, no es una
pieza añadida. Corre local en Docker, latencia de milisegundos, sin cuenta ni red.
Costo: ~2h.

**Relación con Snowflake:** hacen el mismo trabajo. Montar las dos es dos bases para una sola
tarea. Si se quieren ambos tracks, el único reparto honesto es:

| | Rol |
|---|---|
| **TigerData** | Operacional / en vivo — telemetría del turno, contadores del demo, agregados incrementales |
| **Snowflake** | Batch / offline — corpus de 300+ corridas, barridos de parámetros, contrafactual |

Cuesta ~3h extra. Solo si alguien queda libre después de la hora 24.

### Vultr — deploy y control de la caja del demo

Un VM + `docker compose` (app + Timescale). **~1 hora**, y resuelve un problema que ya
teníamos: control total del entorno del demo, todo precacheado, sin depender del wifi.

Si se toma Vultr, **Cloud Run sale del stack**. Una sola caja. Y siempre con el fallback de
correr todo en localhost por si el server falla a media presentación.

No pelea con el track de Gemini (ese es por uso de la API, no por hosting).
**No usar Vultr Cloud Inference** — competiría contra nuestro propio track de Gemini.

### Snowflake — la función de valor ES una query

No es analítica de adorno: **la tabla de valor del agente es un `GROUP BY`.**

```sql
-- Esto es el cerebro del agente, calculado en Snowflake.
SELECT
    FLOOR(minutos_restantes / 15) * 15  AS cubeta,
    zona,
    AVG(ganancia_futura)                AS valor_esperado,
    COUNT(*)                            AS n
FROM decisiones
GROUP BY 1, 2
```

300 corridas × ~200 decisiones = ~60k filas; con barrido de parámetros (umbral de riesgo, peso
de fatiga, tamaño de mochila) llega a millones. Eso ya es un dataset analítico real.

**Pitch del track:** *"Snowflake no guarda nuestros logs — Snowflake calcula la política.
La función de valor del agente es una consulta."*

Usos adicionales, gratis:
- **Barrido de parámetros:** "¿qué umbral de riesgo maximiza ingreso sin cruzar zona roja?"
  → una query con `GROUP BY parametro`, no 40 corridas manuales.
- **Contrafactual del cierre:** las órdenes rechazadas y cuánto habrían rendido → query, y su
  resultado es lo que narra Gemini.
- **Marketplace:** revisar listings gratuitos de clima antes de casarse con Open-Meteo.

**Regla que no se rompe: Snowflake nunca toca el loop de decisión en vivo.** Un round-trip de
300 ms en el momento del ping arruina el demo y mete un punto de falla con el wifi.

```
Offline (antes del demo):  simulador -> Snowflake -> query -> V.json
En vivo:                   el agente lee V.json de disco
```

Es honesto y es como se hace en producción: entrenamiento en Snowflake, inferencia local.
**Costo: ~3 horas** (`write_pandas`, una query, exportar JSON). **No usar Cortex** — compite con
nuestro propio track de Gemini y diluye los dos.

### Solana — reputación portable

Ángulo honesto que resuelve un dolor real: un repartidor con 3,000 entregas en Rappi vale **cero**
el día que se cambia a DiDi — arranca de nuevo. Registro on-chain de entregas completadas
(firmado, sin PII) = un CV que el trabajador **sí posee**. Más pago instantáneo por entrega
(Solana Pay) en vez de esperar el corte semanal.

Encaja con el "fair, driver-side optimization" que el reto plantea.
**Devnet, ~150 líneas, timeboxed.** Si Solana se come el sábado, perdimos el track principal.

### Prioridad entre tracks

Perseguir los cuatro es como se pierde el principal. Orden por retorno:

| | Track | Costo | Veredicto |
|---|---|---|---|
| 1 | **Gemini** | — | Carga producto: juicio + contrafactual |
| 2 | **ElevenLabs** | — | Carga producto: es la UI |
| 3 | **Vultr** | ~1h | Tomarlo. Es el deploy que ya íbamos a hacer |
| 4 | **TigerData** | ~2h | Tomarlo. Es la base que ya íbamos a necesitar |
| 5 | **Snowflake** | ~3h | Solo si sobra gente. Duplica a TigerData |
| 6 | **Solana** | ~4h | El más pegado con cinta. Primero que se corta |

Vultr + TigerData no son add-ons: **son nuestra infraestructura**. Salen más baratos que
Snowflake + Solana juntos y se ven menos oportunistas ante un juez — huele a cazador de tracks
y eso sí resta.

---

## 8. Stack

```
Simulador + Agente   ->  Python, un solo proceso
Store                ->  TigerData / TimescaleDB (Postgres) en Docker
API / eventos vivos  ->  FastAPI + WebSocket
Front del demo       ->  HTML + MapLibre GL (vanilla JS, sin build step)
Deploy               ->  Vultr: un VM + docker compose (fallback: localhost)
```

**Laravel queda fuera.** Es nuestra zona de confort y por eso es la trampa: no hay CRUD, no hay
auth, no hay admin. Meter PHP obliga a un puente PHP↔Python para las matemáticas. Si alguien
insiste, que haga la landing del proyecto.

**Por qué NO funciones serverless:** el simulador tiene **estado y un reloj corriendo** — un
turno es una máquina de estados de 8 horas simuladas. Partirlo en funciones sin estado cuesta un
Redis, un orquestador y seis horas de debugging por un cold start que arruina el demo en vivo.
Queremos un contenedor con un proceso que recuerda. Cloud Run servía; un VM de Vultr sirve igual,
cuesta lo mismo de montar y además gana track y da control total de la caja del demo.

**Dependencias (mínimas):**

| Paquete | Para qué |
|---|---|
| `osmnx` | Grafo de Monterrey + tiempos de viaje |
| `fastapi` + `websockets` | Stream al front |
| `ortools` | Solo el fallback de ruteo con >10 paradas |
| `psycopg` | TigerData/Timescale — store operacional y agregados |
| `snowflake-connector-python[pandas]` | Opcional: batch offline si se toma también ese track |
| `google-genai` | Capa de juicio |
| `elevenlabs` | Voz bidireccional |
| `solders` / `solana-py` | Devnet |

---

## 9. El demo (aquí se gana o se pierde)

El reto dicta el formato. Obedecerlo al pie de la letra y subirle:

0. **Pantalla de configuración**: "tengo clase a las 4, estoy en el Tec, traigo moto."
   Dos horas de ventana. Esto ancla todo el demo en una historia que los jueces viven.
1. Pantalla partida: **Baseline (greedy)** vs **Nuez**. Mapa real de MTY, dos motos
   moviéndose, dos contadores corriendo.
2. Min 4 — **cierre vial en Morones Prieto**. El baseline se mete. Nuez **habla**,
   reencamina, y en pantalla aparece el porqué.
3. Min 6 — **surge en San Pedro**. El baseline se va por el dinero fácil. Nuez lo rechaza
   porque **no alcanza a volver a clase** — y lo dice con esas palabras.
4. Últimos minutos: **el baseline no llega a clase**. Nuez sí, y además en el camino de
   regreso agarra dos pedidos que le quedaban de paso.
5. Cierre: reporte contrafactual + hash de Solana con las entregas del turno.
6. **Dejar que un juez apriete el botón del seed.** *"Escoge un turno que nunca hemos visto."*
   Eso vale más que cualquier slide.

---

## 10. Tareas

**Lo primero, en la hora 1, antes que nada: el contrato de eventos.** Un JSON con la forma de
`oferta`, `decision`, `estado_repartidor` y `evento_mundo`. Sin eso los cuatro carriles se
bloquean entre sí. Se define entre todos, se congela, y cada quien mockea lo que le falta.

Hitos que no se mueven:

| Hora | Hito |
|---|---|
| **1** | Contrato de eventos congelado |
| **10** | **Baseline greedy corriendo con un número.** Sin esto no hay proyecto |
| **18** | Motor le gana al baseline en seeds no vistos |
| **24** | Gemini explicando decisiones |
| **30** | Demo completo de punta a punta |
| **33** | **Feature freeze.** Solo se ensaya y se arreglan bugs |

---

### Carril A — Simulador y datos

| # | Tarea | Listo cuando |
|---|---|---|
| A0 | ~~Grafo de MTY descargado + sanity check~~ | ✅ hecho |
| A1 | ~~Matriz de tiempos precalculada (210 puntos)~~ | ✅ `rutas.minutos()`, consulta O(1) |
| A2 | ~~Factor de tráfico por hora del día~~ | ✅ perilla en `mundo.TRAFICO_POR_HORA` |
| A3 | ~~Generador de ofertas con `seed`~~ | ✅ 94 ofertas/turno, reproducible |
| A4 | ~~Reloj de turno + estado del repartidor~~ | ✅ 5.3 ms por turno de 120 min |
| A5 | Eventos del mundo: surge por zona/hora, cierre vial, lluvia | Se disparan por config y sí afectan tiempos y pagos |
| A6 | ~~Capa de riesgo zona-hora~~ | ✅ `mundo.es_segura()` — **los números hay que ajustarlos** |

### Carril B — Motor de decisión

| # | Tarea | Listo cuando |
|---|---|---|
| B1 | ~~**Baseline greedy**~~ | ✅ **mediana $251 / 4 entregas / 1 de 50 llega tarde** |
| B2 | Ruta exacta por enumeración + costo marginal en minutos | Responde "¿cuántos minutos extra me cuesta este pedido?" |
| B3 | Restricciones duras: regreso factible al ancla + seguridad | Rechaza y dice cuál restricción mandó |
| B4 | Correr 300 turnos → log de decisiones → TigerData | Tabla `decisiones` poblada |
| B5 | Query de la tabla de valor → `V.json` | Archivo en disco, ~32 números por zona |
| B6 | Política de costo de oportunidad leyendo `V.json` | **Gana ≥20% al baseline en 50 seeds no vistos** |
| B7 | Contrafactual: qué habría pasado aceptando lo rechazado | Un número y una lista al cierre del turno |

### Carril C — Front y demo

| # | Tarea | Listo cuando |
|---|---|---|
| C1 | **Contrato de eventos WebSocket** | Congelado en la hora 1 |
| C2 | Pantalla de configuración (ventana, ancla, vehículo, margen) | Cuatro inputs, no una app |
| C3 | Mapa MapLibre con los dos agentes y sus rutas | Dos motos moviéndose sobre calles reales |
| C4 | Contadores + panel de decisión con los términos visibles | Al señalar una decisión se ve por qué |
| C5 | Botón de seed del juez + botón de evento (surge / cierre) | El juez puede apretarlos él mismo |
| C6 | Branding Nuez: nombre, SVG, paleta, prompt de personalidad | **3h máximo, en paralelo** |

### Carril D — Integraciones

| # | Tarea | Listo cuando |
|---|---|---|
| D1 | `docker compose`: app + TigerData/Timescale | `docker compose up` y corre |
| D2 | Gemini: clima + eventos masivos → JSON de pesos y multiplicadores | El motor consume el JSON y cambia de conducta |
| D3 | Gemini: narración de decisiones + reporte contrafactual | Texto listo para la voz |
| D4 | ElevenLabs TTS streaming con la personalidad de Nuez | Habla mientras el turno corre, sin cortar |
| D5 | ElevenLabs STT: el repartidor contesta y ajusta preferencias | "esa colonia no" cambia la función objetivo |
| D6 | Deploy en Vultr | URL pública + fallback localhost probado |
| D7 | Solana devnet: reputación portable | **Recortable.** Primero que se corta |

---

## 11. Plan de 36h

| Bloque | Qué |
|---|---|
| 0–6h | Simulador: grafo OSMnx de MTY, stream de órdenes con seed, surge, reloj de turno |
| 6–10h | Baseline greedy + métrica. **Ya hay un número que batir.** |
| 10–18h | Tabla de valor + costo de oportunidad + batching. Aquí nacen los Results. (Logs a Snowflake y la query de la tabla de valor caen aquí, ~3h del bloque.) |
| 18–24h | Capa Gemini: eventos + explicaciones estructuradas |
| 24–30h | Voz ElevenLabs + UI side-by-side |
| 30–33h | Solana devnet (timeboxed; se corta sin piedad) |
| 33–36h | Ensayar el pitch **ocho veces**. En serio. |

Reparto sugerido (4 personas): simulador+grafo / motor de decisión / front+demo (es más trabajo
del que parece — **el demo es el producto**) / Gemini+voz+Solana.

**Branding de Nuez en paralelo, 3h máximo:** nombre, SVG de la ardilla, paleta, prompt de
personalidad de la voz. Lo hace quien esté en el front, entre tareas. No es un bloque del plan.

La pantalla de configuración (ventana, ancla, vehículo, margen) es parte del bloque de front:
son cuatro inputs, no una app.

---

## 12. Trampas que hunden este reto

- **LLM calculando dinero** → alucina, pierde contra greedy. Motor determinista; LLM solo explica y ajusta pesos.
- **Simulador bonito, agente mediocre** → el 60% de los equipos se queda sin tiempo para el agente. **Baseline corriendo en la hora 10, sin excepciones.**
- **Solana como NFT decorativo** → se nota y resta credibilidad.
- **Sin baseline visible** → "ganó $840" no significa nada para un juez sin comparación.
- **OSRM/OSMnx en vivo durante el demo** → precachear grafo, matrices de tiempo, clima y respuestas de Gemini del guion. El wifi del hackathon falla exactamente durante el pitch, siempre.

---

## 13. Convenciones para trabajar aquí

- **Python 3.11+.** Simulador y agente en un solo proceso, sin servicios extra.
- **Todo turno es reproducible por `seed`.** Si un resultado no se reproduce con su seed, es un bug.
- **El motor no llama a red.** Ninguna decisión de dinero depende de una API externa en vivo.
- **Cada decisión se registra** con sus términos (pago, costo de tiempo, costo de oportunidad,
  restricciones evaluadas). Ese log alimenta el contrafactual y lo que dice la voz.
- **Precachear a disco** todo lo externo: grafo, matrices, clima, eventos, respuestas de Gemini.
- **Antes de agregar una dependencia:** ¿lo resuelve la stdlib en menos de 20 líneas? Entonces stdlib.
- Comentarios y docs en español; nombres de código en inglés.
