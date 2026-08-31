"""Sentence/chunk cache keyed by hash(text + voice-id + settings)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from noncast.hashing import chunk_cache_key


def cache_file(cache_dir: Path, key: str, suffix: str = ".wav") -> Path:
    return cache_dir / "tts" / f"{key}{suffix}"


def lookup(cache_dir: Path, text: str, voice_id: str, settings: dict[str, Any]) -> Path | None:
    key = chunk_cache_key(text, voice_id, settings)
    for suffix in (".wav", ".mp3", ".bin"):
        path = cache_file(cache_dir, key, suffix)
        if path.is_file() and path.stat().st_size > 0:
            return path
    meta = cache_file(cache_dir, key, ".json")
    if meta.is_file():
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            audio = data.get("path")
            if audio and Path(audio).is_file():
                return Path(audio)
        except json.JSONDecodeError:
            return None
    return None


def store(
    cache_dir: Path,
    text: str,
    voice_id: str,
    settings: dict[str, Any],
    audio: bytes,
    suffix: str = ".wav",
) -> Path:
    key = chunk_cache_key(text, voice_id, settings)
    path = cache_file(cache_dir, key, suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio)
    meta = cache_file(cache_dir, key, ".json")
    meta.write_text(
        json.dumps(
            {
                "key": key,
                "voice_id": voice_id,
                "settings": settings,
                "path": str(path),
                "bytes": len(audio),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
