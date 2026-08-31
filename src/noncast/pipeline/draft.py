"""Draft a spoken script from analysis + corpus. LLM polish is optional."""

from __future__ import annotations

import re

from noncast import llm, rag
from noncast.config import Config
from noncast.pipeline.analyze import load_analysis
from noncast.pipeline.io import ensure_run, today_stamp
from noncast.textutil import split_sentences, word_count

SYSTEM = """You write a spoken podcast script.
Rules:
- Use ONLY facts present in the provided sources. No invented family, quotes, or statistics.
- Short sentences. Aim for about 30 words or fewer.
- Conversational, not a listicle. Attribute sources by title.
- Output markdown with ## Spoken then ## Show notes.
- Show notes list the sources you used. Do not add URLs you were not given.
"""


def run(
    cfg: Config,
    date: str | None = None,
    topic: str | None = None,
    minutes: int | None = None,
) -> dict:
    date = today_stamp(date)
    rundir = ensure_run(cfg, date)
    minutes = minutes or cfg.default_duration_minutes
    analysis = load_analysis(rundir)
    if topic:
        analysis["topic"] = topic
    target_words = max(80, minutes * cfg.target_wpm)
    extractive = extractive_script(cfg, analysis, date, minutes, target_words)
    polished = None
    source_blob = _source_blob(analysis)
    polished_raw = llm.complete(_llm_prompt(extractive, source_blob, cfg, minutes), cfg, system=SYSTEM)
    if polished_raw and "## Spoken" in polished_raw:
        polished = polished_raw.strip()
    script = polished or extractive
    path = rundir / "script.md"
    path.write_text(script + "\n", encoding="utf-8")
    return {
        "path": str(path),
        "words": word_count(script),
        "polished": bool(polished),
        "minutes": minutes,
    }


def extractive_script(cfg: Config, analysis: dict, date: str, minutes: int, target_words: int) -> str:
    topic = analysis.get("topic") or analysis.get("query") or "the local corpus"
    host = cfg.persona_name
    show = cfg.show_name
    spoken: list[str] = [
        f"Welcome to {show}. I'm {host}.",
        f"Today is {date}. This episode is about {topic}.",
        "Everything I say is from the local corpus or from a fetched source. If it isn't there, it isn't here.",
    ]
    notes: list[str] = []

    for row in analysis.get("stories") or []:
        story = row.get("story") or {}
        title = story.get("title") or "a story"
        url = story.get("url") or ""
        summary = story.get("summary") or ""
        spoken.append(f"From the feed: {title}.")
        for sent in split_sentences(summary)[:4]:
            spoken.append(sent)
        if url:
            notes.append(f"- [{title}]({url})")
        for c in row.get("corpus") or []:
            spoken.extend(_corpus_lines(c, limit=2))

    for c in analysis.get("corpus") or []:
        spoken.extend(_corpus_lines(c, limit=4))
        title = c.get("title") or "corpus note"
        notes.append(f"- {title} (local corpus)")

    # Stretch toward the target with more retrieval, never invented facts.
    used = word_count(" ".join(spoken))
    extra_q = str(topic)
    if used < target_words * 0.5:
        for hit in rag.retrieve(cfg, extra_q, k=cfg.rag_top_k):
            spoken.extend(_corpus_lines({"title": hit.title, "text": hit.text}, limit=6))
            notes.append(f"- {hit.title} (local corpus)")
            if word_count(" ".join(spoken)) >= target_words * 0.7:
                break

    spoken.append(
        "That's the brief. I did not invent a family, a quote, or a statistic. Sources are in the show notes."
    )
    # Dedup adjacent identical lines
    cleaned: list[str] = []
    seen: set[str] = set()
    for line in spoken:
        key = line.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line.strip())

    notes_uniq = []
    nset = set()
    for n in notes:
        if n not in nset:
            nset.add(n)
            notes_uniq.append(n)
    if not notes_uniq:
        notes_uniq.append("- Local markdown corpus")

    title = f"# {show} — {date}"
    body = "\n\n".join(cleaned)
    notes_md = "\n".join(notes_uniq)
    return f"{title}\n\n## Spoken\n\n{body}\n\n## Show notes\n\n{notes_md}\n"


def _corpus_lines(chunk: dict, limit: int) -> list[str]:
    title = chunk.get("title") or "the corpus"
    text = chunk.get("text") or ""
    text = re.sub(r"^#+\s+.*$", "", text, flags=re.M)
    text = re.sub(r"[*_`]+", "", text)
    lines = [f"From the corpus note {title}."]
    lines.extend(split_sentences(text)[:limit])
    return lines


def _source_blob(analysis: dict) -> str:
    parts: list[str] = []
    for row in analysis.get("stories") or []:
        story = row.get("story") or {}
        parts.append(f"{story.get('title','')}\n{story.get('summary','')}\n{story.get('url','')}")
        for c in row.get("corpus") or []:
            parts.append(c.get("text") or "")
    for c in analysis.get("corpus") or []:
        parts.append(f"{c.get('title','')}\n{c.get('text','')}")
    return "\n\n".join(parts)


def _llm_prompt(extractive: str, sources: str, cfg: Config, minutes: int) -> str:
    return (
        f"Show: {cfg.show_name}. Host: {cfg.persona_name}. Style: {cfg.persona_style}.\n"
        f"Target length: about {minutes} minutes.\n"
        f"Draft to rewrite (keep claims, shorten sentences):\n{extractive}\n\n"
        f"SOURCES (the only allowed facts):\n{sources[:12000]}\n"
    )
