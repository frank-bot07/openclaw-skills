#!/usr/bin/env bash
# preflight.sh — Pre-Flight Update Checker for OpenClaw
# Prevents config crashes during OpenClaw updates.
# https://github.com/openclaw/openclaw
set -euo pipefail

# ─── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'

# ─── Paths ────────────────────────────────────────────────────────────────────
OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
CONFIG_FILE="$OPENCLAW_DIR/openclaw.json"
BACKUP_DIR="$OPENCLAW_DIR/backups"
HISTORY_FILE="$OPENCLAW_DIR/backups/migration-history.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_FILE="$SCRIPT_DIR/../migrations/known-renames.json"

# ─── Helpers ──────────────────────────────────────────────────────────────────
info()    { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET} $*"; }
err()     { echo -e "${RED}✗${RESET} $*"; }
header()  { echo -e "\n${BOLD}${CYAN}$*${RESET}"; }
dim()     { echo -e "${DIM}$*${RESET}"; }

die() { err "$@"; exit 2; }

check_jq() {
  if ! command -v jq &>/dev/null; then
    err "jq is required but not installed."
    echo ""
    echo "  Install with:"
    echo "    macOS:  brew install jq"
    echo "    Ubuntu: sudo apt-get install jq"
    echo "    Alpine: apk add jq"
    exit 2
  fi
}

check_config() {
  [[ -f "$CONFIG_FILE" ]] || die "Config not found: $CONFIG_FILE"
  jq empty "$CONFIG_FILE" 2>/dev/null || die "Config is not valid JSON: $CONFIG_FILE"
}

ensure_backup_dir() {
  mkdir -p "$BACKUP_DIR"
}

current_version() {
  jq -r '.meta.lastTouchedVersion // "unknown"' "$CONFIG_FILE"
}

timestamp() {
  date +"%Y%m%d-%H%M%S"
}

# ─── Backup ───────────────────────────────────────────────────────────────────
do_backup() {
  ensure_backup_dir
  local ts ver backup_path
  ts="$(timestamp)"
  ver="$(current_version)"
  backup_path="$BACKUP_DIR/openclaw-${ver}-${ts}.json"
  cp "$CONFIG_FILE" "$backup_path"
  info "Config backed up to ${DIM}${backup_path}${RESET}"
  echo "$backup_path"
}

# ─── Migration Engine ────────────────────────────────────────────────────────
# Resolve a dotted path (with literal dots in keys) from JSON.
# Handles wildcards (*) for iterating object keys.
jq_path_exists() {
  local json_file="$1" dotpath="$2"
  local jq_expr
  jq_expr=$(dotpath_to_jq "$dotpath")
  jq -e "$jq_expr" "$json_file" &>/dev/null
}

dotpath_to_jq() {
  # Convert dotted path like "channels.discord.guilds" to jq path .channels.discord.guilds
  # Wildcard segments become [] (iterate keys)
  local dotpath="$1"
  local result="."
  IFS='.' read -ra parts <<< "$dotpath"
  for part in "${parts[@]}"; do
    if [[ "$part" == "*" ]]; then
      result="${result}[]"
    else
      result="${result}.\"${part}\""
    fi
  done
  echo "$result"
}

# Get value at a dotpath
jq_get() {
  local json_file="$1" dotpath="$2"
  local jq_expr
  jq_expr=$(dotpath_to_jq "$dotpath")
  jq "$jq_expr" "$json_file" 2>/dev/null
}

# Set value at a dotpath (no wildcards)
jq_set() {
  local json_file="$1" dotpath="$2" value="$3"
  local jq_expr
  jq_expr=$(dotpath_to_jq "$dotpath")
  local tmp
  tmp=$(mktemp)
  jq "${jq_expr} = ${value}" "$json_file" > "$tmp" && mv "$tmp" "$json_file"
}

# Delete at a dotpath (no wildcards)
jq_del() {
  local json_file="$1" dotpath="$2"
  local jq_expr
  jq_expr=$(dotpath_to_jq "$dotpath")
  local tmp
  tmp=$(mktemp)
  jq "del(${jq_expr})" "$json_file" > "$tmp" && mv "$tmp" "$json_file"
}

