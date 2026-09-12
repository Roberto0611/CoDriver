"""La tabla de Results conserva sus unidades y no es una suma a mano."""

from types import SimpleNamespace

from scripts.results_table import metricas


def corrida(*, ganado, entregas, acciones, con_carga, sin_carga, tarde=False, violaciones=0):
    return SimpleNamespace(
        ganado=ganado,
        entregas=entregas,
        decisiones=[SimpleNamespace(accion=accion) for accion in acciones],
        km_con_carga=con_carga,
        km_sin_carga=sin_carga,
        llego_tarde=tarde,
        violaciones=violaciones,
    )


def test_metricas_agrega_los_km_y_no_promedia_porcentajes_de_turnos():
    filas = [
        corrida(
            ganado=120,
            entregas=2,
            acciones=("aceptar", "saltar"),
            con_carga=9,
            sin_carga=1,
        ),
        corrida(
            ganado=60,
            entregas=1,
            acciones=("aceptar",),
            con_carga=0,
            sin_carga=10,
            tarde=True,
            violaciones=1,
        ),
    ]

    assert metricas(filas, 120) == {
        "mean_earnings_mxn": "90.00",
        "median_earnings_mxn": "90.00",
        "mean_mxn_per_hr": "45.00",
        "accept_rate_pct": "66.67",
        "orders_completed": "1.50",
        "deadhead_pct_of_km": "55.00",
        "deadline_misses": 1,
        "safety_violations": 1,
    }
