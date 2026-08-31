"""Ear-lint: ~30-word sentences and kill-word lexicon."""

from __future__ import annotations

import re
from pathlib import Path

from noncast.config import Config
from noncast.models import LintIssue
from noncast.pipeline.io import dump_json, ensure_run, today_stamp
from noncast.textutil import load_killwords, spoken_and_notes, split_sentences, word_count

CONJ_SPLIT = re.compile(r",\s+(?:and|but|so|or|yet)\s+", re.I)


def run(cfg: Config, date: str | None = None, script_path: Path | None = None) -> dict:
    date = today_stamp(date)
    rundir = ensure_run(cfg, date)
    path = Path(script_path) if script_path else rundir / "script.md"
    text = path.read_text(encoding="utf-8")
    spoken, notes = spoken_and_notes(text)
    repaired = repair_text(spoken, cfg.lexicon, cfg.max_sentence_words)
    issues = lint_text(repaired, cfg.lexicon, cfg.max_sentence_words)
    title = text.splitlines()[0] if text.startswith("# ") else "# Episode"
    body = "\n\n".join(split_sentences(repaired)) or repaired
    rebuilt = f"{title}\n\n## Spoken\n\n{body}\n\n## Show notes\n\n{notes or '- Local markdown corpus'}\n"
    path.write_text(rebuilt + "\n", encoding="utf-8")
    report = {
        "path": str(path),
        "issues": [i.__dict__ for i in issues],
        "ok": not any(i.kind in {"long_sentence", "killword"} for i in issues),
        "sentences": len(split_sentences(repaired)),
    }
    dump_json(rundir / "earlint.json", report)
    return report


def lint_text(text: str, lexicon: Path, max_words: int = 30) -> list[LintIssue]:
    issues: list[LintIssue] = []
    kill = load_killwords(lexicon)
    for sent in split_sentences(text):
        wc = word_count(sent)
        if wc > max_words:
            issues.append(LintIssue("long_sentence", sent, f"{wc} words > {max_words}"))
        lower = sent.lower()
        for word, _repl in kill:
            if _contains_word(lower, word.lower()):
                issues.append(LintIssue("killword", sent, word))
    return issues


def repair_text(text: str, lexicon: Path, max_words: int = 30) -> str:
    replaced = _apply_killwords(text, lexicon)
    out: list[str] = []
    for sent in split_sentences(replaced):
        out.extend(_split_long(sent, max_words))
    return " ".join(s.strip() for s in out if s.strip())


def _apply_killwords(text: str, lexicon: Path) -> str:
    result = text
    for word, repl in load_killwords(lexicon):
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.I)
        result = pattern.sub(repl, result)
    result = re.sub(r"\s{2,}", " ", result)
    result = re.sub(r"\s+([,.;!?])", r"\1", result)
    return result.strip()


def _finish_part(part: str, index: int) -> str:
    part = part.strip()
    if not part:
        return ""
    if index > 0 and part[0].islower():
        part = part[0].upper() + part[1:]
    if not part.endswith((".", "!", "?")):
        part = part.rstrip(",;") + "."
    return part


def _split_long(sentence: str, max_words: int) -> list[str]:
    if word_count(sentence) <= max_words:
        return [sentence]
    for sep in ("; ", " — ", " – "):
        if sep in sentence:
            parts = [p for p in (_finish_part(p, i) for i, p in enumerate(sentence.split(sep))) if p]
            if len(parts) > 1:
                out: list[str] = []
                for part in parts:
                    out.extend(_split_long(part, max_words))
                return out
    conj = [p for p in (_finish_part(p, i) for i, p in enumerate(CONJ_SPLIT.split(sentence))) if p]
    if len(conj) > 1:
        out = []
        for part in conj:
            out.extend(_split_long(part, max_words))
        return out
    words = sentence.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i : i + max_words]).strip()
        if chunk and not chunk.endswith((".", "!", "?")):
            chunk += "."
        chunks.append(chunk)
    return chunks


def _contains_word(haystack: str, needle: str) -> bool:
    return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None
