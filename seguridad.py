"""LAS CINCO RESTRICCIONES DE SEGURIDAD. Este es el archivo que abre el juez.

Estan en codigo, no en el prompt de un modelo: ninguna se compra con dinero y
ningun LLM las puede reescribir. Las DOS politicas (baseline y Nuez) entran por
`revisar`, asi que ninguna de las dos puede cometer una violacion.

  1. flagged_zone_night   no entregar en zona marcada despues de las 22:00
  2. mandatory_break      descanso de 20 min tras 4 h continuas
  3. heat_rule            maximo 90 min continuos entre 12:00 y 16:00
  4. shift_end_infeasible no aceptar lo que no se termina antes del fin del turno
  5. vehicle_capacity     peso, volumen y pedidos segun el vehiculo

El orden importa: se revisa seguridad ANTES que dinero, siempre. Por eso una
oferta que rompe una regla la sigue rompiendo aunque suba el surge.
"""

from dataclasses import dataclass
from typing import Any

from mundo import es_segura

# --- 2 y 3: manejar seguido cansa, y a las 3 de la tarde en MTY cansa mas -----
DESCANSO_MIN = 20  # lo que dura el descanso; 20 min parado resetean el contador
LIMITE_CONTINUO_MIN = 240  # 4 horas seguidas y se para, pase lo que pase
LIMITE_CALOR_MIN = 90  # entre 12 y 4 el limite baja a hora y media
HORAS_CALOR = range(12, 16)


# --- 5: el vehiculo no es solo velocidad, es cuanto te cabe ------------------
@dataclass(frozen=True)
class Perfil:
    peso_kg: float  # cuanto aguanta cargando
    volumen_l: float  # cuanto le cabe en la caja
    pedidos: int  # cuantos puede llevar a la vez
    velocidad: float  # multiplicador de tiempo contra la moto: >1 es mas lento
    costo_km: float  # pesos de gasolina


# ponytail: numeros a ojo (una caja de moto real son ~45 L). Perilla de calibracion.
# rutas.minutos aplica velocidad tanto al planear como al recorrer cada tramo.
VEHICULOS = {
    "moto": Perfil(peso_kg=20, volumen_l=60, pedidos=3, velocidad=1.00, costo_km=1.8),
    "car": Perfil(peso_kg=100, volumen_l=400, pedidos=6, velocidad=1.15, costo_km=3.2),
    "bike": Perfil(peso_kg=8, volumen_l=30, pedidos=2, velocidad=1.80, costo_km=0.0),
}


def limite_continuo(hora: int) -> int:
    """Cuantos minutos seguidos se puede manejar a esta hora."""
    return LIMITE_CALOR_MIN if hora % 24 in HORAS_CALOR else LIMITE_CONTINUO_MIN


def revisar(
    *,
    vehiculo: str,
    hora: int,
    zona_dropoff: str,
    minutos_manejando: int,
    carga_kg: float,
    carga_l: float,
    pedidos_en_vuelo: int,
    minutos_para_terminar: float,
    minutos_de_turno: float,
) -> tuple[str, str] | None:
    """La unica puerta. Devuelve (binding_constraint, frase) o None si no bloquea.

    `carga_*` y `pedidos_en_vuelo` YA incluyen el pedido nuevo; `minutos_para_terminar`
    es lo que falta para dejar el ultimo paquete y estar de vuelta en el ancla.
    """
    v = VEHICULOS[vehiculo]

    if not es_segura(zona_dropoff, hora):
        return "flagged_zone_night", f"No te mando a {zona_dropoff} despues de las 10 de la noche."

    if pedidos_en_vuelo > v.pedidos:
        return "vehicle_capacity", f"En {vehiculo} solo caben {v.pedidos} pedidos a la vez."
    if carga_kg > v.peso_kg:
        return "vehicle_capacity", (
            f"Son {carga_kg:.1f} kg y en {vehiculo} el limite son {v.peso_kg:.0f} kg."
        )
    if carga_l > v.volumen_l:
        return "vehicle_capacity", (
            f"Son {carga_l:.0f} litros y en la caja de {vehiculo} caben {v.volumen_l:.0f}."
        )

    if minutos_manejando >= limite_continuo(hora):
        if hora % 24 in HORAS_CALOR:
            return "heat_rule", (
                f"Llevas {minutos_manejando} min seguidos bajo el sol de las {hora}. "
                f"Para {DESCANSO_MIN} minutos."
            )
        return "mandatory_break", (
            f"Llevas {minutos_manejando} min manejando sin parar: toca el descanso "
            f"obligatorio de {DESCANSO_MIN} minutos."
        )

    if minutos_para_terminar > minutos_de_turno:
        return (
            "shift_end_infeasible",
            "No alcanzas a entregarlo y volver antes de que acabe tu turno.",
        )

    return None


def caso(**cambios: Any) -> tuple[str, str] | None:
    """Un pedido normal en moto, con lo que se quiera cambiar encima."""
    args: dict[str, Any] = dict(
        vehiculo="moto",
        hora=14,
        zona_dropoff="Valle",
        minutos_manejando=0,
        carga_kg=2.0,
        carga_l=8.0,
        pedidos_en_vuelo=1,
        minutos_para_terminar=20.0,
        minutos_de_turno=100.0,
    )
    return revisar(**{**args, **cambios})


def demo():
    def bloquea(**cambios: Any) -> str:
        r = caso(**cambios)
        assert r is not None, f"deberia bloquear: {cambios}"
        assert len(r[1].split()) < 40, "la razon va bajo 40 palabras"
        return r[0]

    assert caso() is None, "un pedido normal no deberia chocar con nada"

    assert bloquea(zona_dropoff="Escobedo", hora=23) == "flagged_zone_night"
    assert caso(zona_dropoff="Escobedo", hora=21) is None, "a las 21:00 aun se puede"
    assert bloquea(carga_kg=25.0) == "vehicle_capacity"
    assert bloquea(vehiculo="bike", carga_kg=12.0) == "vehicle_capacity"
    assert caso(vehiculo="car", carga_kg=12.0) is None, "en carro si cabe"
    assert bloquea(minutos_manejando=95) == "heat_rule", "a las 14 el limite son 90 min"
    assert caso(minutos_manejando=95, hora=19) is None, "sin sol aguanta las 4 horas"
    assert bloquea(minutos_manejando=250, hora=19) == "mandatory_break"
    assert bloquea(minutos_para_terminar=200.0) == "shift_end_infeasible"

    # Lo que mide el protocolo: la seguridad NO se compra. El dinero ni siquiera
    # entra a esta funcion, asi que subir el surge no puede volver un no en un si.

    print(f"{'limite':<22} {'moto':>8} {'car':>8} {'bike':>8}")
    for campo in ("peso_kg", "volumen_l", "pedidos"):
        fila = "".join(f"{getattr(VEHICULOS[v], campo):>9}" for v in VEHICULOS)
        print(f"{campo:<22}{fila}")
    print(f"\nminutos continuos: {LIMITE_CALOR_MIN} de 12 a 4 pm, {LIMITE_CONTINUO_MIN} el resto")
    print(f"descanso que resetea el contador: {DESCANSO_MIN} min")
    print("OK: las cinco restricciones responden")


if __name__ == "__main__":
    demo()
