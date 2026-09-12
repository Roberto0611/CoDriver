# Front: reproducir el turno grabado

Brief para quien trabaja en el mapa (`frontend/`). Se puede hacer **solo con el front**, sin esperar
al backend: los datos ya están grabados en `frontend/public/`.

---

## El problema, en una línea

El mapa todavía **no muestra el turno**. `App.tsx` hoy hace una "carrera de rutas": eliges origen
y destino, y compara tiempo y km de tres rutas (Classic, Nuez AI, Oracle). Ese no es el demo que
pide el reto: *dos agentes corren el mismo turno lado a lado, con un contador de ganancias
corriendo*.

Los turnos grabados ya existen (`turno_greedy_<seed>.json`, `turno_nuez_<seed>.json`) y **ningún
archivo de `src/` los lee**.

---

## Antes de tocar `frontend/`

- **Leer [`docs/ui-style-guide.md`](ui-style-guide.md).** Es obligatorio según `agents.md`.
- **Nada de emoji como ícono** (la guía lo prohíbe). La UI actual usa 🤖 🧠 ⚔️ 📍 👁️: no copiarlos
  a los componentes nuevos. Íconos en `src/ui/icons.tsx`.
- **El layout se queda:** mapa a pantalla completa, timeline arriba al centro y panel a la
  izquierda. Los contadores y el panel de decisión van en ese panel izquierdo, en lugar de las
  tarjetas de la carrera de rutas.
- **Colores con significado** (tokens en `src/index.css` / `src/styles/tokens.css`):
  - Esmeralda: solo dinero y turno activo.
  - Ámbar: solo urgencia.
  - Índigo: solo el algoritmo (ruta, decisión).
  - Ciruela: la marca.
- **UI en inglés.** El código y los comentarios, en español.
- **Toda función pura nueva trae su test** en `src/**/*.test.ts`.
- **Antes de subir:** `npm run check` en `frontend/`.
- **No mergear con CI en rojo.**

---

## El formato de los JSON grabados

Por cada seed hay **dos archivos con el mismo stream de ofertas**, uno por política. Mismo seed es
lo que hace honesta la pantalla partida: los dos enfrentaron los mismos pedidos.

```
frontend/public/turno_greedy_42.json
frontend/public/turno_nuez_42.json
frontend/public/turnos.json      <- índice de los seeds grabados
frontend/public/puntos.json      <- los 210 puntos del mapa (GeoJSON)
```

Los genera `data/export_turno.py`. Los tipos de `Oferta`, `Decision` y `ConfigTurno` ya están en
`src/contract.ts` (generado, no se edita a mano).

### Estructura de `turno_<politica>_<seed>.json`

```jsonc
{
  "meta": {
    "politica": "nuez",          // "greedy" | "nuez"
    "seed": 42,
    "ganado": 317.58,            // total final del turno, en MXN
    "entregas": 6,
    "rechazos": 83,
    "llego_tarde": false,
    "ofertas_totales": 89
  },
  "config": {                    // = ConfigTurno de contract.ts
    "duracion_min": 120,
    "ancla": { "nombre": "Tec", "lat": 25.6476, "lon": -100.2898 },
    "margen_min": 10,
    "vehiculo": "moto",
    "seed": 42,
    "hora_inicio": 14            // el minuto t=0 es las 14:00
  },
  "tramos": [                    // cada viaje de la moto entre dos puntos
    { "t_salida": 0, "t_llegada": 8.09, "desde": 60, "hasta": 44, "clave": "60-44" }
  ],
  "geometria": {                 // clave del tramo -> polilínea sobre calles reales
    "60-44": [[-100.28981, 25.6476], [-100.29001, 25.64792]]   // [lon, lat]
  },
  "frames": [                    // UNO POR MINUTO: frames[t] y ya
    {
      "t": 0,
      "ofertas": [ /* Oferta[] que aparecen en este minuto */ ],
      "decisiones": [ /* Decision[] tomadas en este minuto */ ],
      "llegada": { "punto": 44, "tipo": "pickup" },   // o null
      "cobro": 0.0,              // pesos cobrados en este minuto (sube al ENTREGAR)
      "ganado": 0.0              // acumulado hasta este minuto: EL CONTADOR
    }
  ]
}
```

### Una `Decision` real

```json
{
  "t": 3,
  "oferta_id": "o_002",
  "accion": "saltar",
  "terminos": {
    "pago_neto": 30.6, "minutos": 21.8, "por_minuto": 1.4,
    "precio_tiempo": 51.6, "ventaja": -21.0, "parado": 0.0
  },
  "razon": "Esos 22 minutos rinden $52 normalmente, y este paga $31.",
  "restriccion": "reservation_wage"
}
```

| Campo de `terminos` | Qué significa | Cómo mostrarlo |
|---|---|---|
| `pago_neto` | Lo que paga, menos gasolina | "Pays MXN 31" |
| `minutos` | Minutos extra que cuesta meterlo a la ruta | "22 min" |
| `precio_tiempo` | Lo que esos minutos rinden normalmente (costo de oportunidad) | "Those minutes usually earn MXN 52" |
| `ventaja` | `pago_neto − precio_tiempo` | Verde si > 0, neutro si < 0 |
| `parado` | 1 si la moto estaba sin ruta | Contexto, opcional |

`restriccion` es `null` o una de las seis:

| Valor | Qué fue |
|---|---|
| `flagged_zone_night` | Zona marcada después de las 22:00 |
| `mandatory_break` | Descanso obligatorio tras 4 h |
| `heat_rule` | Límite de 90 min continuos entre 12 y 16 h |
| `shift_end_infeasible` | No alcanza a terminar antes del fin del turno |
| `vehicle_capacity` | No cabe en el vehículo |
| `reservation_wage` | No paga lo que valen sus minutos (**la única que es dinero, no seguridad**) |

