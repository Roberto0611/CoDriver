"""La voz, sin gastar un solo caracter de la cuota: ElevenLabs se simula con MockTransport.

El unico test que pega a la API de verdad se activa con NUEZ_VOZ_LIVE=1 y llave presente.
"""

import os
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backendruta import voice
from voz import stt, tts
from voz.config import Config

MP3 = b"ID3fake-mp3-bytes-" * 4


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return Config(_api_key="k-test", cache_dir=tmp_path / "voz", base_url="https://xi.test")


def cliente_fake(
    status: int = 200,
    cuerpo: bytes = MP3,
    registro: list | None = None,
    detalle: object = "boom",
):
    """Un httpx.Client que responde lo que le digas y anota cada request."""

    def handler(req: httpx.Request) -> httpx.Response:
        if registro is not None:
            registro.append(req)
        if req.url.path.endswith("/speech-to-text"):
            return httpx.Response(
                status,
                json={
                    "text": "  not   that neighborhood ",
                    "language_code": "en",
                    "language_probability": 0.97,
                    "audio_duration_secs": 1.4,
                },
            )
        if status != 200:
            return httpx.Response(status, json={"detail": detalle})
        return httpx.Response(200, content=cuerpo, headers={"content-type": "audio/mpeg"})

    return httpx.Client(transport=httpx.MockTransport(handler))


# --- tts ----------------------------------------------------------------------


def test_normalizar_colapsa_espacios():
    assert tts.normalizar("  Skip   it.\n ") == "Skip it."


def test_cache_key_depende_de_texto_voz_y_modelo(cfg: Config):
    a = tts.cache_key("Skip it.", cfg)
    assert a == tts.cache_key("  Skip it. ", cfg), "misma frase, mismo archivo"
    assert a != tts.cache_key("Take it.", cfg)
    assert a != tts.cache_key(
        "Skip it.", Config(_api_key="k", voice_id="otra", cache_dir=cfg.cache_dir)
    )
    assert a != tts.cache_key(
        "Skip it.", Config(_api_key="k", tts_model="eleven_v3", cache_dir=cfg.cache_dir)
    )


def test_sintetizar_llama_una_vez_y_luego_sirve_de_cache(cfg: Config):
    reqs: list[httpx.Request] = []
    with cliente_fake(registro=reqs) as c:
        assert tts.sintetizar("Skip it.", cfg=cfg, client=c) == MP3
        assert tts.sintetizar("Skip it.", cfg=cfg, client=c) == MP3
    assert len(reqs) == 1, "la segunda vez no toca la red"
    assert tts.cache_path("Skip it.", cfg).exists()
    assert not list(cfg.cache_dir.glob("*.part")), "no quedan parciales"


def test_la_request_lleva_llave_voz_modelo_y_formato(cfg: Config):
    reqs: list[httpx.Request] = []
    with cliente_fake(registro=reqs) as c:
        tts.sintetizar("Skip it.", cfg=cfg, client=c)
    r = reqs[0]
    assert r.method == "POST"
    assert r.url.path == f"/v1/text-to-speech/{cfg.voice_id}/stream"
    assert r.url.params["output_format"] == cfg.output_format
    assert r.headers["xi-api-key"] == "k-test"
    import json

    body = json.loads(r.content)
    assert body["text"] == "Skip it."
    assert body["model_id"] == cfg.tts_model
    assert body["voice_settings"]["speed"] == cfg.speed


def test_stream_da_chunks_y_cache_desde_disco(cfg: Config):
    with cliente_fake() as c:
        chunks = list(tts.stream("Skip it.", cfg=cfg, client=c))
    assert b"".join(chunks) == MP3
    with cliente_fake(status=500) as c:  # si tocara la red, fallaria
        assert list(tts.stream("Skip it.", cfg=cfg, client=c)) == [MP3]


def test_errores_de_api_son_vozerror_con_mensaje_util(cfg: Config):
    for status, palabra in ((401, "llave"), (429, "limite"), (500, "500")):
        with cliente_fake(status=status) as c, pytest.raises(tts.VozError, match=palabra):
            tts.sintetizar("Skip it.", cfg=cfg, client=c)
    assert not tts.cache_path("Skip it.", cfg).exists(), "un error no deja cache"


