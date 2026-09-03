from datetime import datetime, timedelta

from garmin_sleep_score_notification.garmin import SleepSummary

# 23:00 local sits one hour ahead of GMT (e.g. BST)
_LEVELS = [
    {"startGMT": "2026-09-01T22:00:00.0", "endGMT": "2026-09-01T22:40:00.0", "activityLevel": 1.0},
    {"startGMT": "2026-09-01T22:40:00.0", "endGMT": "2026-09-01T23:40:00.0", "activityLevel": 0.0},
    {"startGMT": "2026-09-01T23:40:00.0", "endGMT": "2026-09-02T01:10:00.0", "activityLevel": 1.0},
    {"startGMT": "2026-09-02T01:10:00.0", "endGMT": "2026-09-02T01:40:00.0", "activityLevel": 2.0},
    {"startGMT": "2026-09-02T01:40:00.0", "endGMT": "2026-09-02T01:50:00.0", "activityLevel": 3.0},
]


def payload(score, deep=3600, light=14400, rem=5400, awake=720, qualifier="GOOD", levels=None):
    dto = {
        "sleepScores": {"overall": {"value": score, "qualifierKey": qualifier}},
        "deepSleepSeconds": deep,
        "lightSleepSeconds": light,
        "remSleepSeconds": rem,
        "awakeSleepSeconds": awake,
        "sleepStartTimestampGMT": 1_756_764_000_000,  # 2026-09-01T22:00:00Z
        "sleepStartTimestampLocal": 1_756_767_600_000,  # +1h
    }
    out = {"dailySleepDTO": dto}
    if levels is not None:
        out["sleepLevels"] = levels
    return out


def test_parses_score_stages_and_qualifier():
    summary = SleepSummary.from_payload(payload(87, qualifier="EXCELLENT"))
    assert summary.score == 87
    assert summary.qualifier == "Excellent"
    assert [(s.label, s.duration) for s in summary.breakdown()] == [
        ("Deep", timedelta(hours=1)),
        ("Light", timedelta(hours=4)),
        ("REM", timedelta(minutes=90)),
        ("Awake", timedelta(seconds=720)),
    ]


def test_qualifier_falls_back_to_score_bucket():
    assert SleepSummary.from_payload(payload(95, qualifier="")).qualifier == "Excellent"
    assert SleepSummary.from_payload(payload(72, qualifier="")).qualifier == "Fair"


def test_breakdown_percentages_are_of_time_asleep():
    # deep 1h, light 1h, rem 2h -> 25 / 25 / 50
    summary = SleepSummary.from_payload(payload(80, deep=3600, light=3600, rem=7200))
    deep, light, rem, awake = summary.breakdown()
    assert (deep.percent, light.percent, rem.percent) == (25, 25, 50)
    assert awake.label == "Awake"


def test_as_record_is_compact():
    rec = SleepSummary.from_payload(payload(90)).as_record()
    assert rec["score"] == 90
    assert rec["stages_min"] == {"deep": 60, "light": 240, "rem": 90, "awake": 12}


def test_timeline_defaults_empty_without_sleep_levels():
    summary = SleepSummary.from_payload(payload(80))
    assert summary.timeline == ()
    assert summary.start_local is None


def test_timeline_parses_spans_merges_and_localises():
    summary = SleepSummary.from_payload(payload(80, levels=_LEVELS))
    # spans in minutes from the first recorded stage
    assert [(s.label, round(s.start * 60), round(s.end * 60)) for s in summary.timeline] == [
        ("Light", 0, 40),
        ("Deep", 40, 100),
        ("Light", 100, 190),
        ("REM", 190, 220),
        ("Awake", 220, 230),
    ]
    # local start is the first span (22:00 GMT) shifted by +1h
    assert summary.start_local == datetime(2026, 9, 1, 23, 0)


def test_timeline_merges_touching_same_stage_spans():
    levels = [
        {"startGMT": "2026-09-01T22:00:00.0", "endGMT": "2026-09-01T22:30:00.0", "activityLevel": 1.0},
        {"startGMT": "2026-09-01T22:30:00.0", "endGMT": "2026-09-01T23:00:00.0", "activityLevel": 1.0},
    ]
    timeline = SleepSummary.from_payload(payload(80, levels=levels)).timeline
    assert [(s.label, s.start, s.end) for s in timeline] == [("Light", 0.0, 1.0)]


def test_timeline_skips_unknown_levels_and_empty_spans():
    levels = [
        {"startGMT": "2026-09-01T22:00:00.0", "endGMT": "2026-09-01T22:00:00.0", "activityLevel": 1.0},
        {"startGMT": "2026-09-01T22:00:00.0", "endGMT": "2026-09-01T22:30:00.0", "activityLevel": 9.0},
        {"startGMT": "2026-09-01T22:30:00.0", "endGMT": "2026-09-01T23:00:00.0", "activityLevel": 0.0},
    ]
    timeline = SleepSummary.from_payload(payload(80, levels=levels)).timeline
    assert [s.label for s in timeline] == ["Deep"]


def test_not_synced_returns_none():
    assert SleepSummary.from_payload({"dailySleepDTO": None}) is None
    assert SleepSummary.from_payload({"dailySleepDTO": {"sleepScores": None}}) is None
    assert SleepSummary.from_payload({}) is None
    assert SleepSummary.from_payload(None) is None
