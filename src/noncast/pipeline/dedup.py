"""3-day story dedup by URL and near-identical title."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

from noncast.models import Story

TITLE_THRESHOLD = 0.85


def _parse_when(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)


def load_log(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def prune(rows: list[dict], now: datetime, days: int) -> list[dict]:
    cutoff = now - timedelta(days=days)
    kept = []
    for row in rows:
        when = _parse_when(str(row.get("when") or now.isoformat()))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when >= cutoff:
            kept.append(row)
    return kept


def is_duplicate(story: Story, rows: list[dict], now: datetime | None = None, days: int = 3) -> bool:
    now = now or datetime.now(timezone.utc)
    window = prune(rows, now, days)
    url = (story.url or "").strip().lower()
    title = (story.title or "").strip().lower()
    for row in window:
        if url and str(row.get("url") or "").strip().lower() == url:
            return True
        other = str(row.get("title") or "").strip().lower()
        if title and other and SequenceMatcher(None, title, other).ratio() >= TITLE_THRESHOLD:
            return True
    return False


def record(path: Path, stories: list[Story], now: datetime | None = None, days: int = 3) -> None:
    now = now or datetime.now(timezone.utc)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = prune(load_log(path), now, days)
    seen = {(str(r.get("url") or ""), str(r.get("title") or "")) for r in rows}
    for story in stories:
        key = (story.url, story.title)
        if key in seen:
            continue
        rows.append(
            {
                "id": story.id,
                "url": story.url,
                "title": story.title,
                "when": now.isoformat(),
            }
        )
        seen.add(key)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def filter_new(stories: list[Story], path: Path, days: int = 3, now: datetime | None = None) -> tuple[list[Story], list[Story]]:
    now = now or datetime.now(timezone.utc)
    rows = load_log(path)
    fresh, dupes = [], []
    for story in stories:
        if is_duplicate(story, rows, now=now, days=days):
            dupes.append(story)
        else:
            fresh.append(story)
    return fresh, dupes
