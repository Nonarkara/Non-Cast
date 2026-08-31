"""Pluggable voice backends. Never fall back to system TTS (say/espeak)."""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any

from noncast.config import Config
from noncast.models import VoiceUnavailable
from noncast.pipeline import cache
from noncast.pipeline.io import dump_json, ensure_run, today_stamp
from noncast.textutil import spoken_and_notes, split_sentences

SAMPLE_RATE = 24000


def run(cfg: Config, date: str | None = None, script_path: Path | None = None) -> dict:
    date = today_stamp(date)
    rundir = ensure_run(cfg, date)
    path = Path(script_path) if script_path else rundir / "script.md"
    spoken, _ = spoken_and_notes(path.read_text(encoding="utf-8"))
    sentences = split_sentences(spoken)
    settings = {"backend": cfg.voice_backend, "rate": SAMPLE_RATE}
    backend = (cfg.voice_backend or "none").lower()
    out_audio = rundir / "episode.wav"
    result: dict[str, Any] = {
        "backend": backend,
        "voice_id": cfg.voice_id,
        "used_system_fallback": False,
        "placeholder": False,
        "skipped": False,
        "error": None,
        "audio": None,
        "cached": 0,
        "synthesized": 0,
        "sentence_results": [],
    }
    if backend in {"none", "off", "skip"}:
        result["skipped"] = True
        result["error"] = "voice backend is none; synthesis skipped (not a system-voice fallback)"
        dump_json(rundir / "voice.json", result)
        return result

    try:
        engine = _engine(backend, cfg)
    except VoiceUnavailable as exc:
        result["error"] = str(exc)
        result["skipped"] = True
        dump_json(rundir / "voice.json", result)
        return result

    chunks: list[Path] = []
    try:
        for sent in sentences:
            hit = cache.lookup(cfg.cache_dir, sent, cfg.voice_id, settings)
            if hit:
                result["cached"] += 1
                result["sentence_results"].append({"text": sent, "has_audio": True, "cached": True})
                chunks.append(hit)
                continue
            audio, suffix = engine.synthesize(sent, cfg)
            stored = cache.store(cfg.cache_dir, sent, cfg.voice_id, settings, audio, suffix)
            result["synthesized"] += 1
            result["sentence_results"].append({"text": sent, "has_audio": True, "cached": False})
            chunks.append(stored)
        if chunks:
            concat_wav(chunks, out_audio)
            result["audio"] = str(out_audio)
        else:
            result["error"] = "no sentences to synthesize"
    except VoiceUnavailable as exc:
        result["error"] = str(exc)
        result["skipped"] = True
        result["sentence_results"] = []
        result["cached"] = 0
        result["synthesized"] = 0
        if out_audio.exists():
            out_audio.unlink()
    dump_json(rundir / "voice.json", result)
    return result


class _Engine:
    name = "base"

    def synthesize(self, text: str, cfg: Config) -> tuple[bytes, str]:
        raise NotImplementedError


class NullEngine(_Engine):
    """Silent WAV for tests. Never publishable as a real host voice."""

    name = "null"

    def synthesize(self, text: str, cfg: Config) -> tuple[bytes, str]:
        seconds = max(0.15, min(1.5, len(text.split()) / 3.0))
        return silent_wav(seconds, SAMPLE_RATE), ".wav"


class F5Engine(_Engine):
    name = "f5-tts-mlx"

    def synthesize(self, text: str, cfg: Config) -> tuple[bytes, str]:
        ref = cfg.path(cfg.reference_wav)
        if not ref.is_file():
            raise VoiceUnavailable(
                f"missing reference clip at {ref}. Add a consented voices/reference.wav "
                "(gitignored). Apple Silicon: pip install f5-tts-mlx"
            )
        binary = shutil.which("f5-tts_mlx")
        if not binary:
            raise VoiceUnavailable(
                "f5-tts-mlx is not installed. On Apple Silicon: pip install f5-tts-mlx. "
                "Non-Cast will not fall back to say/espeak."
            )
        out = cfg.cache_dir / "f5-tmp.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [binary, "--text", text, "--ref-audio", str(ref), "--output", str(out)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            raise VoiceUnavailable(f"f5-tts-mlx failed: {exc}") from exc
        if not out.is_file():
            raise VoiceUnavailable("f5-tts-mlx produced no audio")
        data = out.read_bytes()
        out.unlink(missing_ok=True)
        return data, ".wav"


