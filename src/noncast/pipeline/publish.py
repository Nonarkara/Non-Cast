"""Write a podcast RSS 2.0 feed. Spotify/Apple follow the feed. No partner API."""

from __future__ import annotations

import hashlib
import html
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from noncast.config import Config
from noncast.models import AuditReport, PublishBlocked
from noncast.pipeline import dedup
from noncast.pipeline.io import dump_json, ensure_run, load_json, today_stamp
from noncast.pipeline.scrape import stories_from_payload
from noncast.pipeline.voice import wav_duration_seconds
from noncast.textutil import spoken_and_notes, word_count


def run(
    cfg: Config,
    date: str | None = None,
    report: AuditReport | None = None,
    publish: bool = False,
) -> dict:
    date = today_stamp(date)
    rundir = ensure_run(cfg, date)
    if not publish:
        payload = {"published": False, "reason": "default --no-publish"}
        dump_json(rundir / "publish.json", payload)
        return payload
    if report is None:
        from noncast.pipeline.audit import run as audit_run

        report = audit_run(cfg, date=date)
    gate(report)
    script = rundir / "script.md"
    audio = _audio(rundir)
    if audio is None:
        raise PublishBlocked("refusing to publish: no episode audio")
    media_name = f"{date}-daily-brief{audio.suffix}"
    dest = cfg.media / media_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(audio.read_bytes())
    spoken, notes = spoken_and_notes(script.read_text(encoding="utf-8") if script.is_file() else "")
    duration = wav_duration_seconds(dest) if dest.suffix.lower() == ".wav" else max(1.0, word_count(spoken) / cfg.target_wpm * 60)
    item = {
        "guid": hashlib.sha256(f"{cfg.show_name}:{date}".encode()).hexdigest(),
        "title": f"{cfg.show_name} — {date}",
        "date": date,
        "description": notes or spoken[:400],
        "enclosure": f"{cfg.site_url}/episodes/{media_name}",
        "length": dest.stat().st_size,
        "type": "audio/wav" if dest.suffix.lower() == ".wav" else "audio/mpeg",
        "duration": int(duration),
        "pubDate": format_datetime(datetime.now(timezone.utc)),
    }
    items = _load_items(cfg)
    items = [i for i in items if i.get("date") != date]
    items.insert(0, item)
    sidecar = cfg.path("data/feed-items.json")
    dump_json(sidecar, items)
    xml = render_feed(cfg, items)
    cfg.feed.parent.mkdir(parents=True, exist_ok=True)
    cfg.feed.write_text(xml, encoding="utf-8")
    stories_path = rundir / "stories.json"
    if stories_path.is_file():
        payload = load_json(stories_path)
        if isinstance(payload, dict):
            dedup.record(
                cfg.dedup_path,
                stories_from_payload(payload),
                days=cfg.story_dedup_days,
            )
    result = {"published": True, "feed": str(cfg.feed), "audio": str(dest), "item": item}
    dump_json(rundir / "publish.json", result)
    return result


def gate(report: AuditReport) -> None:
    if report.used_system_fallback:
        raise PublishBlocked("refusing to publish: system-voice fallback")
    if report.errors:
        raise PublishBlocked("refusing to publish: " + "; ".join(report.errors))
    if report.coverage < report.threshold or not report.publishable:
        raise PublishBlocked(
            f"refusing to publish: coverage {report.coverage:.3f} < {report.threshold}"
        )


def render_feed(cfg: Config, items: list[dict]) -> str:
    channel_items = "\n".join(_item_xml(i) for i in items)
    explicit = "yes" if cfg.explicit else "no"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{escape(cfg.show_name)}</title>
    <link>{escape(cfg.site_url)}</link>
    <language>{escape(cfg.show_language)}</language>
    <description>{escape(cfg.show_description)}</description>
    <itunes:author>{escape(cfg.show_author)}</itunes:author>
    <itunes:summary>{escape(cfg.show_description)}</itunes:summary>
    <itunes:explicit>{explicit}</itunes:explicit>
    <itunes:category text="{escape(cfg.category)}"/>
    <itunes:owner>
      <itunes:name>{escape(cfg.show_author)}</itunes:name>
      <itunes:email>{escape(cfg.email)}</itunes:email>
    </itunes:owner>
    <image>
      <url>{escape(cfg.site_url)}/hero.png</url>
      <title>{escape(cfg.show_name)}</title>
      <link>{escape(cfg.site_url)}</link>
    </image>
{channel_items}
  </channel>
</rss>
"""


def _item_xml(item: dict) -> str:
    desc = html.escape(str(item.get("description") or ""))
    return f"""    <item>
      <title>{escape(str(item.get("title") or ""))}</title>
      <guid isPermaLink="false">{escape(str(item.get("guid") or ""))}</guid>
      <pubDate>{escape(str(item.get("pubDate") or ""))}</pubDate>
      <description>{desc}</description>
      <enclosure url="{escape(str(item.get("enclosure") or ""))}" length="{int(item.get("length") or 0)}" type="{escape(str(item.get("type") or "audio/mpeg"))}"/>
      <itunes:duration>{int(item.get("duration") or 0)}</itunes:duration>
    </item>"""


def _load_items(cfg: Config) -> list[dict]:
    sidecar = cfg.path("data/feed-items.json")
    if sidecar.is_file():
        data = load_json(sidecar)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    return []


def _audio(rundir: Path) -> Path | None:
    for name in ("episode.wav", "episode.mp3"):
        p = rundir / name
        if p.is_file():
            return p
    return None
