from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError


class GarminError(Exception):
    pass


_LEVEL = {0.0: "Deep", 1.0: "Light", 2.0: "REM", 3.0: "Awake"}


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


@dataclass(frozen=True)
class StageSpan:
    label: str
    start: float  # hours from the first recorded stage
    end: float


@dataclass(frozen=True)
class SleepSummary:
    score: int
    qualifier: str
    deep: timedelta
    light: timedelta
    rem: timedelta
    awake: timedelta
    timeline: tuple[StageSpan, ...] = field(default_factory=tuple)
    start_local: datetime | None = None

    @classmethod
    def from_payload(cls, payload: object) -> SleepSummary | None:
        payload = payload if isinstance(payload, dict) else {}
        dto = payload.get("dailySleepDTO") or {}
        overall = (dto.get("sleepScores") or {}).get("overall") or {}
        score = overall.get("value")
        if not isinstance(score, (int, float)):
            return None
        score = int(score)
        qualifier = str(overall.get("qualifierKey") or "").title() or _qualifier(score)
        timeline, start_local = _parse_timeline(payload.get("sleepLevels"), dto)
        return cls(
            score,
            qualifier,
            timedelta(seconds=dto.get("deepSleepSeconds") or 0),
            timedelta(seconds=dto.get("lightSleepSeconds") or 0),
            timedelta(seconds=dto.get("remSleepSeconds") or 0),
            timedelta(seconds=dto.get("awakeSleepSeconds") or 0),
            timeline,
            start_local,
        )

    @property
    def asleep(self) -> timedelta:
        return self.deep + self.light + self.rem

    def _percent(self, part: timedelta) -> int:
        total = self.asleep.total_seconds()
        return round(100 * part.total_seconds() / total) if total else 0

    def breakdown(self) -> list[Stage]:
        pairs = (("Deep", self.deep), ("Light", self.light), ("REM", self.rem), ("Awake", self.awake))
        return [Stage(name, td, self._percent(td)) for name, td in pairs]

    def as_record(self) -> dict:
        mins = {s.label.lower(): round(s.duration.total_seconds() / 60) for s in self.breakdown()}
        return {"score": self.score, "qualifier": self.qualifier, "stages_min": mins}


def _dt(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", ""))


def _parse_timeline(
    levels: object, dto: dict
) -> tuple[tuple[StageSpan, ...], datetime | None]:
    spans: list[tuple[str, datetime, datetime]] = []
    for lv in levels or []:
        try:
            label = _LEVEL.get(float(lv["activityLevel"]))
            start, end = _dt(lv["startGMT"]), _dt(lv["endGMT"])
        except (KeyError, TypeError, ValueError):
            continue
        if not label or end <= start:
            continue
        if spans and spans[-1][0] == label and (start - spans[-1][2]).total_seconds() <= 1:
            spans[-1] = (label, spans[-1][1], end)
        else:
            spans.append((label, start, end))
    if not spans:
        return (), None

    t0 = spans[0][1]
    timeline = tuple(
        StageSpan(
            label,
            (start - t0).total_seconds() / 3600,
            (end - t0).total_seconds() / 3600,
        )
        for label, start, end in spans
    )
    gmt_ms, local_ms = dto.get("sleepStartTimestampGMT"), dto.get("sleepStartTimestampLocal")
    start_local = None
    if isinstance(gmt_ms, (int, float)) and isinstance(local_ms, (int, float)):
        start_local = t0 + timedelta(milliseconds=local_ms - gmt_ms)
    return timeline, start_local


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
