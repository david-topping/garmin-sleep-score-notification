from datetime import timedelta
from pathlib import Path

from garmin_sleep_score_notification import notify
from garmin_sleep_score_notification.config import Config, Person, Recipient
from garmin_sleep_score_notification.garmin import GarminError, SleepSummary, StageSpan
from garmin_sleep_score_notification.mailer import EmailError

WALLACE = "wallace@westwallaby.co.uk"
GROMIT = "gromit@westwallaby.co.uk"


def summary(score=82):
    h = timedelta(hours=1)
    return SleepSummary(score, "Good", h, 4 * h, h, timedelta(minutes=10))


def person(name, *emails):
    return Person(name, Path(f"/tokens/{name}"), tuple(Recipient(e) for e in emails))


def config(tmp_path, *people):
    return Config(
        people=people,
        state_file=tmp_path / "state.json",
        timezone="Europe/London",
        resend_api_key="re_test",
        email_from="sleep@westwallaby.co.uk",
    )


class FakeSender:
    def __init__(self, fail=()):
        self.sent = []
        self.fail = set(fail)

    def send(self, to, subject, text, html, attachments=()):
        self.sent.append(to)
        self.last_attachments = attachments
        if to in self.fail:
            self.fail.discard(to)
            raise EmailError("temporary")


def set_fetch(monkeypatch, fn):
    class FakeFetcher:
        def __init__(self, token_store):
            self.token_store = token_store

        def fetch(self, day):
            return fn(self.token_store, day)

    monkeypatch.setattr(notify, "GarminFetcher", FakeFetcher)


def test_fans_out_and_records(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(82))
    sender = FakeSender()
    cfg = config(tmp_path, person("wallace", WALLACE, GROMIT))

    assert notify.Notifier(cfg, sender).run() == 0
    assert sorted(sender.sent) == sorted([WALLACE, GROMIT])

    sender2 = FakeSender()
    assert notify.Notifier(cfg, sender2).run() == 0
    assert sender2.sent == []


def test_score_not_ready_retries(tmp_path, monkeypatch):
    scores = iter([None, summary(75)])
    set_fetch(monkeypatch, lambda ts, day: next(scores))
    cfg = config(tmp_path, person("wallace", WALLACE))

    notify.Notifier(cfg, FakeSender()).run()

    sender = FakeSender()
    notify.Notifier(cfg, sender).run()
    assert sender.sent == [WALLACE]


def test_one_failure_does_not_block_others(tmp_path, monkeypatch):
    def fetch(ts, day):
        if ts == Path("/tokens/wallace"):
            raise GarminError("expired")
        return summary(90)

    set_fetch(monkeypatch, fetch)
    sender = FakeSender()
    cfg = config(tmp_path, person("wallace", WALLACE), person("gromit", GROMIT))

    assert notify.Notifier(cfg, sender).run() == 1
    assert sender.sent == [GROMIT]


def test_partial_send_failure_retries_only_failed(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(60))
    cfg = config(tmp_path, person("wallace", WALLACE, GROMIT))

    sender = FakeSender(fail=[GROMIT])
    assert notify.Notifier(cfg, sender).run() == 1
    assert sorted(sender.sent) == sorted([WALLACE, GROMIT])

    sender2 = FakeSender()
    assert notify.Notifier(cfg, sender2).run() == 0
    assert sender2.sent == [GROMIT]


def test_state_records_score_and_stage_minutes(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(88))
    cfg = config(tmp_path, person("wallace", WALLACE))
    notify.Notifier(cfg, FakeSender()).run()

    import json

    saved = json.loads((tmp_path / "state.json").read_text())
    record = next(iter(saved.values()))["wallace"]
    assert record["score"] == 88
    assert record["stages_min"] == {"deep": 60, "light": 240, "rem": 60, "awake": 10}
    assert record["recipients"] == [WALLACE]


def test_timeline_is_sent_as_an_inline_attachment(tmp_path, monkeypatch):
    h = timedelta(hours=1)
    with_timeline = SleepSummary(
        80, "Good", h, 4 * h, h, timedelta(minutes=10),
        (StageSpan("Light", 0.0, 0.7), StageSpan("Deep", 0.7, 1.7)),
    )
    set_fetch(monkeypatch, lambda ts, day: with_timeline)
    sender = FakeSender()
    cfg = config(tmp_path, person("wallace", WALLACE))

    notify.Notifier(cfg, sender).run()

    (attachment,) = sender.last_attachments
    assert attachment.content_id == "sleep-timeline"
    assert attachment.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_dry_run_sends_nothing(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(82))
    sender = FakeSender()
    cfg = config(tmp_path, person("wallace", WALLACE))
    assert notify.Notifier(cfg, sender).dry_run() == 0
    assert sender.sent == []
    assert not (tmp_path / "state.json").exists()


class FakeMonitor:
    def __init__(self, ok=True):
        self.pushes = []
        self.ok = ok

    def up(self, msg):
        self.pushes.append(("up", msg))
        return self.ok

    def down(self, msg):
        self.pushes.append(("down", msg))
        return self.ok


def test_pushes_up_once_when_everyone_is_sent(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(82))
    cfg = config(tmp_path, person("wallace", WALLACE), person("gromit", GROMIT))

    monitor = FakeMonitor()
    notify.Notifier(cfg, FakeSender(), monitor).run()
    ((status, msg),) = monitor.pushes
    assert status == "up"
    assert "wallace, gromit" in msg

    monitor2 = FakeMonitor()
    notify.Notifier(cfg, FakeSender(), monitor2).run()
    assert monitor2.pushes == []


def test_no_up_push_while_someone_is_pending(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(82) if "wallace" in str(ts) else None)
    cfg = config(tmp_path, person("wallace", WALLACE), person("gromit", GROMIT))

    monitor = FakeMonitor()
    notify.Notifier(cfg, FakeSender(), monitor).run()
    assert monitor.pushes == []


def test_failed_up_push_is_retried_next_run(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(82))
    cfg = config(tmp_path, person("wallace", WALLACE))

    notify.Notifier(cfg, FakeSender(), FakeMonitor(ok=False)).run()

    monitor = FakeMonitor()
    notify.Notifier(cfg, FakeSender(), monitor).run()
    assert [s for s, _ in monitor.pushes] == ["up"]


def test_unexpected_error_pushes_down_without_details(tmp_path, monkeypatch):
    def fetch(ts, day):
        raise RuntimeError("token=wensleydale-secret")

    set_fetch(monkeypatch, fetch)
    cfg = config(tmp_path, person("wallace", WALLACE))

    monitor = FakeMonitor()
    assert notify.Notifier(cfg, FakeSender(), monitor).run() == 1
    assert monitor.pushes == [("down", "unexpected error: wallace: RuntimeError")]


def test_garmin_error_is_retried_without_down_push(tmp_path, monkeypatch):
    def fetch(ts, day):
        raise GarminError("expired")

    set_fetch(monkeypatch, fetch)
    cfg = config(tmp_path, person("wallace", WALLACE))

    monitor = FakeMonitor()
    assert notify.Notifier(cfg, FakeSender(), monitor).run() == 1
    assert monitor.pushes == []


def test_unreadable_state_pushes_down(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(82))
    (tmp_path / "tea").write_text("")
    cfg = config(tmp_path, person("wallace", WALLACE))
    cfg = Config(**{**cfg.__dict__, "state_file": tmp_path / "tea" / "state.json"})

    monitor = FakeMonitor()
    assert notify.Notifier(cfg, FakeSender(), monitor).run() == 1
    assert monitor.pushes == [("down", "run failed: NotADirectoryError")]
