"""Bitacora JSONL del protocolo Courier, una linea atomica por evento."""

import json
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import Any

AfterAppend = Callable[[dict[str, Any], Path], None]


class EventLog:
    """Escribe eventos cronologicos sin depender de TigerData ni de la red."""

    def __init__(self, path: Path, after_append: AfterAppend | None = None, ascii: bool = False):
        self.path = path
        self._after_append = after_append
        # Opt-in. El validador oficial abre el archivo con la codificacion del sistema
        # (cp1252 en Windows), y una "Á" en UTF-8 trae el byte 0x81 que cp1252 no lee.
        # Con ascii=True los acentos van como Á: el mismo JSON, en bytes que lee
        # cualquier codificacion. Apagado por defecto: el log de /decide no cambia.
        self.ascii = ascii
        self._lock = Lock()

    def start(self, event: dict[str, Any]) -> None:
        """Inicia una bitacora nueva. Solo shift_start puede truncar el archivo."""
        if event.get("event") != "shift_start":
            raise ValueError("el primer evento debe ser shift_start")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = self._serialize(event)
        with self._lock, self.path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.write("\n")
        self._notify(event)

    def append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = self._serialize(event)
        with self._lock, self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.write("\n")
        self._notify(event)

    def _notify(self, event: dict[str, Any]) -> None:
        """La bitacora local ya esta a salvo; un espejo externo no puede tumbarla."""
        if self._after_append is None:
            return
        try:
            self._after_append(event, self.path)
        except Exception:
            # El callback puede ser red o una cola llena; nunca es razon para
            # perder el evento local ni para retrasar una decision.
            return

    def _serialize(self, event: dict[str, Any]) -> str:
        if not isinstance(event.get("event"), str):
            raise ValueError("cada evento necesita el campo event")
        return json.dumps(event, ensure_ascii=self.ascii, separators=(",", ":"), default=str)
