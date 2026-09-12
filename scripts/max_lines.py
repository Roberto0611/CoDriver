"""Ningún archivo de código pasa de MAX líneas. Falla con la lista de los que sí.

    python scripts/max_lines.py <dir> [<dir> ...]

Un archivo largo es un archivo que hace demasiado. Se parte por responsabilidad,
no por la mitad. Los docs no cuentan.
"""

import sys
from pathlib import Path

MAX = 500
EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".css"}
SKIP = {"node_modules", "dist", ".venv", "venv", "__pycache__", ".git", "public", "cache"}


def too_long(root: Path) -> list[tuple[Path, int]]:
    out = []
    for p in root.rglob("*"):
        if p.suffix not in EXTS or not p.is_file():
            continue
        if any(part in SKIP for part in p.parts):
            continue
        n = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
        if n > MAX:
            out.append((p, n))
    return out


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv] or [Path(".")]
    bad = [x for r in roots for x in too_long(r)]
    if bad:
        print(f"Archivos con más de {MAX} líneas:")
        for p, n in sorted(bad, key=lambda x: -x[1]):
            print(f"  {n:>5}  {p}")
        return 1
    print(f"OK: ningún archivo pasa de {MAX} líneas en {', '.join(map(str, roots))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
