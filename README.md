# OpenClaw Skills Suite

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)]()
[![Tests](https://img.shields.io/badge/tests-88%20passing-brightgreen)]()

> A production-ready suite of interconnected skills for [OpenClaw](https://github.com/openclaw/openclaw) — the open-source AI agent platform.

## Skills

| Skill | Description | Tests |
|-------|-------------|-------|
| [`@openclaw/interchange`](./interchange) | Shared .md interchange library — atomic writes, deterministic serialization, schema validation | 32 |
| [`@openclaw/orchestration`](./orchestration) | Multi-agent task queue with collision-safe claiming and dependency chains | 13 |
| [`openclaw-monitor`](./monitoring) | System health monitoring — token spend, task success, cron health | 10 |
| [`openclaw-crm`](./crm) | Local-first CRM for leads, deals, follow-ups, and pipeline reports | 10 |
| [`openclaw-ecommerce`](./ecommerce) | E-commerce price monitoring, order tracking, and margin analysis | 13 |
| [`openclaw-voice`](./voice) | Voice-first interaction with conversation tracking and ElevenLabs integration | 10 |

## The .md Interchange Standard

These skills communicate through `.md` files with YAML frontmatter — a universal protocol any AI agent can read. No APIs, no coupling, no vendor lock-in.

```
ops/    → Shareable operational data (capabilities, status, reports)
state/  → Private runtime data (credentials, local config)
```

Every skill produces interchange files that other skills (and agents) can consume instantly.

## Quick Start

```bash
# Install any skill
cd <skill-name>
npm install

# Run tests
npm test
```

Each skill has its own CLI — see individual READMEs for full usage.

## Architecture

- **SQLite** (WAL mode) for local-first data storage
- **Atomic file writes** via `@openclaw/interchange`
- **No external dependencies** for core functionality
- **88 tests** across the full suite

## License

MIT
