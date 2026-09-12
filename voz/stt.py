"""Audio -> texto. ElevenLabs Scribe. Es el canal de ENTRADA: el repartidor contesta.

    stt.transcribir(audio_bytes, nombre="clip.webm") -> "not that neighborhood"

Acepta lo que grabe el navegador (webm/opus de MediaRecorder) o cualquier formato comun.
"""

from dataclasses import dataclass

import httpx

from voz.config import Config, config
from voz.tts import VozError, _explicar


@dataclass(frozen=True)
class Transcripcion:
    texto: str
    idioma: str | None
    confianza: float | None
    duracion_s: float | None


def transcribir(
    audio: bytes,
    *,
    nombre: str = "clip.webm",
    cfg: Config = config,
    client: httpx.Client | None = None,
) -> Transcripcion:
    if not audio:
        raise VozError("El clip de audio viene vacio.")
    if not cfg.api_key:
        raise VozError("Falta ELEVENLABS_API_KEY en .env (raiz del repo).")

    url = f"{cfg.base_url}/v1/speech-to-text"
    datos = {
        "model_id": cfg.stt_model,
        "tag_audio_events": "false",
        "diarize": "false",
    }
    if cfg.language:
        datos["language_code"] = cfg.language
    archivos = {"file": (nombre, audio)}

    propio = client is None
    client = client or httpx.Client(timeout=cfg.timeout_s)
    try:
        r = client.post(url, headers={"xi-api-key": cfg.api_key}, data=datos, files=archivos)
    except httpx.HTTPError as e:
        raise VozError(f"No se pudo llegar a ElevenLabs: {e}") from e
    finally:
        if propio:
            client.close()

    if r.status_code != 200:
        raise _explicar(r)
    j = r.json()
    return Transcripcion(
        texto=" ".join(str(j.get("text", "")).split()),
        idioma=j.get("language_code"),
        confianza=j.get("language_probability"),
        duracion_s=j.get("audio_duration_secs"),
    )
