from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError


class GarminError(Exception):
    pass


def _qualifier(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 80:
        return "Good"
    if score >= 60:
        return "Fair"
    return "Poor"


@dataclass(frozen=True)
class Stage:
    label: str
    duration: timedelta
    percent: int
    colour: str


@dataclass(frozen=True)
class SleepSummary:
    score: int
    qualifier: str
    deep: timedelta
    light: timedelta
    rem: timedelta
    awake: timedelta

    _COLOURS = {"Deep": "#2f4b7c", "Light": "#5b8def", "REM": "#7b61ff", "Awake": "#e8a33d"}

    @classmethod
    def from_payload(cls, payload: object) -> SleepSummary | None:
        dto = (payload if isinstance(payload, dict) else {}).get("dailySleepDTO") or {}
        overall = (dto.get("sleepScores") or {}).get("overall") or {}
        score = overall.get("value")
        if not isinstance(score, (int, float)):
            return None
        score = int(score)
        qualifier = str(overall.get("qualifierKey") or "").title() or _qualifier(score)
        return cls(
            score,
            qualifier,
            timedelta(seconds=dto.get("deepSleepSeconds") or 0),
            timedelta(seconds=dto.get("lightSleepSeconds") or 0),
            timedelta(seconds=dto.get("remSleepSeconds") or 0),
            timedelta(seconds=dto.get("awakeSleepSeconds") or 0),
        )

    @property
    def asleep(self) -> timedelta:
        return self.deep + self.light + self.rem

    @staticmethod
    def hm(td: timedelta) -> str:
        total = int(td.total_seconds())
        return f"{total // 3600}h {total % 3600 // 60:02d}m"

    def _percent(self, part: timedelta) -> int:
        total = self.asleep.total_seconds()
        return round(100 * part.total_seconds() / total) if total else 0

    def breakdown(self) -> list[Stage]:
        pairs = (("Deep", self.deep), ("Light", self.light), ("REM", self.rem), ("Awake", self.awake))
        return [Stage(name, td, self._percent(td), self._COLOURS[name]) for name, td in pairs]

    def stages(self) -> str:
        return ", ".join(f"{s.label.lower()} {self.hm(s.duration)}" for s in self.breakdown())

    def as_record(self) -> dict:
        mins = {s.label.lower(): round(s.duration.total_seconds() / 60) for s in self.breakdown()}
        return {"score": self.score, "qualifier": self.qualifier, "stages_min": mins}


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
