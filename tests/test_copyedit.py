from noncast.pipeline.copyedit import strip_unsourced


def test_drops_invented_quote():
    spoken = 'The senator said "we will jail every clone tomorrow night." Keep the rest.'
    sources = "The senator discussed consent rules for voice clones."
    text, removed = strip_unsourced(spoken, sources)
    assert any("quote" in r for r in removed)
    assert "jail every clone" not in text


def test_drops_invented_stat():
    spoken = "Fines hit 47 percent last week."
    sources = "The article mentioned consent and publicity rights."
    text, removed = strip_unsourced(spoken, sources)
    assert any("stat" in r for r in removed)
    assert "47 percent" not in text


def test_drops_invented_family():
    spoken = "My mother always hated microphones."
    sources = "A voice is not a person. Consent is the whole plot."
    text, removed = strip_unsourced(spoken, sources)
    assert any("family" in r for r in removed)
    assert "mother" not in text.lower()


def test_keeps_sourced_stat():
    spoken = "The fine was listed as 40 percent in the brief."
    sources = "The agency listed a 40 percent penalty in the brief."
    text, removed = strip_unsourced(spoken, sources)
    assert "40 percent" in text
    assert not any("stat" in r for r in removed)
