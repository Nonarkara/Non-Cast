"""Natural-language command parser.

Calls the pluggable LLM when available; otherwise a deterministic heuristic
that understands the documented example:

    noncast "make a 12 minute episode about voice cloning law, don't publish"
"""

from __future__ import annotations

import json
import re

from noncast.config import Config
from noncast import llm
from noncast.models import Intent

_SYSTEM = """You convert a podcast-kit instruction into JSON.
Return ONLY JSON with keys:
  action: produce_episode | ingest | audit | today
  topic: string or null
  minutes: integer or null
  publish: boolean
  date: YYYY-MM-DD or null
Rules: default publish=false. If the user says don't publish, publish=false.
If they explicitly ask to publish, publish=true.
"""


def parse_nl(text: str, cfg: Config | None = None) -> Intent:
    text = text.strip()
    intent = _heuristic(text)
    if cfg is not None:
        raw = llm.complete(
            f"Instruction:\n{text}\n",
            cfg,
            system=_SYSTEM,
        )
        parsed = _from_llm_json(raw, text)
        if parsed is not None:
            return parsed
    return intent


def _from_llm_json(raw: str | None, original: str) -> Intent | None:
    if not raw:
        return None
    blob = raw.strip()
    if "```" in blob:
        blob = re.sub(r"^```(?:json)?", "", blob).strip()
        blob = blob.split("```", 1)[0].strip()
    try:
        start = blob.find("{")
        end = blob.rfind("}")
        if start == -1 or end == -1:
            return None
        data = json.loads(blob[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    publish = bool(data.get("publish", False))
    minutes = data.get("minutes")
    try:
        minutes_i = int(minutes) if minutes is not None else None
    except (TypeError, ValueError):
        minutes_i = None
    topic = data.get("topic")
    topic_s = str(topic).strip() if topic else None
    action = str(data.get("action") or "produce_episode")
    date = data.get("date")
    return Intent(
        action=action,
        topic=topic_s or None,
        minutes=minutes_i,
        publish=publish,
        date=str(date) if date else None,
        raw=original,
    )


def _heuristic(text: str) -> Intent:
    lower = text.lower()
    publish = False
    if re.search(r"\bpublish\b", lower) and not re.search(
        r"don'?t publish|do not publish|without publishing|no-publish|don't publish", lower
    ):
        publish = True
    if re.search(r"don'?t publish|do not publish|without publishing|no[- ]publish", lower):
        publish = False
    minutes = None
    m = re.search(r"(\d+)\s*-?\s*minute", lower)
    if m:
        minutes = int(m.group(1))
    topic = None
    m = re.search(r"\babout\s+(.+)$", text, re.I)
    if m:
        topic = m.group(1)
        topic = re.split(r",\s*(?:and\s+)?(?:please\s+)?(?:don'?t|do not|without)\b", topic, maxsplit=1, flags=re.I)[0]
        topic = re.sub(r"\bdon'?t publish.*$", "", topic, flags=re.I)
        topic = topic.strip(" .,").strip()
    action = "produce_episode"
    if re.fullmatch(r"today|daily|this morning", lower.strip()):
        action = "today"
        topic = None
    return Intent(action=action, topic=topic or None, minutes=minutes, publish=publish, raw=text)
