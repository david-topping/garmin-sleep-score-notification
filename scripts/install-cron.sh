#!/usr/bin/env bash
# Manage the crontab entries that run garmin-sleep-notify every 30 min from
# 06:00 to 13:00 inclusive. Idempotent: re-running replaces the entries.
#
#   install-cron.sh              install / update
#   install-cron.sh --dry-run    print the resulting crontab, change nothing
#   install-cron.sh --remove     uninstall
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV="$(command -v uv || true)"
LOG="${GARMIN_CRON_LOG:-$HOME/garmin-sleep.log}"
MARKER="# garmin-sleep-notify"
MODE="${1:-install}"

if [[ -z "$UV" ]]; then
  echo "uv not found on PATH - install it first" >&2
  exit 1
fi

current="$(crontab -l 2>/dev/null | grep -vF "$MARKER" || true)"

if [[ "$MODE" == "--remove" ]]; then
  printf '%s\n' "$current" | crontab -
  echo "removed garmin-sleep-notify cron entries"
  exit 0
fi

cmd="cd $REPO_DIR && $UV run garmin-sleep-notify >> $LOG 2>&1 $MARKER"
new="$(printf '%s\n0,30 6-12 * * * %s\n0 13 * * * %s\n' "$current" "$cmd" "$cmd" | sed '/^$/d')"

if [[ "$MODE" == "--dry-run" ]]; then
  echo "would install this crontab:"
  printf '%s\n' "$new"
  exit 0
fi

printf '%s\n' "$new" | crontab -
echo "installed:"
crontab -l | grep -F "$MARKER"
echo "logging to $LOG"
