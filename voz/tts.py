"""Texto -> audio. ElevenLabs streaming TTS, con cache en disco.

La cache no es optimizacion: es el seguro del demo. La cuenta es free (10k caracteres
en total) y el wifi del hackathon falla en el pitch. Toda frase que ya se dijo una vez
se sirve de disco, sin red, y `python -m voz precache` deja el guion listo antes.
"""

import contextlib
import hashlib
import json
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx

from voz.config import Config, config


class VozError(RuntimeError):
    """Algo impidio generar audio. El mensaje dice que hacer.

    `pausar` distingue una caida de ElevenLabs (llave rechazada, sin cuota, 5xx, sin red),
    tras la cual conviene dejar de intentar un rato, de un error de esta frase o de este
    instante (texto vacio, demasiadas peticiones a la vez) que no dice nada de la siguiente.
    """

    def __init__(self, mensaje: str, *, pausar: bool = True):
        super().__init__(mensaje)
        self.pausar = pausar


def normalizar(texto: str) -> str:
    """Espacios colapsados y sin bordes: 'Skip it.  ' y 'Skip it.' son la misma frase."""
    return " ".join(texto.split())


def cache_key(texto: str, cfg: Config = config) -> str:
    """Una frase con una voz, un modelo y un formato es un archivo. Cambia uno, cambia el key."""
    firma = json.dumps(
        [
            normalizar(texto),
            cfg.voice_id,
            cfg.tts_model,
            cfg.output_format,
            cfg.language,
            cfg.voice_settings,
        ],
        sort_keys=True,
    )
    return hashlib.sha256(firma.encode("utf-8")).hexdigest()[:16]


def cache_path(texto: str, cfg: Config = config) -> Path:
    return cfg.cache_dir / f"{cache_key(texto, cfg)}.mp3"


def _headers(cfg: Config) -> dict[str, str]:
    if not cfg.api_key:
        raise VozError("Falta ELEVENLABS_API_KEY en .env (raiz del repo).")
    return {"xi-api-key": cfg.api_key, "Content-Type": "application/json"}


def _explicar(r: httpx.Response) -> VozError:
    try:
        detalle = r.json().get("detail", r.text)
    except ValueError:
        detalle = r.text
    if r.status_code == 401:
        return VozError(f"ElevenLabs rechazo la llave (401): {detalle}")
    if r.status_code == 429:
        # Solo la cuota agotada es caida; "demasiadas a la vez" o "sistema ocupado" pasa solo.
        estado = detalle.get("status") if isinstance(detalle, dict) else None
        return VozError(
            f"ElevenLabs: limite de uso o de caracteres (429): {detalle}",
            pausar=estado == "quota_exceeded",
        )
    return VozError(f"ElevenLabs respondio {r.status_code}: {detalle}")


def stream(
    texto: str,
    *,
    cfg: Config = config,
    client: httpx.Client | None = None,
    usar_cache: bool = True,
) -> Iterator[bytes]:
    """Itera chunks de MP3. Si la frase esta en cache, un solo chunk desde disco y cero red.

    Cuando viene de la API, se escribe a cache al terminar (atomicamente: .part -> .mp3),
    asi una desconexion a medias no deja un archivo roto que luego se sirva. Cada stream
    tiene su propio .part: el prefetch y la reproduccion pueden pedir la misma frase a la
    vez, y con un temporal compartido en Windows uno de los dos truena al renombrar.
    """
    texto = normalizar(texto)
    if not texto:
        raise VozError("No hay texto que decir.", pausar=False)

    ruta = cache_path(texto, cfg)
    if usar_cache and ruta.exists():
        yield ruta.read_bytes()
        return

    url = f"{cfg.base_url}/v1/text-to-speech/{cfg.voice_id}/stream"
    body = {
        "text": texto,
        "model_id": cfg.tts_model,
        "voice_settings": cfg.voice_settings,
    }
    if cfg.language:
        body["language_code"] = cfg.language
    params = {"output_format": cfg.output_format}

    propio = client is None
    client = client or httpx.Client(timeout=cfg.timeout_s)
    try:
        with client.stream("POST", url, headers=_headers(cfg), params=params, json=body) as r:
            if r.status_code != 200:
                r.read()
                raise _explicar(r)
            ruta.parent.mkdir(parents=True, exist_ok=True)
            parcial = ruta.with_name(f"{ruta.stem}.{uuid.uuid4().hex[:8]}.part")
            try:
                with parcial.open("wb") as f:
                    for chunk in r.iter_bytes():
                        if chunk:
                            f.write(chunk)
                            yield chunk
                try:
                    parcial.replace(ruta)
                except OSError:
                    # Otro stream de la misma frase ya la guardo (o la estan leyendo). El audio
                    # ya llego completo al cliente; la cache se queda con la copia del otro.
                    pass
            finally:
                # Desconexion a medias, error de red o reemplazo fallido: sin temporales sueltos.
                with contextlib.suppress(OSError):
                    parcial.unlink(missing_ok=True)
    except httpx.HTTPError as e:
        raise VozError(f"No se pudo llegar a ElevenLabs: {e}") from e
    finally:
        if propio:
            client.close()


def sintetizar(texto: str, *, cfg: Config = config, client: httpx.Client | None = None) -> bytes:
    """Toda la frase en un bytes. Para guardar a archivo o mandar completa."""
    return b"".join(stream(texto, cfg=cfg, client=client))


def en_cache(texto: str, cfg: Config = config) -> bool:
    return cache_path(texto, cfg).exists()