def test_sin_llave_o_sin_texto_falla_claro(
    cfg: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Sin esto, Config toma la llave del .env de quien corre los tests y el test le
    # pega a ElevenLabs de verdad: gasta cuota y falla segun el estado de la cuenta.
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(sys.modules["voz.config"], "load_dotenv", lambda *a, **k: False)
    sin = Config(_api_key=None, cache_dir=tmp_path / "x")
    with pytest.raises(tts.VozError, match="ELEVENLABS_API_KEY"):
        tts.sintetizar("Skip it.", cfg=sin)
    with pytest.raises(tts.VozError, match="texto"):
        tts.sintetizar("   ", cfg=cfg)


# --- stt ----------------------------------------------------------------------


def test_transcribir_manda_multipart_y_limpia_el_texto(cfg: Config):
    reqs: list[httpx.Request] = []
    with cliente_fake(registro=reqs) as c:
        t = stt.transcribir(b"webm-bytes", nombre="clip.webm", cfg=cfg, client=c)
    assert t.texto == "not that neighborhood"
    assert t.idioma == "en" and t.confianza == 0.97
    r = reqs[0]
    assert r.url.path == "/v1/speech-to-text"
    assert r.headers["xi-api-key"] == "k-test"
    assert b'name="model_id"' in r.content and cfg.stt_model.encode() in r.content
    assert b'filename="clip.webm"' in r.content


def test_transcribir_clip_vacio_falla(cfg: Config):
    with pytest.raises(tts.VozError, match="vacio"):
        stt.transcribir(b"", cfg=cfg)


# --- rutas FastAPI -------------------------------------------------------------


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, cfg: Config):
    monkeypatch.setattr(tts, "config", cfg)
    monkeypatch.setattr(voice, "config", cfg)
    monkeypatch.setattr(voice, "_caida_hasta", 0.0)
    app = FastAPI()
    app.include_router(voice.router)
    return TestClient(app)


def test_say_devuelve_audio_y_marca_cache(
    api: TestClient, monkeypatch: pytest.MonkeyPatch, cfg: Config
):
    monkeypatch.setattr(tts, "stream", lambda text, **kw: iter([MP3[:10], MP3[10:]]))
    r = api.get("/api/voice/say", params={"text": "Skip it."})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/mpeg")
    assert r.headers["x-nuez-cache"] == "miss"
    assert r.content == MP3


def test_say_convierte_vozerror_en_502(api: TestClient, monkeypatch: pytest.MonkeyPatch):
    def truena(text, **kw):
        raise tts.VozError("Falta ELEVENLABS_API_KEY")
        yield  # noqa: B901

    monkeypatch.setattr(tts, "stream", truena)
    r = api.get("/api/voice/say", params={"text": "Skip it."})
    assert r.status_code == 502
    assert "ELEVENLABS_API_KEY" in r.json()["detail"]


def test_tras_una_falla_say_no_espera_a_elevenlabs_pero_sirve_la_cache(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
):
    llamadas: list[str] = []
    reloj = [1000.0]

    def truena(text, **kw):
        llamadas.append(text)
        raise tts.VozError("ElevenLabs rechazo la llave (401)")
        yield  # noqa: B901

    monkeypatch.setattr(tts, "stream", truena)
    monkeypatch.setattr(voice, "_ahora", lambda: reloj[0])

    assert api.get("/api/voice/say", params={"text": "Skip it."}).status_code == 502
    assert api.get("/api/voice/say", params={"text": "Take it."}).status_code == 502
    assert llamadas == ["Skip it."], "la segunda frase no debe esperar otra vez a la API"

    # Lo que ya esta en disco sigue sonando con la voz de Nuez aunque la API este caida.
    monkeypatch.setattr(tts, "en_cache", lambda text, **kw: True)
    monkeypatch.setattr(tts, "stream", lambda text, **kw: iter([MP3]))
    assert api.get("/api/voice/say", params={"text": "Skip it."}).status_code == 200

    reloj[0] += voice.PAUSA_TRAS_FALLA_S + 1
    monkeypatch.setattr(tts, "en_cache", lambda text, **kw: False)
    assert api.get("/api/voice/say", params={"text": "Take it."}).status_code == 200, "reintenta"


