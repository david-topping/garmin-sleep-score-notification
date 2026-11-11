# AGENTS.md

## Purpose

Each morning, fetch every configured person's Garmin Connect sleep score plus
stage breakdown (deep / light / rem / awake) and overnight stage timeline, and
email it to their recipients via the Resend API. Runs unattended as a Docker
Compose stack on the Proxmox homelab (supercronic inside the container), with no
phone dependency. The old GCP VM deployment is deprecated.

## Architecture

`src/garmin_sleep_score_notification/` holds one class per concern, each
unit-tested in `tests/`:

| Module         | Class(es)                       | Responsibility |
| -------------- | ------------------------------- | -------------- |
| `config.py`    | `Config`, `Person`, `Recipient` | Load `people.yaml` and `.env` into frozen dataclasses. `Config.load()`. |
| `garmin.py`    | `GarminFetcher`, `SleepSummary`, `StageSpan` | Token-only login and fetch. `SleepSummary` is pure sleep data (score, qualifier, stage breakdown, and a `timeline` of `StageSpan`s parsed from `sleepLevels`), no presentation; `from_payload()` returns `None` when not synced yet; raises `GarminError` on auth/network failure. |
| `email_content.py` | `SleepEmail`, `Attachment`  | Renders `subject`, `text`, `html`, and `attachments` from a `SleepSummary`, and owns all presentation (stage/qualifier colours, `hm()` duration formatting). The card makes no external requests: the HTML is score plus a stage-duration table, and the overnight stage timeline is a PNG embedded via `cid:` so it renders in every client including Gmail. `attachments` is empty when the payload carried no `sleepLevels`. |
| `hypnogram.py` | `Hypnogram`                     | Pillow renderer for the sleep-stage timeline: `StageSpan`s plus stage colours in, PNG bytes out (`None` when empty). No external requests. |
| `mailer.py`    | `EmailSender`                   | One Resend API send (`text`, `html`, and optional inline `attachments`); raises `EmailError`. |
| `state.py`     | `SentState`                     | JSON file: per date and person, `score`, `stages_min`, and which recipient emails were notified, plus a per-date `_uptime_kuma_up` flag. Prunes entries older than 7 days on `save()`. |
| `uptime_kuma.py` | `UptimeKuma`                  | Optional push monitor client. No-op without `UPTIME_KUMA_PUSH_URL`; 10 s timeout; never raises; never logs the URL (it embeds the token). |
| `notify.py`    | `Notifier`                      | Orchestration, Uptime Kuma up/down pushes, plus the `garmin-sleep-notify` CLI (`--dry-run`, `--people-file`). |
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

Docker (current): supercronic runs `garmin-sleep-notify` every 30 min from
06:00 to 13:00 inclusive, in the container's `TZ` (default `Europe/London`).
The schedule is `crontab` in the repo root, two lines (`0,30 6-12`, `0 13`) so
the window edges are exact. supercronic skips a run if the previous one is
still going.

Each run processes only people not already fully notified today; a score that is
not ready is logged and retried next run. Once every recipient for a person has
been emailed, that person is skipped for the rest of the day. "Already sent
today" state is `sent_state.json` (`STATE_FILE`), keyed by ISO date so it resets
daily.

GCP VM (deprecated): host cron every 10 min from 04:30 to 13:00, VM local time,
installed by `scripts/install-cron.sh` (idempotent; `--dry-run`, `--remove`) as
three lines tagged `# garmin-sleep-notify`.

## Monitoring (Uptime Kuma)

Optional. Set `UPTIME_KUMA_PUSH_URL` to a Kuma **Push** monitor URL; unset means
no pushes at all.

- **Up:** once per day, on the first run where every configured person is fully
  sent, push `status=up` with a message like `2026-11-11: sent wallace, gromit`.
  Recorded in state, so later runs that day don't push again. A failed push is
  retried next run.
- **Down:** an unexpected exception (a bug, unreadable state, disk error) pushes
  `status=down` with only the person and exception type, never the message, so
  no tokens or addresses leak.
- `GarminError` and `EmailError` (expired tokens, Garmin not synced, Resend
  hiccup) are expected and retried, so they don't push down. If they persist all
  day, the missing up push trips the heartbeat instead.
- Push failures are logged as a warning and never fail the job.

Kuma setup (davelab: LXC 104, `https://status.davelab.homes`): add a monitor of
type **Push**, group "davelab", heartbeat interval about a day: **90000 s
(25 h)**, since the up push lands whenever the last watch syncs, which drifts
from day to day. Copy the push URL into `.env`. Prefer the LAN
address (`http://192.168.178.15:3001/api/push/<token>`) so pushes don't depend on
Pi-hole or NPM; the `?status=up&msg=OK&ping=` suffix Kuma shows is fine, it is
replaced.

## No phone dependency

Delivery is email via Resend (HTTP API plus key). After `garmin-auth-setup` per
person, nothing running needs a phone, QR scan, or messaging session. Do not
reintroduce one (WhatsApp Web libraries, paired-device SDKs, and so on). Garmin
tokens auto-refresh for ~1 year.

## Secrets / config

