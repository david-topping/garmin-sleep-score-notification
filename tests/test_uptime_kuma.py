import pytest
import requests
import responses
from responses import matchers

from garmin_sleep_score_notification.uptime_kuma import UptimeKuma

PUSH = "https://status.westwallaby.co.uk/api/push/AntiPesto42"
COPIED_URL = PUSH + "?status=up&msg=OK&ping="


def test_no_url_skips_push():
    with responses.RequestsMock() as rsps:
        assert UptimeKuma(None).up("sent wallace") is False
    assert len(rsps.calls) == 0


@pytest.mark.parametrize("status", ["up", "down"])
@responses.activate
def test_replaces_query_from_copied_url(status):
    responses.get(PUSH, match=[matchers.query_param_matcher({"status": status, "msg": "wallace: KeyError"})])
    kuma = UptimeKuma(COPIED_URL)
    assert getattr(kuma, status)("wallace: KeyError") is True


@responses.activate
def test_message_is_truncated():
    responses.get(PUSH, match=[matchers.query_param_matcher({"status": "up", "msg": "t" * 200})])
    assert UptimeKuma(PUSH).up("t" * 500) is True


@responses.activate
def test_timeout_is_short():
    responses.get(PUSH, match=[matchers.request_kwargs_matcher({"timeout": 10})])
    assert UptimeKuma(PUSH).up("ok") is True


@pytest.mark.parametrize(
    "reply",
    [{"body": requests.ConnectionError(COPIED_URL)}, {"status": 500, "body": COPIED_URL}],
)
@responses.activate
def test_failure_is_swallowed_and_token_not_logged(caplog, reply):
    responses.get(PUSH, **reply)
    assert UptimeKuma(COPIED_URL).up("sent gromit") is False
    assert "AntiPesto42" not in caplog.text
    assert "push failed" in caplog.text
