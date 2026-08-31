"""Whole-episode audit. Fail-closed: any error blocks publish."""

from __future__ import annotations

from pathlib import Path

from noncast import rag
from noncast.config import Config
from noncast.models import AuditReport
from noncast.pipeline.earlint import lint_text
from noncast.pipeline.io import dump_json, ensure_run, load_json, today_stamp
from noncast.pipeline.voice import wav_duration_seconds
from noncast.textutil import spoken_and_notes, split_sentences, word_count


def run(
    cfg: Config,
    date: str | None = None,
    audio_path: Path | None = None,
    script_path: Path | None = None,
) -> AuditReport:
    date = today_stamp(date)
    rundir = ensure_run(cfg, date)
    script = Path(script_path) if script_path else rundir / "script.md"
    audio = Path(audio_path) if audio_path else _guess_audio(rundir)
    spoken, notes = spoken_and_notes(script.read_text(encoding="utf-8") if script.is_file() else "")
    voice_meta = {}
    voice_json = rundir / "voice.json"
    if voice_json.is_file():
        loaded = load_json(voice_json)
        if isinstance(loaded, dict):
            voice_meta = loaded

    errors: list[str] = []
    warnings: list[str] = []
    if not script.is_file():
        errors.append("script missing")
        spoken = ""

    issues = lint_text(spoken, cfg.lexicon, cfg.max_sentence_words)
    for issue in issues:
        errors.append(f"{issue.kind}: {issue.detail}")

    source_cov = source_coverage(spoken, rag.all_source_text(cfg) + "\n" + notes, cfg)
    audio_cov = audio_coverage(spoken, audio, voice_meta, cfg)
    used_fallback = bool(voice_meta.get("used_system_fallback"))
    if used_fallback:
        errors.append("system-voice fallback is forbidden")
    if cfg.refuse_system_fallback and voice_meta.get("placeholder"):
        errors.append("placeholder/null voice is not publishable")

    coverage = min(source_cov, audio_cov)
    # Script-only audits still report audio_cov=0, which is an error when publishing.
    if audio_cov < cfg.coverage_threshold:
        errors.append(f"audio coverage {audio_cov:.3f} < {cfg.coverage_threshold}")
    if source_cov < cfg.coverage_threshold:
        errors.append(f"source coverage {source_cov:.3f} < {cfg.coverage_threshold}")
    if coverage < cfg.coverage_threshold:
        errors.append(f"coverage {coverage:.3f} < {cfg.coverage_threshold}")

    # Fail closed on missing audio when voice was supposed to run
    backend = str(voice_meta.get("backend") or cfg.voice_backend)
    if backend not in {"none", "off", "skip"} and not (audio and audio.is_file()):
        errors.append("episode audio missing")
        coverage = 0.0
        audio_cov = 0.0

    report = AuditReport(
        coverage=round(coverage, 4),
        source_coverage=round(source_cov, 4),
        audio_coverage=round(audio_cov, 4),
        threshold=cfg.coverage_threshold,
        errors=errors,
        warnings=warnings,
        used_system_fallback=used_fallback,
        publishable=not errors and coverage >= cfg.coverage_threshold and not used_fallback,
    )
    dump_json(rundir / "audit.json", report.to_dict())
    return report


def source_coverage(spoken: str, sources: str, cfg: Config) -> float:
    sentences = split_sentences(spoken)
    if not sentences:
        return 0.0
    source_l = sources.lower()
    glue = _glue_prefixes(cfg)
    ok = 0
    for sent in sentences:
        lower = sent.lower()
        if any(lower.startswith(g) or g in lower for g in glue):
            ok += 1
            continue
        words = [w for w in lower.replace(".", " ").split() if len(w) > 3]
        if not words:
            ok += 1
            continue
        hits = sum(1 for w in words if w in source_l)
        if hits / max(len(words), 1) >= 0.25:
            ok += 1
    return ok / len(sentences)


def audio_coverage(spoken: str, audio: Path | None, voice_meta: dict, cfg: Config) -> float:
    sentences = split_sentences(spoken)
    if not sentences:
        return 0.0
    rows = voice_meta.get("sentence_results") or []
    if rows:
        by_text = {str(r.get("text") or ""): r for r in rows if isinstance(r, dict)}
        ok = 0
        for sent in sentences:
            row = by_text.get(sent)
            if row and row.get("has_audio"):
                ok += 1
        return ok / len(sentences)
    if audio and audio.is_file():
        expected = word_count(spoken) / max(cfg.target_wpm, 1) * 60.0
        actual = wav_duration_seconds(audio)
        if expected <= 0 or actual <= 0:
            return 0.0
        return max(0.0, min(1.0, actual / expected))
    return 0.0


def _guess_audio(rundir: Path) -> Path | None:
    for name in ("episode.wav", "episode.mp3"):
        p = rundir / name
        if p.is_file():
            return p
    return None


def _glue_prefixes(cfg: Config) -> list[str]:
    return [
        "welcome to",
        "i'm ",
        "i am ",
        "today is ",
        "this episode is about",
        "that's the brief",
        "that is the brief",
        "from the corpus",
        "from the feed",
        "sources are in the show notes",
        "everything i say",
        "the brief has no unsourced",
        cfg.show_name.lower(),
        cfg.persona_name.lower(),
    ]
