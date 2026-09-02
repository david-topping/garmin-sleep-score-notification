from datetime import timedelta

from garmin_sleep_score_notification.garmin import SleepSummary


def payload(score, deep=3600, light=14400, rem=5400, awake=720, qualifier="GOOD"):
    return {
        "dailySleepDTO": {
            "sleepScores": {"overall": {"value": score, "qualifierKey": qualifier}},
            "deepSleepSeconds": deep,
            "lightSleepSeconds": light,
            "remSleepSeconds": rem,
            "awakeSleepSeconds": awake,
        }
    }


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


def test_not_synced_returns_none():
    assert SleepSummary.from_payload({"dailySleepDTO": None}) is None
    assert SleepSummary.from_payload({"dailySleepDTO": {"sleepScores": None}}) is None
    assert SleepSummary.from_payload({}) is None
    assert SleepSummary.from_payload(None) is None