# Rename: copy from→to, delete from
apply_rename() {
  local json_file="$1" from_path="$2" to_path="$3"
  local value
  value=$(jq_get "$json_file" "$from_path")
  if [[ -n "$value" && "$value" != "null" ]]; then
    jq_set "$json_file" "$to_path" "$value"
    jq_del "$json_file" "$from_path"
    return 0
  fi
  return 1
}

# Apply rename_nested (wildcard): for each key under parent, rename child
apply_rename_nested() {
  local json_file="$1" from_pattern="$2" to_pattern="$3"
  # Extract parent path (everything before .*)
  local parent_from parent_to child_from child_to
  parent_from="${from_pattern%%.\**}"
  child_from="${from_pattern##*.*.}"
  parent_to="${to_pattern%%.\**}"
  child_to="${to_pattern##*.*.}"
  
  local parent_jq
  parent_jq=$(dotpath_to_jq "$parent_from")
  
  local keys
  keys=$(jq -r "${parent_jq} | keys[]" "$json_file" 2>/dev/null) || return 1
  
  local applied=0
  while IFS= read -r key; do
    [[ -z "$key" ]] && continue
    local full_from="${parent_from}.${key}.${child_from}"
    local full_to="${parent_to}.${key}.${child_to}"
    if jq_path_exists "$json_file" "$full_from"; then
      apply_rename "$json_file" "$full_from" "$full_to" && ((applied++))
    fi
  done <<< "$keys"
  
  [[ $applied -gt 0 ]]
}

# ─── Check Command ───────────────────────────────────────────────────────────
cmd_check() {
  check_jq
  check_config
  
  header "🔍 Pre-Flight Check"
  dim "Config: $CONFIG_FILE"
  dim "Version: $(current_version)"
  echo ""

  local warnings=0 breaking=0 clean=0

  if [[ ! -f "$MIGRATIONS_FILE" ]]; then
    warn "No migrations database found at $MIGRATIONS_FILE"
    echo ""
    info "Config looks clean — no known migrations to check."
    return 0
  fi

  local migration_count
  migration_count=$(jq '.migrations | length' "$MIGRATIONS_FILE")

  for ((i=0; i<migration_count; i++)); do
    local version changes_count
    version=$(jq -r ".migrations[$i].version" "$MIGRATIONS_FILE")
    changes_count=$(jq ".migrations[$i].changes | length" "$MIGRATIONS_FILE")

    for ((j=0; j<changes_count; j++)); do
      local change_type from_path to_path description
      change_type=$(jq -r ".migrations[$i].changes[$j].type" "$MIGRATIONS_FILE")
      from_path=$(jq -r ".migrations[$i].changes[$j].from" "$MIGRATIONS_FILE")
      to_path=$(jq -r ".migrations[$i].changes[$j].to" "$MIGRATIONS_FILE")
      description=$(jq -r ".migrations[$i].changes[$j].description" "$MIGRATIONS_FILE")

      case "$change_type" in
        rename)
          if jq_path_exists "$CONFIG_FILE" "$from_path"; then
            warn "${BOLD}[v${version}]${RESET} ${YELLOW}Deprecated field:${RESET} ${from_path} → ${to_path}"
            dim "  $description"
            ((warnings++))
          elif jq_path_exists "$CONFIG_FILE" "$to_path"; then
            info "[v${version}] Already migrated: ${to_path}"
            ((clean++))
          else
            dim "  [v${version}] Field not present: ${from_path} (skip)"
          fi
          ;;
        rename_nested)
          # Check if any wildcard matches exist
          local parent_from child_from
          parent_from="${from_path%%.\**}"
          child_from="${from_path##*.*.}"
          local parent_jq
          parent_jq=$(dotpath_to_jq "$parent_from")
          local found_old=0
          local keys
          keys=$(jq -r "${parent_jq} | keys[] // empty" "$CONFIG_FILE" 2>/dev/null) || true
          while IFS= read -r key; do
            [[ -z "$key" ]] && continue
            if jq_path_exists "$CONFIG_FILE" "${parent_from}.${key}.${child_from}"; then
              found_old=1
              break
            fi
          done <<< "$keys"
          if [[ $found_old -eq 1 ]]; then
            warn "${BOLD}[v${version}]${RESET} ${YELLOW}Deprecated nested field:${RESET} ${from_path} → ${to_path}"
            dim "  $description"
            ((warnings++))
          else
            info "[v${version}] Nested field clean: ${to_path}"
            ((clean++))
          fi
          ;;
      esac
    done
  done

  echo ""
  header "📊 Summary"
  [[ $clean -gt 0 ]]    && info "$clean migration(s) already applied"
  [[ $warnings -gt 0 ]] && warn "$warnings field(s) need migration"
  [[ $breaking -gt 0 ]] && err "$breaking breaking change(s) found"

  if [[ $warnings -eq 0 && $breaking -eq 0 ]]; then
    echo ""
    info "${GREEN}${BOLD}All clear!${RESET} Config is up to date. 🎉"
    return 0
  fi

  if [[ $warnings -gt 0 ]]; then
    echo ""
    echo -e "  Run ${BOLD}preflight fix${RESET} to auto-migrate."
    return 1
  fi

  [[ $breaking -gt 0 ]] && return 2
  return 0
}

