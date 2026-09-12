"""Dibuja un turno completo a PNG: que acepto, que rechazo y por donde anduvo.

Uso:  python data/ver_turno.py [seed]

Es para VER que el simulador se comporte como un repartidor de verdad.
El demo de a de veras va en el frontend; esto es la radiografia.
"""

import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).parent.parent))

import rutas  # noqa: E402
from contrato import ConfigTurno, Punto  # noqa: E402
from mundo import ZONAS  # noqa: E402
from sim import indice_de, politica_greedy, simular  # noqa: E402

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 1


def main():
    tec = rutas.COORD_DE[rutas.puntos_de("Tec")[0]]
    cfg = ConfigTurno(duracion_min=120, ancla=Punto("Tec", *tec), seed=SEED, hora_inicio=14)
    res = simular(cfg, politica_greedy)
    aceptadas = {d.oferta_id for d in res.decisiones if d.accion == "aceptar"}

    fig, ax = plt.subplots(figsize=(12, 12), facecolor="#0b0b0f")
    ax.set_facecolor("#0b0b0f")

    # Zonas de fondo
    for zona, (lat, lon, radio) in ZONAS.items():
        ax.add_patch(plt.Circle((lon, lat), radio / 111_000, color="#1e293b",
                                alpha=0.35, zorder=0))
        ax.text(lon, lat, zona, color="#475569", fontsize=7, ha="center", zorder=1)

    # Los 210 puntos donde pueden aparecer pedidos
    ax.scatter([c[1] for c in rutas.COORD_DE], [c[0] for c in rutas.COORD_DE],
               s=4, c="#334155", zorder=2)

    # Ofertas: rechazadas en rojo tenue, aceptadas en verde
    for o in res.ofertas:
        p, d = indice_de(o.pickup), indice_de(o.dropoff)
        xs = [rutas.COORD_DE[p][1], rutas.COORD_DE[d][1]]
        ys = [rutas.COORD_DE[p][0], rutas.COORD_DE[d][0]]
        if o.id in aceptadas:
            ax.plot(xs, ys, color="#22c55e", lw=2.2, alpha=0.9, zorder=4)
            ax.scatter(xs[0], ys[0], s=45, c="#22c55e", marker="s", zorder=5)
        else:
            ax.plot(xs, ys, color="#ef4444", lw=0.6, alpha=0.22, zorder=3)

    # Por donde anduvo de verdad
    if res.trayecto:
        xs = [rutas.COORD_DE[p][1] for _, p, _ in res.trayecto]
        ys = [rutas.COORD_DE[p][0] for _, p, _ in res.trayecto]
        ax.plot(xs, ys, color="#fbbf24", lw=2.5, alpha=0.95, zorder=6,
                marker="o", ms=5, label="recorrido")

    ax.scatter(tec[1], tec[0], s=320, c="#38bdf8", marker="*", zorder=7, label="Tec (ancla)")

    tarde = "LLEGO TARDE" if res.llego_tarde else "llego a tiempo"
    ax.set_title(
        f"Turno seed={SEED}  ·  {len(res.ofertas)} ofertas  ·  {res.entregas} entregas  "
        f"·  ${res.ganado:.0f}  ·  {tarde}\n"
        f"verde = aceptadas    rojo = rechazadas    amarillo = por donde anduvo",
        color="#e2e8f0", fontsize=11, pad=16)
    ax.legend(facecolor="#1e293b", labelcolor="#e2e8f0", loc="lower left")
    ax.set_aspect(1 / 0.9)
    ax.axis("off")

    salida = Path(__file__).parent / f"turno_{SEED}.png"
    fig.savefig(salida, dpi=110, facecolor="#0b0b0f", bbox_inches="tight")
    print(f"{salida}  (${res.ganado:.0f}, {res.entregas} entregas, {res.rechazos} rechazos)")


if __name__ == "__main__":
    main()
