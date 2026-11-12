import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from garmin_sleep_score_notification import notify
from garmin_sleep_score_notification.config import Config, Person, Recipient
from garmin_sleep_score_notification.email import EmailError
from garmin_sleep_score_notification.garmin import GarminError
from garmin_sleep_score_notification.state import SentState

WALLACE = "wallace@westwallaby.co.uk"
GROMIT = "gromit@westwallaby.co.uk"
TODAY = date(2026, 9, 2)


def person(name, *emails):
    return Person(name, Path(f"/tokens/{name}"), tuple(Recipient(e) for e in emails))


@pytest.fixture
def config(tmp_path):
    def make(*people, timezone="Europe/London"):
        return Config(
            people=people,
            state_file=tmp_path / "state.json",
            timezone=timezone,
            resend_api_key="re_wensleydale",
            email_from="sleep@westwallaby.co.uk",
        )

    return make


@pytest.fixture
def fetch(monkeypatch):
    def set_fetch(fn):
        class FakeFetcher:
            def __init__(self, token_store):
                self.token_store = token_store

            def fetch(self, day):
                return fn(self.token_store.name, day)

        monkeypatch.setattr(notify, "GarminFetcher", FakeFetcher)

    return set_fetch


class FakeSender:
    def __init__(self, fail=()):
        self.emails = []
        self.fail = set(fail)

    @property
    def sent(self):
        return [e["to"] for e in self.emails]

    def send(self, to, subject, text, html, attachments=()):
        self.emails.append({"to": to, "text": text, "attachments": attachments})
        if to in self.fail:
            self.fail.discard(to)
            raise EmailError("temporary")


class FakeMonitor:
    def __init__(self):
        self.pushes = []

    def up(self, msg):
        self.pushes.append(("up", msg))
        return True

    def down(self, msg):
        self.pushes.append(("down", msg))
        return True


def run(cfg, sender=None, monitor=None):
    sender = sender or FakeSender()
    monitor = monitor or FakeMonitor()
    code = notify.Notifier(cfg, sender, monitor).run()
    return code, sender, monitor


def test_fans_out_once_per_day(config, fetch, make_summary):
    fetch(lambda name, day: make_summary(82))
    cfg = config(person("wallace", WALLACE, GROMIT))

    code, sender, _ = run(cfg)
    assert code == 0
    assert sorted(sender.sent) == [GROMIT, WALLACE]

    _, again, _ = run(cfg)
    assert again.sent == []


def test_fetches_todays_date(config, fetch, make_summary):
    days = []
    fetch(lambda name, day: days.append(day) or make_summary())
    run(config(person("wallace", WALLACE)))
    assert days == [TODAY]


def test_score_not_ready_retries(config, fetch, make_summary):
    scores = iter([None, make_summary(75)])
    fetch(lambda name, day: next(scores))
    cfg = config(person("wallace", WALLACE))

    assert run(cfg)[1].sent == []
    assert run(cfg)[1].sent == [WALLACE]


def test_one_failure_does_not_block_others(config, fetch, make_summary):
    def fetcher(name, day):
        if name == "wallace":
            raise GarminError("expired")
        return make_summary(90)

    fetch(fetcher)
    code, sender, _ = run(config(person("wallace", WALLACE), person("gromit", GROMIT)))
    assert code == 1
    assert sender.sent == [GROMIT]


def test_partial_send_failure_retries_only_failed(config, fetch, make_summary):
    fetch(lambda name, day: make_summary(60))
    cfg = config(person("wallace", WALLACE, GROMIT))

    code, sender, _ = run(cfg, FakeSender(fail=[GROMIT]))
    assert code == 1
    assert sorted(sender.sent) == [GROMIT, WALLACE]

    code, sender, _ = run(cfg)
    assert code == 0
    assert sender.sent == [GROMIT]


def test_state_records_score_and_stage_minutes(config, fetch, make_summary, tmp_path):
    fetch(lambda name, day: make_summary(88))
    run(config(person("wallace", WALLACE)))

    saved = json.loads((tmp_path / "state.json").read_text())
    assert saved[TODAY.isoformat()]["wallace"] == {
        "score": 88,
        "qualifier": "Good",
        "stages_min": {"deep": 60, "light": 240, "rem": 60, "awake": 10},
        "recipients": [WALLACE],
    }


def test_email_compares_with_yesterdays_score(config, fetch, make_summary, tmp_path):
    state = SentState(tmp_path / "state.json")
    state.mark("wallace", date(2026, 9, 1), {"score": 79}, WALLACE)
    state.save()
    fetch(lambda name, day: make_summary(85))

    _, sender, _ = run(config(person("wallace", WALLACE)))
    assert "▲ 6 vs yesterday" in sender.emails[0]["text"]


