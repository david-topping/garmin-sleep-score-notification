from __future__ import annotations

from datetime import date
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError

from .sleep import SleepSummary


class GarminError(Exception):
    pass


class GarminFetcher:
    def __init__(self, token_store: str | Path) -> None:
        self.token_store = Path(token_store).expanduser()

    def fetch(self, day: date) -> SleepSummary | None:
        if not self.token_store.exists():
            raise GarminError(f"no token store at {self.token_store}: run auth-setup")
        client = Garmin()
        try:
            client.login(tokenstore=str(self.token_store))
            payload = client.get_sleep_data(day.isoformat())
        except GarminConnectAuthenticationError as exc:
            raise GarminError(f"auth failed ({exc}): re-run auth-setup") from exc
        except Exception as exc:
            raise GarminError(f"fetch failed: {exc}") from exc
        return SleepSummary.from_payload(payload)
