# SKILL: Model Switchboard v3

## What It Does
Local web dashboard for managing OpenClaw model configuration, cron job model assignments, and API keys.

## How to Launch
```bash
cd ~/.openclaw/workspace/skills/model-switchboard-v3
python3 scripts/server.py
# Opens at http://localhost:7878
```

## Three Panels
1. **Gateway Config** — primary/fallback models, provider API key status, allowed models list
2. **Cron Jobs** — all 37 cron jobs with model assignment, status, bulk reassignment
3. **Model Health** — per-model provider/key status, dependency counts, gateway roles

## Security
- API keys NEVER returned in full — masked as `sk-...xxxx`
- Keys stored in `~/.openclaw/openclaw.json` env.vars (OpenClaw native)
- Backup to `~/.openclaw/workspace/.env`
- Input type=password, never in API responses or logs

## Crash Prevention
- Validates provider key exists before adding a model
- Shows dependency count + names before removing a model
- Auto-backup before every destructive change (rolling 10)
- One-click restore from backup panel

## Files
- `scripts/server.py` — Pure Python stdlib backend (http.server)
- `ui/index.html` — Single-file SPA frontend (HTML+CSS+JS, no CDN)
- `config/defaults.json` — Configuration reference

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/health | Server health check |
| GET | /api/config | Gateway config (keys masked) |
| POST | /api/config/key | Set/update an API key |
| POST | /api/config/gateway | Update primary/fallback routing |
| GET | /api/cron | All cron jobs enriched |
| POST | /api/cron/model | Reassign one job's model |
| POST | /api/cron/bulk-model | Bulk reassign by model |
| GET | /api/models | Model health info |
| POST | /api/models/add | Add model (validates key) |
| POST | /api/models/remove | Remove model (warns on deps) |
| GET | /api/backups | List backups |
| POST | /api/backup/create | Create manual backup |
| POST | /api/backup/restore | Restore a backup |
| GET | /api/validate | Validate full config |
