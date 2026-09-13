# TigerData para frontend

## Objetivo

Mostrar el historial y resumen de decisiones de Nuez sin conectar React a la
base de datos. El frontend solo llama al backend; el backend consulta TigerData
o, si la base no está disponible, el JSONL local de replay.

```text
React -> GET /analytics/shift -> backend -> TigerData
                                      └-> JSONL (fallback)
```

No usar credenciales de Postgres, SQL ni `TIGERDATA_DATABASE_URL` en el front.

## Endpoint

```text
GET ${API_URL}/analytics/shift
```

`API_URL` ya existe en `frontend/src/lib/api.ts`:

```ts
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'
```

La ruta se monta al arrancar `backendruta/main.py`. Para probarla con backend
corriendo:

```text
http://127.0.0.1:8000/analytics/shift
```

## Respuesta

```json
{
  "source": "tigerdata",
  "log_path": "cache/courier/current_shift.jsonl",
  "total_decisions": 24,
  "accepted": 8,
  "skipped": 16,
  "accept_rate_pct": 33.33,
  "by_constraint": {
    "opportunity_cost": 10,
    "heat_rule": 3,
    "shift_end_infeasible": 3
  },
  "accepted_net_mxn": 418.5,
  "timeline": [
    {
      "sim_time": "2026-03-21T14:30:00",
      "order_id": "ORD-42",
      "decision": "SKIP",
      "reason": "Heat limit reached.",
      "binding_constraint": "heat_rule",
      "net_pay_mxn": 80
    }
  ]
}
```

- `source` será `tigerdata` cuando la consulta llegó a la base. `jsonl` significa
  que la app sigue funcionando con su bitácora local; no es un error.
- `by_constraint` usa `opportunity_cost` para rechazos económicos sin una
  restricción de seguridad.
- `accepted_net_mxn` es la suma proyectada de las órdenes aceptadas, no sustituye
  el contador final de ganancias entregadas del simulador.

## Tipos y cliente

Crear `frontend/src/lib/analytics.ts`:

```ts
import { API_URL } from './api'

export type DecisionTimelineItem = {
  sim_time: string
  order_id: string
  decision: 'ACCEPT' | 'SKIP'
  reason: string
  binding_constraint: string | null
  net_pay_mxn: number
}

export type ShiftAnalytics = {
  source: 'tigerdata' | 'jsonl'
  log_path: string
  total_decisions: number
  accepted: number
  skipped: number
  accept_rate_pct: number
  by_constraint: Record<string, number>
  accepted_net_mxn: number
  timeline: DecisionTimelineItem[]
}

export async function getShiftAnalytics(signal?: AbortSignal): Promise<ShiftAnalytics> {
  const response = await fetch(`${API_URL}/analytics/shift`, { signal })
  if (!response.ok) throw new Error(`Analytics unavailable: ${response.status}`)
  return response.json() as Promise<ShiftAnalytics>
}
```

## Uso en un componente

Recargar después de una decisión importante, al acabar el turno, o cada 3–5
segundos durante un demo live. No hacer polling cada frame de animación.

```tsx
const [analytics, setAnalytics] = useState<ShiftAnalytics | null>(null)
const [analyticsError, setAnalyticsError] = useState<string | null>(null)

useEffect(() => {
  const controller = new AbortController()

  void getShiftAnalytics(controller.signal)
    .then(setAnalytics)
    .catch((error: unknown) => {
      if ((error as Error).name !== 'AbortError') setAnalyticsError('History unavailable')
    })

  return () => controller.abort()
}, [lastDecision?.order_id])
```

## Primera UI recomendada

Una tarjeta pequeña llamada **Decision history**:

```text
DECISION HISTORY                         TigerData / Local replay
8 accepted · 16 skipped · 33% acceptance

Why Nuez skipped orders
Heat rule                    3
Return-to-class deadline     3
Opportunity cost            10

Latest: SKIP · ORD-42
Heat limit reached.
```

Usar `source === 'tigerdata'` para el badge. Si es `jsonl`, decir `Local replay`;
no mostrar una alerta roja porque el fallback es un comportamiento esperado.

## No hacer

- No abrir una conexión a TigerData desde React.
- No mostrar `log_path` ni detalles de infraestructura al juez.
- No presentar `accepted_net_mxn` como ganancia final realizada.
- No bloquear el replay o el demo si analytics falla.
