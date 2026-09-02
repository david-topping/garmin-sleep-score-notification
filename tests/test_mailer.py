import pytest

from garmin_sleep_score_notification import mailer
from garmin_sleep_score_notification.mailer import EmailError, EmailSender


class FakeResp:
    def __init__(self, status_code=200, text='{"id": "abc"}'):
        self.status_code = status_code
        self.text = text


def test_send_ok(monkeypatch):
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json)
        return FakeResp()

    monkeypatch.setattr(mailer.requests, "post", fake_post)
    EmailSender("re_key", "Sleep <sleep@westwallaby.co.uk>").send(
        "gromit@westwallaby.co.uk", "subj", "body", "<p>body</p>"
    )

    assert seen["url"] == "https://api.resend.com/emails"
    assert seen["headers"] == {"Authorization": "Bearer re_key"}
    assert seen["json"] == {
        "from": "Sleep <sleep@westwallaby.co.uk>",
        "to": "gromit@westwallaby.co.uk",
        "subject": "subj",
        "text": "body",
        "html": "<p>body</p>",
    }


def test_inline_image_becomes_attachment(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mailer.requests,
        "post",
        lambda url, headers, json, timeout: seen.update(json=json) or FakeResp(),
    )
    EmailSender("re_key", "s@x.co.uk").send(
        "g@x.co.uk", "subj", "t", "<p>h</p>", ("sleepring", b"\x89PNG")
    )
    att = seen["json"]["attachments"][0]
    assert att["content_id"] == "sleepring"
    assert att["filename"] == "sleepring.png"
    assert base64_ok(att["content"], b"\x89PNG")


def base64_ok(encoded, raw):
    import base64

    return base64.b64decode(encoded) == raw


def test_missing_api_key(monkeypatch):
    monkeypatch.setattr(mailer.requests, "post", lambda **_: FakeResp())
    with pytest.raises(EmailError):
        EmailSender("", "sleep@westwallaby.co.uk").send("gromit@westwallaby.co.uk", "s", "b", "h")


def test_http_error(monkeypatch):
    monkeypatch.setattr(
        mailer.requests, "post", lambda url, headers, json, timeout: FakeResp(422, "bad")
    )
    with pytest.raises(EmailError):
        EmailSender("re_key", "sleep@westwallaby.co.uk").send("g@x.co.uk", "s", "b", "h")


def test_network_error(monkeypatch):
    def boom(url, headers, json, timeout):
        raise mailer.requests.RequestException("no route")

    monkeypatch.setattr(mailer.requests, "post", boom)
    with pytest.raises(EmailError):
        EmailSender("re_key", "sleep@westwallaby.co.uk").send("g@x.co.uk", "s", "b", "h")
