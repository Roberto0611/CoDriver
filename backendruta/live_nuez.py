"""Nuez en el demo en vivo: la politica que lee a Gemini y lo que Gemini alcanza a ver.

La capa lenta (`strategy.CapaEstrategia`) publica una estrategia desde su hilo, y Nuez
lee la ultima publicada en cada pedido, igual que /decide. Eso hace que el turno en
vivo dependa de CUANDO contesto Gemini, que no sale del seed. Por eso `NuezEnVivo`
anota con que estrategia decidio cada pedido: el contrafactual de la sesion
(`contrafactual.reporte(..., estrategias=)`) re-simula con esas mismas, y su "real"
es el turno que el juez vio aunque Gemini haya movido una perilla a media corrida.
"""

from types import SimpleNamespace
from typing import Any

import shocks
import valor
from backendruta import strategy, zonas
from backendruta.strategy import CapaEstrategia
from contrato import ConfigTurno, Decision, EstadoRepartidor, Oferta
from estrategia import Estrategia
from nuez import politica_nuez
from reloj import Turno
from sim import Parada


class NuezEnVivo:
    """La politica de Nuez para un `reloj.Turno` en vivo. Una por sesion."""

    def __init__(self, capa: CapaEstrategia, duracion_min: int) -> None:
        self.capa = capa
        self.tabla = valor.para_turno(duracion_min)
        # oferta_id -> la estrategia con la que se decidio. Cada oferta se decide una vez.
        self.usadas: dict[str, Estrategia] = {}

    def __call__(
        self,
        oferta: Oferta,
        estado: EstadoRepartidor,
        ruta: list[Parada],
        cfg: ConfigTurno,
        *,
        activos: shocks.Activos,
    ) -> tuple[list[Parada] | None, Decision]:
        # Una sola lectura: el hilo de Gemini puede publicar otra entre dos accesos, y lo
        # que se anota tiene que ser justo aquello con lo que se decidio.
        estrategia = self.capa.actual
        self.usadas[oferta.id] = estrategia
        return politica_nuez(
            oferta,
            estado,
            ruta,
            cfg,
            tabla=self.tabla,
            estrategia=estrategia,
            activos=activos,
        )


def contexto_modelo(turno: Turno) -> dict[str, Any]:
    """Foto del turno de Nuez cuando el hilo lento va a consultar Gemini."""
    estado = SimpleNamespace(
        config=turno.cfg,
        current_minute=turno.t,
        position=turno.pos,
        accepted=turno.aceptadas,
        offered=len(turno.res.decisiones),
        completed=turno.res.entregas,
        earnings_mxn=turno.res.ganado,
    )
    return strategy.contexto_del_turno(estado, zonas.NOMBRES, turno.activos())
