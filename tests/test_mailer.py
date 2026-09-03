import base64

import pytest

from garmin_sleep_score_notification import mailer
from garmin_sleep_score_notification.email_content import Attachment
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


def test_send_with_inline_attachment(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mailer.requests,
        "post",
        lambda url, headers, json, timeout: seen.update(json=json) or FakeResp(),
    )
    EmailSender("re_key", "sleep@westwallaby.co.uk").send(
        "gromit@westwallaby.co.uk",
        "subj",
        "body",
        '<img src="cid:sleep-timeline">',
        [Attachment("sleep-timeline.png", b"\x89PNG...", "sleep-timeline")],
    )
    assert seen["json"]["attachments"] == [
        {
            "filename": "sleep-timeline.png",
            "content": base64.b64encode(b"\x89PNG...").decode("ascii"),
            "content_id": "sleep-timeline",
        }
    ]


def test_no_attachments_key_when_none_given(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        mailer.requests,
        "post",
        lambda url, headers, json, timeout: seen.update(json=json) or FakeResp(),
    )
    EmailSender("re_key", "s@x.co").send("g@x.co", "s", "b", "h")
    assert "attachments" not in seen["json"]


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
