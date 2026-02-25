# Skill: preflight

Pre-Flight Update Checker for OpenClaw. Prevents config crashes during updates by detecting renamed/removed fields and auto-migrating.

## Commands

Run via the bash script:

```bash
bash ~/.openclaw/workspace/skills/preflight/scripts/preflight.sh <command>
```

| Command | Description |
|---------|-------------|
| `check` | Dry run — show what fields need migration (no changes) |
| `fix` | Auto-migrate config (creates backup first) |
| `update` | Full pipeline: backup → check → fix → npm update → restart |
| `rollback` | Restore last config backup |
| `history` | Show migration history |

## When to Use

- Before updating OpenClaw (`preflight check`)
- When gateway crashes after update (`preflight rollback`)
- To do a safe full update (`preflight update`)

## Requirements

- `jq` (script checks and provides install instructions if missing)
- `npm` (for the update command)

## Exit Codes

- `0` — clean, no issues
- `1` — warnings (fixable with `preflight fix`)
- `2` — breaking changes or errors

## Adding Migrations

Edit `migrations/known-renames.json` to add new known field renames between versions.
