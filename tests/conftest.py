import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from garmin_sleep_score_notification.garmin import SleepSummary, StageSpan

_PAYLOAD = json.loads((Path(__file__).parent / "fixtures" / "sleep_payload.json").read_text())

MORNING = datetime(2026, 9, 2, 7, 15, tzinfo=ZoneInfo("Europe/London"))


@pytest.fixture(autouse=True)
def frozen_morning(time_machine):
    time_machine.move_to(MORNING, tick=False)


@pytest.fixture
def sleep_payload():
    return copy.deepcopy(_PAYLOAD)


@pytest.fixture
def summary(sleep_payload):
    return SleepSummary.from_payload(sleep_payload)


@pytest.fixture
def make_summary():
    def make(score=82, qualifier="Good", timeline=(), start_local=None):
        h = timedelta(hours=1)
        return SleepSummary(
            score, qualifier, h, 4 * h, h, timedelta(minutes=10), timeline, start_local
        )

    return make


@pytest.fixture
def spans():
    return (
        StageSpan("Light", 0.0, 0.7),
        StageSpan("Deep", 0.7, 1.7),
        StageSpan("Light", 1.7, 3.2),
        StageSpan("REM", 3.2, 3.7),
        StageSpan("Awake", 3.7, 3.9),
    )
