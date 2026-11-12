import re
from datetime import date

import pytest

from garmin_sleep_score_notification.email import SleepEmail

DAY = date(2026, 9, 2)


@pytest.fixture
def email(summary):
    return SleepEmail("wallace", DAY, summary, previous_score=78)


@pytest.fixture
def plain_email(make_summary):
    return SleepEmail("wallace", DAY, make_summary(88))


def test_subject(plain_email):
    assert plain_email.subject == "Wallace's Sleep Score 88/100 02/09/26"


def test_text(email, snapshot):
    assert email.text == snapshot


def test_text_without_previous_score(plain_email, snapshot):
    assert plain_email.text == snapshot


def test_html(email, snapshot):
    assert email.html == snapshot


@pytest.mark.parametrize(
    ("previous", "expected"),
    [(78, "▲ 6 vs yesterday"), (90, "▼ 6 vs yesterday"), (84, "Same as yesterday")],
)
def test_change_vs_yesterday(summary, previous, expected):
    email = SleepEmail("wallace", DAY, summary, previous)
    assert expected in email.text
    assert expected in email.html


def test_no_previous_score_means_no_comparison(plain_email):
    assert "yesterday" not in plain_email.text
    assert "yesterday" not in plain_email.html


def test_html_makes_no_external_requests(email):
    urls = set(re.findall(r"""(?:https?:)?//[^\s"'<>)]+""", email.html))
    assert urls <= {"http://www.w3.org/1999/xhtml"}  # xmlns, never fetched
    assert "url(" not in email.html


def test_html_escapes_the_name(summary):
    email = SleepEmail("<b>feathers</b>", DAY, summary)
    assert "<b>feathers" not in email.html.lower()
    assert "&lt;b&gt;feathers" in email.html.lower()


def test_html_forces_light_scheme(email):
    assert 'name="color-scheme" content="light only"' in email.html


def test_timeline_is_a_cid_image_with_matching_attachment(email):
    assert 'src="cid:sleep-timeline"' in email.html
    assert 'alt="Sleep stage timeline: Deep 1h 44m, Light 3h 57m, REM 1h 49m, Awake 0h 15m"' in email.html

    (attachment,) = email.attachments
    assert attachment.filename == "sleep-timeline.png"
    assert attachment.content_id == "sleep-timeline"
    assert attachment.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_no_timeline_means_no_image_and_no_attachment(plain_email):
    assert "<img" not in plain_email.html
    assert plain_email.attachments == []
