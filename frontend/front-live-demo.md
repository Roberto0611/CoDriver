# Modo Live Demo: trabajo pendiente

## Objetivo

Agregar un modo **Live demo** separado del replay actual. En este modo, Greedy y
Nuez reciben exactamente el mismo flujo de ofertas de un seed nuevo, sus estados
evolucionan en tiempo real y un juez puede inyectar un cierre vial o surge a mitad
del turno. La pantalla debe enseñar la reacción real, no una animación pregrabada.

El entregable del reto es justamente esta corrida: dos agentes lado a lado, el mismo
turno fresco, contadores que cambian y una disrupción a mitad de la demostración.

## Estado actual (importante)

> Esta sección describe lo que había **antes** del demo live. Ya se implementó: `/sim`
> no tiene botones de shock y el demo vive en `/live`. Ver
> [Cómo correr el demo live](#cómo-correr-el-demo-live).

`frontend/src/SimView.tsx` es un **reproductor de turnos grabados**. Carga
`/turnos.json` y los archivos JSON exportados; mapa, rutas, decisiones y contadores
no se calculan en el navegador ni llegan desde una simulación activa.

Hay dos botones visibles:

- `Cerrar Constitución`
- `Empezar lluvia`

Actualmente solo hacen `POST /shock`. No inician un turno ni modifican los JSON que
está reproduciendo la vista. Si no existe un turno iniciado en el backend,
`POST /shock` responde `409 no hay turno activo`; si sí existiera, el replay de todos
modos seguiría mostrando su historia fija. Por tanto, esos botones **no son todavía
un demo live funcional** y no deben presentarse como tal.

El backend sí tiene piezas útiles:

- `POST /shift/start`, `POST /decide`, `POST /shock`, `POST /shift/end`.
- `shocks.py` aplica la física determinista de cierre, lluvia, surge y delay.
- `backendruta/courier_api.py` registra los eventos en JSONL.

Pero `CourierService` mantiene una sola `state`; no alcanza para correr Greedy y
Nuez aislados y simultáneamente desde una sola sesión HTTP.

## Decisión de producto/UI

Mantener dos modos explícitos:

| Modo                | Fuente de verdad            | Controles                                                      |
| ------------------- | --------------------------- | -------------------------------------------------------------- |
| **Recorded replay** | JSON ya exportado           | play, pausa, velocidad, selector de seed. Sin inyectar shocks. |
| **Live demo**       | simulación viva del backend | iniciar seed, play/pause, cierre vial y surge.                 |

Para el pitch basta con **Closure** y **Surge**. No priorizar lluvia: es menos visual y
el reto pide surge _o_ cierre. Si se deja lluvia, debe funcionar igual que los otros,
no ser un botón decorativo.

## Arquitectura recomendada

No intentar convertir `SimView` en un cliente que llame directamente `/decide` para
cada política. El servidor debe ser dueño del reloj, del stream de ofertas y de los
dos estados. Eso garantiza que ambos agentes vean la misma oferta en el mismo minuto
y evita lógica de negocio duplicada en React.

Crear un coordinador de demo live, por ejemplo `backendruta/live_demo.py`, que tenga:

```text
LiveDemoSession
  config y seed
  minuto actual
  stream de ofertas generado una sola vez
  estado / resultado de Greedy
  estado / resultado de Nuez
  shocks activos (la misma foto inmutable para los dos)
  eventos para el frontend y JSONL del turno
```

Puede reutilizar el motor de `sim.py` y las políticas existentes (`politica_greedy` y
`politica_nuez`). No copiar ni reescribir las reglas de seguridad, ruteo o shocks.

### API mínima propuesta

Prefijar estas rutas con `/live` para no romper el protocolo oficial `/decide`:

```text
POST /live/start
  body: { seed, duracion_min, hora_inicio, vehiculo, ancla, margen_min }
  response: snapshot inicial + session_id

POST /live/tick
  body: { session_id, minutes: 1 }
  response: snapshot después de avanzar

POST /live/shock
  body: { session_id, shock_type, zone?, duration_min?, multiplier?, road?, order_id?, slip_min? }
  response: shock registrado + snapshot

GET /live/status/{session_id}
  response: snapshot actual

POST /live/end
  body: { session_id }
  response: resultado final + ruta del JSONL

GET /live/counterfactual/{session_id}
  response: el contrafactual de Nuez sobre el turno ya terminado, con sus shocks
  (409 si sigue corriendo; mismo esquema que contrafactual_<seed>.json)
```

Para el primer corte, el navegador puede hacer `tick` cada 500 ms (1 minuto simulado
por tick), igual que el reproductor. WebSockets no son necesarios para el demo y
aumentarían el riesgo.

### Contrato de `snapshot`

Definir un tipo compartido/documentado. Debe incluir solo lo necesario para pintar:

```json
{
  "session_id": "...",
  "minute": 37,
  "status": "running",
  "active_shocks": [{ "type": "closure", "zone": 2, "ends_at_min": 77 }],
  "offers_this_tick": [{ "order_id": "...", "pickup": 1, "dropoff": 2, "pay_mxn": 48 }],
  "greedy": {
    "position": 12,
    "earnings_mxn": 84,
    "deliveries": 2,
    "skipped": 4,
    "route": [],
    "last_decision": { "order_id": "...", "decision": "ACCEPT", "reason": "..." }
  },
  "nuez": {
    "position": 8,
    "earnings_mxn": 109,
    "deliveries": 3,
    "skipped": 3,
    "route": [],
    "last_decision": {
      "order_id": "...",
      "decision": "SKIP",
      "reason": "...",
      "binding_constraint": null
    }
  }
}
```

Usar coordenadas o IDs de punto compatibles con el mapa actual. La razón de Nuez debe
llegar completa: no volver a sintetizarla y perder la restricción que mandó.

## Plan de implementación

### 1. Backend: sesión doble y determinista

- [x] Leer `sim.py` y extraer/reutilizar el avance de un minuto sin alterar el
      resultado de `simular()` ni los benchmarks de `comparar.py`.
- [x] Crear `LiveDemoSession` con un estado independiente para cada política.
- [x] Generar las ofertas una sola vez a partir del seed; entregar la misma instancia
      lógica/oferta equivalente a Greedy y Nuez en el mismo minuto.
- [x] Al inyectar un shock, aplicarlo a los dos agentes desde el mismo minuto. La
      física siempre debe usar `shocks.py`; Gemini no decide si un cierre ralentiza
      una calle.
- [x] Escribir `shock`, ofertas, decisiones y resultados en JSONL para que el turno
      pueda auditarse y eventualmente exportarse como replay.
- [x] Garantizar que una sesión nueva no comparte rutas, dinero, ofertas aceptadas ni
      shocks con una sesión anterior.

### 2. Backend: endpoints y pruebas

- [x] Implementar las rutas `/live/*` anteriores en un router separado.
- [x] Validar que no se pueda hacer `tick` después de terminar ni inyectar shock sin
      sesión activa.
- [x] Agregar tests que fijen:
  - mismo seed + mismos ticks => mismo snapshot/decisiones;
  - Greedy y Nuez ven exactamente las mismas ofertas;
  - closure cambia los tiempos de ruta de ambos;
  - surge cambia el pago de las ofertas afectadas;
  - un shock aparece en el JSONL;
  - el flujo normal sin shock no modifica los resultados existentes de `comparar.py`.

### 3. Frontend: separar replay de live

- [x] Conservar `/sim` como **Recorded replay**. Quitar de esta vista los botones que
      llaman `/shock`, o dejarlos deshabilitados con una explicación; nunca deben
      aparentar que alteran el JSON grabado.
- [x] Crear una ruta, por ejemplo `/live`, con `LiveSimView.tsx`.
- [x] Reusar, cuando sea posible, mapa, marcadores, `Counters`, `Decisions` y estilos
      de `SimView.tsx`; no duplicar componentes visuales.
- [x] Agregar formulario mínimo de inicio: seed (por defecto 2000 o aleatorio),
      vehículo, duración, ancla y botón **Start live shift**.
- [x] Mientras corre, llamar `/live/tick` según la velocidad elegida y pintar el
      `snapshot` recibido. El backend es la fuente de verdad.
- [x] Habilitar solo con sesión activa:
  - **Close Constitución** (zone 2, 40 min, road `Constitución`) → quedó en zona 0,
    ver [Desviaciones decididas](#desviaciones-decididas);
  - **Trigger surge** (zona visible, multiplicador y duración fijos para el demo).
- [x] Al recibir el resultado, mostrar un banner persistente con el shock, cuándo
      expira y el cambio que provocó. No ocultarlo automáticamente a los 10 segundos.
- [x] Mostrar en ambas tarjetas la decisión inmediatamente posterior al shock y la
      razón de Nuez. Ese es el momento que se va a narrar durante el pitch.
- [x] Manejar errores de red con mensaje visible y detener el autoplay; no limitarse
      a `console.error`.

### 4. Voz (solo después de que live funcione)

- [x] Al recibir una decisión nueva de Nuez, llamar `say(reason)` de
      `frontend/src/voice/nuez.ts` si la decisión merece ser narrada
      (`voice/liveNarration.ts` decide qué, `voice/useLiveNarration.ts` lo entrega).
- [x] No hablar cada oferta: como mínimo, hablar rechazos por reglas duras (seguridad y
      vehículo lleno) y la primera decisión relevante tras un shock.
- [x] Usar `prefetch()` solo para el replay grabado; un turno live no puede conocer
      de antemano todas sus frases.

## Definición de terminado

Una persona que no escribió el código puede hacer esto sin modificar archivos:

1. Abrir `/live` y escoger un seed que no se haya mostrado antes.
2. Pulsar **Start live shift**; ambos agentes arrancan en $0 y avanzan a la vez.
3. Pulsar **Close Constitución** cerca del minuto 30.
4. Ver banner del cierre, rutas/tiempos afectados y la siguiente explicación de Nuez.
5. Terminar el turno; ver ganancias y entregas de ambos.
6. Abrir el JSONL producido y encontrar el evento `shock` y las decisiones posteriores.
7. Repetir con el mismo seed y el mismo minuto de shock; obtener las mismas decisiones.

## Desviaciones decididas

- **Cierre en zona 0 (Centro) + "Constitución", no zona 2.** La zona 2 es Valle; JP
  eligió exactitud geográfica. Como no todo seed pasa por Centro, hay un seed ensayado.
- **Surge: Tec (zona 4), ×1.8, 30 min.** Fijo en `DEMO_SHOCKS`
  (`frontend/src/lib/live.ts`) para que el demo sea un click, en la zona del ancla.
- **Sin botón de lluvia.** El backend acepta `rain` en `/live/shock`; la UI muestra cierre,
  surge y restaurante atrasado, que es lo que pide el reto.
- **Restaurante atrasado: +15 min al siguiente pedido por aparecer.** Fijo en
  `DEMO_SHOCKS.delay`; el backend elige el pedido (el primero con `t_aparece` ≥ minuto actual)
  y el retraso dura hasta el final del turno. El botón es solo icono (reloj, ámbar como el surge):
  con texto la píldora se mete bajo el logo a 1280×800. No se resalta en el mapa; el mapa vuela a
  la zona del restaurante. El banner nombra el pedido y enseña la decisión de cada agente sobre
  **ese** pedido, no la primera decisión después del shock.
- **Tramos sobre calles reales.** Se usa el grafo que `main.py` ya carga
  (`live_api.registry.usar_grafo(G)`), sin cargarlo dos veces. Sin
  `data/mty_graph.pkl` los tramos caen a línea recta; las decisiones no cambian.
- **JSONL live** usa los nombres oficiales del esquema; se valida con
  `courier/validate_format (2).py`. Es para auditar el turno live; el replay del
  protocolo §6 usa la bitácora de `/decide` (ver [La bitácora JSONL](#la-bitácora-jsonl)).
- **Contrafactual aparte de End.** `GET /live/counterfactual/{session_id}` re-simula el turno
  con los mismos shocks, una corrida por salto por dinero (`contrafactual.py`). 2 h tarda
  ~0.3 s, pero 8 h tarda ~4 s: dentro de `/live/end` dejaría el botón colgado. Se calcula al
  pedirlo, sin el candado del registro, y se guarda por sesión. El front lo pide al terminar y
  lo pinta con el mismo bloque que `/sim` (`CounterfactualReport`), bajo el resumen final.

## Cómo correr el demo live

Requisitos: dependencias instaladas como en el `README.md` (`pip install` y
`npm install` en `frontend`). `data/mty_graph.pkl` no está en git; sin él todo funciona,
pero los tramos se dibujan en línea recta.

**1. Backend**, desde la raíz del repo (ahí se resuelve `cache/live/`):

```bash
python -m uvicorn backendruta.main:app --host 127.0.0.1 --port 8000
```

**2. Frontend.** Llama a `http://127.0.0.1:8000` por defecto (`frontend/src/lib/api.ts`):

```bash
npm --prefix frontend run dev
```

Si la API corre en otro host o puerto:

```bash
VITE_API_URL=http://127.0.0.1:9000 npm --prefix frontend run dev
```

**3.** Abrir `http://localhost:5173/live`.

### Guion ensayado

1. En **New live shift**, pulsar **Rehearsed** (seed 2005). Lo demás por defecto:
   Motorcycle, 2 h, Tec.
2. **Start live shift**: los dos arrancan en $0 y avanzan juntos.
3. Pausar en la píldora cuando el reloj marque **14:29–14:30** y esperar a que se
   detenga: el shock entra en el minuto que marca el reloj.
4. **Close Constitución**. El banner dice _Injected at 14:30_.
5. Reanudar. A las 14:32 llega la primera oferta tras el cierre: Nuez la acepta y Greedy
   la salta por capacidad. Señalar el banner: tramos por Centro de ambos y la razón de
   Nuez.
6. Pausar cuando el reloj marque **14:56** y esperar a que se detenga.
7. Pulsar el botón del reloj (**Restaurant +15 min**, solo icono, entre _Trigger surge_ y
   _End shift_). El banner dice «Order o_045, pickup in Guadalupe», «+15 min at the
   restaurant» y «Waiting for order o_045 to be offered…».
8. Reanudar. A las 14:56 se ofrece o_045: Nuez la **salta** por `shift_end_infeasible`
   (_No alcanzas a entregarlo y volver antes de que acabe tu turno._; el pedido pasa de 11.6 a
   25 min). Sin el retraso la aceptaba. Greedy la salta igual, con o sin retraso. Señalar el
   SKIP de Nuez y su razón en el banner. Este volteo depende de que el cierre de las 14:30 ya
   esté puesto: sin el cierre, un delay en el 56 no cambia la decisión.
9. Dejar correr al menos hasta 15:30 (ver
   [Momentos de seguridad](#momentos-de-seguridad-en-el-seed-ensayado)) y pulsar
   **End shift**. El panel baja solo al resultado final y a la ruta del **Event log**. Con el
   cierre a las 14:30 y el retraso a las 14:56 termina en Greedy $353.63 / 4 entregas y Nuez
   $428.65 / 7 entregas (solo con el cierre, Nuez termina en $395.94).
10. Un momento después aparece **If Nuez had taken its skips** en la misma tarjeta: el
    contrafactual re-simula el turno con el cierre y el retraso puestos. En el guion: 5 saltos
    por dinero; tomando cualquiera solo, 3 habrían ganado menos y 2 lo mismo. Cada renglón es una
    corrida aparte: los deltas no se suman.

Un cierre entre 14:27 y 14:33 sigue cambiando los tramos por Centro de los dos, así que
pasarse un minuto no arruina el demo; solo cambia la corrida para repetirla. El retraso no
tiene ese margen: en otro minuto le pega a otro pedido. Con el cierre puesto, los minutos donde
un +15 cambia una decisión son 47 y 48 (o_037, Nuez), 56 (o_045, Nuez) y 72 (o_059, Greedy). Fuera de
esos minutos el banner sigue siendo honesto: nombra el pedido y enseña lo que decidió cada uno.

### La bitácora JSONL

Es la bitácora de **auditoría** del turno live: los dos agentes, sus decisiones y los shocks
del juez, con los nombres del esquema oficial. El replay del protocolo §6 (grabar un turno,
reproducirlo contra el sistema y comparar decisiones) se hace sobre la bitácora de `/decide`
(`cache/courier/current_shift.jsonl`, o `$NUEZ_EVENT_LOG`), que es la de un solo repartidor.

Cada sesión escribe `cache/live/<session_id>.jsonl` (o `$NUEZ_LIVE_DIR/<session_id>.jsonl`
si esa variable está definida al arrancar la API). El `session_id` es
`live-<seed>-<6 hex>` y el panel muestra la ruta en **Event log** al terminar. Las más
recientes:

```bash
ls -t cache/live | head -n 2
```

El evento `shock` con su número de línea (el delay trae `order_id` y `slip_min`); las
decisiones posteriores son las líneas de abajo:

```bash
python -c "import json,sys; [print(n, l, end='') for n, l in enumerate(open(sys.argv[1], encoding='utf-8'), 1) if json.loads(l).get('event') == 'shock']" cache/live/live-2005-AAAAAA.jsonl
```

### Repetir y comprobar determinismo

Repetir el guion con el mismo seed y el shock en el mismo minuto (mismo _Injected at_).
Después comparar las decisiones de las dos bitácoras, ignorando `session_id` y
`latency_ms`:

```bash
python -c "import json,sys; ign={'session_id','latency_ms'}; d=lambda p: [{k: v for k, v in e.items() if k not in ign} for e in map(json.loads, open(p, encoding='utf-8')) if e.get('event') == 'decision']; a, b = d(sys.argv[1]), d(sys.argv[2]); print('iguales' if a == b else 'DISTINTAS', len(a), len(b))" cache/live/live-2005-AAAAAA.jsonl cache/live/live-2005-BBBBBB.jsonl
```

Debe imprimir `iguales` con el mismo número de decisiones. Si dice `DISTINTAS`, revisar
primero con el comando anterior que el `shock` esté en el mismo minuto en los dos
archivos. La velocidad (×1, ×2, ×4) no afecta: cada tick es un minuto.

## Momentos de seguridad en el seed ensayado

El protocolo pide ver al menos dos restricciones de seguridad disparándose en vivo. En el
seed 2005 (2 h desde 14:00, moto, Tec, margen 10, cierre a las 14:30, sin surge) los dos
agentes disparan **tres restricciones duras**: dos de seguridad, `shift_end_infeasible` y
`heat_rule`, y una de **capacidad**, `vehicle_capacity`. La capacidad es dura pero no es
seguridad: un vehículo lleno es un límite físico, no un riesgo para el repartidor (así la
clasifica main en `contrafactual.py` y `lib/decision-text.ts`). No hace falta otro seed. El
retraso de las 14:56 no mueve la primera vez de ninguna; agrega el `shift_end_infeasible` de
Nuez sobre o_045.

| Hora  | Agente | Restricción            | Tipo      | Razón corta                                              |
| ----- | ------ | ---------------------- | --------- | -------------------------------------------------------- |
| 14:06 | Nuez   | `vehicle_capacity`     | capacidad | En moto solo caben 3 pedidos a la vez                    |
| 14:08 | Greedy | `vehicle_capacity`     | capacidad | 37 L y en la caja de moto caben 20                       |
| 14:09 | Greedy | `shift_end_infeasible` | seguridad | No alcanza a entregar y volver antes del fin             |
| 14:34 | Greedy | `shift_end_infeasible` | seguridad | Por el cierre: sin él, la saltaba por `reservation_wage` |
| 14:43 | Nuez   | `shift_end_infeasible` | seguridad | Por el cierre: sin él, la primera es a las 15:00         |
| 15:30 | Nuez   | `heat_rule`            | seguridad | 90 min seguidos bajo el sol de las 15; para 20 min       |
| 15:33 | Greedy | `heat_rule`            | seguridad | 91 min seguidos; sin cierre, la primera es a las 15:47   |

- Nuez repite `vehicle_capacity` en la mayoría de las ofertas entre 14:06 y 14:42,
  mientras lleva 3 pedidos. Llegar a 14:45 antes de **End shift** muestra capacidad y fin de
  turno, que es **una sola** de seguridad; la segunda (`heat_rule`) pide dejar correr hasta
  15:30.
- La lista de decisiones y los avisos en pantalla son de Nuez; los rechazos de Greedy
  quedan en el JSONL.
- `flagged_zone_night` (después de las 22:00) y `mandatory_break` (4 h seguidas) no
  caben en un turno de 14:00 a 16:00.
- Se midió con `LiveDemoSession` y geometría `linea_recta`, contando las decisiones con
  `binding_constraint` distinto de `null` y de `reservation_wage`, y comparando con la
  misma corrida sin cierre.

## Fuera de alcance para este corte

- WebSockets, cuentas de usuario, persistencia en Tiger, control de voz o IA generativa
  en el loop de decisión.
- Hacer que Gemini decida pedidos o modifique las restricciones duras.
- Recalibrar `V.json`, cambiar la política Nuez o tocar los resultados medidos.
- Convertir el replay ya grabado en live: son productos distintos y ambos son útiles.

## Riesgos que no se deben ignorar

1. **Una sola sesión actual:** `CourierService` usa `self.state`; reutilizarlo para
   los dos agentes mezclará el turno. Crear estados separados o un coordinador propio.
2. **Equidad:** no generar una lista de ofertas por política. El stream se genera una
   sola vez antes de decidir y se distribuye a ambas.
3. **Replay falso:** un banner de shock sobre datos grabados no demuestra reacción.
   La respuesta posterior debe venir de una decisión recalculada.
4. **Cambiar los benchmarks:** el modo live debe reutilizar el motor sin tocar el
   contrato de `comparar.py`. Correr `python -m pytest` y `python comparar.py 200`
   antes de entregar.
5. **Demo frágil:** para el pitch, tener un seed y minuto de shock ensayados, pero
   conservar la opción de introducir un seed nuevo para probar que no es video.
