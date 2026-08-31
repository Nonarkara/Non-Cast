from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from noncast.paths import find_root, load_dotenv

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def _table(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    return value if isinstance(value, dict) else {}


@dataclass
class Config:
    root: Path
    show_name: str = "Daily Brief"
    show_author: str = "Host"
    show_description: str = ""
    show_language: str = "en"
    site_url: str = "https://example.com/brief"
    feed_path: str = "public/feed.xml"
    email: str = "host@example.com"
    explicit: bool = False
    category: str = "Technology"
    persona_name: str = "Host"
    persona_bio: str = ""
    persona_style: str = "conversational"
    default_duration_minutes: int = 12
    target_wpm: int = 155
    max_sentence_words: int = 30
    coverage_threshold: float = 0.95
    story_dedup_days: int = 3
    rss_timeout_seconds: int = 8
    rss_retries: int = 2
    default_publish: bool = False
    rss_feeds: list[str] = field(default_factory=list)
    corpus_dir: str = "corpus"
    index_path: str = "data/rag.sqlite"
    chunk_size: int = 400
    chunk_overlap: int = 60
    rag_backend: str = "auto"
    rag_top_k: int = 8
    voice_backend: str = "none"
    voice_id: str = "host-primary"
    reference_wav: str = "voices/reference.wav"
    refuse_system_fallback: bool = True
    llm_backend: str = "ollama"
    llm_model: str = "llama3.2"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_timeout_seconds: int = 30
    output_dir: str = "public"
    media_dir: str = "public/episodes"
    lexicon_path: str = "lexicon/killwords.txt"

    def path(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else (self.root / p)

    @property
    def corpus(self) -> Path:
        return self.path(self.corpus_dir)

    @property
    def index(self) -> Path:
        return self.path(self.index_path)

    @property
    def feed(self) -> Path:
        return self.path(self.feed_path)

    @property
    def media(self) -> Path:
        return self.path(self.media_dir)

    @property
    def lexicon(self) -> Path:
        return self.path(self.lexicon_path)

    @property
    def data(self) -> Path:
        return self.path("data")

    @property
    def cache_dir(self) -> Path:
        return self.path("data/cache")

    @property
    def runs_dir(self) -> Path:
        return self.path("data/runs")

    @property
    def dedup_path(self) -> Path:
        return self.path("data/story-dedup.jsonl")

    def run_dir(self, date: str) -> Path:
        return self.runs_dir / date


def load_config(root: Path | None = None) -> Config:
    root = find_root(root)
    load_dotenv(root)
    cfg = Config(root=root)
    toml_path = root / "noncast.toml"
    data: dict[str, Any] = {}
    if toml_path.is_file():
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))

    show = _table(data, "show")
    persona = _table(data, "persona")
    pipeline = _table(data, "pipeline")
    rss = _table(data, "rss")
    rag = _table(data, "rag")
    voice = _table(data, "voice")
    llm = _table(data, "llm")
    publish = _table(data, "publish")

    cfg.show_name = str(show.get("name", cfg.show_name))
    cfg.show_author = str(show.get("author", cfg.show_author))
    cfg.show_description = str(show.get("description", cfg.show_description))
    cfg.show_language = str(show.get("language", cfg.show_language))
    cfg.site_url = str(show.get("site_url", cfg.site_url)).rstrip("/")
    cfg.feed_path = str(show.get("feed_path", cfg.feed_path))
    cfg.email = str(show.get("email", cfg.email))
    cfg.explicit = bool(show.get("explicit", cfg.explicit))
    cfg.category = str(show.get("category", cfg.category))

    cfg.persona_name = str(persona.get("name", cfg.persona_name))
    cfg.persona_bio = str(persona.get("bio", cfg.persona_bio))
    cfg.persona_style = str(persona.get("style", cfg.persona_style))

    cfg.default_duration_minutes = int(pipeline.get("default_duration_minutes", cfg.default_duration_minutes))
    cfg.target_wpm = int(pipeline.get("target_wpm", cfg.target_wpm))
    cfg.max_sentence_words = int(pipeline.get("max_sentence_words", cfg.max_sentence_words))
    cfg.coverage_threshold = float(pipeline.get("coverage_threshold", cfg.coverage_threshold))
    cfg.story_dedup_days = int(pipeline.get("story_dedup_days", cfg.story_dedup_days))
    cfg.rss_timeout_seconds = int(pipeline.get("rss_timeout_seconds", cfg.rss_timeout_seconds))
    cfg.rss_retries = int(pipeline.get("rss_retries", cfg.rss_retries))
    cfg.default_publish = bool(pipeline.get("default_publish", cfg.default_publish))

    feeds = rss.get("feeds", [])
    cfg.rss_feeds = [str(u) for u in feeds] if isinstance(feeds, list) else []

    cfg.corpus_dir = str(rag.get("corpus_dir", cfg.corpus_dir))
    cfg.index_path = str(rag.get("index_path", cfg.index_path))
    cfg.chunk_size = int(rag.get("chunk_size", cfg.chunk_size))
    cfg.chunk_overlap = int(rag.get("chunk_overlap", cfg.chunk_overlap))
    cfg.rag_backend = str(rag.get("backend", cfg.rag_backend))
    cfg.rag_top_k = int(rag.get("top_k", cfg.rag_top_k))

    cfg.voice_backend = str(voice.get("backend", cfg.voice_backend))
    cfg.voice_id = str(voice.get("id", cfg.voice_id))
    cfg.reference_wav = str(voice.get("reference_wav", cfg.reference_wav))
    cfg.refuse_system_fallback = bool(voice.get("refuse_system_fallback", cfg.refuse_system_fallback))

    cfg.llm_backend = str(llm.get("backend", cfg.llm_backend))
    cfg.llm_model = str(llm.get("model", cfg.llm_model))
    cfg.llm_base_url = str(llm.get("base_url", cfg.llm_base_url))
    cfg.llm_timeout_seconds = int(llm.get("timeout_seconds", cfg.llm_timeout_seconds))

    cfg.output_dir = str(publish.get("output_dir", cfg.output_dir))
    cfg.media_dir = str(publish.get("media_dir", cfg.media_dir))

    cfg.voice_backend = os.environ.get("NONCAST_VOICE_BACKEND", cfg.voice_backend)
    cfg.voice_id = os.environ.get("NONCAST_VOICE_ID", cfg.voice_id)
    cfg.llm_backend = os.environ.get("NONCAST_LLM_BACKEND", cfg.llm_backend)
    cfg.llm_model = os.environ.get("NONCAST_LLM_MODEL", os.environ.get("OPENAI_MODEL", os.environ.get("ANTHROPIC_MODEL", cfg.llm_model)))
    if os.environ.get("OLLAMA_HOST"):
        cfg.llm_base_url = os.environ["OLLAMA_HOST"].rstrip("/")
    return cfg
