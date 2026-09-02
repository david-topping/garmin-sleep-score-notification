from datetime import date, timedelta
from pathlib import Path

from garmin_sleep_score_notification import notify
from garmin_sleep_score_notification.config import Config, Person, Recipient
from garmin_sleep_score_notification.garmin import GarminError, SleepSummary
from garmin_sleep_score_notification.mailer import EmailError

WALLACE = "wallace@westwallaby.co.uk"
GROMIT = "gromit@westwallaby.co.uk"


def summary(score=82):
    z = timedelta()
    return SleepSummary(score, z, z, z, z)


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

    def send(self, to, subject, body):
        self.sent.append(to)
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


def test_message_has_score_and_stages():
    p = person("wallace", WALLACE)
    assert notify.Notifier._subject(p, summary(88)) == "wallace's Garmin sleep score: 88/100"
    body = notify.Notifier._body(p, summary(88), date(2026, 9, 2))
    assert "Wed 02 Sep" in body
    assert "Score: 88/100" in body
    assert "deep 0h00m" in body


def test_dry_run_sends_nothing(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(82))
    sender = FakeSender()
    cfg = config(tmp_path, person("wallace", WALLACE))
    assert notify.Notifier(cfg, sender).dry_run() == 0
    assert sender.sent == []
    assert not (tmp_path / "state.json").exists()
