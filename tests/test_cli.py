import json

from noncast import __version__
from noncast.cli import main
from noncast.nl import parse_nl


def test_help(capsys):
    code = main(["--help"])
    out = capsys.readouterr().out.lower()
    assert code == 0
    assert "ingest" in out
    assert "today" in out
    assert "audit" in out
    assert "noncast" in out


def test_help_via_empty(capsys):
    code = main([])
    assert code == 0
    assert "fork" in capsys.readouterr().out.lower()


def test_version(capsys):
    code = main(["--version"])
    assert code == 0
    assert __version__ in capsys.readouterr().out


def test_status(project, capsys):
    code = main(["status"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["show"] == "Daily Brief"
    assert data["coverage_threshold"] == 0.95


def test_nl_heuristic_example():
    intent = parse_nl("make a 12 minute episode about voice cloning law, don't publish")
    assert intent.minutes == 12
    assert intent.publish is False
    assert intent.topic is not None
    assert "voice cloning law" in intent.topic.lower()
