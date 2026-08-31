from noncast import rag


def test_ingest_and_retrieve_rss(cfg, project):
    stats = rag.ingest(cfg, project / "corpus")
    assert int(stats["documents"]) >= 2
    assert int(stats["chunks"]) >= 2
    hits = rag.retrieve(cfg, "rss enclosure feed directories", k=3)
    assert hits
    blob = " ".join(h.title.lower() + " " + h.text.lower() for h in hits[:2])
    assert "enclosure" in blob or "rss" in blob


def test_retrieve_voice_topic(cfg, project):
    rag.ingest(cfg, project / "corpus")
    hits = rag.retrieve(cfg, "voice cloning consent reference clip", k=3)
    assert hits
    blob = " ".join(h.title.lower() + " " + h.text.lower() for h in hits[:2])
    assert "consent" in blob or "voice" in blob or "reference" in blob


def test_skip_unchanged(cfg, project):
    first = rag.ingest(cfg, project / "corpus")
    second = rag.ingest(cfg, project / "corpus")
    assert int(second["skipped"]) >= int(first["documents"])
    assert int(second["added"]) == 0
