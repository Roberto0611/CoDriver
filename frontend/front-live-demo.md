# Modo Live Demo: trabajo pendiente

## Objetivo

Agregar un modo **Live demo** separado del replay actual. En este modo, Greedy y
Nuez reciben exactamente el mismo flujo de ofertas de un seed nuevo, sus estados
evolucionan en tiempo real y un juez puede inyectar un cierre vial o surge a mitad
del turno. La pantalla debe enseñar la reacción real, no una animación pregrabada.

El entregable del reto es justamente esta corrida: dos agentes lado a lado, el mismo
turno fresco, contadores que cambian y una disrupción a mitad de la demostración.

## Estado actual (importante)

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

| Modo | Fuente de verdad | Controles |
|---|---|---|
| **Recorded replay** | JSON ya exportado | play, pausa, velocidad, selector de seed. Sin inyectar shocks. |
| **Live demo** | simulación viva del backend | iniciar seed, play/pause, cierre vial y surge. |

Para el pitch basta con **Closure** y **Surge**. No priorizar lluvia: es menos visual y
el reto pide surge *o* cierre. Si se deja lluvia, debe funcionar igual que los otros,
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
  body: { session_id, shock_type, zone?, duration_min, multiplier?, road? }
  response: shock registrado + snapshot

GET /live/status/{session_id}
  response: snapshot actual

POST /live/end
  body: { session_id }
  response: resultado final + ruta del JSONL
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
    "last_decision": { "order_id": "...", "decision": "SKIP", "reason": "...", "binding_constraint": null }
  }
}
```

Usar coordenadas o IDs de punto compatibles con el mapa actual. La razón de Nuez debe
llegar completa: no volver a sintetizarla y perder la restricción que mandó.

## Plan de implementación

### 1. Backend: sesión doble y determinista

- [ ] Leer `sim.py` y extraer/reutilizar el avance de un minuto sin alterar el
      resultado de `simular()` ni los benchmarks de `comparar.py`.
- [ ] Crear `LiveDemoSession` con un estado independiente para cada política.
- [ ] Generar las ofertas una sola vez a partir del seed; entregar la misma instancia
      lógica/oferta equivalente a Greedy y Nuez en el mismo minuto.
- [ ] Al inyectar un shock, aplicarlo a los dos agentes desde el mismo minuto. La
      física siempre debe usar `shocks.py`; Gemini no decide si un cierre ralentiza
      una calle.
- [ ] Escribir `shock`, ofertas, decisiones y resultados en JSONL para que el turno
      pueda auditarse y eventualmente exportarse como replay.
- [ ] Garantizar que una sesión nueva no comparte rutas, dinero, ofertas aceptadas ni
      shocks con una sesión anterior.

### 2. Backend: endpoints y pruebas

- [ ] Implementar las rutas `/live/*` anteriores en un router separado.
- [ ] Validar que no se pueda hacer `tick` después de terminar ni inyectar shock sin
      sesión activa.
- [ ] Agregar tests que fijen:
  - mismo seed + mismos ticks => mismo snapshot/decisiones;
  - Greedy y Nuez ven exactamente las mismas ofertas;
  - closure cambia los tiempos de ruta de ambos;
  - surge cambia el pago de las ofertas afectadas;
  - un shock aparece en el JSONL;
  - el flujo normal sin shock no modifica los resultados existentes de `comparar.py`.

### 3. Frontend: separar replay de live

- [ ] Conservar `/sim` como **Recorded replay**. Quitar de esta vista los botones que
      llaman `/shock`, o dejarlos deshabilitados con una explicación; nunca deben
      aparentar que alteran el JSON grabado.
- [ ] Crear una ruta, por ejemplo `/live`, con `LiveSimView.tsx`.
- [ ] Reusar, cuando sea posible, mapa, marcadores, `Counters`, `Decisions` y estilos
      de `SimView.tsx`; no duplicar componentes visuales.
- [ ] Agregar formulario mínimo de inicio: seed (por defecto 2000 o aleatorio),
      vehículo, duración, ancla y botón **Start live shift**.
- [ ] Mientras corre, llamar `/live/tick` según la velocidad elegida y pintar el
      `snapshot` recibido. El backend es la fuente de verdad.
- [ ] Habilitar solo con sesión activa:
  - **Close Constitución** (zone 2, 40 min, road `Constitución`);
  - **Trigger surge** (zona visible, multiplicador y duración fijos para el demo).
- [ ] Al recibir el resultado, mostrar un banner persistente con el shock, cuándo
      expira y el cambio que provocó. No ocultarlo automáticamente a los 10 segundos.
- [ ] Mostrar en ambas tarjetas la decisión inmediatamente posterior al shock y la
      razón de Nuez. Ese es el momento que se va a narrar durante el pitch.
- [ ] Manejar errores de red con mensaje visible y detener el autoplay; no limitarse
      a `console.error`.

### 4. Voz (solo después de que live funcione)

- [ ] Al recibir una decisión nueva de Nuez, llamar `say(reason)` de
      `frontend/src/voice/nuez.ts` si la decisión merece ser narrada.
- [ ] No hablar cada oferta: como mínimo, hablar rechazos por seguridad y la primera
      decisión relevante tras un shock.
- [ ] Usar `prefetch()` solo para el replay grabado; un turno live no puede conocer
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