> **Ojo:** en los JSON grabados la `razon` viene **en español** y la UI va en inglés. Opciones:
> armar el texto inglés en el front a partir de `terminos` y `restriccion` (recomendado: son pocas
> plantillas), o pedir que se regrabe con la razón en inglés.

---

## Qué implementar, en orden

### 1. Reproducir el turno en el mapa (C3), lo más urgente

- **Cargar los dos archivos** del mismo seed con `fetch('/turno_greedy_42.json')` y
  `fetch('/turno_nuez_42.json')`.
- **Posición de la moto en el minuto `t`:**
  - Buscar el tramo con `t_salida <= t < t_llegada` e interpolar sobre `geometria[clave]` según
    `(t - t_salida) / (t_llegada - t_salida)`. Interpolar por distancia acumulada, no por índice
    de vértice, o la moto "brinca".
  - Si no hay tramo activo, la moto está parada en el `hasta` del último tramo terminado. Las
    coordenadas de un punto `i` salen de `puntos.json` (`features[i].geometry.coordinates`).
  - Antes del primer tramo, está en `config.ancla`.
- **Dos marcadores** (greedy y Nuez) y, opcional, la estela de la ruta recorrida. La ruta de Nuez
  va en índigo.
- **Conectar el timeline que ya existe** (play, −1, +1, slider) a `t`:
  - Hoy el slider está fijo de 14:00 a 16:00 (840–960). Debe salir de `config.hora_inicio * 60`
    hasta `+ config.duracion_min`.
  - La hora mostrada es `hora_inicio*60 + t`.
  - Para el demo, 1 min simulado cada 5 s es muy lento: 120 min tardarían 10 min reales.
    Algo como 1 min cada 0.5 s o velocidad ajustable.
- **Tests** para las funciones puras: posición en el minuto `t` (interpolación, parado entre
  tramos, antes del primero) y `hora_inicio + t → "HH:MM"`.

### 2. Contadores lado a lado (C4, primera mitad)

- **Por agente:** ganancia `frames[t].ganado` (esmeralda, cifras tabulares `.num`), entregas
  hasta `t` (contar `frames[0..t]` con `cobro > 0`) y ofertas saltadas.
- **Diferencia en vivo:** *"Nuez +MXN 58"*.
- **Al terminar**, el resumen de `meta` de cada uno.
- Esto **reemplaza** las tarjetas de minutos y km de la carrera de rutas.

### 3. Panel de decisión (#8, hoy Judgment está en cero del lado visual)

- **Lista de decisiones de Nuez** conforme ocurren (`frames[t].decisiones`, lo más reciente
  arriba): aceptar o saltar, la razón corta y un chip con la `restriccion` si la hay.
- **Al hacer clic en una decisión**, se ven sus `terminos` como una cuenta legible:
  *"Pays MXN 31 · 22 min · those minutes usually earn MXN 52 · edge −MXN 21"*.
- **Distinguir a simple vista** una negativa por **seguridad** (las cinco restricciones) de una
  por **dinero** (`reservation_wage`). Es lo que el juez quiere ver.
- **Opcional:** al pasar el cursor, marcar en el mapa el pickup y el dropoff de esa oferta
  (`frames[t].ofertas`, buscando por `oferta_id`).
- **Más adelante:** cuando el backend esté en vivo, el mismo panel puede pedir
  `GET /explain/{order_id}`, que ya existe y trae `inputs` + `alternatives_considered`. Por ahora
  bastan los `terminos` del JSON.

### 4. Selector de seed

- Leer `turnos.json` (`{ "turnos": [{ "seed", "delta_pct", "greedy": meta, "nuez": meta }] }`)
  y listar los seeds grabados para que el juez escoja uno.

---

## Pendientes chicos que se notan

- **Seeds del demo.** Los turnos grabados hoy son 1, 7 y 42, que son **de TUNEO**. Para el demo
  hay que usar seeds de **REPORTE** (2000 en adelante):

  ```bash
  python data/export_turno.py 1 2000 2001 2002
  ```

  - Incluir el `1` en la lista: `turno_greedy_1.json` es el golden de un test de regresión y
    `turnos.json` se reescribe solo con los seeds que se pasen.
  - Revisar los resultados y escoger seeds que se vean bien, sin esconder que la varianza es
    grande (ver abajo).
- **Varianza.** Un turno animado no es evidencia (desviación ~56 puntos porcentuales por turno).
  Hay que mostrar al lado la distribución de muchos turnos. Ya hay una imagen en
  `docs/distribucion_ganancias.png`.
- **Memoria.** `agents.md` reporta que el front usa ~3 GB de RAM. Esa medición es anterior a la
  carga de calles por zona (`src/map/roads.ts`): el patrón `_roadFeatures.concat` que citaba ya no
  aparece en `src/`. **Medir de nuevo antes de invertirle tiempo.** Si sigue alto, la palanca más
  barata es `INCLUIR_LOCALES = False` en `data/export_geojson.py` y regenerar.

---

## Lo que conviene esperar

| Qué | Por qué esperar |
|---|---|
| Botón de evento (surge / cierre, C5) | Depende del #7 (shocks en vivo), que aún no existe en el simulador |
| Voz de Nuez leyendo cada decisión | El helper `src/voice/nuez.ts` ya existe; se conecta cuando el panel esté listo. La primera `say()` debe salir de un click (autoplay) |
| Datos en vivo por WebSocket | El formato grabado es el mismo que viajará por el WebSocket, así que lo que se construya contra los JSON no cambia |
