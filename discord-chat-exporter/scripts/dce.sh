#!/usr/bin/env bash
# Discord Chat Exporter wrapper — runs DCE CLI via Docker
# Usage: ./dce.sh <command> [options...]
# Requires: DISCORD_TOKEN env var (or pass -t TOKEN manually)
# Exports land in ./dce-exports/ by default

set -euo pipefail

EXPORT_DIR="${DCE_EXPORT_DIR:-$(pwd)/dce-exports}"
mkdir -p "$EXPORT_DIR"

IMAGE="tyrrrz/discordchatexporter:stable"

# Pull image if not present
if ! docker image inspect "$IMAGE" &>/dev/null; then
  echo "Pulling $IMAGE..."
  docker pull "$IMAGE"
fi

TOKEN_ARGS=()
if [[ -n "${DISCORD_TOKEN:-}" ]]; then
  TOKEN_ARGS=(--env "DISCORD_TOKEN=$DISCORD_TOKEN")
fi

TTY_FLAG=""
if [ -t 0 ]; then TTY_FLAG="-it"; fi

exec docker run --rm $TTY_FLAG \
  -v "$EXPORT_DIR:/out" \
  "${TOKEN_ARGS[@]}" \
  "$IMAGE" \
  "$@"
