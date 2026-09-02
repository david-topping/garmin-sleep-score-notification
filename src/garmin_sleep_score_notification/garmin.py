from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError


class GarminError(Exception):
    pass


@dataclass(frozen=True)
class SleepSummary:
    score: int
    deep: timedelta
    light: timedelta
    rem: timedelta
    awake: timedelta

    @classmethod
    def from_payload(cls, payload: object) -> SleepSummary | None:
        dto = (payload if isinstance(payload, dict) else {}).get("dailySleepDTO") or {}
        score = ((dto.get("sleepScores") or {}).get("overall") or {}).get("value")
        if not isinstance(score, (int, float)):
            return None
        return cls(
            int(score),
            timedelta(seconds=dto.get("deepSleepSeconds") or 0),
            timedelta(seconds=dto.get("lightSleepSeconds") or 0),
            timedelta(seconds=dto.get("remSleepSeconds") or 0),
            timedelta(seconds=dto.get("awakeSleepSeconds") or 0),
        )

    @staticmethod
    def _hm(td: timedelta) -> str:
        total = int(td.total_seconds())
        return f"{total // 3600}h{total % 3600 // 60:02d}m"

    def stages(self) -> str:
        return (
            f"deep {self._hm(self.deep)}, light {self._hm(self.light)}, "
            f"rem {self._hm(self.rem)}, awake {self._hm(self.awake)}"
        )


class GarminFetcher:
    def __init__(self, token_store: str | Path) -> None:
        self.token_store = Path(token_store).expanduser()

    def fetch(self, day: date) -> SleepSummary | None:
        if not self.token_store.exists():
            raise GarminError(f"no token store at {self.token_store} - run auth-setup")
        client = Garmin()
        try:
            client.login(tokenstore=str(self.token_store))
            payload = client.get_sleep_data(day.isoformat())
        except GarminConnectAuthenticationError as exc:
            raise GarminError(f"auth failed ({exc}) - re-run auth-setup") from exc
        except Exception as exc:
            raise GarminError(f"fetch failed: {exc}") from exc
        return SleepSummary.from_payload(payload)
