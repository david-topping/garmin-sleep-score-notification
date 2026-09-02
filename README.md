# Garmin Sleep Score Notification

Fetches each configured person's Garmin Connect sleep score every morning and
emails it (score, qualifier, deep/light/REM/awake breakdown) to their recipients
via [Resend](https://resend.com). Runs unattended on a headless GCP `e2-micro`
VM via cron, with no phone or browser session after one-time setup.

## Design

- **Token auth:** `garmin-auth-setup` does an interactive login once per person
  and caches an OAuth token (`garth`) that auto-refreshes for ~1 year. The
  scheduled job never re-authenticates.
- **Retry until sent:** cron runs every 10 min from 04:30 to 13:00. Each run
  emails anyone whose score is available and not yet sent today; if the watch
  hasn't synced, it logs and retries next run. State (`state/sent_state.json`,
  keyed by date) makes it exactly-once per person per day and resets
  automatically.
- **Fan-out config:** `people.yaml` maps people to recipient lists. Arbitrary
  fan-out (one score to many, one address across many people, receive-only
  people). Adding a person or recipient is config, not code.
- **Isolation:** one person's auth or send failure never blocks the others.
  Exit codes: `0` ok, `1` a fetch/send failed, `2` config error.

## Architecture

| Module | Responsibility |
|---|---|
| `config.py` | Load `.env` and `people.yaml` into `Config` / `Person` / `Recipient` |
| `garmin.py` | `GarminFetcher`, `SleepSummary` (score, qualifier, stage breakdown) |
| `email_content.py` | `SleepEmail`: subject, plain-text, HTML |
| `mailer.py` | `EmailSender`: Resend API |
| `state.py` | `SentState`: sent-today tracker, 7-day pruning |
| `notify.py` | `Notifier`: orchestration plus the `garmin-sleep-notify` CLI |
| `auth_setup.py` | `AuthSetup`: the `garmin-auth-setup` CLI |

Each module is independently unit-tested (`uv run pytest`). uv-managed
throughout; no pip or manual venv.

## Setup

```bash
uv sync
cp .env.example .env                # RESEND_API_KEY, EMAIL_FROM (verified Resend domain)
cp people.example.yaml people.yaml  # people and recipient emails
uv run garmin-auth-setup <name>     # once per person: email, password, MFA
```

## Run

```bash
uv run garmin-sleep-notify            # the job
uv run garmin-sleep-notify --dry-run  # fetch and log, send nothing
```

## Deploy

```bash
git clone <repo-url> && cd garmin-sleep-score-notification
uv sync
# populate .env and people.yaml, run garmin-auth-setup per person
./scripts/install-cron.sh             # idempotent; also --dry-run and --remove
```

Ship changes with `git pull && uv sync`. Cron uses VM local time, so set the VM
timezone accordingly.
