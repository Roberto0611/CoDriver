"""Las perillas que el modelo SI puede mover, y hasta donde.

El motor decide solo, en microsegundos, leyendo este objeto de memoria. El modelo
corre aparte y lo unico que hace es proponer una `Estrategia` nueva. Nunca ve un
pedido, nunca contesta un ping, nunca entra a la ventana de decision.

Tres perillas, y ninguna es de seguridad:

    margen_mxn          que tan exigente es con el dinero
    descuento_parado    cuanto vale un minuto estando quieto
    multiplicador_zona  encarecer el tiempo hacia una zona (lluvia, cierre, concierto)

Las cinco restricciones duras viven en `seguridad.py` y **ningun modelo las alcanza**.
Si el modelo dijera "metete a Escobedo a las 11 PM que pagan bien", el motor dice que
no igual: el dinero ni siquiera entra a esa funcion.

`sanear` es la otra mitad de la promesa. Un modelo puede alucinar, puede venir
envenenado por un prompt en un nombre de calle, o simplemente puede equivocarse de
unidades. Los rangos de aqui son el limite de cuanto daño puede hacer: un margen de
$9999 apagaria al repartidor, y esto lo recorta a 12 antes de que llegue al motor.
"""

from dataclasses import dataclass, field, replace
from typing import Any

import mundo

# Rangos duros. Fuera de esto no es una estrategia, es un bug.
# ponytail: el techo del margen esta MEDIDO, no inventado. Barrido en 120 seeds de
# TUNEO (120 min, moto, 14:00), ganancia media por turno:
#     margen   0     1     2     4     8    12    22    40
#     $      258   260   260   264   265   261   235   142
# De 0 a 12 el motor nunca se lastima; de ahi para arriba se apaga solo. 12 es el
# ultimo valor seguro, asi que hasta ahi llega lo que el modelo puede mover.
MARGEN_MAX = 12.0
DESCUENTO_MIN, DESCUENTO_MAX = 0.1, 1.0
ZONA_MIN, ZONA_MAX = 0.5, 3.0


@dataclass(frozen=True)
class Estrategia:
    """Lo que el motor lee en cada ping. Inmutable: se reemplaza entera, no se muta."""

    margen_mxn: float = 1.0
    descuento_parado: float = 0.5
    multiplicador_zona: dict[str, float] = field(default_factory=dict)
    fuente: str = "base"  # base | gemini | falso
    nota: str = ""  # una frase de por que, para el JSONL y para la voz

    def precio_de_zona(self, zona: str) -> float:
        return self.multiplicador_zona.get(zona, 1.0)

    def resumen(self) -> dict[str, Any]:
        """Lo que va al JSONL en `strategy_update` y a `explain_decision`."""
        return {
            "source": self.fuente,
            "min_edge_mxn": self.margen_mxn,
            "idle_discount": self.descuento_parado,
            "zone_multipliers": dict(self.multiplicador_zona),
            "note": self.nota,
        }


# Los valores de hoy. Mientras nadie actualice la estrategia, el agente se comporta
# EXACTAMENTE igual que cuando se midio el +29.2%. El numero no se apuesta a que un
# modelo se porte bien.
BASE = Estrategia()


def sanear(crudo: Any, fuente: str = "gemini") -> Estrategia:
    """Convierte lo que devolvio el modelo en una Estrategia usable, o revienta.

    Recorta en vez de rechazar: una perilla fuera de rango casi siempre es un error
    de unidades, y quedarse con la estrategia vieja por un decimal seria peor. Lo que
    si se rechaza es lo que no se puede interpretar.
    """
    if not isinstance(crudo, dict):
        raise ValueError(f"la estrategia debe ser un objeto, llego {type(crudo).__name__}")

    def numero(clave: str, base: float, bajo: float, alto: float) -> float:
        valor = crudo.get(clave, base)
        try:
            return min(alto, max(bajo, float(valor)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{clave} no es un numero: {valor!r}") from exc

    zonas: dict[str, float] = {}
    crudas = crudo.get("multiplicador_zona") or crudo.get("zone_multipliers") or {}
    if not isinstance(crudas, dict):
        raise ValueError("multiplicador_zona debe ser un objeto zona -> factor")
    for zona, factor in crudas.items():
        # Una zona inventada se ignora en silencio: el modelo no puede crear geografia.
        if zona not in mundo.ZONAS:
            continue
        try:
            zonas[zona] = min(ZONA_MAX, max(ZONA_MIN, float(factor)))
        except (TypeError, ValueError):
            continue

    nota = str(crudo.get("nota") or crudo.get("note") or "")
    return Estrategia(
        margen_mxn=numero("margen_mxn", BASE.margen_mxn, 0.0, MARGEN_MAX),
        descuento_parado=numero(
            "descuento_parado", BASE.descuento_parado, DESCUENTO_MIN, DESCUENTO_MAX
        ),
        multiplicador_zona=zonas,
        fuente=fuente,
        nota=nota[:200],
    )


def marcar_vieja(actual: Estrategia) -> Estrategia:
    """La misma estrategia, anotada como heredada de cuando el modelo si respondia."""
    if actual.fuente.endswith("_vieja"):
        return actual
    return replace(actual, fuente=f"{actual.fuente}_vieja")


def demo():
    assert BASE.margen_mxn == 1.0 and BASE.descuento_parado == 0.5
    assert BASE.precio_de_zona("Centro") == 1.0, "sin estrategia nadie encarece nada"

    # Lo que el modelo deberia devolver un dia de lluvia.
    buena = sanear({"margen_mxn": 3.5, "multiplicador_zona": {"Centro": 1.6}, "nota": "llueve"})
    assert buena.margen_mxn == 3.5
    assert buena.precio_de_zona("Centro") == 1.6
    assert buena.precio_de_zona("Valle") == 1.0

    # Y lo que pasa cuando alucina. Ninguna de estas puede apagar al repartidor.
    loca = sanear({"margen_mxn": 9999, "descuento_parado": -3, "multiplicador_zona": {"Narnia": 9}})
    assert loca.margen_mxn == MARGEN_MAX
    assert loca.descuento_parado == DESCUENTO_MIN
    assert loca.multiplicador_zona == {}, "el modelo no puede inventar zonas"

    for basura in ("una frase", 42, None):
        try:
            sanear(basura)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{basura!r} no deberia pasar por estrategia")

    assert marcar_vieja(buena).fuente == "gemini_vieja"
    assert marcar_vieja(marcar_vieja(buena)).fuente == "gemini_vieja", "no se apila el sufijo"

    print(f"base:  {BASE.resumen()}")
    print(f"lluvia:{buena.resumen()}")
    print(f"loca:  {loca.resumen()}   <- recortada, no rechazada")
    print("OK: el modelo mueve perillas, dentro de rango, y nunca toca seguridad")


if __name__ == "__main__":
    demo()
