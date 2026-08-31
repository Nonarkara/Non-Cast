from noncast.hashing import chunk_cache_key


def test_same_inputs_same_key():
    settings = {"backend": "f5-tts-mlx", "rate": 24000}
    a = chunk_cache_key("Hello there.", "host-primary", settings)
    b = chunk_cache_key("Hello there.", "host-primary", settings)
    assert a == b
    assert len(a) == 64


def test_text_or_voice_or_settings_change_key():
    base = chunk_cache_key("Hello there.", "host-primary", {"rate": 24000})
    assert chunk_cache_key("Hello there!", "host-primary", {"rate": 24000}) != base
    assert chunk_cache_key("Hello there.", "host-other", {"rate": 24000}) != base
    assert chunk_cache_key("Hello there.", "host-primary", {"rate": 22050}) != base
