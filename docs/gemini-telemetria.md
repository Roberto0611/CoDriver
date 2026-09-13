# Telemetría de Gemini para el pitch

## Qué mide

`GET /shift/status` ahora incluye `gemini_usage` y cada intento queda como evento
`model_usage` en el JSONL del turno.

```json
{
  "provider": "gemini",
  "model": "...",
  "calls": 1,
  "successful_calls": 1,
  "failed_calls": 0,
  "input_tokens": 120,
  "output_tokens": 30,
  "total_tokens": 150,
  "estimated_cost_usd": null,
  "estimated_cost_mxn": null,
  "cost_configured": false,
  "interval_s": 300
}
```

Las cuentas son **por turno**: se reinician en `/shift/start` y siguen visibles tras
`/shift/end` para que se pueda mostrar el resumen final.

## Mensaje correcto para el jurado

> Gemini is not called for every delivery. It is a slow strategy advisor: one initial
> consultation and then at most one every five real minutes. The deterministic engine
> decides every order locally in microseconds.

Una jornada real de 8 horas tiene como máximo una consulta inicial más una por cada
intervalo de cinco minutos: aproximadamente **97 llamadas**, no cientos de llamadas
por cada oferta. Un demo acelerado puede mostrar menos; se debe leer el contador real,
nunca prometer un número fijo.

## Costo: cómo mostrarlo sin inventar

La API devuelve los tokens reales de entrada y salida. El costo se calcula solo si el
equipo configura en `.env` las tarifas vigentes del modelo que de verdad usa:

```env
GEMINI_INPUT_USD_PER_MILLION=<USD por 1M tokens de entrada>
GEMINI_OUTPUT_USD_PER_MILLION=<USD por 1M tokens de salida>
USD_TO_MXN=<tipo de cambio>
```

Antes del pitch, verificar el modelo activo (`GEMINI_MODELO`) y copiar sus tarifas
oficiales actuales. Si no se configuran, la pantalla debe mostrar **“cost rate not
configured”**, no `$0.00`.

## Tarjeta recomendada para el front

Mostrarla solo en Live Demo, cerca del badge de Gemini:

```text
GEMINI STRATEGY ADVISOR
1 call · 150 tokens · MXN $0.00xx estimated
Never in the order-decision path
```

Si Gemini falla: mantener los acumulados y cambiar el estado a:

```text
GEMINI DEGRADED
Last safe strategy active · 1 failed call
```

No presentarlo como “AI cost of every order”: el diferenciador es precisamente que
el costo y la latencia del modelo están fuera de la ruta de decisión.
