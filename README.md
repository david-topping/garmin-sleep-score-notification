# garmin-sleep-score-notification

Every morning, fetch each configured person's Garmin Connect sleep score + stage
breakdown and email it to their recipients via [Resend](https://resend.com).
Runs unattended on a headless GCP `e2-micro` VM — no phone dependency.

Each email is a small HTML card — score, qualifier, a stacked deep/light/REM bar,
and per-stage durations — with a plain-text fallback. Subject:
`wallace sleep score 88 03/09/26`.

## Config

- **`.env`** (gitignored) – `RESEND_API_KEY` and `EMAIL_FROM` required; `PEOPLE_FILE`,
  `STATE_FILE`, `TIMEZONE`, `LOG_LEVEL` optional. Template: `.env.example`.
- **`people.yaml`** (gitignored) – the people → recipients list. Structured, not
  flat `.env` keys, because the list is dynamic and each person owns a
  variable-length list of recipients. Template: `people.example.yaml`.

`EMAIL_FROM` must be on a domain verified in Resend, or use `onboarding@resend.dev`
(delivers only to your own Resend account email — fine for testing).

Fan-out: many recipients per person, the same address under many people, and
receive-only people (a recipient with no `people` entry) are all fine. Not pairwise.

## One-time setup

```bash
uv sync
cp .env.example .env             && $EDITOR .env           # Resend key + from address
cp people.example.yaml people.yaml && $EDITOR people.yaml   # people + recipient emails
uv run garmin-auth-setup <name>                             # per person: email + password + MFA
```

`garmin-auth-setup` writes `~/.garmin_tokens/<name>/` and the scheduled job
reuses it (auto-refreshes ~1 year). Re-run only if that person starts failing
with an auth error.

## Running

```bash
uv run garmin-sleep-notify            # the real job
uv run garmin-sleep-notify --dry-run  # fetch + log, send nothing, write nothing
```

Each run: for every person not already fully notified today, fetch the score and
email each not-yet-notified recipient. Score not synced yet → logged and retried
next run. Fully notified → skipped for the rest of the day. State lives in
`state/sent_state.json`, keyed by date, so it resets each day. One person's
failure never blocks the others. Exit: `0` ok, `1` a fetch/send failed, `2`
config error.

## Deploy to the VM

Project `garmin-sleep-score-to-whatsapp`, instance `garmin-sleep-notifications-vm`,
zone `us-west1-b`, `e2-micro`, Ubuntu 24.04.

```bash
gcloud compute ssh garmin-sleep-notifications-vm --zone us-west1-b
curl -LsSf https://astral.sh/uv/install.sh | sh && exec $SHELL
sudo timedatectl set-timezone Europe/London
git clone <repo-url> ~/garmin-sleep-score-notification
cd ~/garmin-sleep-score-notification && uv sync
cp .env.example .env && $EDITOR .env
cp people.example.yaml people.yaml && $EDITOR people.yaml
uv run garmin-auth-setup <name>          # per person
uv run garmin-sleep-notify --dry-run     # check
./scripts/install-cron.sh                # schedule it
```

### Crontab

```bash
./scripts/install-cron.sh            # install / update
./scripts/install-cron.sh --dry-run  # preview, change nothing
./scripts/install-cron.sh --remove   # uninstall
```

Idempotent. Installs two entries (every 30 min 06:00–13:00 inclusive; a single
`0,30 6-13` would also fire at 13:30), logging to `~/garmin-sleep.log`:

```cron
0,30 6-12 * * * cd ~/garmin-sleep-score-notification && ~/.local/bin/uv run garmin-sleep-notify >> ~/garmin-sleep.log 2>&1
0    13   * * * cd ~/garmin-sleep-score-notification && ~/.local/bin/uv run garmin-sleep-notify >> ~/garmin-sleep.log 2>&1
```

Ship changes: `git pull && uv sync` on the VM.

## Test end-to-end locally

```bash
uv run pytest                          # 1. offline unit suite

cp .env.example .env                   # 2. real Resend key; EMAIL_FROM + one recipient = your email
cp people.example.yaml people.yaml     #    one person = you
uv run garmin-auth-setup <you>         # 3. real token store
uv run garmin-sleep-notify --dry-run   # 4. real fetch, nothing sent
uv run garmin-sleep-notify             # 5. real email to yourself
uv run garmin-sleep-notify             # 6. run again -> "already sent today"
cat state/sent_state.json
```

## Layout

```
config.py    people.yaml + .env  -> Config / Person / Recipient
garmin.py    GarminFetcher, SleepSummary (score + qualifier + stages)
email_content.py  SleepEmail (subject / text / html)
mailer.py    EmailSender (Resend)
state.py     SentState (sent-today JSON tracker; stores score + stage minutes)
notify.py    Notifier + garmin-sleep-notify CLI
auth_setup.py  AuthSetup + garmin-auth-setup CLI
scripts/install-cron.sh   install/remove the VM cron entries
```

uv only – `uv add`, `uv run`, `uv sync`. No pip, no manual venv.
