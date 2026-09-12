# Front: qué ya está y qué sigue

Para quien trabaja en `frontend/`. Actualizado el **12 de septiembre**, después del PR de
`explain_decision` + capa de Gemini.

El brief anterior ([`front-turno-grabado.md`](../front-turno-grabado.md)) está **casi todo hecho**.
Este documento es el delta: qué quedó listo, qué te dio de nuevo el backend, y qué falta en orden
de importancia.

---

## 1. Lo que ya funciona

`SimView.tsx` ya reproduce el turno grabado. Concretamente:

| | |
|---|---|
| Mapa a pantalla completa con las calles reales | ✅ |
| Las dos motos corriendo el mismo turno | ✅ |
| Timeline: play/pausa, ±1 min, scrubber, velocidad 1x–8x | ✅ |
| Selector de turnos con su delta | ✅ |
| Contadores Greedy vs Nuez, con resumen final | ✅ `sim/Counters.tsx` |
| Panel de decisiones con chip de restricción | ✅ `sim/Decisions.tsx` |
| Chip rosa = seguridad, ámbar = dinero | ✅ `lib/decision-text.ts` |

Eso ya es el demo que pide el reto. Lo que sigue es lo que sube **Judgment**, que es la mitad del
puntaje y donde todavía estamos cortos.

---

## 2. Lo nuevo que te dio el backend

### 2a. Los turnos grabados tienen campos nuevos (ya regenerados)

`data/export_turno.py` se volvió a correr, así que los JSON en `frontend/public/` ya traen cinco
términos que **nada en `src/` lee todavía**:

```json
"terminos": {
  "pago_neto": 43.8,
  "minutos": 20.0,
  "precio_tiempo": 59.7,
  "ventaja": -15.9,
  "parado": 0.0,

  "margen_exigido": 1.0,          // ← nuevo: cuánto exige la estrategia vigente
  "multiplicador_zona": 1.0,      // ← nuevo: 1.0 normal; >1 si Gemini encareció esa zona
  "minutos_ruta_actual": 45.6,    // ← nuevo: lo que ya trae encolado
  "minutos_para_terminar": 103.9, // ← nuevo: entregar todo Y volver al ancla
  "minutos_de_turno": 107         // ← nuevo: lo que queda de turno
}
```

Los últimos tres son **la cuenta del fin de turno**, y son oro para el panel. Cuando la restricción
es `shift_end_infeasible`, ahora puedes enseñar por qué con números en vez de una etiqueta:

> *Aceptarlo son 104 min y solo quedan 107. No alcanza.*

Eso responde en pantalla una de las preguntas literales del juez: *"¿por qué saltaste esa orden?"*.

### 2b. El backend ya habla, en vivo

Todo en `http://127.0.0.1:8000` (ya hay tres archivos que usan esa base; conviene unificarla en
`API_URL` de `voice/nuez.ts`, que además respeta `VITE_API_URL`).

| Endpoint | Qué da |
|---|---|
| `GET /zones` | id, nombre, lat, lon de las 14 zonas |
| `POST /shift/start` | arranca un turno |
| `POST /decide` | decide una oferta: `decision`, `reason`, `binding_constraint`, `latency_ms`, `tier`, `degraded` |
| `GET /explain/{order_id}` | **la explicación completa** de una decisión ya tomada |
| `GET /shift/status` | minuto, pedidos en vuelo, y **`degraded`** |
| `POST /shift/end` | cierra y resume |

El que más vale la pena es `/explain/{order_id}`. Devuelve `inputs` (posición, tiempo restante,
límites del vehículo, estrategia activa) y `alternatives_considered`: qué más se evaluó y por qué
perdió. En un rechazo por seguridad trae la línea que queremos que el juez vea:

> *Pay math alone says ACCEPT, but safety constraints cannot be bought with money.*

**Ojo:** eso vive en el backend en vivo, no en los JSON grabados. El replay grabado sigue siendo el
seguro contra el wifi; lo de abajo es para cuando el backend esté corriendo.

### 2c. La capa de Gemini

Gemini corre en un hilo aparte y **nunca decide un pedido**: solo mueve tres perillas que el motor
lee entre pings. De ahí salen dos cosas para pantalla:

- **La nota de Gemini**, una frase en español lista para mostrar y para la voz. Ejemplo real:
  *"Lluvia en Centro, aplicamos multiplicador para compensar."*
- **`degraded: true`** cuando el modelo no responde. Los jueces van a invalidar la credencial a
  media corrida y **tiene que verse en pantalla**. Un fallback silencioso es crédito parcial.

---

## 3. Lo que falta, en orden

### 🔴 1. Que se vea una restricción activarse

El spec es explícito:

> *"A constraint that exists in code but is never demonstrated triggering scores low. Rehearse at
> least two as live demo moments."*

Hoy las restricciones solo salen como un chip en la lista, que se pierde entre decisiones. Y sí se
están disparando: en los turnos grabados, por turno,

