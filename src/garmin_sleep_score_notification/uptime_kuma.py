from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

import requests

log = logging.getLogger("garmin_sleep")


class UptimeKuma:
    TIMEOUT = 10

    def __init__(self, push_url: str | None) -> None:
        # Kuma's copied URL already carries ?status=up&msg=OK&ping=, which would clash with ours.
        self.url = urlunsplit(urlsplit(push_url)._replace(query="")) if push_url else None

    def up(self, msg: str) -> bool:
        return self._push("up", msg)

    def down(self, msg: str) -> bool:
        return self._push("down", msg)

    def _push(self, status: str, msg: str) -> bool:
        if not self.url:
            return False
        try:
            resp = requests.get(
                self.url, params={"status": status, "msg": msg[:200]}, timeout=self.TIMEOUT
            )
            resp.raise_for_status()
        except Exception as exc:
            # The push URL embeds the monitor token, so log only the error type.
            log.warning("uptime kuma %s push failed (%s)", status, type(exc).__name__)
            return False
        log.info("uptime kuma: pushed %s", status)
        return True
