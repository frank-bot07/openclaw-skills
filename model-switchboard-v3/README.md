# Model Switchboard v3

A local web dashboard for managing OpenClaw's model configuration, cron job assignments, and API keys. Full rebuild of v2 with improved security, crash prevention, and UI.

## Quick Start

```bash
python3 ~/.openclaw/workspace/skills/model-switchboard-v3/scripts/server.py
```

Then open: **http://localhost:7878**

## Features

### 🌐 Panel 1 — Gateway Config
- View and edit primary/fallback model routing
- See all provider API key statuses with green/red indicators
- Add/remove models from the allowed list with validation
- Add/update API keys (masked display, secure storage)

### ⏰ Panel 2 — Cron Job Command Center
- All cron jobs with name, model, schedule, last status, next run
- Status dots (green/red/yellow) and flagged indicators for unknown models
- One-click model reassignment per job
- Multi-select + bulk reassignment
- Filter by status, model, or search text
- Bulk reassign: move all jobs from model X to model Y

### 🩺 Panel 3 — Model Health Monitor
- Every allowed model with provider, key status, cron dependency count
- Gateway role indicators (primary, fallback, image-primary, etc.)
- Remove warnings with dep counts and affected job names

### 💾 Panel 4 — Backups
- Rolling 10 backups auto-created before every change
- Manual backup creation
- One-click restore with pre-restore safety backup

## Security

| Feature | Implementation |
|---------|----------------|
| Keys in UI | `sk-...xxxx` (last 4 chars only) |
| Key input | `type="password"` fields |
| API responses | Never include key values |
| Key storage | `~/.openclaw/openclaw.json` env.vars |
| Key backup | `~/.openclaw/workspace/.env` (chmod 600) |

## Tech Stack

- **Backend**: Python 3 stdlib only (`http.server`, `json`, `subprocess`, `shutil`)
- **Frontend**: Single `index.html` — HTML + CSS + vanilla JS, zero dependencies, no CDN
- **Theme**: Dark zinc/slate palette

## Data Sources

| Data | Source |
|------|--------|
| Model config | `~/.openclaw/openclaw.json` |
| Cron jobs | `~/.openclaw/cron/jobs.json` |
| Backups | `~/.openclaw/switchboard-backups/` |

## Requirements

- Python 3.8+
- OpenClaw installed at `~/.npm-global/lib/node_modules/openclaw/`
- OpenClaw config at `~/.openclaw/openclaw.json`

## Port

Default: **7878** (avoids conflict with OpenClaw gateway at 3000)
