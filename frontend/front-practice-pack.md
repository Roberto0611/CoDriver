# Safety Lab: replay del practice pack Courier

El archivo público `courier_practice_pack_replay.json` no es un turno normal ni un
duelo Greedy-vs-Nuez. Es una inspección visual de las 14 pruebas de seguridad del
pack oficial a lo largo de un turno de 8.5 h. No lo agregues a `turnos.json`: ese
índice promete que hay dos políticas enfrentando exactamente el mismo stream.

## Uso mínimo

Agregar una vista o tab separado, por ejemplo **Safety Lab**, que haga:

```ts
const replay = await fetch('/courier_practice_pack_replay.json').then((r) => r.json())
```

La UI debe mostrar:

1. Una línea de tiempo 14:00–22:30 con 14 puntos (`test.minute`).
2. Al elegir un punto: orden, pago, pickup/dropoff, estado enviado y servicio
   declarado.
3. `expected` frente a `actual`: ACCEPT/SKIP, binding constraint, razón y PASS/FAIL.
4. Un color para reglas de seguridad y uno neutral para los controles que deben
   aceptar. No usar el rojo/verde como única señal: escribir el veredicto.

Para el pitch, dejar seleccionados PP-004 (calor), PP-010 (zona nocturna) y PP-014
(el control corto antes del fin del turno). Es una prueba auditable de que la regla
se ejecutó, no un gráfico inventado.

## Regenerar

```bash
python data/export_practice_pack_replay.py \
  --pack courier-update/practice_pack/practice_pack.csv \
  --key courier-update/practice_pack/practice_pack_key.json \
  --scorecard cache/courier/practice_pack_scorecard.json
```

El JSON se actualiza después de cada corrida del runner. Sin `--scorecard`, el
archivo conserva las pruebas y expectativas pero deja vacío el resultado real.
