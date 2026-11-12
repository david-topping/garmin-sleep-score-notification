# Garmin Sleep Score Notification

Emails each person's Garmin sleep score every morning via Resend.

## Local

```bash
uv sync
cp .env.example .env && cp people.example.yaml people.yaml
uv run garmin-auth-setup <name>
uv run garmin-sleep-notify --dry-run
uv run pytest
```

## Docker

```bash
cp .env.example .env
mkdir -p data && cp people.example.yaml data/people.yaml && sudo chown -R 1000:1000 data
docker compose run --rm -it garmin-sleep-notify garmin-auth-setup <name>
docker compose up -d
```

Details in [AGENTS.md](AGENTS.md).
