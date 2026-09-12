"""Configuracion de la voz. AQUI se cambia la voz de Nuez (Eli): un solo lugar.

Todo se puede sobreescribir por variable de entorno (.env) sin tocar codigo:

    ELEVENLABS_API_KEY      obligatoria
    NUEZ_VOICE_ID           id de voz de ElevenLabs (default: Jessica)
    NUEZ_TTS_MODEL          eleven_flash_v2_5 (rapido) | eleven_v3 (mas expresivo, mas lento)
    NUEZ_STT_MODEL          scribe_v1
    ELEVENLABS_BASE_URL     https://api.us.elevenlabs.io (ruteo USA, mas cerca de MTY)

Voces premade en la cuenta que suenan a Nuez (jovenes, conversacionales, en ingles):
    cgSgspJ2msm6clMCkdW9  Jessica  playful, bright, warm      <- default
    FGY2WhTYpPnrIDTdsKH5  Laura    enthusiast, quirky
    bIHbv24MWmeRgasZH58o  Will     relaxed optimist (masc.)
    SAz9YHcvj6GT2YYXdXww  River    relaxed, neutral
Lista completa: `python -m voz voices`.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


@dataclass
class Config:
    _api_key: str | None = None
    voice_id: str = field(
        default_factory=lambda: os.getenv("NUEZ_VOICE_ID", "cgSgspJ2msm6clMCkdW9")
    )
    tts_model: str = field(default_factory=lambda: os.getenv("NUEZ_TTS_MODEL", "eleven_flash_v2_5"))
    stt_model: str = field(default_factory=lambda: os.getenv("NUEZ_STT_MODEL", "scribe_v1"))
    base_url: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_BASE_URL", "https://api.us.elevenlabs.io")
    )
    # mp3 chico: para voz basta y baja la latencia (la doc de ElevenLabs lo recomienda).
    output_format: str = "mp3_22050_32"
    # Personalidad: estable pero con algo de estilo, y un poco mas rapida que lo normal,
    # como alguien que te habla al oido mientras manejas.
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.3
    speed: float = 1.05
    language: str | None = None
    cache_dir: Path = RAIZ / "cache" / "voz"
    timeout_s: float = 30.0

    @property
    def api_key(self) -> str | None:
        key = self._api_key or os.getenv("ELEVENLABS_API_KEY")
        if not key:
            load_dotenv(RAIZ / ".env", override=True)
            key = os.getenv("ELEVENLABS_API_KEY")
        return key

    @property
    def voice_settings(self) -> dict[str, float | bool]:
        return {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "speed": self.speed,
            "use_speaker_boost": True,
        }


config = Config()
