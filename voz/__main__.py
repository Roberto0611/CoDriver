"""CLI de la voz.

python -m voz say "Skip it. 22 minutes into Valle."     genera (o sirve de cache) y guarda
python -m voz say "..." --out demo.mp3                          y lo escribe donde digas
python -m voz precache frases.txt                               una frase por linea, todas a cache
python -m voz listen clip.webm                                  transcribe un archivo
python -m voz voices                                            lista las voces de la cuenta
python -m voz quota                                             caracteres usados / limite
"""

import sys
from pathlib import Path

import httpx

from voz import stt, tts
from voz.config import config


def say(texto: str, out: str | None) -> int:
    hit = tts.en_cache(texto)
    audio = tts.sintetizar(texto)
    destino = Path(out) if out else tts.cache_path(texto)
    if out:
        destino.write_bytes(audio)
    print(f"{'cache' if hit else 'api  '}  {len(audio) / 1e3:6.1f} KB  {destino}")
    return 0


def precache(archivo: str) -> int:
    frases = [ln.strip() for ln in Path(archivo).read_text(encoding="utf-8").splitlines()]
    frases = [f for f in frases if f and not f.startswith("#")]
    nuevas = [f for f in frases if not tts.en_cache(f)]
    chars = sum(len(f) for f in nuevas)
    print(f"{len(frases)} frases, {len(nuevas)} nuevas ({chars} caracteres a gastar)")
    with httpx.Client(timeout=config.timeout_s) as client:
        for f in nuevas:
            tts.sintetizar(f, client=client)
            print(f"  ok  {f[:70]}")
    return 0


def listen(archivo: str) -> int:
    p = Path(archivo)
    t = stt.transcribir(p.read_bytes(), nombre=p.name)
    print(f"[{t.idioma} {t.confianza:.2f}] {t.texto}" if t.confianza else t.texto)
    return 0


def voices() -> int:
    r = httpx.get(f"{config.base_url}/v1/voices", headers={"xi-api-key": config.api_key or ""})
    r.raise_for_status()
    for v in r.json()["voices"]:
        marca = "<- actual" if v["voice_id"] == config.voice_id else ""
        print(f"  {v['voice_id']}  {v['name']:<40} {marca}")
    return 0


def quota() -> int:
    r = httpx.get(
        f"{config.base_url}/v1/user/subscription", headers={"xi-api-key": config.api_key or ""}
    )
    r.raise_for_status()
    j = r.json()
    print(f"{j['tier']}: {j['character_count']} / {j['character_limit']} caracteres")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, *rest = argv
    if cmd == "say" and rest:
        out = rest[rest.index("--out") + 1] if "--out" in rest else None
        return say(rest[0], out)
    if cmd == "precache" and rest:
        return precache(rest[0])
    if cmd == "listen" and rest:
        return listen(rest[0])
    if cmd == "voices":
        return voices()
    if cmd == "quota":
        return quota()
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except tts.VozError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
