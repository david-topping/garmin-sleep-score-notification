# AGENTS.md

## Purpose

Each morning, fetch every configured person's Garmin Connect sleep score plus
stage breakdown (deep / light / rem / awake) and overnight stage timeline, and
email it to their recipients via the Resend API. Runs unattended as a Docker
Compose stack on the Proxmox homelab (supercronic inside the container), with no
phone dependency. The old GCP VM deployment is deprecated.

## Architecture

`src/garmin_sleep_score_notification/` is packaged by feature, one class per
concern:

| Module | Class(es) | Responsibility |
| --- | --- | --- |
| `config.py` | `Config`, `Person`, `Recipient` | Load `people.yaml` and `.env` into frozen dataclasses. `Config.load()`. |
| `garmin/sleep.py` | `SleepSummary`, `Stage`, `StageSpan` | Pure sleep data (score, qualifier, stage breakdown, a `timeline` of `StageSpan`s parsed from `sleepLevels`, and `wake_local` from `sleepEndTimestampLocal`), no presentation. `from_payload()` returns `None` when not synced yet. |
| `garmin/fetcher.py` | `GarminFetcher`, `GarminError` | Token-only login and fetch; raises `GarminError` on auth/network failure. |
| `garmin/auth_setup.py` | `AuthSetup` | Interactive one-time login and token dump (`garmin-auth-setup <name>`). |
| `email/content.py` | `SleepEmail`, `Attachment` | Renders `subject`, `text`, `html` and `attachments` from a `SleepSummary` plus yesterday's score, and owns presentation data (stage/qualifier colours, `hm()`). |
| `email/templates/` | (none) | `sleep.mjml.j2` (Jinja2, then MJML via `mjml-python`) for the HTML part, `sleep.txt.j2` for the plain-text part. |
| `email/hypnogram.py` | `Hypnogram` | Pillow renderer for the sleep-stage timeline: `StageSpan`s plus stage colours in, PNG bytes out (`None` when empty). |
| `email/sender.py` | `EmailSender`, `EmailError` | One Resend API send (`text`, `html`, and optional inline `attachments`). |
| `state.py` | `SentState` | JSON file: per date and person, `score`, `qualifier`, `stages_min`, `wake` (`HH:MM`), and which recipient emails were notified. Prunes entries older than 7 days on `save()`. |
| `uptime_kuma.py` | `UptimeKuma` | Optional push monitor client. No-op without `UPTIME_KUMA_PUSH_URL`; 10 s timeout; never raises; never logs the URL (it embeds the token). |
| `notify.py` | `Notifier` | Orchestration, Uptime Kuma up/down pushes, plus the `garmin-sleep-notify` CLI (`--dry-run`, `--preview DIR`, `--people-file`). Exit codes: `0` ok, `1` a fetch or send failed, `2` config error. |
| `__init__.py` | (none) | `configure_logging()` only. |

`garmin/` and `email/` re-export their public classes from `__init__.py`.

### Email

The HTML is an MJML template rendered by `mjml-python` (Rust, no Node), so it is
responsive, Outlook-safe table markup with inlined styles. Email clients run no
JavaScript and only some CSS: edit `sleep.mjml.j2`, not raw HTML. Rules:

- No external requests. `mjml2html(..., fonts={})` stops MJML adding a Google
  Fonts link; no remote images. The stage timeline is a PNG embedded via
  `cid:` so it renders everywhere, including Gmail. `attachments` is empty when
  the payload carried no `sleepLevels`.
- Light only (`color-scheme: light only`): the PNG has a white background.
- The leaderboard is the last section. Each row is a person's average `score`
  and average `wake` over the last 7 days (today plus 6 earlier days in
  `sent_state.json`, using whichever nights have data), ranked by average
  score. Someone not synced yet today still shows their earlier average;
  anyone with no data is listed last. Each recipient gets their own render,
  since the leaderboard depends on the reader.
- "vs yesterday" comes from yesterday's `score` in `sent_state.json`, omitted
  when there is none.
- Iterate on the design with `garmin-sleep-notify --preview out/` (real fetch,
  writes `<name>.html`, `.txt` and the PNG, sends and records nothing), then
  `uv run pytest --snapshot-update` and review the snapshot diff.

### Tests

pytest, packaged like `src/` (`tests/garmin/`, `tests/email/`). Shared fixtures
are in `tests/conftest.py`: time is frozen to 2026-09-02 07:15 Europe/London
with `time-machine` for every test, and `summary` comes from
`tests/fixtures/sleep_payload.json`, a realistic Garmin payload. HTTP is
mocked with `responses`, the email HTML and text are `syrupy` snapshots
(`tests/email/__snapshots__/`), and coverage is `uv run pytest --cov`.

Adding a person or recipient is a `people.yaml` change, never code.

Style: class-based, comments kept to an absolute minimum, simplicity over
cleverness. Keep it that way.

## Fan-out model

`people.yaml` is a flat list of **people** (someone whose score is fetched). Each
owns a list of **recipients** (`email`, optional `label`). Any fan-out is valid:
many recipients per person, the same address under many people, and receive-only
participants (a recipient with no `people` entry). Not pairwise: do not
reintroduce an "A notifies B, B notifies A" assumption.

A person may also set their own `email`. That only feeds the leaderboard: the
email to an address ranks every person whose score that address receives, plus
the person whose own `email` it is (marked "you"). Hidden when that's fewer
than two people.

## Scheduling

Docker (current): supercronic runs `garmin-sleep-notify` every 5 min from
04:30 to 14:00 inclusive, in the container's `TZ` (default `Europe/London`).
The schedule is `crontab` in the repo root, three lines (`30-55/5 4`, `*/5 5-13`,
`0 14`) so
the window edges are exact. supercronic skips a run if the previous one is
still going.

