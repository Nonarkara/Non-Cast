from noncast.models import AuditReport, PublishBlocked
from noncast.pipeline.publish import gate


def test_low_coverage_blocks_publish():
    report = AuditReport(
        coverage=0.5,
        source_coverage=0.5,
        audio_coverage=0.5,
        threshold=0.95,
        errors=["coverage 0.500 < 0.95"],
        publishable=False,
    )
    try:
        gate(report)
        raise AssertionError("expected PublishBlocked")
    except PublishBlocked as exc:
        assert "coverage" in str(exc)


def test_audit_error_blocks_even_if_coverage_high():
    report = AuditReport(
        coverage=0.99,
        source_coverage=0.99,
        audio_coverage=0.99,
        threshold=0.95,
        errors=["killword: delve"],
        publishable=False,
    )
    try:
        gate(report)
        raise AssertionError("expected PublishBlocked")
    except PublishBlocked as exc:
        assert "killword" in str(exc)


def test_system_voice_blocks_even_if_clean_otherwise():
    report = AuditReport(
        coverage=1.0,
        source_coverage=1.0,
        audio_coverage=1.0,
        threshold=0.95,
        errors=[],
        used_system_fallback=True,
        publishable=False,
    )
    try:
        gate(report)
        raise AssertionError("expected PublishBlocked")
    except PublishBlocked as exc:
        assert "system-voice" in str(exc)


def test_clean_high_coverage_may_publish():
    report = AuditReport(
        coverage=0.97,
        source_coverage=0.97,
        audio_coverage=0.97,
        threshold=0.95,
        errors=[],
        used_system_fallback=False,
        publishable=True,
    )
    gate(report)


def test_today_default_does_not_publish(project, cfg):
    from noncast import rag
    from noncast.pipeline.today import run_today

    rag.ingest(cfg, project / "corpus")
    summary = run_today(cfg, date="2026-08-31", topic="rss feeds", minutes=3, publish_flag=False)
    assert summary["publish"]["published"] is False
    script = project / "data" / "runs" / "2026-08-31" / "script.md"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "## Spoken" in text
    assert "Daily Brief" in text or "Welcome" in text