| seed | `heat_rule` | `shift_end_infeasible` | `vehicle_capacity` |
|---|---|---|---|
| 2000 | 23 | 32 | 32 |
| 2001 | 18 | 3 | 66 |
| 2002 | 17 | 65 | 5 |

**La `heat_rule` se dispara 17–23 veces por turno y nadie la ve.** Es la regla de que entre 12 y 4
de la tarde no se manejan más de 90 minutos seguidos — muy fácil de contar y muy vistosa.

Lo que haría falta: cuando una decisión se salta por seguridad, que el mapa o el panel **lo
anuncien**, no que aparezca una línea más en una lista. Un banner de dos segundos, el chip
pulsando, el marcador de la moto cambiando de color. Algo que el juez no pueda perderse.

### 🔴 2. La distribución, al lado del turno

Este es un problema de honestidad y el juez lo va a atacar: *"¿por qué debería creerle a ese
número?"*.

La varianza por turno es enorme. Los tres turnos grabados:

```
seed 2000    greedy $ 90   nuez $267    +198%
seed 2001    greedy $133   nuez $313    +135%
seed 2002    greedy $235   nuez $173     −26%
```

**Un turno animado no es evidencia.** Si enseñamos el 2000 parecemos tramposos; si cae el 2002
parecemos malos. Lo correcto es el turno bonito **al lado** de la distribución de 200 turnos, donde
el número real es **+29.2%, ganando en 150 de 200**.

Ya hay dos imágenes generadas en `docs/`: `comparacion_algoritmos.png` y
`distribucion_ganancias.png`. Lo más barato es meterlas como un panel; lo mejor sería un histograma
en vivo, pero la imagen ya resuelve el 80%.

### 🟡 3. El indicador de modo degradado

Un badge chiquito, arriba: **"Gemini: activo"** / **"Gemini: caído — usando última estrategia"**.
Se lee de `GET /shift/status` → `degraded`, o del campo `degraded` que viene en cada `/decide`.

Es literalmente un momento del guion del demo: el juez borra la credencial, el badge se pone
ámbar, **y el turno no se detiene**. Sin el badge, ese punto no existe.

### 🟡 4. La cuenta del fin de turno en el detalle

Con los campos de §2a, cuando `restriccion === 'shift_end_infeasible'`, el detalle expandido puede
decir:

> *Entregarlo y volver son 104 min. Quedan 107 de turno. No alcanza.*

Son tres números que ya están en el JSON. Es el cambio más barato de toda esta lista y responde
una pregunta que el juez hace seguro.

### 🟡 5. La nota de Gemini en pantalla

Una línea, donde se vea, con lo último que dijo la capa de estrategia. Viene de los eventos
`strategy_update` del JSONL en vivo, o de `/shift/status`.

Es el único lugar del demo donde se nota que hay un LLM — y conviene que se note **fuera** de la
ventana de decisión, que es justo nuestro argumento técnico.

### 🟢 6. Limpieza pendiente

- **La UI todavía usa emoji como ícono** (🤖 🧠 ⚔️ 📍 👁️). `docs/ui-style-guide.md` lo prohíbe y
  `agents.md` lo marca como obligatorio. Los íconos están en `src/ui/icons.tsx`.
- **Tres archivos declaran la URL del backend por su cuenta** (`map/layers.ts`, `map/route.ts`,
  `voice/nuez.ts`). Unificar en `API_URL`, que ya respeta `VITE_API_URL`.
- **Medir la RAM otra vez.** El dato de ~3 GB es anterior a la carga de calles por zona. Si sigue
  alto, la palanca más barata es `INCLUIR_LOCALES = False` en `data/export_geojson.py`.

---

## 4. Reglas de la casa

- **`src/contract.ts` se genera, no se edita a mano.** Sale de `contrato.py` con
  `python scripts/contract_codegen.py --write`. El job "Contract Check" del CI falla si no coincide.
- **`docs/ui-style-guide.md` antes de tocar nada.** Colores con significado: esmeralda solo dinero,
  ámbar solo urgencia, rosa solo seguridad.
- **Ningún archivo pasa de 500 líneas** (`python scripts/max_lines.py .`). `panel.css` ya se partió
  dos veces por esto; si un CSS crece, se parte por pantalla, no por la mitad.
- **Nada se mergea con CI en rojo.** Antes de subir, en `frontend/`: `npm run check`.
- **Main ha llegado en rojo dos veces seguidas.** Si tu PR falla el CI, revisa primero si el error
  es tuyo o venía en el merge — los últimos dos traían tests rotos que no eran de quien abrió el PR.

---

## 5. Si tuviera que escoger dos

**La §3.1 (que se vea la restricción) y la §3.2 (la distribución).** Las dos atacan directo el
criterio de Judgment, que es la mitad del puntaje y donde estamos más flojos. Las otras cuatro son
mejoras; esas dos son puntos.
