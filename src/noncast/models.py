from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Story:
    id: str
    title: str
    url: str
    summary: str
    published: str
    feed: str

    def key(self) -> str:
        return (self.url or self.title).strip().lower()


@dataclass
class ChunkHit:
    chunk_id: int
    path: str
    title: str
    text: str
    score: float


@dataclass
class Intent:
    action: str = "produce_episode"
    topic: str | None = None
    minutes: int | None = None
    publish: bool = False
    date: str | None = None
    raw: str = ""


@dataclass
class LintIssue:
    kind: str
    sentence: str
    detail: str


@dataclass
class AuditReport:
    coverage: float
    source_coverage: float
    audio_coverage: float
    threshold: float
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    used_system_fallback: bool = False
    publishable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage": self.coverage,
            "source_coverage": self.source_coverage,
            "audio_coverage": self.audio_coverage,
            "threshold": self.threshold,
            "errors": self.errors,
            "warnings": self.warnings,
            "used_system_fallback": self.used_system_fallback,
            "publishable": self.publishable,
        }


class PublishBlocked(RuntimeError):
    """Raised when publish is requested but audit fail-closes."""


class VoiceUnavailable(RuntimeError):
    """Configured voice backend cannot run. Never fall back to system TTS."""
