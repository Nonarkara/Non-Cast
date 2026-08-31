from noncast.pipeline.earlint import lint_text, repair_text
from noncast.textutil import split_sentences, word_count


def test_flags_long_sentence(tmp_path):
    lexicon = tmp_path / "kill.txt"
    lexicon.write_text("delve\tlook\n", encoding="utf-8")
    long = " ".join(["word"] * 42) + "."
    issues = lint_text(long, lexicon, max_words=30)
    kinds = {i.kind for i in issues}
    assert "long_sentence" in kinds


def test_flags_killword(tmp_path):
    lexicon = tmp_path / "kill.txt"
    lexicon.write_text("delve\tlook\n", encoding="utf-8")
    issues = lint_text("We should delve into the feed today.", lexicon, max_words=30)
    assert any(i.kind == "killword" and i.detail == "delve" for i in issues)


def test_repair_splits_and_replaces(tmp_path):
    lexicon = tmp_path / "kill.txt"
    lexicon.write_text("delve\tlook\nutilize\tuse\n", encoding="utf-8")
    text = (
        "We should delve into the numbers, and then utilize the feed, "
        "and also remember that a spoken sentence should stay under thirty words "
        "so the ear can keep the claim without stacking a second claim on top."
    )
    repaired = repair_text(text, lexicon, max_words=30)
    assert "delve" not in repaired.lower()
    assert "utilize" not in repaired.lower()
    for sent in split_sentences(repaired):
        assert word_count(sent) <= 30


def test_short_sentence_untouched(tmp_path):
    lexicon = tmp_path / "kill.txt"
    lexicon.write_text("delve\tlook\n", encoding="utf-8")
    text = "Keep this line."
    assert repair_text(text, lexicon, max_words=30) == "Keep this line."
