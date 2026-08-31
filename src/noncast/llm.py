"""Pluggable LLM over stdlib HTTP. No vendor SDK.

Default: local Ollama. Optional OpenAI / Anthropic via env keys.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from noncast.config import Config


class LLMError(RuntimeError):
    pass


def complete(prompt: str, cfg: Config, system: str | None = None) -> str | None:
    """Return model text, or None if the backend is down / unconfigured."""
    backend = (cfg.llm_backend or "ollama").lower()
    try:
        if backend == "openai" or (backend == "auto" and os.environ.get("OPENAI_API_KEY")):
            return _openai(prompt, cfg, system)
        if backend == "anthropic" or (backend == "auto" and os.environ.get("ANTHROPIC_API_KEY")):
            return _anthropic(prompt, cfg, system)
        return _ollama(prompt, cfg, system)
    except (LLMError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _http_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise LLMError("non-object JSON")
    return parsed


def _ollama(prompt: str, cfg: Config, system: str | None) -> str:
    url = cfg.llm_base_url.rstrip("/") + "/api/generate"
    payload: dict[str, Any] = {
        "model": cfg.llm_model,
        "prompt": prompt if not system else f"{system}\n\n{prompt}",
        "stream": False,
    }
    result = _http_json(url, payload, {}, cfg.llm_timeout_seconds)
    text = str(result.get("response") or "").strip()
    if not text:
        raise LLMError("empty Ollama response")
    return text


def _openai(prompt: str, cfg: Config, system: str | None) -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise LLMError("OPENAI_API_KEY missing")
    model = os.environ.get("OPENAI_MODEL", cfg.llm_model or "gpt-4o-mini")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    result = _http_json(
        "https://api.openai.com/v1/chat/completions",
        {"model": model, "messages": messages, "temperature": 0.2},
        {"Authorization": f"Bearer {key}"},
        cfg.llm_timeout_seconds,
    )
    choices = result.get("choices") or []
    if not choices:
        raise LLMError("empty OpenAI response")
    text = str(choices[0].get("message", {}).get("content") or "").strip()
    if not text:
        raise LLMError("empty OpenAI content")
    return text


def _anthropic(prompt: str, cfg: Config, system: str | None) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise LLMError("ANTHROPIC_API_KEY missing")
    model = os.environ.get("ANTHROPIC_MODEL", cfg.llm_model or "claude-3-5-haiku-latest")
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    result = _http_json(
        "https://api.anthropic.com/v1/messages",
        payload,
        {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        cfg.llm_timeout_seconds,
    )
    blocks = result.get("content") or []
    texts = [str(b.get("text") or "") for b in blocks if isinstance(b, dict)]
    text = "\n".join(t for t in texts if t).strip()
    if not text:
        raise LLMError("empty Anthropic response")
    return text
