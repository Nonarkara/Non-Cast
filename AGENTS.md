# AGENTS.md

You are operating **Non-Cast**, a forkable kit that turns a local markdown corpus into a daily (or on-demand) podcast script, optional audio, and an RSS feed.

You are **not** required to be Claude. Cursor, Claude Code, Codex, Gemini CLI, Aider, OpenCode, VS Code agents, and humans in a terminal all use the same CLI.

## What this repo is

- Generic. Identity lives in `noncast.toml`, `corpus/`, `docs/hero.png`, and `voices/reference.wav` (gitignored).
- Not a hosted SaaS. Not a Spotify Partner integration. Directories follow `public/feed.xml`.
- Happy path: **no vendor SDK**. LLM = HTTP to Ollama (optional OpenAI/Anthropic via env). RAG = sqlite + tf-idf (or sqlite-vec if installed).

## Commands (do these; do not invent a parallel toolchain)

```bash
pip install -e ".[dev]"          # once per checkout
noncast init                     # idempotent dirs + missing files
noncast ingest ./corpus          # (re)index markdown
noncast today --no-publish       # scrape → … → script.md; default
noncast today --publish          # RSS only if audit coverage ≥ 0.95
noncast "make a 12 minute episode about <topic>, don't publish"
noncast audit episode.mp3 episode.md
noncast scrape|analyze|draft|copyedit|earlint|voice|publish
noncast status
python -m noncast.pipeline <stage>
pytest -q
```

Outputs for a date land in `data/runs/YYYY-MM-DD/` (`stories.json`, `analysis.json`, `script.md`, `earlint.json`, `voice.json`, `audit.json`, `summary.json`).

## Non-negotiable rules

1. **Do not invent family stories, quotes, or statistics.** If it is not in `corpus/` or a fetched item, do not put it in the script.
2. **Default `--no-publish`.** Never publish because a chat model feels done.
3. **Fail closed.** Coverage `< 0.95`, any audit error, missing audio, or system-voice fallback → refuse publish.
4. **Never** call `say`, espeak, or another system TTS as a fallback. If `f5-tts-mlx` / ElevenLabs / OpenAI TTS is missing or unkeyed, skip voice and keep the script.
5. **Never commit** `.env`, API keys, or `voices/reference.wav`.
6. Keep show names in `noncast.toml` generic unless the forker already changed them.
7. Do not add GPU tests. Do not hit live TTS APIs in tests.

## How a forker adds their voice

1. Replace `corpus/*.md` with their writing (RAG).
2. Edit `[show]` and `[persona]` in `noncast.toml`.
3. Add RSS URLs under `[rss].feeds` if they want news beats (empty = corpus-only, works offline).
4. Place a consented clip at `voices/reference.wav`.
5. Set `[voice].backend` to `f5-tts-mlx` (Apple Silicon), `elevenlabs`, or `openai`. Keys only in `.env`.
6. `noncast ingest ./corpus` then `noncast today --no-publish`. Read `script.md` before `--publish`.

## LLM

- Default backend: local Ollama (`llm.base_url`, default `http://127.0.0.1:11434`).
- NL commands call the LLM when reachable; if it is down, `noncast.nl` parses duration/topic/`don't publish` heuristically and still runs `today`.
- Optional: `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`. Stdlib HTTP only.

## Efficiency already implemented — do not “improve” by stalling

- TTS cache: `hash(text + voice-id + settings)` under `data/cache/tts/`.
- RSS: parallel, `rss_timeout_seconds` (8), `rss_retries` (2). No 240s waits.
- Story dedup: 3-day window, URL or near-identical title.

## Quality

- Ear-lint: ~30-word sentences; replacements in `lexicon/killwords.txt`.
- Copyedit strips unsourced quotes/stats and invented kinship (“my mother…”).
- Whole-episode coverage must be ≥ `pipeline.coverage_threshold` (0.95) before publish.

## If you are lost

Read `README.md` (10-minute path + mermaid) and `docs/architecture.md` (stage I/O). Run `noncast --help` and `noncast status`. Prefer editing one pipeline module over adding a new framework.
