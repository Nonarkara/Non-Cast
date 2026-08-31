"""Agent-agnostic CLI. No vendor SDK required for the happy path."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from noncast import __version__, initkit, rag
from noncast.config import load_config
from noncast.models import PublishBlocked
from noncast.nl import parse_nl
from noncast.paths import find_root
from noncast.pipeline import analyze, audit, copyedit, draft, earlint, publish, scrape, voice
from noncast.pipeline.io import today_stamp
from noncast.pipeline.today import run_today

COMMANDS = {
    "init",
    "ingest",
    "today",
    "audit",
    "scrape",
    "analyze",
    "draft",
    "copyedit",
    "earlint",
    "voice",
    "publish",
    "status",
    "help",
    "version",
}

HELP = f"""Non-Cast {__version__} — fork, add a corpus, get a daily podcast.

Commands:
  noncast init
  noncast ingest ./corpus
  noncast today
  noncast today --no-publish
  noncast "make a 12 minute episode about voice cloning law, don't publish"
  noncast audit episode.mp3 episode.md
  noncast scrape|analyze|draft|copyedit|earlint|voice|publish
  noncast status

Default is --no-publish. Coverage must be ≥ 0.95 and audit must be clean to publish.
Natural-language commands call the pluggable LLM (Ollama by default) and fall back
to a heuristic parser if the model is down.

