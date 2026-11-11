import requests

from garmin_sleep_score_notification import uptime_kuma
from garmin_sleep_score_notification.uptime_kuma import UptimeKuma

PUSH_URL = "https://status.westwallaby.co.uk/api/push/AntiPesto42?status=up&msg=OK&ping="


class FakeGet:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def __call__(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        if self.error:
            raise self.error
        return self

    def raise_for_status(self):
        pass


def test_no_url_skips_push(monkeypatch):
    get = FakeGet()
    monkeypatch.setattr(uptime_kuma.requests, "get", get)
    assert UptimeKuma(None).up("sent wallace") is False
    assert get.calls == []


def test_replaces_query_from_copied_url(monkeypatch):
    get = FakeGet()
    monkeypatch.setattr(uptime_kuma.requests, "get", get)

    assert UptimeKuma(PUSH_URL).down("wallace: KeyError") is True

    ((url, params, timeout),) = get.calls
    assert url == "https://status.westwallaby.co.uk/api/push/AntiPesto42"
    assert params == {"status": "down", "msg": "wallace: KeyError"}
    assert timeout <= 10


def test_failure_is_swallowed_and_token_not_logged(monkeypatch, caplog):
    get = FakeGet(error=requests.ConnectionError(PUSH_URL))
    monkeypatch.setattr(uptime_kuma.requests, "get", get)

    assert UptimeKuma(PUSH_URL).up("sent gromit") is False
    assert "AntiPesto42" not in caplog.text
    assert "ConnectionError" in caplog.text