def test_solo_una_caida_real_pausa_a_elevenlabs(cfg: Config):
    """401, cuota agotada, 5xx y sin red dicen 'la API no sirve ahorita'; lo demas no."""
    casos = [
        (401, "boom", True),
        (429, {"status": "quota_exceeded", "message": "sin cuota"}, True),
        (429, {"status": "too_many_concurrent_requests", "message": "espera"}, False),
        (503, "boom", True),
    ]
    for status, detalle, pausa in casos:
        with (
            cliente_fake(status=status, detalle=detalle) as c,
            pytest.raises(tts.VozError) as err,
        ):
            tts.sintetizar("Skip it.", cfg=cfg, client=c)
        assert err.value.pausar is pausa, (status, detalle)

    with pytest.raises(tts.VozError) as vacio:
        tts.sintetizar("   ", cfg=cfg)
    assert vacio.value.pausar is False

    def sin_red(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin wifi", request=req)

    with (
        httpx.Client(transport=httpx.MockTransport(sin_red)) as c,
        pytest.raises(tts.VozError) as red,
    ):
        tts.sintetizar("Skip it.", cfg=cfg, client=c)
    assert red.value.pausar is True


def test_errores_que_no_son_caida_no_pausan_la_voz(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
):
    llamadas: list[str] = []

    def ocupada(text, **kw):
        llamadas.append(text)
        raise tts.VozError("ElevenLabs: demasiadas a la vez (429)", pausar=False)
        yield  # noqa: B901

    monkeypatch.setattr(tts, "stream", ocupada)
    assert api.get("/api/voice/say", params={"text": "   "}).status_code == 502
    assert api.get("/api/voice/say", params={"text": "Skip it."}).status_code == 502
    assert api.get("/api/voice/say", params={"text": "Take it."}).status_code == 502
    assert llamadas == ["   ", "Skip it.", "Take it."], "cada frase vuelve a intentar la API"


def test_dos_streams_de_la_misma_frase_a_la_vez_no_truenan(cfg: Config):
    """El prefetch y la reproduccion pueden pedir la misma frase al mismo tiempo."""

    class Lento(httpx.SyncByteStream):
        def __init__(self, tag: bytes, n: int, pausa: float):
            self.tag, self.n, self.pausa = tag, n, pausa

        def __iter__(self):
            for _ in range(self.n):
                time.sleep(self.pausa)
                yield self.tag * 100

    def cliente(tag: bytes, n: int, pausa: float) -> httpx.Client:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, stream=Lento(tag, n, pausa))

        return httpx.Client(transport=httpx.MockTransport(handler))

    errores: list[BaseException] = []
    recibido: dict[bytes, bytes] = {}

    def uno(tag: bytes, n: int, pausa: float, espera: float) -> None:
        time.sleep(espera)
        try:
            with cliente(tag, n, pausa) as c:
                recibido[tag] = tts.sintetizar("Skip it.", cfg=cfg, client=c)
        except BaseException as e:  # noqa: BLE001 - el test reporta cualquier falla
            errores.append(e)

    hilos = [
        threading.Thread(target=uno, args=(b"A", 30, 0.01, 0.0)),
        threading.Thread(target=uno, args=(b"B", 18, 0.013, 0.05)),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert not errores, errores
    assert recibido == {b"A": b"A" * 3000, b"B": b"B" * 1800}
    guardado = tts.cache_path("Skip it.", cfg).read_bytes()
    assert guardado in (b"A" * 3000, b"B" * 1800), "la cache es una copia entera, no una mezcla"
    assert not list(cfg.cache_dir.glob("*.part")), "no quedan temporales"


def test_say_rechaza_texto_vacio_o_enorme(api: TestClient):
    assert api.get("/api/voice/say", params={"text": ""}).status_code == 422
    assert (
        api.get("/api/voice/say", params={"text": "x" * (voice.MAX_CHARS + 1)}).status_code == 422
    )


def test_listen_transcribe_el_archivo(api: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        stt,
        "transcribir",
        lambda audio, **kw: stt.Transcripcion("not that neighborhood", "en", 0.9, 1.0),
    )
    r = api.post("/api/voice/listen", files={"file": ("clip.webm", b"webm", "audio/webm")})
    assert r.status_code == 200
    assert r.json() == {"text": "not that neighborhood", "language": "en", "confidence": 0.9}


def test_config_no_expone_la_llave(api: TestClient, cfg: Config):
    j = api.get("/api/voice/config").json()
    assert j["has_key"] is True and j["voice_id"] == cfg.voice_id
    assert "k-test" not in str(j)


# --- en vivo (opcional) ----------------------------------------------------------


@pytest.mark.skipif(
    os.getenv("NUEZ_VOZ_LIVE") != "1" or not os.getenv("ELEVENLABS_API_KEY"),
    reason="NUEZ_VOZ_LIVE=1 y ELEVENLABS_API_KEY para pegarle a ElevenLabs de verdad",
)
def test_en_vivo_genera_mp3(tmp_path: Path):
    cfg = Config(cache_dir=tmp_path / "voz")
    audio = tts.sintetizar("Skip it.", cfg=cfg)
    assert len(audio) > 1000
    assert audio[:3] == b"ID3" or audio[0] == 0xFF, "deberia ser MP3"
