"""Rank stories against the local corpus."""

from __future__ import annotations

from pathlib import Path

from noncast import rag
from noncast.config import Config
from noncast.models import ChunkHit, Story
from noncast.pipeline.io import dump_json, ensure_run, load_json, today_stamp
from noncast.pipeline.scrape import stories_from_payload
from noncast.textutil import tokenize


def run(cfg: Config, date: str | None = None, topic: str | None = None) -> dict:
    date = today_stamp(date)
    rundir = ensure_run(cfg, date)
    stories_path = rundir / "stories.json"
    stories: list[Story] = []
    if stories_path.is_file():
        stories = stories_from_payload(load_json(stories_path))  # type: ignore[arg-type]

    ranked = []
    for story in stories:
        query = f"{story.title} {story.summary} {topic or ''}"
        hits = rag.retrieve(cfg, query, k=min(4, cfg.rag_top_k))
        score = hits[0].score if hits else 0.0
        ranked.append(
            {
                "story": {
                    "id": story.id,
                    "title": story.title,
                    "url": story.url,
                    "summary": story.summary,
                    "published": story.published,
                    "feed": story.feed,
                },
                "score": round(score, 4),
                "corpus": [_hit(h) for h in hits[:3]],
            }
        )
    ranked.sort(key=lambda row: row["score"], reverse=True)

    query = topic or _daily_query(date)
    corpus_hits = rag.retrieve(cfg, query, k=cfg.rag_top_k)
    payload = {
        "date": date,
        "topic": topic,
        "query": query,
        "stories": ranked,
        "corpus": [_hit(h) for h in corpus_hits],
        "token_hint": tokenize(query)[:12],
    }
    dump_json(rundir / "analysis.json", payload)
    return payload


def load_analysis(rundir: Path) -> dict:
    path = rundir / "analysis.json"
    if not path.is_file():
        return {"stories": [], "corpus": [], "topic": None, "query": ""}
    data = load_json(path)
    return data if isinstance(data, dict) else {"stories": [], "corpus": []}


def _hit(hit: ChunkHit) -> dict:
    return {
        "title": hit.title,
        "path": hit.path,
        "text": hit.text,
        "score": round(hit.score, 4),
    }


def _daily_query(date: str) -> str:
    themes = [
        "listening craft cadence sentence",
        "rss feed enclosure publish",
        "voice clone consent identity",
        "local corpus sqlite fork",
    ]
    day = int(date.replace("-", "")[-2:]) if date else 0
    return themes[day % len(themes)]
