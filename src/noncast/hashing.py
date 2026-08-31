from __future__ import annotations

import json
import hashlib
from collections.abc import Mapping
from typing import Any


def sha256_text(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def chunk_cache_key(text: str, voice_id: str, settings: Mapping[str, Any] | None = None) -> str:
    payload = {
        "text": text.strip(),
        "voice_id": voice_id,
        "settings": dict(settings or {}),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
