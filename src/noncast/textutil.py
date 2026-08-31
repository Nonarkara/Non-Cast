from __future__ import annotations

import re
from pathlib import Path

ABBREV = {
    "mr",
    "mrs",
    "ms",
    "dr",
    "prof",
    "sr",
    "jr",
    "vs",
    "etc",
    "al",
    "fig",
    "eg",
    "ie",
    "us",
    "uk",
    "inc",
    "ltd",
    "st",
    "ave",
}

WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
QUOTE_RE = re.compile(r"[“\"]([^”\"]{8,})[”\"]")
STAT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:%|percent|per\s+cent)\b|\b\d{1,3}(?:,\d{3})+\b|\b\d+\s+(?:million|billion|thousand)\b",
    re.I,
)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
FAMILY_RE = re.compile(
    r"\b(?:my|our)\s+(?:mom|mother|dad|father|wife|husband|son|daughter|kids|children|"
    r"brother|sister|grandma|grandfather|grandmother|baby)\b",
    re.I,
)
SPOKEN_HEADER = re.compile(r"^##\s+Spoken\s*$", re.I | re.M)
NOTES_HEADER = re.compile(r"^##\s+Show notes\s*$", re.I | re.M)


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text)]


def word_count(text: str) -> int:
    return len(tokenize(text))


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    parts: list[str] = []
    buf: list[str] = []
    tokens = re.findall(r"\S+|\s+", text)
    for tok in tokens:
        buf.append(tok)
        stripped = tok.strip()
        if stripped.endswith((".", "!", "?")) and not stripped.endswith("..."):
            word = stripped.rstrip(".!?").lower()
            if word in ABBREV or (len(word) == 1 and word.isalpha()):
                continue
            sentence = "".join(buf).strip()
            if sentence:
                parts.append(sentence)
            buf = []
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def extract_quotes(text: str) -> list[str]:
    return [m.group(1).strip() for m in QUOTE_RE.finditer(text)]


def extract_stats(text: str) -> list[str]:
    found = []
    for m in STAT_RE.finditer(text):
        token = m.group(0)
        if YEAR_RE.fullmatch(token.replace(",", "")):
            continue
        found.append(token)
    return found


def family_mentions(text: str) -> list[str]:
    return [m.group(0) for m in FAMILY_RE.finditer(text)]


def spoken_and_notes(markdown: str) -> tuple[str, str]:
    notes = NOTES_HEADER.search(markdown)
    spoken_h = SPOKEN_HEADER.search(markdown)
    if spoken_h and notes:
        return markdown[spoken_h.end() : notes.start()].strip(), markdown[notes.end() :].strip()
    if notes:
        return markdown[: notes.start()].strip(), markdown[notes.end() :].strip()
    return markdown.strip(), ""


def strip_front_matter(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm = text[3:end].strip()
            body = text[end + 4 :].lstrip("\n")
            title = ""
            for line in fm.splitlines():
                if line.lower().startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"').strip("'")
            return body, title
    return text, ""


def title_from_markdown(path: Path, text: str) -> str:
    body, fm_title = strip_front_matter(text)
    if fm_title:
        return fm_title
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").replace("_", " ")


def load_killwords(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        return []
    rows: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            word, repl = line.split("\t", 1)
        else:
            word, repl = line, ""
        rows.append((word.strip(), repl.strip()))
    rows.sort(key=lambda pair: len(pair[0]), reverse=True)
    return rows


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    size = max(size, 40)
    overlap = min(max(overlap, 0), size - 1)
    chunks: list[str] = []
    i = 0
    while i < len(words):
        piece = words[i : i + size]
        chunks.append(" ".join(piece))
        if i + size >= len(words):
            break
        i += size - overlap
    return chunks


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)
