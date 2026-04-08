import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { getDb } from './db.js';
import { listProfiles } from './profiles.js';
import { listConversations } from './conversations.js';
import { writeMd } from '../../interchange/src/index.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workspaceDir = path.join(__dirname, '..', '..');
const interchangeDir = path.join(workspaceDir, 'interchange', 'voice');

const opsDir = path.join(interchangeDir, 'ops');
const stateDir = path.join(interchangeDir, 'state');

fs.mkdirSync(interchangeDir, { recursive: true });
fs.mkdirSync(opsDir, { recursive: true });
fs.mkdirSync(stateDir, { recursive: true });

const BASE_META = {
  skill: 'voice',
  generator: 'voice@1.0.0',
  version: 1,
};

/**
 * Generate interchange MD files.
 * @param {import('better-sqlite3').Database} [dbOverride] - Optional DB instance (for testing).
 */
export async function generateInterchange(dbOverride) {
  await generateCapabilities();
  await generateProfiles(dbOverride);
  await generateRecent(dbOverride);
}

async function generateCapabilities() {
  const meta = { ...BASE_META, type: 'summary', layer: 'ops', tags: ['capabilities', 'reference'] };
  const content = `# Voice Capabilities

## Command Reference

- \`voice transcript list [--today] [--search "query"]\` - List recent conversations, optionally filtered by today or search terms in transcripts.
- \`voice transcript show <conversation-id>\` - Display the full transcript of a conversation.
- \`voice transcript add <conversation-id> --speaker user|assistant --text "..." [--confidence 1.0]\` - Add a transcript line.
- \`voice conversation start [--summary "context"]\` - Start a new conversation and return its ID.
- \`voice conversation end <conversation-id> [--summary "..."]\` - End a conversation, optionally update summary.
- \`voice profile list\` - List all voice profiles.
- \`voice profile add <name> --voice-id <elevenlabs-id> [--settings '{}']\` - Add a new voice profile.
- \`voice profile default <name>\` - Set the default voice profile.
- \`voice refresh\` - Regenerate interchange files.
- \`voice backup [--output path]\` - Create a database backup.
- \`voice restore <backup-file>\` - Restore from a backup file.

## Supported Modes

- CLI-based commands only (v1).
- No real-time conversation mode (planned for v1.1).
- Uses Whisper for STT and ElevenLabs for TTS (wrappers via child_process).
- Transcript storage and search in SQLite.`;
  await writeMd(path.join(opsDir, 'capabilities.md'), meta, content);
}

async function generateProfiles(dbOverride) {
  const db = dbOverride || getDb();
  const profiles = listProfiles(db);
  const meta = { ...BASE_META, type: 'summary', layer: 'ops', tags: ['profiles'] };
  let content = `# Voice Profiles

`;
  profiles.forEach(p => {
    let desc = 'No description provided.';
    try {
      const settings = JSON.parse(p.settings_json);
      desc = settings.description || desc;
    } catch {}
    content += `## ${p.name}\n\n${desc}\n\n`;
  });
  await writeMd(path.join(opsDir, 'profiles.md'), meta, content);
}

async function generateRecent(dbOverride) {
  const db = dbOverride || getDb();
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const todayStart = now.toISOString();
  const recent = db.prepare(`SELECT id, summary, started FROM conversations WHERE ended IS NOT NULL ORDER BY ended DESC LIMIT 5`).all();
  const todayCount = db.prepare(`SELECT COUNT(*) as count FROM conversations WHERE started >= ?`).get(todayStart).count;
  const durations = db.prepare(`SELECT (julianday(ended) - julianday(started)) * 86400 as duration FROM conversations WHERE ended IS NOT NULL`).all();
  let totalDuration = 0;
  durations.forEach(d => { totalDuration += d.duration || 0; });
  const totalMinutes = Math.round(totalDuration / 60);

  const meta = { ...BASE_META, type: 'summary', layer: 'state', tags: ['recent', 'activity'] };
  let content = `# Recent Voice Activity

## Last 5 Conversations
`;
  recent.forEach(c => {
    content += `- ${c.id.substring(0, 8)}: ${c.summary || 'No summary'} (started ${c.started})\n`;
  });
  content += `\n## Today's Conversation Count: ${todayCount}\n\n## Total Conversation Duration: ${totalMinutes} minutes\n`;
  await writeMd(path.join(stateDir, 'recent.md'), meta, content);
}
