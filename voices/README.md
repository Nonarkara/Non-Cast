# Voice clip (gitignored)

Put a short, clearly consented clip of **your** speaking voice here as `reference.wav`.

- 5–15 seconds of dry speech, one speaker, no music.
- Never commit this file. It is listed in `.gitignore`.
- Point `voice.reference_wav` and `voice.id` at it in `noncast.toml`.
- Local backend: `f5-tts-mlx` (Apple Silicon). Hosted stubs: `elevenlabs`, `openai`.
- If the backend is missing, Non-Cast **refuses** system-voice fallback (`say`, espeak, etc.) and will not publish.
