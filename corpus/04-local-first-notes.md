# Local first notes

This kit is meant to be forked, not rented. The writing lives as markdown on disk. The index lives as a sqlite file you can delete. Retrieval defaults to a local algorithm: sqlite-vec if you installed it, tf-idf if you did not. A cloud embedding API can wait. Most daily shows are small enough that a hashed or tf-idf index answers “what have I already argued about voice and feeds?” without a GPU.

Agents should be interchangeable. A human in a terminal, Cursor, Claude Code, Codex, Gemini CLI, Aider, OpenCode, and VS Code should all be able to run `noncast` after reading `AGENTS.md`. The happy path does not import a vendor SDK. Ollama is an HTTP POST. OpenAI and Anthropic, if you opt in with environment variables, are also HTTP POSTs. Missing keys mean “skip polish,” not “crash the day.”

Caching is how a daily job stays cheap. Hash the sentence text with the voice id and the synthesizer settings. If the hash hits, do not pay again. If the copyeditor changes a comma, the hash misses, which is correct: the ear will hear the comma.

Dedup is how a daily job stays sane. If a story URL or a near-identical title appeared in the last three days, skip it. Listeners notice when Tuesday’s cold open is Monday’s cold open with a new adjective.

Coverage is how a daily job stays honest. If fewer than ninety-five percent of spoken sentences have real audio from the configured voice, do not publish. If the auditor throws, do not publish. A half-voiced episode in the feed is worse than a quiet day.

When you add your own voice to this repo, you add files, not mythology: essays in `corpus/`, a consented `voices/reference.wav`, a show name in `noncast.toml`, and feeds if you want news. Then `noncast ingest ./corpus` and `noncast today --no-publish`. Read the script. Only then consider `--publish`.
