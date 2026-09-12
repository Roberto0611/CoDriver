"""Rutas de voz. Se montan en main.py con `app.include_router(voice.router)`.

    GET  /api/voice/say?text=...     audio/mpeg (streaming). Va directo a <audio src=...>.
    POST /api/voice/listen           multipart `file` -> {"text": ...}. El repartidor contesta.
    GET  /api/voice/config           voz y modelo activos, para mostrarlos en pantalla.

La llave de ElevenLabs no sale de aqui. Cada frase se cachea en disco (ver voz/tts.py).
"""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from voz import stt, tts
from voz.config import config

router = APIRouter(prefix="/api/voice", tags=["voice"])

MAX_CHARS = 400  # una frase de Nuez son ~100; esto frena un abuso que vacie la cuota


@router.get("/say")
def say(text: str = Query(..., min_length=1, max_length=MAX_CHARS)) -> StreamingResponse:
    hit = tts.en_cache(text)
    try:
        chunks = tts.stream(text)
        # Se fuerza la primera llamada aqui: un error debe ser un 502, no un stream roto.
        primero = next(chunks)
    except tts.VozError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except StopIteration:
        raise HTTPException(status_code=502, detail="ElevenLabs no devolvio audio.") from None

    def cuerpo():
        yield primero
        yield from chunks

    return StreamingResponse(
        cuerpo(),
        media_type="audio/mpeg",
        headers={
            "X-Nuez-Cache": "hit" if hit else "miss",
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.post("/listen")
async def listen(file: Annotated[UploadFile, File()]) -> dict[str, object]:
    audio = await file.read()
    try:
        t = stt.transcribir(audio, nombre=file.filename or "clip.webm")
    except tts.VozError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"text": t.texto, "language": t.idioma, "confidence": t.confianza}


@router.get("/config")
def voice_config() -> dict[str, object]:
    return {
        "voice_id": config.voice_id,
        "tts_model": config.tts_model,
        "stt_model": config.stt_model,
        "has_key": bool(config.api_key),
    }
