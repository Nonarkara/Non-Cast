"""Create local dirs and missing kit files. Idempotent."""

from __future__ import annotations

from pathlib import Path

from noncast.config import Config, load_config
from noncast.paths import find_root

DEFAULT_TOML = """# Generic show identity. Replace every string here when you fork.

[show]
name = "Daily Brief"
author = "Host"
description = "A daily spoken brief generated from a local writing corpus and optional RSS beats."
language = "en"
site_url = "https://example.com/brief"
feed_path = "public/feed.xml"
email = "host@example.com"
explicit = false
category = "Technology"

[persona]
name = "Host"
bio = "A precise host who only speaks from the local corpus and fetched sources."
style = "conversational, short sentences, no invented facts"

[pipeline]
default_duration_minutes = 12
target_wpm = 155
max_sentence_words = 30
coverage_threshold = 0.95
story_dedup_days = 3
rss_timeout_seconds = 8
rss_retries = 2
default_publish = false

[rss]
feeds = []

[rag]
corpus_dir = "corpus"
index_path = "data/rag.sqlite"
chunk_size = 400
chunk_overlap = 60
backend = "auto"
top_k = 8

[voice]
backend = "none"
id = "host-primary"
reference_wav = "voices/reference.wav"
refuse_system_fallback = true

[llm]
backend = "ollama"
model = "llama3.2"
base_url = "http://127.0.0.1:11434"
timeout_seconds = 30

[publish]
output_dir = "public"
media_dir = "public/episodes"
"""

DEFAULT_KILLWORDS = """delve\tlook
tapestry\tmix
furthermore\talso
utilize\tuse
leverage\tuse
literally
as an ai
in conclusion\tto close
let's dive in\tlet's begin
"""

DEFAULT_ENV = """# Copy from .env.example. Happy path needs no keys.
# OLLAMA_HOST=http://127.0.0.1:11434
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# ELEVENLABS_API_KEY=
"""

VOICE_README = """# Voice clip (gitignored)

Put a consented clip of your speaking voice here as `reference.wav`.
Never commit it. If synthesis is unavailable, Non-Cast will not fall back to system TTS.
"""


def run(root: Path | None = None) -> dict:
    root = (root or find_root()).resolve()
    created: list[str] = []

    def ensure_dir(rel: str) -> None:
        path = root / rel
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(rel + "/")

    def ensure_file(rel: str, content: str) -> None:
        path = root / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            created.append(rel)

    for d in (
        "corpus",
        "lexicon",
        "voices",
        "docs",
        "data",
        "data/cache",
        "data/runs",
        "public",
        "public/episodes",
    ):
        ensure_dir(d)
    ensure_file("noncast.toml", DEFAULT_TOML)
    ensure_file("lexicon/killwords.txt", DEFAULT_KILLWORDS)
    ensure_file(".env.example", DEFAULT_ENV)
    ensure_file("voices/README.md", VOICE_README)
    corpus = root / "corpus"
    if not any(corpus.glob("*.md")):
        ensure_file(
            "corpus/hello.md",
            "# Hello from the corpus\n\nReplace this file with your own essays. "
            "Non-Cast will not invent family stories, quotes, or statistics.\n",
        )
    cfg = load_config(root)
    return {"root": str(cfg.root), "created": created, "show": cfg.show_name}
