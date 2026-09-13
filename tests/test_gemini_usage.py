"""Telemetria del asesor Gemini: evidencia, nunca una dependencia de la ruta rapida."""

from backendruta.strategy import CapaEstrategia, RespuestaModelo, UsoTokens


def respuesta(_contexto):
    return RespuestaModelo(
        propuesta={"margen_mxn": 2.0, "nota": "traffic changed"},
        uso=UsoTokens(entrada=120, salida=30),
        modelo="gemini-test",
    )


def test_uso_acumula_llamadas_tokens_y_costo_configurable(monkeypatch):
    monkeypatch.setenv("GEMINI_INPUT_USD_PER_MILLION", "0.10")
    monkeypatch.setenv("GEMINI_OUTPUT_USD_PER_MILLION", "0.40")
    monkeypatch.setenv("USD_TO_MXN", "18")
    capa = CapaEstrategia(respuesta, fuente="gemini")

    assert capa.refrescar() is True
    uso = capa.estado_publico()["gemini_usage"]

    assert uso == {
        "provider": "gemini",
        "model": "gemini-test",
        "calls": 1,
        "successful_calls": 1,
        "failed_calls": 0,
        "input_tokens": 120,
        "output_tokens": 30,
        "total_tokens": 150,
        "estimated_cost_usd": 0.000024,
        "estimated_cost_mxn": 0.000432,
        "cost_configured": True,
        "interval_s": 300.0,
        "interval_simulated_min": 30,
    }


def test_uso_cuenta_falla_sin_inventar_tokens():
    def caido(_contexto):
        raise RuntimeError("network down")

    capa = CapaEstrategia(caido, fuente="gemini")
    assert capa.refrescar() is False
    uso = capa.estado_publico()["gemini_usage"]
    assert (uso["calls"], uso["successful_calls"], uso["failed_calls"]) == (1, 0, 1)
    assert uso["total_tokens"] == 0
    assert uso["estimated_cost_usd"] is None


def test_suplente_local_no_se_vende_como_uso_de_gemini():
    capa = CapaEstrategia(respuesta, fuente="falso")
    capa.refrescar()
    assert capa.estado_publico()["gemini_usage"]["calls"] == 0
