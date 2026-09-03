# AGENTS.md

## Purpose

Each morning, fetch every configured person's Garmin Connect sleep score plus
stage breakdown (deep / light / rem / awake) and overnight stage timeline, and
email it to their recipients via the Resend API. Runs unattended on a headless
GCP VM with no phone dependency.

## Architecture

`src/garmin_sleep_score_notification/` holds one class per concern, each
unit-tested in `tests/`:

| Module         | Class(es)                       | Responsibility |
| -------------- | ------------------------------- | -------------- |
| `config.py`    | `Config`, `Person`, `Recipient` | Load `people.yaml` and `.env` into frozen dataclasses. `Config.load()`. |
| `garmin.py`    | `GarminFetcher`, `SleepSummary`, `StageSpan` | Token-only login and fetch. `SleepSummary` is pure sleep data (score, qualifier, stage breakdown, and a `timeline` of `StageSpan`s parsed from `sleepLevels`), no presentation; `from_payload()` returns `None` when not synced yet; raises `GarminError` on auth/network failure. |
| `email_content.py` | `SleepEmail`, `Attachment`  | Renders `subject`, `text`, `html`, and `attachments` from a `SleepSummary`, and owns all presentation (stage/qualifier colours, `hm()` duration formatting). The card makes no external requests: stage split is an inline `<svg>` donut (with a legend carrying the same figures for clients that strip SVG, e.g. Gmail), and the stage timeline is a PNG embedded via `cid:` so it renders in every client including Gmail. `attachments` is empty when the payload carried no `sleepLevels`. |
| `donut.py`     | `Donut`                         | Inline-SVG donut renderer: `(colour, fraction)` segments plus centre text in, `<svg>` string out. No images or requests. |
| `hypnogram.py` | `Hypnogram`                     | Pillow renderer for the sleep-stage timeline: `StageSpan`s plus stage colours in, PNG bytes out (`None` when empty). No external requests. |
| `mailer.py`    | `EmailSender`                   | One Resend API send (`text`, `html`, and optional inline `attachments`); raises `EmailError`. |
| `state.py`     | `SentState`                     | JSON file: per date and person, `score`, `stages_min`, and which recipient emails were notified. Prunes entries older than 7 days on `save()`. |
| `notify.py`    | `Notifier`                      | Orchestration plus the `garmin-sleep-notify` CLI (`--dry-run`, `--people-file`). |
| `auth_setup.py`| `AuthSetup`                     | Interactive one-time login and token dump (`garmin-auth-setup <name>`). |
| `__init__.py`  | (none)                          | `configure_logging()` only. |

Adding a person or recipient is a `people.yaml` change, never code.

Style: class-based, comments kept to an absolute minimum, simplicity over
cleverness. Keep it that way.

## Fan-out model

`people.yaml` is a flat list of **people** (someone whose score is fetched). Each
owns a list of **recipients** (`email`, optional `label`). Any fan-out is valid:
many recipients per person, the same address under many people, and receive-only
participants (a recipient with no `people` entry). Not pairwise: do not
reintroduce an "A notifies B, B notifies A" assumption.

## Scheduling

Cron runs `garmin-sleep-notify` every 10 min from 04:30 to 13:00 inclusive, VM
local time. Installed by `scripts/install-cron.sh` (idempotent; `--dry-run` to
preview, `--remove` to uninstall) as three crontab lines tagged
`# garmin-sleep-notify`: `30,40,50 4`, `*/10 5-12`, `0 13`, split so the window
edges are exact.

Each run processes only people not already fully notified today; a score that is
not ready is logged and retried next run. Once every recipient for a person has
been emailed, that person is skipped for the rest of the day. "Already sent
today" state is `state/sent_state.json` (override `STATE_FILE`), keyed by ISO
date so it resets daily.

## No phone dependency

Delivery is email via Resend (HTTP API plus key). After `garmin-auth-setup` per
person, nothing running needs a phone, QR scan, or messaging session. Do not
reintroduce one (WhatsApp Web libraries, paired-device SDKs, and so on). Garmin
tokens auto-refresh for ~1 year.

## Secrets / config

| File | Committed | Purpose |
| --- | --- | --- |
| `.env` / `.env.example` | no / yes | `RESEND_API_KEY`, `EMAIL_FROM`, paths, timezone, log level |
| `people.yaml` / `people.example.yaml` | no / yes | People and their recipient emails |
| `~/.garmin_tokens/<name>/` | no | Per-person Garmin token store |
| `state/sent_state.json` | no | Runtime sent-today tracker |

When you add a config key, update the matching `.example` file in the same
change. `tests/test_config.py` guards parsing.

## Deployment

- GCP project: `garmin-sleep-score-to-whatsapp`
- VM: `garmin-sleep-notifications-vm`, zone `us-west1-b`, `e2-micro` (Always Free)
- OS: Ubuntu 24.04 LTS
- Deploy: `git clone`, `uv sync`, `uv run`. Ship changes with `git pull && uv sync`.

## Local dev

```bash
uv sync
uv run pytest                          # offline
uv run garmin-auth-setup <name>        # real Garmin login
uv run garmin-sleep-notify --dry-run   # real fetch, sends nothing, writes nothing
uv run garmin-sleep-notify             # real job
```

Dependencies via `uv add` and `uv add --dev` only.