Each run processes only people not already fully notified today, in two passes:
fetch all of them, then send, so a leaderboard sees every score available in
that run. A score that is not ready is logged and retried next run. Once every recipient for a person has
been emailed, that person is skipped for the rest of the day. "Already sent
today" state is `sent_state.json` (`STATE_FILE`), keyed by ISO date so it resets
daily.

GCP VM (deprecated): host cron every 10 min from 04:30 to 13:00, VM local time,
installed by `scripts/install-cron.sh` (idempotent; `--dry-run`, `--remove`) as
three lines tagged `# garmin-sleep-notify`.

## Monitoring (Uptime Kuma)

Optional. Set `UPTIME_KUMA_PUSH_URL` to a Kuma **Push** monitor URL; unset means
no pushes at all.

The monitor answers "is the script running and healthy", not "did everyone get
an email": someone not wearing their watch must never alert.

- **Up:** every run with no failures pushes `status=up`, with a message like
  `ok, sent: David, waiting: Vicky`. "No sleep score yet" is not a failure, so
  a person who never syncs keeps it green.
- **No push:** a run with a `GarminError` or `EmailError` (expired tokens,
  Garmin or Resend unreachable). One bad run is harmless; if every run fails,
  the heartbeat runs out and Kuma alerts.
- **Down:** an unexpected exception (a bug, unreadable state, disk error) pushes
  `status=down` with only the person and exception type, never the message, so
  no tokens or addresses leak.
- Push failures are logged as a warning and never fail the job.

Kuma setup (davelab: LXC 104, `https://status.davelab.homes`): add a monitor of
type **Push**, group "davelab", heartbeat interval **55800 s (15.5 h)**: the
longest normal gap is 14:00 to 04:30 (14.5 h), so it alerts by about 05:30 if the
container stopped or every run failed. Copy the push URL into `.env`. Prefer the LAN
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
| `.env` / `.env.example` | no / yes | `RESEND_API_KEY`, `EMAIL_FROM`, `TZ`, `UPTIME_KUMA_PUSH_URL`, log level. compose interpolates these; in Portainer they're the stack's environment variables instead. |
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

`compose.yaml` takes its settings by interpolation (`${VAR}`), not `env_file`,
so the same file works from a local `.env` or from Portainer's stack
environment variables. `RESEND_API_KEY` and `EMAIL_FROM` are required; the
deploy fails fast without them.

### Portainer (current)

1. On the Docker host, create the data folder once (Garmin tokens can't be
   entered through Portainer):
   `sudo mkdir -p /opt/garmin-sleep-notify/data`, put `people.yaml` and
   `garmin_tokens/` in it, then `sudo chown -R 1000:1000 /opt/garmin-sleep-notify/data`.
2. Portainer > Stacks > Add stack > **Repository**: this repo's URL, reference
   `refs/heads/main`, compose path `compose.yaml`.
3. Environment variables: `RESEND_API_KEY`, `EMAIL_FROM`, `TZ`,
   `UPTIME_KUMA_PUSH_URL`, and `DATA_DIR=/opt/garmin-sleep-notify/data`. It has
   to be absolute: Portainer resolves relative paths inside its own volume.
4. Deploy. Logs show in the container's log view.
5. Updates: the stack's **Pull and redeploy** (with re-pull/rebuild), or turn on
   GitOps updates (polling) to follow `main`.

New person without tokens to copy:
`docker exec -it garmin-sleep-notify garmin-auth-setup <name>`, or the container
console in Portainer. In `people.yaml`, leave `token_store` out (or use a
`/data/...` path); a `~/...` path from the VM won't exist in the container.

### CLI alternative

```bash
git clone <repo-url> /opt/garmin-sleep-notify && cd /opt/garmin-sleep-notify
cp .env.example .env                       # fill in
mkdir -p data && cp people.example.yaml data/people.yaml   # edit
sudo chown -R 1000:1000 data
docker compose run --rm garmin-sleep-notify garmin-sleep-notify --dry-run
docker compose up -d
```

Update with `git pull && docker compose up -d --build`.

### Migrating from the GCP VM

1. On the VM, stop the job: `./scripts/install-cron.sh --remove`. Don't run
   both: they share no state and would double-send.
2. Copy into the homelab `data/`:
   - `~/.garmin_tokens/<name>/` (each person) to `data/garmin_tokens/<name>/`
   - `<repo>/people.yaml` to `data/people.yaml`, then delete its `token_store`
     lines
   - `<repo>/state/sent_state.json` to `data/state/sent_state.json` (optional:
     only stops a same-day resend)
3. Take `RESEND_API_KEY` and `EMAIL_FROM` from the VM's `<repo>/.env` into the
   Portainer stack's environment variables (or a local `.env` for the CLI
   route). Don't carry over `PEOPLE_FILE`, `STATE_FILE` or `TIMEZONE`.
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
uv run pytest --cov                    # with coverage
uv run garmin-auth-setup <name>        # real Garmin login
uv run garmin-sleep-notify --dry-run   # real fetch, sends nothing, writes nothing
uv run garmin-sleep-notify --preview out/  # dry run that also writes each email to out/
uv run garmin-sleep-notify             # real job
```

Docker locally: `docker compose build`, then
`docker compose run --rm garmin-sleep-notify garmin-sleep-notify --dry-run`
(set `DATA_DIR` to a scratch folder with a `people.yaml`).

Dependencies via `uv add` and `uv add --dev` only.
