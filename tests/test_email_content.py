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


def test_html_has_no_external_resources():
    html = EMAIL.html
    assert html.startswith("<!DOCTYPE html>")
    assert "<img" not in html and "src=" not in html and "url(" not in html
    assert "https://" not in html  # xmlns is http://www.w3.org/..., not a fetched resource
    assert "Wallace" in html and "88" in html and "Good" in html and "REM" in html


def test_html_forces_light_scheme():
    assert 'name="color-scheme" content="light only"' in EMAIL.html


def test_html_has_inline_svg_donut_and_total():
    html = EMAIL.html
    assert "<svg" in html
    assert "TOTAL SLEEP" in html and "6h 00m" in html
    # one sector path per non-awake stage
    assert html.count("<path") == 3


def test_donut_sectors_are_contiguous_and_cover_the_circle():
    import re

    svg = EMAIL._donut_svg()
    # each sector starts with "M x y" on the outer radius; the first sector starts at
    # the top (x == 60) and the sectors chain end-to-start around the circle
    starts = re.findall(r'd="M ([\d.]+) ([\d.]+) A 52', svg)
    assert len(starts) == 3
    assert abs(float(starts[0][0]) - 60) < 0.01  # first sector begins at 12 o'clock
