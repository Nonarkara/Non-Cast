# Security Policy

## Secrets

- Copy `.env.example` to `.env`. Never commit `.env`.
- Never commit `voices/reference.wav` or other voice clips. A reference clip is a biometric-ish artifact.
- API keys for optional OpenAI, Anthropic, and ElevenLabs backends belong in the environment only.

## Fail-closed behavior

Non-Cast refuses to publish when:

- whole-episode coverage is below `0.95`
- the auditor reports any error
- synthesis would use a system-voice fallback (`say`, espeak, etc.)

Treat a change that bypasses those gates as a security bug.

## Reporting

Please report vulnerabilities privately via GitHub Security Advisories on this repository. Do not open a public issue with keys, clips, or exploit details.
