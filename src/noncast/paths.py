from __future__ import annotations

import os
from pathlib import Path


def cwd() -> Path:
    return Path.cwd().resolve()


def find_root(start: Path | None = None) -> Path:
    env = os.environ.get("NONCAST_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    here = (start or cwd()).resolve()
    for p in [here, *here.parents]:
        if (p / "noncast.toml").exists():
            return p
    return here


def load_dotenv(root: Path) -> None:
    path = root / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value
