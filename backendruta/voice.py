"""Rutas de voz. Se montan en main.py con `app.include_router(voice.router)`.

    GET  /api/voice/say?text=...     audio/mpeg (streaming). Va directo a <audio src=...>.
    POST /api/voice/listen           multipart `file` -> {"text": ...}. El repartidor contesta.
    GET  /api/voice/config           voz y modelo activos, para mostrarlos en pantalla.

La llave de ElevenLabs no sale de aqui. Cada frase se cachea en disco (ver voz/tts.py).
"""

import os
import time
from typing import Annotated

import httpx
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from voz import stt, tts
from voz.config import config

router = APIRouter(prefix="/api/voice", tags=["voice"])

MAX_CHARS = 400  # una frase de Nuez son ~100; esto frena un abuso que vacie la cuota

# Tras una falla de ElevenLabs (llave rechazada, sin cuota, sin red) las frases que no estan
# en cache responden 502 al instante durante este rato. Sin esto cada frase del demo espera
# el rechazo de la API antes de que el front caiga a la voz del navegador, y llega tarde.
PAUSA_TRAS_FALLA_S = 60.0
_caida_hasta = 0.0
_ultima_falla = ""


def _ahora() -> float:
    return time.monotonic()


from dataclasses import replace

@router.get("/say")
def say(
    text: str = Query(..., min_length=1, max_length=MAX_CHARS),
    lang: str | None = Query(None)
) -> StreamingResponse:
    global _caida_hasta, _ultima_falla
    cfg = replace(config, language=lang) if lang else config
    hit = tts.en_cache(text, cfg=cfg)
    if not hit and _ahora() < _caida_hasta:
        raise HTTPException(status_code=502, detail=f"ElevenLabs en pausa: {_ultima_falla}")
    try:
        chunks = tts.stream(text, cfg=cfg)
        # Se fuerza la primera llamada aqui: un error debe ser un 502, no un stream roto.
        primero = next(chunks)
    except tts.VozError as e:
        if e.pausar:  # texto vacio o "demasiadas a la vez" no dicen que la API este caida
            _caida_hasta, _ultima_falla = _ahora() + PAUSA_TRAS_FALLA_S, str(e)
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


@router.post("/agent")
async def conversacion_agente(file: Annotated[UploadFile, File()]) -> dict[str, object]:
    audio = await file.read()

    # 1. Escuchar (Speech to Text)
    try:
        t = stt.transcribir(audio, nombre=file.filename or "clip.webm")
    except tts.VozError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    user_text = t.texto

    if not user_text.strip():
        return {"transcription": "", "reply": "No entendí lo que dijiste, ¿puedes repetir?"}

    # 2. Pensar (OpenRouter LLM)
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        raise HTTPException(status_code=500, detail="Falta OPENROUTER_API_KEY en .env")

    system_prompt = (
        "You are Nuez, a helpful, friendly, and very concise AI assistant for a delivery "
        "simulator. IMPORTANT: Always reply in the exact language the user just used "
        "(if they speak Spanish, reply in Spanish, if Hindi, in Hindi, etc)."
    )

    model = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {openrouter_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        },
        timeout=15.0,
    )

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"OpenRouter Error: {response.text}")

    llm_reply = response.json()["choices"][0]["message"]["content"]

    # 3. Devolver texto (el frontend llamará a /say para generar la voz)
    return {"transcription": user_text, "reply": llm_reply}
