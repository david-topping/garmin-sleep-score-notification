from datetime import date, timedelta
from pathlib import Path

import pytest

from garmin_sleep_score_notification import notify
from garmin_sleep_score_notification.config import Config, Person, Recipient
from garmin_sleep_score_notification.garmin import GarminError, SleepSummary
from garmin_sleep_score_notification.whatsapp import WhatsAppError


def summary(score=82):
    z = timedelta()
    return SleepSummary(score, z, z, z, z)


def person(name, *phones):
    return Person(name, Path(f"/tokens/{name}"), tuple(Recipient(p, f"k{p}") for p in phones))


def config(tmp_path, *people):
    return Config(people=people, state_file=tmp_path / "state.json", timezone="UTC")


class FakeSender:
    def __init__(self, fail=()):
        self.sent = []
        self.fail = set(fail)

    def send(self, phone, apikey, message):
        self.sent.append(phone)
        if phone in self.fail:
            self.fail.discard(phone)
            raise WhatsAppError("temporary")


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
    cfg = config(tmp_path, person("alice", "+1", "+2"))

    assert notify.Notifier(cfg, sender).run() == 0
    assert sorted(sender.sent) == ["+1", "+2"]

    sender2 = FakeSender()
    assert notify.Notifier(cfg, sender2).run() == 0
    assert sender2.sent == []


def test_score_not_ready_retries(tmp_path, monkeypatch):
    scores = iter([None, summary(75)])
    set_fetch(monkeypatch, lambda ts, day: next(scores))
    cfg = config(tmp_path, person("alice", "+1"))

    sender = FakeSender()
    notify.Notifier(cfg, sender).run()
    assert sender.sent == []

    sender2 = FakeSender()
    notify.Notifier(cfg, sender2).run()
    assert sender2.sent == ["+1"]


def test_one_failure_does_not_block_others(tmp_path, monkeypatch):
    def fetch(ts, day):
        if ts == Path("/tokens/alice"):
            raise GarminError("expired")
        return summary(90)

    set_fetch(monkeypatch, fetch)
    sender = FakeSender()
    cfg = config(tmp_path, person("alice", "+1"), person("bob", "+2"))

    assert notify.Notifier(cfg, sender).run() == 1
    assert sender.sent == ["+2"]


def test_partial_send_failure_retries_only_failed(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(60))
    cfg = config(tmp_path, person("alice", "+1", "+2"))

    sender = FakeSender(fail=["+2"])
    assert notify.Notifier(cfg, sender).run() == 1
    assert sorted(sender.sent) == ["+1", "+2"]

    sender2 = FakeSender()
    assert notify.Notifier(cfg, sender2).run() == 0
    assert sender2.sent == ["+2"]


def test_message_has_score_and_stages(tmp_path):
    msg = notify.Notifier._message(person("alice", "+1"), summary(88), date(2026, 9, 2))
    assert "alice's Garmin sleep for Wed 02 Sep: 88/100" in msg
    assert "deep 0h00m" in msg


def test_dry_run_sends_nothing(tmp_path, monkeypatch):
    set_fetch(monkeypatch, lambda ts, day: summary(82))
    sender = FakeSender()
    cfg = config(tmp_path, person("alice", "+1"))
    assert notify.Notifier(cfg, sender).dry_run() == 0
    assert sender.sent == []
    assert not (tmp_path / "state.json").exists()
