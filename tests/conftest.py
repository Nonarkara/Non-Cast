from __future__ import annotations

from pathlib import Path

import pytest

from noncast.config import load_config
from noncast.initkit import run as init_run


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    init_run(tmp_path)
    (tmp_path / "corpus" / "rss.md").write_text(
        "# The RSS enclosure\n\n"
        "An enclosure is the audio file listed in a feed item. "
        "Directories follow the feed. Spotify and Apple do not need a partner API.\n",
        encoding="utf-8",
    )
    (tmp_path / "corpus" / "voice.md").write_text(
        "# Voice cloning consent\n\n"
        "A reference clip is not a vibe file. Consent is the whole plot. "
        "Fail closed if the synthesizer is missing. Do not use a system voice.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NONCAST_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def cfg(project: Path):
    return load_config(project)
