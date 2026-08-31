"""Fetch RSS beats. Runnable: python -m noncast scrape  OR  noncast scrape"""

from __future__ import annotations

from noncast.config import Config
from noncast.models import Story
from noncast.pipeline import dedup, rss
from noncast.pipeline.io import dump_json, ensure_run, today_stamp, utcnow


def run(cfg: Config, date: str | None = None) -> dict:
    date = today_stamp(date)
    rundir = ensure_run(cfg, date)
    fetched = rss.fetch_feeds(cfg.rss_feeds, timeout=cfg.rss_timeout_seconds, retries=cfg.rss_retries)
    items: list[Story] = []
    seen: set[str] = set()
    for feed in fetched:
        for story in feed.get("items") or []:
            key = story.key()
            if key in seen:
                continue
            seen.add(key)
            items.append(story)
    fresh, dupes = dedup.filter_new(items, cfg.dedup_path, days=cfg.story_dedup_days)
    payload = {
        "date": date,
        "fetched_at": utcnow().isoformat(),
        "feeds": [
            {k: v for k, v in feed.items() if k != "items"}
            | {"item_count": feed.get("item_count", 0)}
            for feed in fetched
        ],
        "items": [_story_dict(s) for s in fresh],
        "deduped": [_story_dict(s) for s in dupes],
    }
    dump_json(rundir / "stories.json", payload)
    return payload


def _story_dict(story: Story) -> dict:
    return {
        "id": story.id,
        "title": story.title,
        "url": story.url,
        "summary": story.summary,
        "published": story.published,
        "feed": story.feed,
    }


def stories_from_payload(payload: dict) -> list[Story]:
    out = []
    for row in payload.get("items") or []:
        out.append(
            Story(
                id=str(row.get("id") or ""),
                title=str(row.get("title") or ""),
                url=str(row.get("url") or ""),
                summary=str(row.get("summary") or ""),
                published=str(row.get("published") or ""),
                feed=str(row.get("feed") or ""),
            )
        )
    return out
