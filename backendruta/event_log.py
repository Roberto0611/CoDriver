"""Bitacora JSONL del protocolo Courier, una linea atomica por evento."""

import json
from pathlib import Path
from threading import Lock
from typing import Any


class EventLog:
    """Escribe eventos cronologicos sin depender de TigerData ni de la red."""

    def __init__(self, path: Path):
        self.path = path
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

    def append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = self._serialize(event)
        with self._lock, self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.write("\n")

    @staticmethod
    def _serialize(event: dict[str, Any]) -> str:
        if not isinstance(event.get("event"), str):
            raise ValueError("cada evento necesita el campo event")
        return json.dumps(event, ensure_ascii=False, separators=(",", ":"), default=str)
