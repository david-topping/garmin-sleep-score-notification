#!/usr/bin/env bash
# Manage the crontab entries that run garmin-sleep-notify every 10 min from
# 04:30 to 13:00 inclusive. Idempotent: re-running replaces the entries.
#
#   install-cron.sh              install / update
#   install-cron.sh --dry-run    print the resulting crontab, change nothing
#   install-cron.sh --remove     uninstall
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${GARMIN_CRON_LOG:-$HOME/garmin-sleep.log}"
MARKER="# garmin-sleep-notify"
MODE="${1:-install}"

existing="$(crontab -l 2>/dev/null || true)"
current="$(printf '%s\n' "$existing" | grep -vF "$MARKER" | sed '/^$/d' || true)"

if [[ "$MODE" == "--remove" ]]; then
  if ! printf '%s\n' "$existing" | grep -qF "$MARKER"; then
    echo "no garmin-sleep-notify cron entries to remove"
  elif [[ -n "$current" ]]; then
    printf '%s\n' "$current" | crontab -
    echo "removed garmin-sleep-notify cron entries"
  else
    crontab -r 2>/dev/null || true
    echo "removed garmin-sleep-notify cron entries (crontab now empty)"
  fi
  exit 0
fi

UV="$(command -v uv || true)"
if [[ -z "$UV" ]]; then
  echo "uv not found on PATH: install it first" >&2
  exit 1
fi

cmd="cd $REPO_DIR && $UV run garmin-sleep-notify >> $LOG 2>&1 $MARKER"
new="$(printf '%s\n30,40,50 4 * * * %s\n*/10 5-12 * * * %s\n0 13 * * * %s\n' \
  "$current" "$cmd" "$cmd" "$cmd" | sed '/^$/d')"

if [[ "$MODE" == "--dry-run" ]]; then
  echo "would install this crontab:"
  printf '%s\n' "$new"
  exit 0
fi

printf '%s\n' "$new" | crontab -
echo "installed:"
crontab -l | grep -F "$MARKER"
echo "logging to $LOG"
