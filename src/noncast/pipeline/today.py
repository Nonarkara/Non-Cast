"""End-to-end pipeline. Default is --no-publish until a forker opts in AND coverage ≥ 0.95."""

from __future__ import annotations

from noncast.config import Config
from noncast.models import PublishBlocked
from noncast.pipeline import analyze, audit, copyedit, draft, earlint, publish, scrape, voice
from noncast.pipeline.io import dump_json, ensure_run, today_stamp


def run_today(
    cfg: Config,
    *,
    date: str | None = None,
    topic: str | None = None,
    minutes: int | None = None,
    publish_flag: bool = False,
    script_only: bool = False,
) -> dict:
    date = today_stamp(date)
    rundir = ensure_run(cfg, date)
    scrape_info = scrape.run(cfg, date=date)
    analyze.run(cfg, date=date, topic=topic)
    draft_info = draft.run(cfg, date=date, topic=topic, minutes=minutes)
    copyedit.run(cfg, date=date)
    ear = earlint.run(cfg, date=date)
    voice_info: dict = {"skipped": True}
    if not script_only:
        voice_info = voice.run(cfg, date=date)
    report = audit.run(cfg, date=date)
    pub: dict
    if publish_flag:
        try:
            pub = publish.run(cfg, date=date, report=report, publish=True)
        except PublishBlocked as exc:
            pub = {"published": False, "reason": str(exc)}
    else:
        pub = publish.run(cfg, date=date, report=report, publish=False)
    summary = {
        "date": date,
        "rundir": str(rundir),
        "script": draft_info.get("path"),
        "stories": len((scrape_info.get("items") or [])),
        "deduped": len((scrape_info.get("deduped") or [])),
        "earlint_ok": ear.get("ok"),
        "voice": {k: voice_info.get(k) for k in ("backend", "skipped", "error", "audio", "cached", "synthesized")},
        "audit": report.to_dict(),
        "publish": pub,
    }
    dump_json(rundir / "summary.json", summary)
    return summary
