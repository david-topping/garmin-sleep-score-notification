# syntax=docker/dockerfile:1.10

FROM scratch AS supercronic-amd64
ADD --chmod=755 --checksum=sha256:cc232108374e8e2b537045f2d5eaa1229f619db314c3ba6a14d38b35dc0aa123 \
    https://github.com/aptible/supercronic/releases/download/v0.2.51/supercronic-linux-amd64 /supercronic

FROM scratch AS supercronic-arm64
ADD --chmod=755 --checksum=sha256:4ae22576a78223d8ccdf5f3b3660a5cbb5288416bf0ca96afc4a36d195932b94 \
    https://github.com/aptible/supercronic/releases/download/v0.2.51/supercronic-linux-arm64 /supercronic

FROM supercronic-${TARGETARCH} AS supercronic

FROM ghcr.io/astral-sh/uv:0.12.7 AS uv

FROM python:3.12.16-slim-trixie

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/.venv/bin:$PATH \
    TZ=Europe/London \
    PEOPLE_FILE=/data/people.yaml \
    STATE_FILE=/data/state/sent_state.json \
    GARMIN_TOKENS_DIR=/data/garmin_tokens

COPY --from=uv /uv /usr/local/bin/uv
COPY --from=supercronic /supercronic /usr/local/bin/supercronic

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

RUN useradd --uid 1000 --create-home app && mkdir -p /data && chown app:app /data
COPY crontab /app/crontab
USER app
VOLUME /data

CMD ["supercronic", "-passthrough-logs", "/app/crontab"]
