# AGENTS.md

## Purpose

Each morning, fetch every configured person's Garmin Connect sleep score + stage
breakdown (deep / light / rem / awake) and email it to their recipients via the
Resend API. Runs unattended on a headless GCP VM with no phone dependency.

## Architecture

`src/garmin_sleep_score_notification/` — one class per concern, each unit-tested
in `tests/`:

| Module         | Class(es)                       | Responsibility |
| -------------- | ------------------------------- | -------------- |
| `config.py`    | `Config`, `Person`, `Recipient` | Load `people.yaml` + `.env` into frozen dataclasses. `Config.load()`. |
| `garmin.py`    | `GarminFetcher`, `SleepSummary` | Token-only login + fetch. `SleepSummary.from_payload()` returns `None` when the score isn't synced yet; raises `GarminError` on auth/network failure. |
| `mailer.py`    | `EmailSender`                   | One Resend API send; raises `EmailError`. |
| `state.py`     | `SentState`                     | JSON file: per date + person, the score and which recipient emails were notified. Prunes entries older than 7 days on `save()`. |
| `notify.py`    | `Notifier`                      | Orchestration + `garmin-sleep-notify` CLI (`--dry-run`, `--people-file`). |
| `auth_setup.py`| `AuthSetup`                     | Interactive one-time login + token dump (`garmin-auth-setup <name>`). |
| `__init__.py`  | —                               | `configure_logging()` only. |

Adding a person or recipient is a `people.yaml` change, never code.

Style: class-based, comments kept to an absolute minimum, simplicity over
cleverness. Keep it that way.

## Fan-out model

`people.yaml` is a flat list of **people** (someone whose score is fetched). Each
owns a list of **recipients** (`email`, optional `label`). Any fan-out is valid:
many recipients per person, the same address under many people, and receive-only
participants (a recipient with no `people` entry). Not pairwise — do not
reintroduce an "A notifies B, B notifies A" assumption.

## Scheduling

Cron runs `garmin-sleep-notify` every 30 min, 06:00–13:00 inclusive, VM local
time. Installed by `scripts/install-cron.sh` (idempotent; `--dry-run` to preview,
`--remove` to uninstall) as two crontab lines tagged `# garmin-sleep-notify` — a single
`0,30 6-13` would also fire at 13:30, hence the split into `0,30 6-12` + `0 13`.

Each run processes only people not already fully notified today; score-not-ready
is logged and retried next run. "Already sent today" state is `state/sent_state.json`
(override `STATE_FILE`), keyed by ISO date so it resets daily.

## No phone dependency

Delivery is email via Resend (HTTP API + key). After `garmin-auth-setup` per
person, nothing running needs a phone, QR scan, or messaging session. Do not
reintroduce one (WhatsApp Web libraries, paired-device SDKs, etc.). Garmin tokens
auto-refresh ~1 year.

## Secrets / config

| File | Committed | Purpose |
| --- | --- | --- |
| `.env` / `.env.example` | no / yes | `RESEND_API_KEY`, `EMAIL_FROM`, paths, timezone, log level |
| `people.yaml` / `people.example.yaml` | no / yes | People → recipient emails |
| `~/.garmin_tokens/<name>/` | no | Per-person Garmin token store |
| `state/sent_state.json` | no | Runtime sent-today tracker |

Add a config key → update the matching `.example` file in the same change;
`tests/test_config.py` guards parsing.

## Deployment

- GCP project: `garmin-sleep-score-to-whatsapp`
- VM: `garmin-sleep-notifications-vm`, zone `us-west1-b`, `e2-micro` (Always Free)
- OS: Ubuntu 24.04 LTS
- Deploy: `git clone` → `uv sync` → `uv run`. Ship changes with `git pull && uv sync`.

## Local dev

```bash
uv sync
uv run pytest                          # offline
uv run garmin-auth-setup <name>        # real Garmin login
uv run garmin-sleep-notify --dry-run   # real fetch, sends nothing, writes nothing
uv run garmin-sleep-notify             # real job
```

Dependencies via `uv add` / `uv add --dev` only.
