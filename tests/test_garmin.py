from garmin_sleep_score_notification.garmin import SleepSummary


def payload(score, deep=3600, light=14400, rem=5400, awake=720):
    return {
        "dailySleepDTO": {
            "sleepScores": {"overall": {"value": score}},
            "deepSleepSeconds": deep,
            "lightSleepSeconds": light,
            "remSleepSeconds": rem,
            "awakeSleepSeconds": awake,
        }
    }


def test_parses_score_and_stages():
    summary = SleepSummary.from_payload(payload(87))
    assert summary.score == 87
    assert summary.stages() == "deep 1h00m, light 4h00m, rem 1h30m, awake 0h12m"


def test_float_score_coerced():
    assert SleepSummary.from_payload(payload(87.0)).score == 87


def test_not_synced_returns_none():
    assert SleepSummary.from_payload({"dailySleepDTO": None}) is None
    assert SleepSummary.from_payload({"dailySleepDTO": {"sleepScores": None}}) is None
    assert SleepSummary.from_payload({}) is None
    assert SleepSummary.from_payload(None) is None
