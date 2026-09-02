from datetime import date

from garmin_sleep_score_notification.state import SentState

DAY = date(2026, 9, 2)


def test_partial_then_complete(tmp_path):
    path = tmp_path / "s.json"
    required = {"+1", "+2"}

    state = SentState(path)
    assert not state.is_done("alice", DAY, required)
    state.mark("alice", DAY, 82, "+1")
    state.save()

    reloaded = SentState(path)
    assert reloaded.sent_recipients("alice", DAY) == {"+1"}
    assert not reloaded.is_done("alice", DAY, required)
    reloaded.mark("alice", DAY, 82, "+2")
    assert reloaded.is_done("alice", DAY, required)


def test_resets_next_day(tmp_path):
    state = SentState(tmp_path / "s.json")
    state.mark("alice", DAY, 82, "+1")
    assert not state.is_done("alice", date(2026, 9, 3), {"+1"})


def test_prunes_old_days(tmp_path):
    path = tmp_path / "s.json"
    state = SentState(path)
    state.mark("alice", date(2020, 1, 1), 50, "+1")
    state.mark("alice", DAY, 82, "+1")
    state.save()
    assert SentState(path).sent_recipients("alice", date(2020, 1, 1)) == set()


def test_corrupt_file(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{ not json")
    assert SentState(path).sent_recipients("alice", DAY) == set()
