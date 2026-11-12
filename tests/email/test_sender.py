import base64

import pytest
import requests
import responses
from responses import matchers

from garmin_sleep_score_notification.email import Attachment, EmailError, EmailSender

URL = "https://api.resend.com/emails"
FROM = "Sleep <sleep@westwallaby.co.uk>"
GROMIT = "gromit@westwallaby.co.uk"


@pytest.fixture
def sender():
    return EmailSender("re_wensleydale", FROM)


@responses.activate
def test_send_posts_to_resend(sender):
    responses.post(
        URL,
        json={"id": "cracker-1"},
        match=[
            matchers.header_matcher({"Authorization": "Bearer re_wensleydale"}),
            matchers.json_params_matcher(
                {"from": FROM, "to": GROMIT, "subject": "subj", "text": "body", "html": "<p>body</p>"}
            ),
        ],
    )
    sender.send(GROMIT, "subj", "body", "<p>body</p>")


@responses.activate
def test_send_with_inline_attachment(sender):
    png = b"\x89PNG\r\n\x1a\nwrong-trousers"
    responses.post(
        URL,
        match=[
            matchers.json_params_matcher(
                {
                    "attachments": [
                        {
                            "filename": "sleep-timeline.png",
                            "content": base64.b64encode(png).decode("ascii"),
                            "content_id": "sleep-timeline",
                        }
                    ]
                },
                strict_match=False,
            )
        ],
    )
    sender.send(GROMIT, "s", "b", '<img src="cid:sleep-timeline">', [Attachment("sleep-timeline.png", png, "sleep-timeline")])


def test_missing_api_key_never_calls_resend():
    with responses.RequestsMock() as rsps, pytest.raises(EmailError, match="RESEND_API_KEY"):
        EmailSender("", FROM).send(GROMIT, "s", "b", "h")
    assert len(rsps.calls) == 0


@pytest.mark.parametrize(
    "reply",
    [
        {"status": 422, "body": "invalid from address"},
        {"body": requests.ConnectionError("no route to Wigan")},
        {"body": requests.Timeout()},
    ],
)
@responses.activate
def test_failures_become_email_error(sender, reply):
    responses.post(URL, **reply)
    with pytest.raises(EmailError):
        sender.send(GROMIT, "s", "b", "h")
