"""Las disrupciones a media jornada: `surge`, `closure`, `rain`, `delay`.

El brief exige al menos una en vivo durante el demo, y el protocolo las inyecta
con el evento `shock` del JSONL. Los cuatro tipos hacen dos cosas MUY distintas y
no hay que mezclarlas:

    FISICA (aqui, en codigo)            JUICIO (la capa de Gemini)
    el cierre hace que el viaje         cuanto conviene evitar esa zona
    tarde mas, de verdad                (estrategia.multiplicador_zona)

Si cerraron una avenida, el viaje tarda mas aunque el modelo este caido, aunque
opine otra cosa, aunque no exista. Un cierre no es una opinion. Por eso la fisica
vive en la ruta rapida y determinista, y el modelo solo mueve las ganas.

`Activos` es una FOTO inmutable de lo que esta vigente en un minuto, y se pasa como
argumento a quien la necesite. La tentacion es una variable global "esta lloviendo":
eso rompe el replay, porque el orden en que cada quien la lea cambia el resultado y
no queda en el log. Como argumento, es un dato mas de la decision y se audita.
"""

import random
from dataclasses import dataclass
from typing import Literal

Tipo = Literal["surge", "closure", "rain", "delay"]

# ponytail: cuanto se estira el tiempo. Numeros a ojo, perilla de calibracion.
# Un cierre real desvia por calles secundarias; la lluvia en MTY no para la ciudad
# pero si la vuelve lenta en todas partes.
FACTOR_CIERRE = 2.2
FACTOR_LLUVIA = 1.35

# Generacion para las corridas medidas: una disrupcion por hora, en promedio.
POR_MINUTO = 1 / 60
SAL = 0x510C  # semilla aparte: NO toca el dado de las ofertas


@dataclass(frozen=True)
class Shock:
    """Una disrupcion. Los campos que no aplican a su tipo van vacios."""

    t: int  # minuto del turno en que entra
    tipo: Tipo
    duracion_min: int
    zona: str | None = None  # surge y closure
    multiplicador: float = 1.0  # surge
    calle: str | None = None  # closure: solo para poder nombrarla en la razon
    oferta_id: str | None = None  # delay
    retraso_min: int = 0  # delay

    def vigente_en(self, t: int) -> bool:
        return self.t <= t < self.t + self.duracion_min


@dataclass(frozen=True)
class Activos:
    """Lo que esta pasando en este minuto. Inmutable y explicito."""

    shocks: tuple[Shock, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.shocks)

    def factor_tiempo(self, zona_a: str, zona_b: str) -> float:
        """Cuanto se estira un tramo entre esas dos zonas. 1.0 si no pasa nada."""
        factor = 1.0
        for s in self.shocks:
            if s.tipo == "rain":
                factor *= FACTOR_LLUVIA
            elif s.tipo == "closure" and s.zona in (zona_a, zona_b):
                factor *= FACTOR_CIERRE
        return factor

    def factor_pago(self, zona_pickup: str) -> float:
        """El surge de la plataforma. Se cotiza donde nace el pedido."""
        factor = 1.0
        for s in self.shocks:
            if s.tipo == "surge" and s.zona == zona_pickup:
                factor *= s.multiplicador
        return factor

    def retraso(self, oferta_id: str) -> int:
        """Minutos que se atraso el restaurante de ESE pedido."""
        return sum(s.retraso_min for s in self.shocks if s.oferta_id == oferta_id)

    def frase(self, zona_a: str, zona_b: str) -> str:
        """Como nombrar la disrupcion en la razon. Cadena vacia si no aplica ninguna."""
        for s in self.shocks:
            if s.tipo == "closure" and s.zona in (zona_a, zona_b):
                donde = s.calle or s.zona
                return f"Cerraron {donde}"
            if s.tipo == "rain":
                return "Con la lluvia"
        return ""


NINGUNO = Activos()


def en(t: int, todos: tuple[Shock, ...]) -> Activos:
    """La foto del minuto t. Los shocks expiran solos a los `duracion_min`."""
    if not todos:
        return NINGUNO
    return Activos(tuple(s for s in todos if s.vigente_en(t)))


