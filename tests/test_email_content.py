from datetime import date, timedelta

from garmin_sleep_score_notification.email_content import SleepEmail
from garmin_sleep_score_notification.garmin import SleepSummary

SUMMARY = SleepSummary(
    88, "Good", timedelta(hours=1), timedelta(hours=4), timedelta(hours=1), timedelta(minutes=18)
)
EMAIL = SleepEmail("wallace", date(2026, 9, 2), SUMMARY)


def test_subject():
    assert EMAIL.subject == "Wallace's Sleep Score 88/100 02/09/26"


def test_text_has_score_and_stages():
    assert "Wallace's Garmin sleep" in EMAIL.text
    assert "Score: 88/100 (Good)" in EMAIL.text
    assert "Total sleep: 6h 00m" in EMAIL.text
    assert "Deep" in EMAIL.text and "1h 00m" in EMAIL.text


def test_html_is_self_contained():
    html = EMAIL.html
    assert html.startswith("<div")
    assert "http://" not in html and "https://" not in html
    assert "Wallace" in html and "88" in html and "Good" in html and "REM" in html


def test_html_has_ring_and_total_sleep():
    html = EMAIL.html
    assert "conic-gradient(" in html
    assert "Total sleep" in html and "6h 00m" in html


def test_ring_gradient_is_cumulative_and_full():
    # deep 1h, light 4h, rem 1h -> asleep 6h -> 16.7 / 66.7 / 16.7, ending at 100
    gradient = EMAIL._ring_gradient()
    assert gradient.startswith("#")
    assert gradient.strip().endswith("100.0%")
