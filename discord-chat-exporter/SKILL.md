---
name: discord-chat-exporter
description: Export Discord chat history to files using DiscordChatExporter (DCE). Use when asked to export, archive, backup, or download Discord messages, channels, DMs, or entire servers. Supports HTML, JSON, TXT, CSV formats with date filtering, media downloads, and partitioning. Runs via Docker.
---

# Discord Chat Exporter

Export Discord channel/DM/server message history to files via [DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter) CLI (Docker).

## Prerequisites

- Docker installed and running
- A Discord bot token (bot must be in the target server) OR a user token

Pull the image (one-time):
```bash
docker pull tyrrrz/discordchatexporter:stable
```

## Token

Set `DISCORD_TOKEN` env var or pass `-t TOKEN` to every command. The bot token from OpenClaw's Discord config can be reused if the bot has access to the target channels.

Use the wrapper script at `scripts/dce.sh` for convenience — it reads `DISCORD_TOKEN` from the environment automatically.

## Commands

All commands output to `/out` inside the container, mapped to a host directory via `-v`.

### List servers
```bash
./scripts/dce.sh guilds
```

### List channels in a server
```bash
./scripts/dce.sh channels -g SERVER_ID
```

### List DM channels
```bash
./scripts/dce.sh dm
```

### Export a single channel
```bash
./scripts/dce.sh export -c CHANNEL_ID
```

### Export all channels in a server
```bash
./scripts/dce.sh exportguild -g SERVER_ID
```

### Export all DMs
```bash
./scripts/dce.sh exportdm
```

### Export everything accessible
```bash
./scripts/dce.sh exportall
```

## Common Options

| Flag | Description | Example |
|------|-------------|---------|
| `-f FORMAT` | Output format: `HtmlDark` (default), `HtmlLight`, `PlainText`, `Json`, `Csv` | `-f Json` |
| `-o PATH` | Output path (file or directory) | `-o /out/export.html` |
| `--after DATE` | Messages after date (ISO 8601) | `--after 2025-01-01` |
| `--before DATE` | Messages before date | `--before 2025-12-31` |
| `--media` | Download attachments, avatars, embeds | `--media` |
| `--reuse-media` | Skip already-downloaded media (requires `--media`) | `--reuse-media` |
| `-p N` | Partition every N messages or size (e.g. `20mb`) | `-p 10000` |
| `--locale LOCALE` | Date format locale | `--locale en-US` |

### Output path template tokens
`%g` server ID, `%G` server name, `%t` category ID, `%T` category name, `%c` channel ID, `%C` channel name, `%d` current date

## Examples

Export a channel as JSON for the last 30 days:
```bash
./scripts/dce.sh export -c 123456789 -f Json --after "$(date -v-30d +%Y-%m-%d)"
```

Export entire server as HTML with media:
```bash
./scripts/dce.sh exportguild -g 123456789 --media --reuse-media -o "/out/%G/%T/%C.html"
```

Export channel between specific dates:
```bash
./scripts/dce.sh export -c 123456789 --after 2025-01-01 --before 2025-02-01
```
