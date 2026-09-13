"""El flujo CLI calibra offline y evalua la misma configuracion en seeds nuevos."""

import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_calibracion_y_comparacion_con_ventana_y_vehiculo_propios(tmp_path):
    tabla = tmp_path / "valor.json"
    crear = subprocess.run(
        [
            sys.executable,
            "valor.py",
            "--duracion",
            "137",
            "--hora-inicio",
            "8",
            "--vehiculo",
            "bike",
            "--turnos",
            "3",
            "--salida",
            str(tabla),
        ],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "TUNEO" in crear.stdout
    datos = json.loads(tabla.read_text(encoding="utf-8"))
    assert datos["calibracion"] == {
        "duracion_min": 137,
        "hora_inicio": 8,
        "vehiculo": "bike",
        "seeds": {"conjunto": "TUNEO", "inicio": 0, "cantidad": 3},
    }
    comparar = subprocess.run(
        [
            sys.executable,
            "comparar.py",
            "2",
            "--duracion",
            "137",
            "--hora-inicio",
            "8",
            "--vehiculo",
            "bike",
            "--tabla",
            str(tabla),
        ],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "REPORTE 2000-2001" in comparar.stdout
    assert "137 min; inicio: 8:00; bike" in comparar.stdout


def test_cli_rechaza_tabla_corta_para_ocho_horas():
    resultado = subprocess.run(
        [sys.executable, "comparar.py", "1", "--duracion", "480", "--tabla", "V.json"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 2
    assert "la tabla cubre 120 min" in resultado.stderr


def test_cli_de_510_minutos_reporta_la_tabla_que_realmente_uso():
    resultado = subprocess.run(
        [sys.executable, "comparar.py", "1", "--duracion", "510"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "tabla: V_510.json" in resultado.stdout
