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


def test_html_references_inline_chart_and_total():
    html = EMAIL.html
    assert f'src="cid:{SleepEmail.CHART_CID}"' in html
    assert "Total sleep" in html and "6h 00m" in html
    assert "Wallace" in html and "88" in html and "Good" in html and "REM" in html


def test_chart_url_is_quickchart_doughnut():
    url = EMAIL.chart_url
    assert url.startswith("https://quickchart.io/chart?")
    assert "doughnut" in url
    # minutes for deep, light, rem (awake excluded)
    assert "60%2C240%2C60" in url
    # centre label is total sleep, per-segment value labels are off
    assert "6h%2000m" in url
    assert "datalabels%3A%7Bdisplay%3Afalse%7D" in url