# ─── Fix Command ──────────────────────────────────────────────────────────────
cmd_fix() {
  check_jq
  check_config
  
  header "🔧 Auto-Migrating Config"
  
  # Backup first
  local backup_path
  backup_path=$(do_backup)
  
  # Work on a copy, then swap
  local work_file
  work_file=$(mktemp)
  cp "$CONFIG_FILE" "$work_file"
  
  local applied=0 failed=0

  if [[ ! -f "$MIGRATIONS_FILE" ]]; then
    info "No migrations to apply."
    rm -f "$work_file"
    return 0
  fi

  local migration_count
  migration_count=$(jq '.migrations | length' "$MIGRATIONS_FILE")

  for ((i=0; i<migration_count; i++)); do
    local version changes_count
    version=$(jq -r ".migrations[$i].version" "$MIGRATIONS_FILE")
    changes_count=$(jq ".migrations[$i].changes | length" "$MIGRATIONS_FILE")

    for ((j=0; j<changes_count; j++)); do
      local change_type from_path to_path
      change_type=$(jq -r ".migrations[$i].changes[$j].type" "$MIGRATIONS_FILE")
      from_path=$(jq -r ".migrations[$i].changes[$j].from" "$MIGRATIONS_FILE")
      to_path=$(jq -r ".migrations[$i].changes[$j].to" "$MIGRATIONS_FILE")

      case "$change_type" in
        rename)
          if jq_path_exists "$work_file" "$from_path"; then
            if apply_rename "$work_file" "$from_path" "$to_path"; then
              info "[v${version}] Renamed: ${from_path} → ${to_path}"
              ((applied++))
            else
              err "[v${version}] Failed to rename: ${from_path}"
              ((failed++))
            fi
          fi
          ;;
        rename_nested)
          if apply_rename_nested "$work_file" "$from_path" "$to_path"; then
            info "[v${version}] Renamed nested: ${from_path} → ${to_path}"
            ((applied++))
          fi
          ;;
      esac
    done
  done

  if [[ $applied -gt 0 ]]; then
    cp "$work_file" "$CONFIG_FILE"
    info "${BOLD}Applied $applied migration(s).${RESET}"
    
    # Record in history
    record_history "$applied" "$backup_path"
  else
    info "Nothing to migrate — config is already current."
  fi

  [[ $failed -gt 0 ]] && err "$failed migration(s) failed."
  rm -f "$work_file"
  
  [[ $failed -gt 0 ]] && return 2
  return 0
}

