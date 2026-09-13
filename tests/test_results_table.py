"""La tabla de Results conserva sus unidades y no es una suma a mano."""

from argparse import Namespace
from types import SimpleNamespace

from scripts.results_table import escribir_tabla, metricas


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


def encabezado(tmp_path, **config):
    """Las lineas de comentario que van arriba del CSV, sin los renglones."""
    args = Namespace(salida=tmp_path / "tabla.csv", **config)
    escribir_tabla([], args)
    return [linea for linea in args.salida.read_text("utf-8").splitlines() if linea.startswith("#")]


def test_el_encabezado_nombra_los_dos_conjuntos_de_seeds_y_n(tmp_path):
    # El protocolo topa Results en 3 si la diapositiva no dice cual es cual.
    lineas = encabezado(tmp_path, turnos=50, duracion=120, hora_inicio=14, vehiculo="moto")

    assert "# Tuning seeds (TUNEO): 0-1999, used for the value table." in lineas
    assert "# Reporting seeds (REPORTE): 2000-2049, n=50 held-out shifts." in lineas


def test_el_encabezado_describe_la_config_completa(tmp_path):
    lineas = encabezado(tmp_path, turnos=20, duracion=480, hora_inicio=16, vehiculo="bike")

    assert (
        "# Config: vehicle bike, start 16:00, anchor Tec, 480-min shift, 10-min margin." in lineas
    )
    assert "# Reporting seeds (REPORTE): 2000-2019, n=20 held-out shifts." in lineas


def test_el_encabezado_dice_limites_del_vehiculo_y_regla_de_fin_de_turno(tmp_path):
    # El simulador exige regresar al ancla; /decide no. La tabla dice cual midio.
    lineas = encabezado(tmp_path, turnos=50, duracion=120, hora_inicio=14, vehiculo="moto")

    assert (
        "# Limits (moto): 20 kg, 20 L, 3 orders. Shift end: deliver and be back at anchor Tec"
        " by shift end minus margin." in lineas
    )


def test_el_encabezado_no_vende_al_oracle_como_optimo_teorico(tmp_path):
    # oracle.resolver se queda con lo mejor entre su busqueda en haz y las cinco
    # politicas online: es el mejor plan offline que conocemos, no una cota probada.
    lineas = encabezado(tmp_path, turnos=50, duracion=120, hora_inicio=14, vehiculo="moto")
    texto = "\n".join(lineas)

    assert "best-known offline plan" in texto
    assert "not a proven upper bound" in texto
    assert "theoretical" not in texto
