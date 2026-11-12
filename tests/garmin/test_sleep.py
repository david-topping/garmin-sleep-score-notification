from datetime import datetime, timedelta

import pytest

from garmin_sleep_score_notification.garmin import SleepSummary


def levels(*spans):
    return [
        {"startGMT": f"2026-09-01T{start}:00.0", "endGMT": f"2026-09-01T{end}:00.0", "activityLevel": lvl}
        for start, end, lvl in spans
    ]


def test_parses_score_stages_and_qualifier(summary):
    assert summary.score == 84
    assert summary.qualifier == "Good"
    assert [(s.label, s.duration) for s in summary.breakdown()] == [
        ("Deep", timedelta(minutes=104)),
        ("Light", timedelta(minutes=237)),
        ("REM", timedelta(minutes=109)),
        ("Awake", timedelta(minutes=15)),
    ]
    assert summary.asleep == timedelta(minutes=450)


@pytest.mark.parametrize(
    ("score", "expected"),
    [(100, "Excellent"), (90, "Excellent"), (89, "Good"), (80, "Good"), (79, "Fair"), (60, "Fair"), (59, "Poor"), (0, "Poor")],
)
def test_qualifier_falls_back_to_score_bucket(sleep_payload, score, expected):
    sleep_payload["dailySleepDTO"]["sleepScores"]["overall"] = {"value": score, "qualifierKey": ""}
    assert SleepSummary.from_payload(sleep_payload).qualifier == expected


def test_breakdown_percentages_are_of_time_asleep(make_summary):
    deep, light, rem, awake = make_summary().breakdown()
    assert (deep.percent, light.percent, rem.percent) == (17, 67, 17)
    assert awake.label == "Awake"


def test_as_record_is_compact(summary):
    assert summary.as_record() == {
        "score": 84,
        "qualifier": "Good",
        "stages_min": {"deep": 104, "light": 237, "rem": 109, "awake": 15},
        "wake": "06:32",
    }


def test_wake_time_is_local(summary):
    assert summary.wake_local == datetime(2026, 9, 2, 6, 32)


def test_no_wake_time_leaves_it_out_of_the_record(sleep_payload):
    del sleep_payload["dailySleepDTO"]["sleepEndTimestampLocal"]
    summary = SleepSummary.from_payload(sleep_payload)
    assert summary.wake_local is None
    assert "wake" not in summary.as_record()


def test_timeline_defaults_empty_without_sleep_levels(sleep_payload):
    del sleep_payload["sleepLevels"]
    summary = SleepSummary.from_payload(sleep_payload)
    assert summary.timeline == ()
    assert summary.start_local is None


def test_timeline_parses_spans_and_localises(summary):
    assert len(summary.timeline) == 17
    first, last = summary.timeline[0], summary.timeline[-1]
    assert (first.label, first.start, round(first.end * 60)) == ("Light", 0.0, 22)
    assert (last.label, round(last.end * 60)) == ("Awake", 465)
    assert summary.start_local == datetime(2026, 9, 1, 22, 47)


def test_timeline_merges_touching_same_stage_spans(sleep_payload):
    sleep_payload["sleepLevels"] = levels(("22:00", "22:30", 1.0), ("22:30", "23:00", 1.0))
    timeline = SleepSummary.from_payload(sleep_payload).timeline
    assert [(s.label, s.start, s.end) for s in timeline] == [("Light", 0.0, 1.0)]


def test_timeline_skips_unknown_levels_and_empty_spans(sleep_payload):
    sleep_payload["sleepLevels"] = levels(
        ("22:00", "22:00", 1.0), ("22:00", "22:30", 9.0), ("22:30", "23:00", 0.0)
    ) + [{"startGMT": "teatime", "endGMT": None, "activityLevel": 1.0}]
    timeline = SleepSummary.from_payload(sleep_payload).timeline
    assert [s.label for s in timeline] == ["Deep"]


@pytest.mark.parametrize(
    "payload",
    [{"dailySleepDTO": None}, {"dailySleepDTO": {"sleepScores": None}}, {}, None, []],
)
def test_not_synced_returns_none(payload):
    assert SleepSummary.from_payload(payload) is None
