"""El demo en vivo: Greedy y Nuez en el mismo turno, minuto a minuto.

    s = LiveDemoSession("live-2005-ab12", cfg, Path("logs/live-2005-ab12.jsonl"))
    s.tick()                                   # corre un minuto, devuelve el snapshot
    s.shock("closure", 40, zona=0, calle="Constitución")
    s.end()                                    # adelanta hasta el final y cierra

No es un segundo motor. Cada agente es un `reloj.Turno`, el mismo que corre
`simular()` para `comparar.py`, y los dos reciben la MISMA lista de ofertas,
generada una vez aqui. Si cada turno la generara por su cuenta seguiria saliendo
igual (depende solo del seed), pero entonces la equidad seria una coincidencia y
no algo que se ve en el codigo. El shock se inyecta en los dos en el mismo minuto,
y la fisica es la de `shocks.py`: aqui no se decide nada, solo se reparte y se anota.

El snapshot (lo espeja `frontend/src/lib/live.ts`, los nombres son contrato):

    {
      "session_id": "live-2005-ab12",
      "minute": 37,                 # el siguiente minuto a correr; [0, minute) ya corrieron
      "duration_min": 120, "start_hour": 14, "seed": 2005,
      "status": "running",          # running | finished (tick llego al final) | ended (end())
      "active_shocks": [{"type": "closure", "zone": 0, "zone_name": "Centro",
                         "road": "Constitución", "starts_at_min": 30, "ends_at_min": 70,
                         "multiplier": 1.0}],
      "offers_this_tick": [{"order_id": "o_041", "minute": 36, "pickup": 88, "dropoff": 12,
                            "pickup_zone": "Tec", "dropoff_zone": "Contry", "pay_mxn": 48.2}],
      "greedy": {
        "position": 12, "coords": [-100.29, 25.65],          # [lon, lat]
        "earnings_mxn": 84.0, "deliveries": 2, "skipped": 4, "cancelled": 0,
        "route": [{"type": "pickup", "point": 88, "order_id": "o_041"}],
        "last_decision": {"order_id": "o_041", "minute": 36, "decision": "ACCEPT",
                          "reason": "...", "binding_constraint": null, "terms": {}},
        "frames": [...],            # uno por minuto de este tick, como export_turno.a_frames
        "new_legs": [{"t_salida": 36, "t_llegada": 41.3, "desde": 12, "hasta": 88,
                      "clave": "12-88"}],
        "geometry": {"12-88": [[-100.29, 25.65], [-100.30, 25.66]]},
        "result": null              # el `meta` del exportador cuando ya no corre
      },
      "nuez": { ...igual... }
    }

`frames`, `new_legs`, `geometry` y `offers_this_tick` son deltas: solo `tick()` los
llena. `snapshot()`, `shock()` y `end()` los mandan vacios. `geometry` trae nada mas
las claves que ese agente no ha mandado, asi cada lado del front puede guardar su
propio mapa de geometria como en el replay grabado.
"""

from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any, Literal

import rutas
import shocks
import valor
from backendruta import zonas
from backendruta.event_log import EventLog
from backendruta.live_geometry import Geometria, linea_recta
from contrato import ConfigTurno, Decision, Oferta
from nuez import politica_nuez
from reloj import Turno
from sim import generar_ofertas, indice_de, politica_greedy

# El menor seed >= 2000 donde cerrar Centro en el 30 cambia tramos de los dos y decisiones de Nuez.
SEED_ENSAYADO = 2005

AGENTES = ("greedy", "nuez")
TIPOS = {"closure", "surge", "rain"}
CON_ZONA = {"closure", "surge"}


class SesionTerminada(Exception):
    """tick, shock o end sobre una sesion que ya no corre. El router lo vuelve 409."""


def _decision(d: Decision) -> dict[str, Any]:
    # La razon va tal cual la escribio la politica: resintetizarla aqui perderia
    # la restriccion que mando, que es justo lo que el juez quiere ver.
    return {
        "order_id": d.oferta_id,
        "minute": d.t,
        "decision": "ACCEPT" if d.accion == "aceptar" else "SKIP",
        "reason": d.razon,
        "binding_constraint": d.restriccion,
        "terms": d.terminos,
    }


