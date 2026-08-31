"""Run a single pipeline stage: python -m noncast.pipeline scrape"""

from __future__ import annotations

import sys

from noncast.cli import main as cli_main

STAGES = {
    "scrape",
    "analyze",
    "draft",
    "copyedit",
    "earlint",
    "voice",
    "audit",
    "publish",
    "today",
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print("usage: python -m noncast.pipeline <stage> [args...]")
        print("stages:", ", ".join(sorted(STAGES)))
        return 0
    if argv[0] not in STAGES:
        print(f"unknown stage {argv[0]!r}", file=sys.stderr)
        return 2
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
