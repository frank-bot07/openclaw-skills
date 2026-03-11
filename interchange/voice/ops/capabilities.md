---
content_hash: sha256:0162cf3c7eabc48c541e00997e8d9dd07528aba0863c96e292d8fdbcbc658b37
generation_id: 1
generator: voice@1.0.0
layer: ops
skill: voice
tags:
  - capabilities
  - reference
type: summary
updated: "2026-03-11T05:20:48.934Z"
version: 1
---
# Voice Capabilities

## Command Reference

- `voice transcript list [--today] [--search "query"]` - List recent conversations, optionally filtered by today or search terms in transcripts.
- `voice transcript show <conversation-id>` - Display the full transcript of a conversation.
- `voice transcript add <conversation-id> --speaker user|assistant --text "..." [--confidence 1.0]` - Add a transcript line.
- `voice conversation start [--summary "context"]` - Start a new conversation and return its ID.
- `voice conversation end <conversation-id> [--summary "..."]` - End a conversation, optionally update summary.
- `voice profile list` - List all voice profiles.
- `voice profile add <name> --voice-id <elevenlabs-id> [--settings '{}']` - Add a new voice profile.
- `voice profile default <name>` - Set the default voice profile.
- `voice refresh` - Regenerate interchange files.
- `voice backup [--output path]` - Create a database backup.
- `voice restore <backup-file>` - Restore from a backup file.

## Supported Modes

- CLI-based commands only (v1).
- No real-time conversation mode (planned for v1.1).
- Uses Whisper for STT and ElevenLabs for TTS (wrappers via child_process).
- Transcript storage and search in SQLite.