class LiveDemoSession:
    """Una sesion del demo. Nada vive a nivel de modulo: dos sesiones no comparten
    rutas, dinero ni shocks, porque todo cuelga de `self`."""

    def __init__(
        self,
        session_id: str,
        cfg: ConfigTurno,
        log_path: Path,
        geometria: Geometria = linea_recta,
    ) -> None:
        self.session_id = session_id
        self.cfg = cfg
        self.geometria = geometria
        self.status: Literal["running", "finished", "ended"] = "running"
        self.shocks: list[shocks.Shock] = []

        self.ofertas = generar_ofertas(cfg)
        self.por_minuto: dict[int, list[Oferta]] = {}
        for o in self.ofertas:
            self.por_minuto.setdefault(o.t_aparece, []).append(o)

        tabla = valor.para_turno(cfg.duracion_min)
        self.turnos = {
            "greedy": Turno(cfg, politica_greedy, ofertas=self.ofertas),
            "nuez": Turno(cfg, partial(politica_nuez, tabla=tabla), ofertas=self.ofertas),
        }
        # Hasta donde ya se reporto cada lista del Resultado. Los Turnos solo crecen
        # sus listas, asi que lo nuevo de un minuto es todo lo que esta despues del cursor.
        self._cursor = {
            a: {"decisiones": 0, "tramos": 0, "cobros": 0, "trayecto": 0} for a in AGENTES
        }
        self._ganado_frames = dict.fromkeys(AGENTES, 0.0)  # el `ganado` de los frames
        self._claves: dict[str, set[str]] = {a: set() for a in AGENTES}
        self._ultima: dict[str, dict[str, Any] | None] = dict.fromkeys(AGENTES)
        self._resultado: dict[str, dict[str, Any] | None] = dict.fromkeys(AGENTES)

        ancla = rutas.indice_mas_cercano(cfg.ancla.lat, cfg.ancla.lon)
        self.log = EventLog(log_path)
        self.log.start(
            {
                "event": "shift_start",
                "mode": "live",
                "session_id": session_id,
                "seed": cfg.seed,
                "duration_min": cfg.duracion_min,
                "start_hour": cfg.hora_inicio,
                "vehicle": cfg.vehiculo,
                "anchor_zone": zonas.ID_POR_NOMBRE[rutas.ZONA_DE[ancla]],
                "margin_min": cfg.margen_min,
            }
        )

    @property
    def minute(self) -> int:
        return self.turnos["greedy"].t  # los dos avanzan juntos, siempre

    # --- lo que llama el router ------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """El estado completo, sin deltas. Para start y status."""
        return self._snapshot([], {a: [] for a in AGENTES}, nuevos=False)

    def tick(self, minutes: int = 1) -> dict[str, Any]:
        self._vivo()
        if minutes < 1:
            raise ValueError("minutes debe ser al menos 1")
        ofertas: list[dict[str, Any]] = []
        frames: dict[str, list[dict[str, Any]]] = {a: [] for a in AGENTES}
        # Pedir mas minutos de los que quedan no es error: se corre hasta el final.
        # Lo que nunca se hace es llamar paso() de mas, porque Turno no se protege.
        for _ in range(minutes):
            if self.minute >= self.cfg.duracion_min:
                break
            ofertas += self._minuto(frames)
        if self.minute >= self.cfg.duracion_min:
            self._cerrar("finished")
        return self._snapshot(ofertas, frames, nuevos=True)

    def shock(
        self,
        tipo: str,
        duracion_min: int,
        zona: int | None = None,
        multiplicador: float = 1.0,
        calle: str | None = None,
    ) -> dict[str, Any]:
        self._vivo()
        if tipo not in TIPOS:
            raise ValueError(f"shock {tipo!r} desconocido; usa {sorted(TIPOS)}")
        if not 1 <= duracion_min <= 240:
            raise ValueError("duration_min va de 1 a 240")
        if tipo in CON_ZONA and zona is None:
            raise ValueError(f"un {tipo} necesita zona")
        if tipo == "surge" and not 1.0 < multiplicador <= 3.0:
            raise ValueError("el multiplicador de un surge va de mas de 1.0 hasta 3.0")
        # Cada tipo lleva solo lo suyo: la lluvia es en toda la ciudad aunque le
        # manden zona, y un cierre con multiplicador 1.8 no significa nada. Pintarlos
        # asi en el banner seria mentirle al juez sobre la fisica.
        if tipo not in CON_ZONA:
            zona = None
        nombre = zonas.nombre(zona) if zona is not None else None  # ValueError si no existe

        s = shocks.Shock(
            t=self.minute,
            tipo=tipo,  # type: ignore[arg-type]  # validado arriba contra TIPOS
            duracion_min=duracion_min,
            zona=nombre,
            multiplicador=multiplicador if tipo == "surge" else 1.0,
            calle=calle if tipo == "closure" else None,
        )
        for turno in self.turnos.values():
            turno.inyectar(s)
        self.shocks.append(s)

        self.log.append(
            {
                "event": "shock",
                "minute": s.t,
                "shock_type": s.tipo,
                "zone": zona,
                "zone_name": s.zona,
                "road": s.calle,
                "duration_min": s.duracion_min,
                "multiplier": s.multiplicador,
                "ends_at_min": s.t + s.duracion_min,
            }
        )
        return {"shock": self._shock(s), "snapshot": self.snapshot()}

    def end(self) -> dict[str, Any]:
        """Adelanta hasta el final sin armar frames (nadie los va a animar) y cierra.
        Las decisiones si quedan en el JSONL: el turno completo tiene que auditarse."""
        if self.status == "ended":
            raise SesionTerminada(f"la sesion {self.session_id} ya termino")
        if self.status == "running":
            while self.minute < self.cfg.duracion_min:
                self._minuto(None)
            self._cerrar("ended")
        self.status = "ended"
        return {**self.snapshot(), "event_log": str(self.log.path)}

    # --- el minuto ---------------------------------------------------------------

    def _vivo(self) -> None:
        if self.status != "running":
            raise SesionTerminada(f"la sesion {self.session_id} ya no corre ({self.status})")

    def _minuto(self, frames: dict[str, list[dict[str, Any]]] | None) -> list[dict[str, Any]]:
        """Corre el minuto actual en los dos agentes. Devuelve las ofertas que aparecieron."""
        t = self.minute
        ofertas = [self._oferta(o) for o in self.por_minuto.get(t, [])]
        for o in ofertas:
            self.log.append({"event": "offer", **o})

        for a, turno in self.turnos.items():
            res, cur = turno.res, self._cursor[a]
            cancelados = res.cancelados
            turno.paso()

            decs = res.decisiones[cur["decisiones"] :]
            cobros = res.cobros[cur["cobros"] :]
            llegadas = res.trayecto[cur["trayecto"] :]
            cur["decisiones"], cur["cobros"] = len(res.decisiones), len(res.cobros)
            cur["trayecto"] = len(res.trayecto)

            for d in decs:
                ultima = self._ultima[a] = _decision(d)
                self.log.append({"event": "decision", "agent": a, **ultima})

            # Suma y no dict(cobros): dos entregas en el mismo punto caen en el mismo
            # minuto, y el contador tiene que subir por las dos.
            cobro = sum(pesos for _, pesos in cobros)
            self._ganado_frames[a] += cobro
            if cobro:
                self.log.append(
                    {
                        "event": "earnings_update",
                        "agent": a,
                        "minute": t,
                        "cobro": round(cobro, 2),
                        "earnings_mxn": round(res.ganado, 2),
                        "deliveries": res.entregas,
                    }
                )
            if res.cancelados > cancelados:
                self.log.append(
                    {
                        "event": "order_cancelled",
                        "agent": a,
                        "minute": t,
                        "count": res.cancelados - cancelados,
                        "cancelled": res.cancelados,
                    }
                )

            if frames is not None:
                llegada = llegadas[-1] if llegadas else None  # la ultima gana, como en a_frames
                frames[a].append(
                    {
                        "t": t,
                        "ofertas": [asdict(o) for o in self.por_minuto.get(t, [])],
                        "decisiones": [asdict(d) for d in decs],
                        "llegada": {"punto": llegada[1], "tipo": llegada[2]} if llegada else None,
                        "cobro": round(cobro, 2),
                        "ganado": round(self._ganado_frames[a], 2),
                    }
                )
        return ofertas

    def _cerrar(self, status: Literal["finished", "ended"]) -> None:
        self.status = status
        for a, turno in self.turnos.items():
            res = turno.cerrar()
            # El mismo `meta` que graba data/export_turno.py: el front lo pinta igual.
            self._resultado[a] = {
                "politica": a,
                "seed": self.cfg.seed,
                "ganado": res.ganado,
                "entregas": res.entregas,
                "rechazos": res.rechazos,
                "violaciones": res.violaciones,
                "llego_tarde": res.llego_tarde,
                "regreso_en": res.regreso_en,
                "cancelados": res.cancelados,
                "ofertas_totales": len(res.ofertas),
            }
        self.log.append(
            {"event": "shift_end", "minute": self.minute, "status": status, **self._resultado}
        )

    # --- armar el snapshot -----------------------------------------------------

    def _oferta(self, o: Oferta) -> dict[str, Any]:
        pickup, dropoff = indice_de(o.pickup), indice_de(o.dropoff)
        # La misma formula con la que el motor paga al entregar: el surge se cotiza
        # con los shocks vigentes cuando aparece el ping.
        factor = shocks.en(o.t_aparece, tuple(self.shocks)).factor_pago(rutas.ZONA_DE[pickup])
        return {
            "order_id": o.id,
            "minute": o.t_aparece,
            "pickup": pickup,
            "dropoff": dropoff,
            "pickup_zone": rutas.ZONA_DE[pickup],
            "dropoff_zone": rutas.ZONA_DE[dropoff],
            "pay_mxn": round(o.pago * o.surge * factor, 1),
        }

    def _shock(self, s: shocks.Shock) -> dict[str, Any]:
        return {
            "type": s.tipo,
            "zone": zonas.ID_POR_NOMBRE.get(s.zona) if s.zona else None,
            "zone_name": s.zona,
            "road": s.calle,
            "starts_at_min": s.t,
            "ends_at_min": s.t + s.duracion_min,
            "multiplier": s.multiplicador,
        }

    def _snapshot(
        self,
        ofertas: list[dict[str, Any]],
        frames: dict[str, list[dict[str, Any]]],
        nuevos: bool,
    ) -> dict[str, Any]:
        vigentes = shocks.en(self.minute, tuple(self.shocks)).shocks
        return {
            "session_id": self.session_id,
            "minute": self.minute,
            "duration_min": self.cfg.duracion_min,
            "start_hour": self.cfg.hora_inicio,
            "seed": self.cfg.seed,
            "status": self.status,
            "active_shocks": [self._shock(s) for s in vigentes],
            "offers_this_tick": ofertas,
            **{a: self._agente(a, frames[a], nuevos) for a in AGENTES},
        }

    def _agente(self, a: str, frames: list[dict[str, Any]], nuevos: bool) -> dict[str, Any]:
        turno = self.turnos[a]
        res = turno.res
        tramos: list[tuple[float, float, int, int]] = []
        if nuevos:  # solo tick consume el cursor: snapshot() no se come los tramos de nadie
            tramos = res.tramos[self._cursor[a]["tramos"] :]
            self._cursor[a]["tramos"] = len(res.tramos)
        sin_mandar = [x for x in tramos if f"{x[2]}-{x[3]}" not in self._claves[a]]
        geometria = self.geometria(sin_mandar) if sin_mandar else {}
        self._claves[a].update(geometria)

        lat, lon = rutas.COORD_DE[turno.pos]
        return {
            "position": turno.pos,
            "coords": [lon, lat],
            "earnings_mxn": round(res.ganado, 2),
            "deliveries": res.entregas,
            "skipped": res.rechazos,
            "cancelled": res.cancelados,
            "route": [
                {"type": p.tipo, "point": p.punto, "order_id": p.oferta_id} for p in turno.ruta
            ],
            "last_decision": self._ultima[a],
            "frames": frames,
            "new_legs": [
                {
                    "t_salida": s,
                    "t_llegada": round(ll, 2),
                    "desde": d,
                    "hasta": h,
                    "clave": f"{d}-{h}",
                }
                for s, ll, d, h in tramos
            ],
            "geometry": geometria,
            "result": self._resultado[a],
        }
