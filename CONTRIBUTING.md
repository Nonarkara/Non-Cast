# Contributing to Non-Cast

Non-Cast is a **kit**. Forkers supply identity. Keep the defaults generic.

Licensed under MIT. Copyright © 2026 Non Arkaraprasertkul / Axiom X Co., Ltd. See [LICENSE](LICENSE).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
noncast init
noncast ingest ./corpus
pytest -q
```

No GPU tests. Do not add tests that call ElevenLabs, OpenAI TTS, or f5-tts-mlx.

## Pipeline modules

Each stage is runnable alone (`noncast earlint`, `python -m noncast.pipeline earlint`). Prefer a small change in one stage over a new cross-cutting abstraction.

## Rules that PRs must not weaken

- Default is `--no-publish`. Coverage `< 0.95` or any audit error **fail-closes**.
- Never fall back to system TTS (`say`, espeak).
- Happy path: stdlib HTTP only. No vendor SDK required.
- Do not commit `.env`, API keys, or `voices/reference.wav`.
- Do not invent family, quotes, or statistics in drafts or fixtures that the auditor would accept unsourced.
- Show names in `noncast.toml` stay generic unless you are documenting a forker example.

## Docs

If you change the pipeline, update `docs/architecture.md` and the mermaid diagram in `README.md`. `AGENTS.md` must stay enough for a non-Claude agent to operate the repo.
