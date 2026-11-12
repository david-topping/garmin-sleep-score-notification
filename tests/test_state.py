from datetime import date

import pytest

from garmin_sleep_score_notification.state import SentState

DAY = date(2026, 9, 2)
W = "wallace@westwallaby.co.uk"
G = "gromit@westwallaby.co.uk"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "sent_state.json"


def test_partial_then_complete(path):
    required = {W, G}

    state = SentState(path)
    assert not state.is_done("wallace", DAY, required)
    state.mark("wallace", DAY, {"score": 82}, W)
    state.save()

    reloaded = SentState(path)
    assert reloaded.sent_recipients("wallace", DAY) == {W}
    assert not reloaded.is_done("wallace", DAY, required)
    reloaded.mark("wallace", DAY, {"score": 82}, G)
    assert reloaded.is_done("wallace", DAY, required)


def test_no_recipients_is_never_done(path):
    assert not SentState(path).is_done("wallace", DAY, set())


def test_resets_next_day(path):
    state = SentState(path)
    state.mark("wallace", DAY, {"score": 82}, W)
    assert not state.is_done("wallace", date(2026, 9, 3), {W})


@pytest.mark.parametrize(("day", "kept"), [(date(2026, 8, 26), True), (date(2026, 8, 25), False)])
def test_keeps_seven_days(path, day, kept):
    state = SentState(path)
    state.mark("wallace", day, {"score": 50}, W)
    state.save()
    assert (SentState(path).sent_recipients("wallace", day) == {W}) is kept


def test_score_of_a_day(path):
    state = SentState(path)
    state.mark("wallace", DAY, {"score": 82}, W)
    assert state.score("wallace", DAY) == 82
    assert state.score("gromit", DAY) is None
    assert state.score("wallace", date(2026, 9, 1)) is None


def test_corrupt_file(path):
    path.write_text("{ not json")
    assert SentState(path).sent_recipients("wallace", DAY) == set()