| File | Committed | Purpose |
| --- | --- | --- |
| `.env` / `.env.example` | no / yes | `RESEND_API_KEY`, `EMAIL_FROM`, `TZ`, `UPTIME_KUMA_PUSH_URL`, paths, log level. Also compose's `env_file`. |
| `people.yaml` / `people.example.yaml` | no / yes | People and their recipient emails. Docker: `data/people.yaml`. |
| token store per person | no | `$GARMIN_TOKENS_DIR/<name>/garmin_tokens.json` unless a person sets `token_store`. Local default `~/.garmin_tokens`, Docker `data/garmin_tokens`. |
| `sent_state.json` | no | Runtime sent-today tracker. Local `state/`, Docker `data/state/`. |

Env vars:

| Var | Default (local / Docker) | Notes |
| --- | --- | --- |
| `RESEND_API_KEY` | required | |
| `EMAIL_FROM` | required | Verified Resend domain |
| `TZ` | system / `Europe/London` | Drives "today" and, in Docker, the cron schedule |
| `TIMEZONE` | unset | Legacy; wins over `TZ` for "today" only. Leave unset in Docker. |
| `UPTIME_KUMA_PUSH_URL` | unset | Optional push monitor |
| `PEOPLE_FILE` | `./people.yaml` / `/data/people.yaml` | |
| `STATE_FILE` | `./state/sent_state.json` / `/data/state/sent_state.json` | |
| `GARMIN_TOKENS_DIR` | `~/.garmin_tokens` / `/data/garmin_tokens` | |
| `DATA_DIR` | `./data` | compose only: host path mounted at `/data` |
| `LOG_LEVEL` | `INFO` | Logs go to stdout |

When you add a config key, update the matching `.example` file in the same
change. `tests/test_config.py` guards parsing.

## Deployment: homelab Docker (current)

Image: `python:3.12.16-slim-trixie`, uv `0.12.7`, supercronic `v0.2.51`
(sha256 pinned for amd64 and arm64). Dependencies via
`uv sync --frozen --no-dev`. Runs as uid 1000; `CMD` is supercronic, so
`docker compose run` can override it with any CLI.

Data volume (`${DATA_DIR:-./data}` on the host, `/data` in the container), all
of it persistent and none of it in the image:

```text
data/
  people.yaml                       # people and recipients
  garmin_tokens/<name>/garmin_tokens.json
  state/sent_state.json             # sent-today and heartbeat state
```

The container writes refreshed Garmin tokens and state back here, so it must be
owned by uid 1000: `sudo chown -R 1000:1000 data`.

First deploy, on the Docker host:

```bash
git clone <repo-url> /opt/garmin-sleep-notify && cd /opt/garmin-sleep-notify
cp .env.example .env                       # fill in; set UPTIME_KUMA_PUSH_URL
mkdir -p data && cp people.example.yaml data/people.yaml   # edit
sudo chown -R 1000:1000 data
docker compose build
docker compose run --rm -it garmin-sleep-notify garmin-auth-setup <name>   # per person, or migrate tokens
docker compose run --rm garmin-sleep-notify garmin-sleep-notify --dry-run
docker compose up -d
```

Update: `git pull && docker compose up -d --build`. Logs: Portainer's container
log view, or `docker compose logs -f`. In `people.yaml`, leave `token_store` out
(or use a `/data/...` path); a `~/...` path from the VM won't exist in the
container.

Portainer: a stack deployed from this directory with the CLI shows up in
Portainer (limited control) with logs and restart. For a Portainer git-repo
stack instead, relative paths resolve inside Portainer's own volume, so set
`DATA_DIR` to an absolute host path and make sure `.env` exists next to the
compose file (or switch `env_file` to Portainer's `stack.env`).

### Migrating from the GCP VM

1. On the VM, stop the job: `./scripts/install-cron.sh --remove`. Don't run
   both: they share no state and would double-send.
2. Copy into the homelab `data/`:
   - `~/.garmin_tokens/<name>/` (each person) to `data/garmin_tokens/<name>/`
   - `<repo>/people.yaml` to `data/people.yaml`, then delete its `token_store`
     lines
   - `<repo>/state/sent_state.json` to `data/state/sent_state.json` (optional:
     only stops a same-day resend)
3. Copy `<repo>/.env` to the homelab repo's `.env` (not into `data/`), drop any
   `PEOPLE_FILE`, `STATE_FILE` or `TIMEZONE` lines, and add `TZ` and
   `UPTIME_KUMA_PUSH_URL`.
4. `sudo chown -R 1000:1000 data`, dry run, `docker compose up -d`.

## Deployment: GCP VM (deprecated)

Kept for reference until the VM is shut down.

- GCP project: `garmin-sleep-score-to-whatsapp`
- VM: `garmin-sleep-notifications-vm`, zone `us-west1-b`, `e2-micro` (Always Free)
- OS: Ubuntu 24.04 LTS
- Deploy: `git clone`, `uv sync`, `uv run`, `./scripts/install-cron.sh`. Ship
  changes with `git pull && uv sync`.

## Local dev

```bash
uv sync
uv run pytest                          # offline
uv run garmin-auth-setup <name>        # real Garmin login
uv run garmin-sleep-notify --dry-run   # real fetch, sends nothing, writes nothing
uv run garmin-sleep-notify             # real job
```

Docker locally: `docker compose build`, then
`docker compose run --rm garmin-sleep-notify garmin-sleep-notify --dry-run`
(set `DATA_DIR` to a scratch folder with a `people.yaml`).

Dependencies via `uv add` and `uv add --dev` only.