# ─── Update Command ──────────────────────────────────────────────────────────
cmd_update() {
  check_jq
  check_config

  header "🚀 Full Update Pipeline"
  echo ""

  # Step 1: Check
  echo -e "${BOLD}Step 1/4:${RESET} Pre-flight check..."
  local check_exit=0
  cmd_check || check_exit=$?

  # Step 2: Fix if needed
  if [[ $check_exit -eq 1 ]]; then
    echo ""
    echo -e "${BOLD}Step 2/4:${RESET} Auto-migrating..."
    cmd_fix || { err "Migration failed. Aborting update."; return 2; }
  elif [[ $check_exit -eq 2 ]]; then
    err "Breaking changes found. Manual intervention required."
    return 2
  else
    echo ""
    echo -e "${BOLD}Step 2/4:${RESET} No migration needed."
  fi

  # Step 3: Update OpenClaw
  echo ""
  echo -e "${BOLD}Step 3/4:${RESET} Updating OpenClaw..."
  if command -v npm &>/dev/null; then
    if npm update -g openclaw 2>&1; then
      info "OpenClaw updated."
    else
      err "npm update failed. Config is safe (backed up)."
      return 2
    fi
  else
    warn "npm not found — skipping package update. Update manually."
  fi

  # Step 4: Restart
  echo ""
  echo -e "${BOLD}Step 4/4:${RESET} Restarting gateway..."
  if command -v openclaw &>/dev/null; then
    openclaw gateway restart 2>&1 && info "Gateway restarted." || warn "Gateway restart returned non-zero. Check manually."
  else
    warn "openclaw CLI not found in PATH. Restart manually."
  fi

  echo ""
  info "${GREEN}${BOLD}Update complete!${RESET} 🎉"
}

# ─── Rollback Command ────────────────────────────────────────────────────────
cmd_rollback() {
  check_jq
  ensure_backup_dir

  header "⏪ Rollback"

  # Find latest backup
  local latest
  latest=$(ls -t "$BACKUP_DIR"/openclaw-*.json 2>/dev/null | head -1)
  
  if [[ -z "$latest" ]]; then
    err "No backups found in $BACKUP_DIR"
    return 1
  fi

  dim "Restoring from: $latest"
  cp "$latest" "$CONFIG_FILE"
  info "Config restored from backup."
  
  if command -v openclaw &>/dev/null; then
    echo ""
    echo -n "Restart gateway? [y/N] "
    read -r answer
    if [[ "$answer" =~ ^[Yy] ]]; then
      openclaw gateway restart 2>&1 && info "Gateway restarted." || warn "Restart returned non-zero."
    fi
  fi
}

# ─── History Command ─────────────────────────────────────────────────────────
record_history() {
  local count="$1" backup_path="$2"
  ensure_backup_dir
  local entry
  entry=$(jq -n \
    --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --arg ver "$(current_version)" \
    --arg cnt "$count" \
    --arg bak "$backup_path" \
    '{timestamp: $ts, version: $ver, migrations_applied: ($cnt|tonumber), backup: $bak}')
  
  if [[ -f "$HISTORY_FILE" ]]; then
    local tmp
    tmp=$(mktemp)
    jq --argjson entry "$entry" '. + [$entry]' "$HISTORY_FILE" > "$tmp" && mv "$tmp" "$HISTORY_FILE"
  else
    echo "[$entry]" > "$HISTORY_FILE"
  fi
}

cmd_history() {
  check_jq
  
  header "📜 Migration History"
  
  if [[ ! -f "$HISTORY_FILE" ]]; then
    dim "No migrations recorded yet."
    return 0
  fi

  jq -r '.[] | "  \(.timestamp)  v\(.version)  \(.migrations_applied) migration(s)  ← \(.backup)"' "$HISTORY_FILE"
}

# ─── Main ─────────────────────────────────────────────────────────────────────
usage() {
  echo -e "${BOLD}preflight${RESET} — Pre-Flight Update Checker for OpenClaw"
  echo ""
  echo "Usage: preflight <command>"
  echo ""
  echo "Commands:"
  echo "  check      Dry run — show what would break"
  echo "  fix        Auto-migrate config for new version"
  echo "  update     Full pipeline: backup → check → fix → update → restart"
  echo "  rollback   Restore last backup"
  echo "  history    Show migration history"
  echo ""
  echo "Examples:"
  echo "  preflight check          # See what needs fixing"
  echo "  preflight fix            # Fix it"
  echo "  preflight update         # Do everything"
}

case "${1:-}" in
  check)    cmd_check ;;
  fix)      cmd_fix ;;
  update)   cmd_update ;;
  rollback) cmd_rollback ;;
  history)  cmd_history ;;
  -h|--help|help) usage ;;
  *)
    usage
    [[ -n "${1:-}" ]] && { echo ""; err "Unknown command: $1"; exit 1; }
    ;;
esac
