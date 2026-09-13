// Al final del turno en vivo mostramos el "what if" del mismo seed cuando está
// grabado. Un turno fresco no se re-simula a escondidas: cae al benchmark 2000 y
// lo nombra como referencia, sobre todo si el juez disparó una disrupción.

import { useEffect, useState } from 'react'

import { cargarContrafactual, type Contrafactual } from '../lib/contrafactual'
import { CounterfactualReport } from './Counterfactual'

const SEED_REFERENCIA = 2000

interface Props {
  seed: number
  terminado: boolean
}

export function LiveCounterfactual({ seed, terminado }: Props) {
  const [referencia, setReferencia] = useState<{ turnoSeed: number; datos: Contrafactual } | null>(
    null
  )

  useEffect(() => {
    if (!terminado) return
    let vigente = true

    void (async () => {
      const delTurno = await cargarContrafactual(seed)
      const datos =
        delTurno ?? (seed === SEED_REFERENCIA ? null : await cargarContrafactual(SEED_REFERENCIA))
      if (!vigente || !datos) return
      setReferencia({ turnoSeed: seed, datos })
    })()

    return () => {
      vigente = false
    }
  }, [seed, terminado])

  const datos = referencia?.turnoSeed === seed ? referencia.datos : null
  if (!terminado || !datos) return null

  return (
    <CounterfactualReport
      datos={datos}
      horaInicio={14}
      titulo={`If Navie had taken its skips · Recorded Seed ${datos.seed}`}
      nota="Recorded benchmark (14:00–16:00, motorcycle), not a calculation of this fresh live shift."
    />
  )
}