class ElevenLabsEngine(_Engine):
    name = "elevenlabs"

    def synthesize(self, text: str, cfg: Config) -> tuple[bytes, str]:
        key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not key:
            raise VoiceUnavailable("ELEVENLABS_API_KEY missing; refusing system-voice fallback")
        voice_id = os.environ.get("ELEVENLABS_VOICE_ID", cfg.voice_id)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        payload = (
            '{"text":'
            + _json_str(text)
            + ',"model_id":"eleven_monolingual_v1"}'
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "xi-api-key": key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read(), ".mp3"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise VoiceUnavailable(f"ElevenLabs stub failed: {exc}") from exc


class OpenAITTSEngine(_Engine):
    name = "openai"

    def synthesize(self, text: str, cfg: Config) -> tuple[bytes, str]:
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise VoiceUnavailable("OPENAI_API_KEY missing; refusing system-voice fallback")
        payload = (
            '{"model":"tts-1","voice":"alloy","input":' + _json_str(text) + "}"
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech",
            data=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read(), ".mp3"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise VoiceUnavailable(f"OpenAI TTS stub failed: {exc}") from exc


def _json_str(text: str) -> str:
    import json

    return json.dumps(text)


def _engine(backend: str, cfg: Config) -> _Engine:
    if backend == "null":
        if os.environ.get("NONCAST_ALLOW_NULL_VOICE") != "1":
            raise VoiceUnavailable("null voice is test-only; set NONCAST_ALLOW_NULL_VOICE=1")
        return NullEngine()
    if backend in {"f5", "f5-tts-mlx", "f5tts"}:
        return F5Engine()
    if backend in {"elevenlabs", "11labs"}:
        return ElevenLabsEngine()
    if backend in {"openai", "openai-tts"}:
        return OpenAITTSEngine()
    raise VoiceUnavailable(
        f"unknown voice backend {backend!r}. Non-Cast will not use system voices."
    )


def silent_wav(seconds: float, rate: int = SAMPLE_RATE) -> bytes:
    n = int(rate * seconds)
    with _BytesWave(rate) as buf:
        buf.writeframes(b"\x00\x00" * n)
        return buf.getvalue()


class _BytesWave:
    def __init__(self, rate: int):
        import io

        self._buf = io.BytesIO()
        self._rate = rate
        self._wav: wave.Wave_write | None = None

    def __enter__(self) -> wave.Wave_write:
        self._wav = wave.open(self._buf, "wb")
        self._wav.setnchannels(1)
        self._wav.setsampwidth(2)
        self._wav.setframerate(self._rate)
        return self._wav

    def __exit__(self, *args: object) -> None:
        if self._wav:
            self._wav.close()

    def getvalue(self) -> bytes:
        return self._buf.getvalue()


def concat_wav(paths: list[Path], dest: Path) -> None:
    """Concatenate wav chunks. Non-wav files are wrapped as a single copy if alone."""
    wavs = [p for p in paths if p.suffix.lower() == ".wav"]
    if not wavs:
        dest.write_bytes(paths[0].read_bytes())
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    params = None
    frames = []
    for p in wavs:
        with wave.open(str(p), "rb") as w:
            if params is None:
                params = w.getparams()
            frames.append(w.readframes(w.getnframes()))
    assert params is not None
    with wave.open(str(dest), "wb") as out:
        out.setparams(params)
        for f in frames:
            out.writeframes(f)


def wav_duration_seconds(path: Path) -> float:
    if not path.is_file():
        return 0.0
    if path.suffix.lower() != ".wav":
        return 0.0
    try:
        with wave.open(str(path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate() or 1
            return frames / float(rate)
    except wave.Error:
        return 0.0
