from pathlib import Path

from noncast.pipeline.rss import fetch_feeds, parse_feed


FIXTURE = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Fixture Feed</title>
    <item>
      <title>Voice cloning law in committee</title>
      <link>https://example.com/voice-law</link>
      <description>A bill about consent for voice clones. Not legal advice.</description>
      <pubDate>Mon, 31 Aug 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>RSS directories follow the feed</title>
      <link>https://example.com/rss</link>
      <description>Apple and Spotify subscribe to a valid RSS enclosure.</description>
    </item>
  </channel>
</rss>
"""


def test_parse_rss_items():
    items = parse_feed(FIXTURE, "https://example.com/feed.xml")
    assert len(items) == 2
    assert "voice cloning" in items[0].title.lower()


def test_file_url_fetch(tmp_path: Path):
    feed = tmp_path / "feed.xml"
    feed.write_text(FIXTURE, encoding="utf-8")
    results = fetch_feeds([feed.as_uri()], timeout=2, retries=0)
    assert results[0]["ok"] is True
    assert results[0]["item_count"] == 2


def test_dead_host_fails_fast():
    # 192.0.2.0/24 is documentation-only; connect should fail quickly with a short timeout.
    results = fetch_feeds(["http://192.0.2.1/feed.xml"], timeout=1, retries=0)
    assert results[0]["ok"] is False
    assert results[0]["elapsed_ms"] < 10_000
