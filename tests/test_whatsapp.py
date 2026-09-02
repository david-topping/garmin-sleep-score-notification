import pytest

from garmin_sleep_score_notification import whatsapp
from garmin_sleep_score_notification.whatsapp import WhatsAppError, WhatsAppSender


class FakeResp:
    def __init__(self, status_code=200, text="Message queued."):
        self.status_code = status_code
        self.text = text


def test_send_ok(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        whatsapp.requests,
        "get",
        lambda url, params, timeout: seen.update(params) or FakeResp(),
    )
    WhatsAppSender().send("+1", "key", "hi")
    assert seen == {"phone": "+1", "text": "hi", "apikey": "key"}


def test_bad_apikey(monkeypatch):
    monkeypatch.setattr(
        whatsapp.requests, "get", lambda url, params, timeout: FakeResp(text="ApiKey not valid")
    )
    with pytest.raises(WhatsAppError):
        WhatsAppSender().send("+1", "bad", "hi")


def test_http_error(monkeypatch):
    monkeypatch.setattr(
        whatsapp.requests, "get", lambda url, params, timeout: FakeResp(500, "oops")
    )
    with pytest.raises(WhatsAppError):
        WhatsAppSender().send("+1", "key", "hi")


def test_network_error(monkeypatch):
    def boom(url, params, timeout):
        raise whatsapp.requests.RequestException("no route")

    monkeypatch.setattr(whatsapp.requests, "get", boom)
    with pytest.raises(WhatsAppError):
        WhatsAppSender().send("+1", "key", "hi")
