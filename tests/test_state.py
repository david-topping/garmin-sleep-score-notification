from datetime import date

from garmin_sleep_score_notification.state import SentState

DAY = date(2026, 9, 2)
W = "wallace@westwallaby.co.uk"
G = "gromit@westwallaby.co.uk"


def test_partial_then_complete(tmp_path):
    path = tmp_path / "s.json"
    required = {W, G}

    state = SentState(path)
    assert not state.is_done("wallace", DAY, required)
    state.mark("wallace", DAY, 82, W)
    state.save()

    reloaded = SentState(path)
    assert reloaded.sent_recipients("wallace", DAY) == {W}
    assert not reloaded.is_done("wallace", DAY, required)
    reloaded.mark("wallace", DAY, 82, G)
    assert reloaded.is_done("wallace", DAY, required)


def test_resets_next_day(tmp_path):
    state = SentState(tmp_path / "s.json")
    state.mark("wallace", DAY, 82, W)
    assert not state.is_done("wallace", date(2026, 9, 3), {W})


def test_prunes_old_days(tmp_path):
    path = tmp_path / "s.json"
    state = SentState(path)
    state.mark("wallace", date(2020, 1, 1), 50, W)
    state.mark("wallace", DAY, 82, W)
    state.save()
    assert SentState(path).sent_recipients("wallace", date(2020, 1, 1)) == set()


def test_corrupt_file(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{ not json")
    assert SentState(path).sent_recipients("wallace", DAY) == set()
