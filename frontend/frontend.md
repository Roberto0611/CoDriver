# Front: qué agregar de los shocks y las métricas

Actualizado el 12 de septiembre, después del trabajo de disrupciones. Todo lo de abajo es
front; el backend ya está listo y probado.

---

## 1. 🔴 El botón del shock — es lo único obligatorio

El brief lo pide textual: **al menos una disrupción a mitad del turno durante el demo**. Hoy
no hay forma de dispararla desde la pantalla, así que ese punto no existe.

```
POST http://127.0.0.1:8000/shock
```

Cuatro tipos. Estos son los payloads que funcionan:

```json
{"shock_type": "closure", "zone": 2, "duration_min": 40, "road": "Constitución"}
{"shock_type": "rain", "duration_min": 45}
{"shock_type": "surge", "zone": 4, "multiplier": 1.8, "duration_min": 25}
{"shock_type": "delay", "order_id": "ORD-0007", "slip_min": 15}
```

Los ids de zona salen de `GET /zones`. La respuesta trae `active_shocks` con cuántas hay vivas.

**Los dos que mejor se ven son `closure` y `rain`**, porque cambian el mapa completo. El
`surge` es más sutil (sube el pago de una zona) y el `delay` necesita un pedido en vuelo.

### Qué debería pasar en pantalla

```
el juez aprieta "cierre en Centro"
   → banner: "Cierre en Centro · 40 min"
   → la siguiente decisión ya sale distinta, con el cierre nombrado en la razón
```

Ese es el momento del demo. Si el banner no está, el juez no sabe que su botón hizo algo.

---

## 2. 🔴 La razón se está tirando a la basura

Esto lo encontré revisando y es el hallazgo importante.

`lib/decision-text.ts` **descarta** el campo `razon` del JSON y genera su propio texto en
inglés. El comentario del archivo lo dice: _"la `razon` del JSON viene en español; esta
función la reemplaza"_.

El problema es que ahora la razón trae información que el texto generado no tiene:

|                           |                                                                                     |
| ------------------------- | ----------------------------------------------------------------------------------- |
| **lo que trae el JSON**   | `"Cerraron Constitución, esos 34 minutos rinden $42 normalmente, y este paga $22."` |
| **lo que se muestra hoy** | `"Skip: MXN 22 for 34 min"`                                                         |

Se pierde el **por qué** justo cuando por fin lo tenemos. Y el spec es explícito:

> _"A correct decision with a generic or wrong reason does not earn the Judgment credit."_

**Lo mínimo:** mostrar `razon` tal cual en el detalle expandido. El resumen corto de la lista
puede seguir generado, no hay bronca.

Las razones que nombran una disrupción empiezan con `"Cerraron ..."` o `"Con la lluvia..."`,
por si quieres detectarlas para resaltarlas.

---

## 3. 🟡 Cuatro campos nuevos en el JSON grabado

Ya están exportados, en `frontend/public/turno_*.json`:

```json
"meta": {
  "violaciones": 0,          // aceptó algo infactible → romper la regla
  "llego_tarde": false,      // no volvió antes de (duración − margen)
  "regreso_en": 109.5,       // el minuto exacto en que llegó al ancla
  "cancelados": 0            // pedidos soltados por una disrupción
}
```

Hay que agregarlos a `TurnoMeta` en `lib/turno.ts`.

### `Counters.tsx` necesita reencuadrarse

Hoy dice esto, y mezcla dos cosas distintas:

```
Late?    No
```

Debería ser dos líneas:

```
Safety violations     0
Back by 14:50         109.5 min   ✓
```

- **`violaciones`** es _"¿aceptó algo que sus propios números decían que no alcanzaba?"_.
  Siempre es 0, y ese cero es el que pide el protocolo.
- **`llego_tarde`** es _"¿volvió a tiempo?"_. Puede ser `true` por algo que pasó **después**
  de aceptar — empezó a llover cuando ya traía tres pedidos.

Si el juez ve una sola línea ambigua llamada "Late", lee "violó la regla". No es lo que pasó.

### `cancelados` no es un contador, es un momento

Si sale 1 significa: _"empezó a llover, Nuez soltó el pedido que todavía no recogía para
alcanzar a volver a clase"_. Eso se cuenta en voz alta, no se esconde en una cifra chiquita.

La lógica es la de un repartidor real: puedes cancelar lo que no has recogido, no puedes tirar
comida que ya cargas.

---

## 4. 🟢 Lo que NO hay que tocar

**`t_salida` ahora viene con decimales** (antes era entero). Ya lo revisé: `lib/sim.ts`
interpola con `(t - t_salida) / (t_llegada - t_salida)`, así que funciona igual y la moto se va
a mover más preciso. **Cero cambios.**

---

## 5. Números que cambiaron

Si tienes algo hardcodeado, está viejo:

```
                     greedy      NUEZ
sin disrupciones      $198      $264     +33.5%    (era +29%)
con disrupciones      $189      $251     +32.9%
```

Los turnos grabados se regeneraron completos.

Y hay un dato nuevo que es buen material de pantalla — la tabla de rivales:

```
AcceptAll     $180        GreedyRate    $206
HighestPay    $133        OurAgent      $265
NearestFirst  $128        Oracle        $281
```

El `Oracle` es un solver offline que **conoce todo el turno de antemano**. Estamos en el
**94% del óptimo teórico**. Ese número se dice en voz alta.

---

## 6. Si tuvieras que escoger dos

**El botón del shock (§1) y no tirar la razón (§2).** Los dos atacan Judgment directo, que es
la mitad del puntaje. Lo demás son mejoras; esos dos son puntos.