def generar(seed: int, duracion_min: int, zonas: tuple[str, ...], ofertas=()) -> tuple[Shock, ...]:
    """Disrupciones reproducibles para las corridas medidas.

    Usa su PROPIO dado. El stream de ofertas depende solo de `cfg.seed` y se
    escribe completo antes de que el agente decida nada, asi que generar shocks
    aparte lo deja byte por byte identico: el numero sin shocks no se mueve.
    """
    rng = random.Random(seed ^ SAL)
    fuera: list[Shock] = []
    for t in range(duracion_min):
        if rng.random() > POR_MINUTO:
            continue
        tipo: Tipo = rng.choice(["surge", "closure", "rain", "delay"])
        if tipo == "surge":
            fuera.append(
                Shock(
                    t,
                    "surge",
                    rng.randint(15, 40),
                    zona=rng.choice(zonas),
                    multiplicador=round(rng.uniform(1.3, 1.9), 2),
                )
            )
        elif tipo == "closure":
            fuera.append(
                Shock(t, "closure", rng.randint(20, 60), zona=rng.choice(zonas), calle=None)
            )
        elif tipo == "rain":
            fuera.append(Shock(t, "rain", rng.randint(25, 60)))
        else:
            # El delay necesita un pedido al que pegarle: uno que siga por venir.
            futuras = [o for o in ofertas if o.t_aparece >= t]
            if futuras:
                objetivo = rng.choice(futuras)
                fuera.append(
                    Shock(
                        t,
                        "delay",
                        duracion_min - t,  # una vez tarde, tarde para siempre
                        oferta_id=objetivo.id,
                        retraso_min=rng.randint(8, 20),
                    )
                )
    return tuple(fuera)


def demo():
    assert not NINGUNO, "sin shocks la foto es falsa"
    assert NINGUNO.factor_tiempo("Tec", "Centro") == 1.0
    assert NINGUNO.factor_pago("Tec") == 1.0
    assert NINGUNO.frase("Tec", "Centro") == ""

    cierre = Shock(30, "closure", 40, zona="Centro", calle="Constitucion")
    lluvia = Shock(10, "rain", 30)
    surge = Shock(0, "surge", 20, zona="Tec", multiplicador=1.6)

    # A los 45 min ya expiraron el surge (0-20) y la lluvia (10-40); queda el cierre.
    hoy = en(45, (cierre, lluvia, surge))
    assert len(hoy.shocks) == 1, "a los 45 min solo sigue vivo el cierre"
    assert hoy.factor_tiempo("Tec", "Centro") == FACTOR_CIERRE, "el cierre toca ese tramo"
    assert hoy.factor_tiempo("Tec", "Valle") == 1.0, "y no toca los demas"
    assert hoy.frase("Tec", "Centro") == "Cerraron Constitucion"

    temprano = en(15, (cierre, lluvia, surge))
    assert temprano.factor_tiempo("Tec", "Valle") == FACTOR_LLUVIA, "la lluvia es en toda la ciudad"
    assert temprano.factor_pago("Tec") == 1.6
    assert temprano.factor_pago("Valle") == 1.0

    assert en(90, (cierre, lluvia, surge)).shocks == (), "todos expiran solos"

    zonas = ("Tec", "Centro", "Valle")
    a = generar(0, 120, zonas)
    assert a == generar(0, 120, zonas), "mismo seed, mismos shocks: el replay depende de esto"
    assert generar(1, 120, zonas) != a, "otro seed, otras disrupciones"
    # No todos los turnos traen una: a ~1 por hora, algunos salen limpios (el 7, p.ej.).
    # Para el demo la disrupcion se inyecta a mano, no se espera a que caiga sola.
    assert a, "el seed 0 si trae disrupciones"

    print(f"seed 0, turno de 120 min -> {len(a)} disrupciones")
    for s in a:
        extra = f" en {s.zona}" if s.zona else ""
        print(f"  min {s.t:>3}  {s.tipo:<8} {s.duracion_min:>3} min{extra}")
    print("OK")


if __name__ == "__main__":
    demo()
