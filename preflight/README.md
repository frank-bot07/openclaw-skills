# 🛫 preflight

### Stop crashing your OpenClaw gateway after every update.

![Works with OpenClaw 2026.2.x](https://img.shields.io/badge/OpenClaw-2026.2.x-blue?style=flat-square)
![Pure Bash](https://img.shields.io/badge/Pure-Bash-green?style=flat-square)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

**The problem:** You run `npm update -g openclaw`, restart the gateway, and get:

```
[ERROR] Invalid config: "channels.discord.botToken" is not a recognized field
[ERROR] Gateway failed to start — config validation error
[FATAL] Process exited with code 1
```

Sound familiar? Config fields get renamed between versions. Your gateway crashes. You scramble to figure out what changed.

**The fix:** Run `preflight check` before updating.

```
🔍 Pre-Flight Check
  Config: ~/.openclaw/openclaw.json
  Version: 2026.2.20

⚠ [v2026.2.21] Deprecated field: channels.discord.botToken → channels.discord.token
    Discord bot token field renamed
⚠ [v2026.2.22] Deprecated field: channels.discord.groups → channels.discord.guilds
    Discord groups renamed to guilds to match Discord API terminology

📊 Summary
✓ 0 migration(s) already applied
⚠ 2 field(s) need migration

  Run preflight fix to auto-migrate.
```

Then `preflight fix`:

```
🔧 Auto-Migrating Config
✓ Config backed up to ~/.openclaw/backups/openclaw-2026.2.20-20260224-223000.json
✓ [v2026.2.21] Renamed: channels.discord.botToken → channels.discord.token
✓ [v2026.2.22] Renamed: channels.discord.groups → channels.discord.guilds
✓ Applied 2 migration(s).
```

Or just do everything at once: `preflight update` — backup, check, fix, update, restart. Done.

---

## Install

```bash
# One-liner via ClawHub
clawhub install preflight

# Or clone manually
git clone https://github.com/openclaw/skill-preflight.git \
  ~/.openclaw/workspace/skills/preflight
```

## Usage

```bash
# Alias for convenience (add to .zshrc/.bashrc)
alias preflight='bash ~/.openclaw/workspace/skills/preflight/scripts/preflight.sh'

# Check what would break
preflight check

# Auto-fix config
preflight fix

# Full update pipeline (backup → check → fix → update → restart)
preflight update

# Oh no, something broke — rollback
preflight rollback

# See what's been migrated
preflight history
```

## How It Works

1. Reads your `~/.openclaw/openclaw.json`
2. Compares against a database of known field renames between versions
3. Reports what needs to change (dry run) or auto-migrates
4. Always creates a timestamped backup before touching anything
5. Records migration history for auditability

## Requirements

- **bash** (macOS/Linux — no Windows support yet)
- **jq** — the script checks for it and shows install instructions if missing

## Contributing

**Found a new rename between versions?** Add it to `migrations/known-renames.json` and open a PR!

Format:

```json
{
  "version": "2026.2.XX",
  "changes": [
    {
      "type": "rename",
      "from": "old.dotpath.field",
      "to": "new.dotpath.field",
      "description": "Why this changed"
    }
  ]
}
```

Supported change types:
- `rename` — simple field rename at a fixed path
- `rename_nested` — rename with wildcard (`*`) for iterating object keys

## Links

- [OpenClaw Documentation](https://docs.openclaw.com)
- [OpenClaw Discord](https://discord.gg/openclaw)
- [Report an Issue](https://github.com/openclaw/skill-preflight/issues)

---

Made with 🦾 by the OpenClaw community. Never crash on update again.