def test_timeline_is_sent_as_an_inline_attachment(config, fetch, summary):
    fetch(lambda name, day: summary)
    _, sender, _ = run(config(person("wallace", WALLACE)))

    (attachment,) = sender.emails[0]["attachments"]
    assert attachment.content_id == "sleep-timeline"
    assert attachment.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_dry_run_sends_and_writes_nothing(config, fetch, make_summary, tmp_path):
    fetch(lambda name, day: make_summary(82))
    sender = FakeSender()
    assert notify.Notifier(config(person("wallace", WALLACE)), sender).dry_run() == 0
    assert sender.sent == []
    assert not (tmp_path / "state.json").exists()


def test_preview_writes_viewable_files(config, fetch, summary, tmp_path):
    fetch(lambda name, day: summary)
    out = tmp_path / "preview"
    notify.Notifier(config(person("wallace", WALLACE)), FakeSender()).dry_run(out)

    html = (out / "wallace.html").read_text()
    assert 'src="wallace-sleep-timeline.png"' in html
    assert "cid:" not in html
    assert (out / "wallace-sleep-timeline.png").read_bytes()[:4] == b"\x89PNG"
    assert "Score: 84/100 (Good)" in (out / "wallace.txt").read_text()
    assert not (tmp_path / "state.json").exists()


@pytest.mark.parametrize(
    ("now", "tz", "expected"),
    [
        (datetime(2026, 9, 1, 23, 30, tzinfo=timezone.utc), "Europe/London", date(2026, 9, 2)),
        (datetime(2026, 9, 1, 23, 30, tzinfo=timezone.utc), "UTC", date(2026, 9, 1)),
        (datetime(2026, 9, 2, 3, 0, tzinfo=timezone.utc), "America/Los_Angeles", date(2026, 9, 1)),
    ],
)
def test_today_follows_the_configured_timezone(config, time_machine, now, tz, expected):
    time_machine.move_to(now, tick=False)
    assert notify.Notifier(config(timezone=tz), FakeSender(), FakeMonitor())._today() == expected


def test_bad_timezone_falls_back_to_system_time(config, caplog):
    notifier = notify.Notifier(config(timezone="Wigan/Tottington_Hall"), FakeSender(), FakeMonitor())
    assert isinstance(notifier._today(), date)
    assert "bad TIMEZONE" in caplog.text


def test_pushes_up_on_every_healthy_run(config, fetch, make_summary):
    fetch(lambda name, day: make_summary(82))
    cfg = config(person("wallace", WALLACE), person("gromit", GROMIT))

    for _ in range(2):
        _, _, monitor = run(cfg)
        assert monitor.pushes == [("up", "ok, sent: wallace, gromit, waiting: -")]


def test_missing_score_is_still_healthy(config, fetch, make_summary):
    fetch(lambda name, day: make_summary(82) if name == "wallace" else None)
    code, _, monitor = run(config(person("wallace", WALLACE), person("gromit", GROMIT)))
    assert code == 0
    assert monitor.pushes == [("up", "ok, sent: wallace, waiting: gromit")]


def test_send_failure_skips_up_push(config, fetch, make_summary):
    fetch(lambda name, day: make_summary(82))
    code, _, monitor = run(config(person("wallace", WALLACE)), FakeSender(fail=[WALLACE]))
    assert code == 1
    assert monitor.pushes == []


def test_garmin_error_skips_all_pushes(config, fetch):
    def fetcher(name, day):
        raise GarminError("expired")

    fetch(fetcher)
    code, _, monitor = run(config(person("wallace", WALLACE)))
    assert code == 1
    assert monitor.pushes == []


def test_unexpected_error_pushes_down_without_details(config, fetch):
    def fetcher(name, day):
        raise RuntimeError("token=wensleydale-secret")

    fetch(fetcher)
    code, _, monitor = run(config(person("wallace", WALLACE)))
    assert code == 1
    assert monitor.pushes == [("down", "unexpected error: wallace: RuntimeError")]


def test_unreadable_state_pushes_down(config, fetch, make_summary, tmp_path):
    fetch(lambda name, day: make_summary(82))
    (tmp_path / "tea").write_text("")
    cfg = Config(**{**config(person("wallace", WALLACE)).__dict__, "state_file": tmp_path / "tea" / "state.json"})

    code, _, monitor = run(cfg)
    assert code == 1
    assert monitor.pushes == [("down", "run failed: NotADirectoryError")]


def test_cli_config_error_exits_2(tmp_path):
    assert notify.main(["--people-file", str(tmp_path / "missing.yaml")]) == 2
