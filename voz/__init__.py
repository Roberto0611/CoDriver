"""La voz de Nuez: texto -> audio (ElevenLabs TTS) y audio -> texto (ElevenLabs Scribe).

    from voz import tts, stt
    tts.sintetizar("Skip it.")          -> bytes MP3 (cacheado en disco)
    stt.transcribir(audio_bytes)        -> "not that neighborhood"

Va directo al REST de ElevenLabs con httpx: el SDK oficial no instala en Windows por
rutas largas, y son dos endpoints. La llave vive en .env (ELEVENLABS_API_KEY) y nunca
sale del backend.
"""

from voz.config import Config, config
from voz.tts import VozError, cache_path, sintetizar, stream

__all__ = ["Config", "VozError", "cache_path", "config", "sintetizar", "stream"]
