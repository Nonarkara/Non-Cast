from datetime import datetime, timedelta, timezone

from noncast.models import Story
from noncast.pipeline.dedup import filter_new, is_duplicate, record


def _story(title: str, url: str) -> Story:
    return Story(id=title, title=title, url=url, summary="", published="", feed="x")


def test_url_dedup_within_three_days(tmp_path):
    path = tmp_path / "dedup.jsonl"
    now = datetime(2026, 8, 31, tzinfo=timezone.utc)
    first = _story("Voice cloning bill", "https://example.com/a")
    record(path, [first], now=now, days=3)
    later = now + timedelta(days=2)
    fresh, dupes = filter_new([first], path, days=3, now=later)
    assert dupes and not fresh


def test_url_allowed_after_window(tmp_path):
    path = tmp_path / "dedup.jsonl"
    now = datetime(2026, 8, 31, tzinfo=timezone.utc)
    first = _story("Voice cloning bill", "https://example.com/a")
    record(path, [first], now=now, days=3)
    later = now + timedelta(days=4)
    fresh, dupes = filter_new([first], path, days=3, now=later)
    assert fresh and not dupes


def test_near_identical_title(tmp_path):
    path = tmp_path / "dedup.jsonl"
    now = datetime(2026, 8, 31, tzinfo=timezone.utc)
    record(path, [_story("Voice cloning law passes senate", "https://example.com/a")], now=now, days=3)
    twin = _story("Voice cloning law passes the senate", "https://example.com/b")
    assert is_duplicate(twin, __import__("noncast.pipeline.dedup", fromlist=["load_log"]).load_log(path), now=now, days=3)


def test_distinct_titles_pass(tmp_path):
    path = tmp_path / "dedup.jsonl"
    now = datetime(2026, 8, 31, tzinfo=timezone.utc)
    record(path, [_story("RSS directories follow the feed", "https://example.com/a")], now=now, days=3)
    other = _story("A completely different local-first note", "https://example.com/b")
    fresh, dupes = filter_new([other], path, days=3, now=now)
    assert fresh and not dupes
