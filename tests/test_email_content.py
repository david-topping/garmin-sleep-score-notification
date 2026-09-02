from datetime import date, timedelta

from garmin_sleep_score_notification.email_content import SleepEmail
from garmin_sleep_score_notification.garmin import SleepSummary

SUMMARY = SleepSummary(
    88, "Good", timedelta(hours=1), timedelta(hours=4), timedelta(hours=1), timedelta(minutes=18)
)
EMAIL = SleepEmail("wallace", date(2026, 9, 2), SUMMARY)


def test_subject():
    assert EMAIL.subject == "wallace sleep score 88 02/09/26"


def test_text_has_score_and_stages():
    assert "Score: 88/100 (Good)" in EMAIL.text
    assert "Deep" in EMAIL.text and "1h 00m" in EMAIL.text


def test_html_is_self_contained():
    html = EMAIL.html
    assert html.startswith("<div")
    assert "http://" not in html and "https://" not in html
    assert "88" in html and "Good" in html and "REM" in html
