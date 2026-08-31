from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from noncast.config import Config


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def today_stamp(date: str | None = None) -> str:
    if date:
        return date
    return utcnow().date().isoformat()


def dump_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_run(cfg: Config, date: str) -> Path:
    rundir = cfg.run_dir(date)
    rundir.mkdir(parents=True, exist_ok=True)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    return rundir