Read AGENTS.md. Identity lives in noncast.toml and corpus/. Do not invent facts.
"""


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(HELP)
        return 0
    if argv[0] in {"-V", "--version", "version"}:
        print(__version__)
        return 0
    if argv[0] not in COMMANDS and not argv[0].startswith("-"):
        return cmd_nl(argv)
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else (0 if code is None else 1)
    return int(args.func(args))


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="noncast", description="Daily podcast kit", add_help=True)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="Create local dirs and missing kit files")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("ingest", help="Index markdown corpus")
    s.add_argument("path", nargs="?", default="./corpus")
    s.set_defaults(func=cmd_ingest)

    s = sub.add_parser("today", help="Run scrape → … → audit (default --no-publish)")
    _episode_flags(s)
    s.set_defaults(func=cmd_today)

    s = sub.add_parser("audit", help="Whole-episode audit (fail-closed)")
    s.add_argument("audio", nargs="?", help="episode.mp3 or episode.wav")
    s.add_argument("script", nargs="?", help="episode.md")
    s.add_argument("--date")
    s.set_defaults(func=cmd_audit)

    for name, fn, help_ in (
        ("scrape", cmd_scrape, "Fetch RSS (parallel, short timeout, 2 retries)"),
        ("analyze", cmd_analyze, "Rank stories against the corpus"),
        ("draft", cmd_draft, "Write script.md"),
        ("copyedit", cmd_copyedit, "Kill-words, quotes, stats, family"),
        ("earlint", cmd_earlint, "~30 word sentences"),
        ("voice", cmd_voice, "Synthesize (no system-voice fallback)"),
        ("publish", cmd_publish, "Write RSS if audit passes"),
    ):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--date")
        if name in {"analyze", "draft"}:
            s.add_argument("--topic")
        if name == "draft":
            s.add_argument("--minutes", type=int)
        if name in {"copyedit", "earlint", "voice"}:
            s.add_argument("script", nargs="?")
        if name == "publish":
            s.add_argument("--publish", action="store_true")
        s.set_defaults(func=fn)

    s = sub.add_parser("status", help="Show config and index stats")
    s.set_defaults(func=cmd_status)
    return p


def _episode_flags(s: argparse.ArgumentParser) -> None:
    s.add_argument("--date")
    s.add_argument("--topic")
    s.add_argument("--minutes", type=int)
    s.add_argument("--publish", action="store_true", help="Attempt RSS publish (still fail-closed)")
    s.add_argument("--no-publish", action="store_true", default=False, help="Do not publish (default)")
    s.add_argument("--script-only", action="store_true", help="Skip voice synthesis")


def cmd_init(_args: argparse.Namespace) -> int:
    info = initkit.run()
    print(f"initialized {info['root']} ({info['show']})")
    if info["created"]:
        print("created:")
        for rel in info["created"]:
            print(f"  {rel}")
    print("next: drop markdown in corpus/ && noncast ingest ./corpus && noncast today --no-publish")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    cfg = load_config()
    stats = rag.ingest(cfg, Path(args.path).expanduser())
    print(json.dumps(stats, indent=2))
    return 0


def cmd_today(args: argparse.Namespace) -> int:
    cfg = load_config()
    publish_flag = bool(args.publish) and not bool(args.no_publish)
    summary = run_today(
        cfg,
        date=args.date,
        topic=args.topic,
        minutes=args.minutes,
        publish_flag=publish_flag,
        script_only=bool(args.script_only),
    )
    print(json.dumps(summary, indent=2))
    script = summary.get("script")
    if script:
        print(f"\nscript: {script}", file=sys.stderr)
    if not summary.get("publish", {}).get("published"):
        print("not published (default --no-publish or audit fail-closed)", file=sys.stderr)
    return 0


def cmd_nl(argv: list[str]) -> int:
    cfg = load_config()
    text = " ".join(argv)
    intent = parse_nl(text, cfg)
    if intent.action == "ingest":
        stats = rag.ingest(cfg, cfg.corpus)
        print(json.dumps(stats, indent=2))
        return 0
    summary = run_today(
        cfg,
        date=intent.date,
        topic=intent.topic,
        minutes=intent.minutes,
        publish_flag=intent.publish,
    )
    print(json.dumps({"intent": intent.__dict__, "run": summary}, indent=2))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    cfg = load_config()
    report = audit.run(
        cfg,
        date=args.date,
        audio_path=Path(args.audio) if args.audio else None,
        script_path=Path(args.script) if args.script else None,
    )
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.publishable else 1


def cmd_scrape(args: argparse.Namespace) -> int:
    print(json.dumps(scrape.run(load_config(), date=args.date), indent=2, default=str))
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    topic = getattr(args, "topic", None)
    print(json.dumps(analyze.run(load_config(), date=args.date, topic=topic), indent=2))
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    print(
        json.dumps(
            draft.run(
                load_config(),
                date=args.date,
                topic=getattr(args, "topic", None),
                minutes=getattr(args, "minutes", None),
            ),
            indent=2,
        )
    )
    return 0


def cmd_copyedit(args: argparse.Namespace) -> int:
    script = Path(args.script) if getattr(args, "script", None) else None
    print(json.dumps(copyedit.run(load_config(), date=args.date, script_path=script), indent=2))
    return 0


def cmd_earlint(args: argparse.Namespace) -> int:
    script = Path(args.script) if getattr(args, "script", None) else None
    report = earlint.run(load_config(), date=args.date, script_path=script)
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


def cmd_voice(args: argparse.Namespace) -> int:
    script = Path(args.script) if getattr(args, "script", None) else None
    info = voice.run(load_config(), date=args.date, script_path=script)
    print(json.dumps(info, indent=2))
    return 0 if not info.get("error") or info.get("skipped") else 1


def cmd_publish(args: argparse.Namespace) -> int:
    cfg = load_config()
    try:
        info = publish.run(cfg, date=args.date, publish=bool(getattr(args, "publish", False)))
    except PublishBlocked as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(info, indent=2, default=str))
    return 0 if info.get("published") else 1


def cmd_status(_args: argparse.Namespace) -> int:
    root = find_root()
    cfg = load_config(root)
    stats = {"documents": 0, "chunks": 0, "backend": cfg.rag_backend}
    if cfg.index.is_file():
        idx = rag.open_index(cfg)
        try:
            stats = idx.stats()
        finally:
            idx.close()
    print(
        json.dumps(
            {
                "version": __version__,
                "root": str(cfg.root),
                "show": cfg.show_name,
                "corpus": str(cfg.corpus),
                "rag": stats,
                "voice_backend": cfg.voice_backend,
                "llm_backend": cfg.llm_backend,
                "coverage_threshold": cfg.coverage_threshold,
                "default_publish": cfg.default_publish,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
