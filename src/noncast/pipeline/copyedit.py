"""Copyedit: kill-words, sentence length, no invented family/quotes/stats."""

from __future__ import annotations

import re
from pathlib import Path

from noncast import rag
from noncast.config import Config
from noncast.pipeline.earlint import lint_text, repair_text
from noncast.pipeline.io import dump_json, ensure_run, today_stamp
from noncast.textutil import (
    extract_quotes,
    extract_stats,
    family_mentions,
    spoken_and_notes,
    split_sentences,
    tokenize,
    word_count,
)

URL_RE = re.compile(r"https?://\S+")


def run(cfg: Config, date: str | None = None, script_path: Path | None = None) -> dict:
    date = today_stamp(date)
    rundir = ensure_run(cfg, date)
    path = Path(script_path) if script_path else rundir / "script.md"
    original = path.read_text(encoding="utf-8")
    spoken, notes = spoken_and_notes(original)
    sources = _sources(cfg, notes, rundir)
    repaired = repair_text(spoken, cfg.lexicon, cfg.max_sentence_words)
    repaired = URL_RE.sub("the link in the show notes", repaired)
    stripped, removed = strip_unsourced(repaired, sources)
    # Re-run length repair after stripping
    stripped = repair_text(stripped, cfg.lexicon, cfg.max_sentence_words)
    issues = [i.__dict__ for i in lint_text(stripped, cfg.lexicon, cfg.max_sentence_words)]
    rebuilt = _rebuild(original, stripped, notes)
    path.write_text(rebuilt + "\n", encoding="utf-8")
    report = {
        "path": str(path),
        "removed": removed,
        "remaining_issues": issues,
        "words": word_count(stripped),
    }
    dump_json(rundir / "copyedit.json", report)
    return report


def strip_unsourced(spoken: str, sources: str) -> tuple[str, list[str]]:
    source_l = sources.lower()
    source_tokens = set(tokenize(sources))
    removed: list[str] = []
    kept: list[str] = []
    for sent in split_sentences(spoken):
        drop_reason = None
        for quote in extract_quotes(sent):
            if quote.lower() not in source_l:
                drop_reason = f"unsourced quote: {quote[:80]}"
                break
        if not drop_reason:
            for stat in extract_stats(sent):
                if stat.lower() not in source_l and stat not in sources:
                    drop_reason = f"unsourced stat: {stat}"
                    break
        if not drop_reason:
            for fam in family_mentions(sent):
                # Allowed only if the same kinship phrase appears in sources
                if fam.lower() not in source_l:
                    drop_reason = f"invented family: {fam}"
                    break
        if drop_reason:
            # Keep the sentence if it is mostly sourced besides the bad span — still fail closed: drop it.
            removed.append(drop_reason)
            continue
        kept.append(sent)
    if not kept:
        kept = ["The brief has no unsourced claims left to read."]
    return " ".join(kept), removed


def _sources(cfg: Config, notes: str, rundir: Path) -> str:
    parts = [rag.all_source_text(cfg), notes]
    stories = rundir / "stories.json"
    analysis = rundir / "analysis.json"
    for extra in (stories, analysis):
        if extra.is_file():
            parts.append(extra.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _rebuild(original: str, spoken: str, notes: str) -> str:
    title = original.splitlines()[0] if original.startswith("# ") else "# Episode"
    notes_block = notes.strip() or "- Local markdown corpus"
    body = "\n\n".join(split_sentences(spoken)) or spoken
    return f"{title}\n\n## Spoken\n\n{body}\n\n## Show notes\n\n{notes_block}\n"
