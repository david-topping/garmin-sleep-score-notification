from datetime import datetime
from io import BytesIO

from PIL import Image

from garmin_sleep_score_notification.email_content import _STAGE_COLOUR
from garmin_sleep_score_notification.garmin import StageSpan
from garmin_sleep_score_notification.hypnogram import Hypnogram

SPANS = (
    StageSpan("Light", 0.0, 0.7),
    StageSpan("Deep", 0.7, 1.7),
    StageSpan("Light", 1.7, 3.2),
    StageSpan("REM", 3.2, 3.7),
    StageSpan("Awake", 3.7, 3.9),
)


def test_png_is_a_valid_image():
    png = Hypnogram(SPANS, _STAGE_COLOUR, datetime(2026, 9, 1, 23, 0)).png()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    img = Image.open(BytesIO(png))
    assert img.format == "PNG"
    assert img.width > img.height  # a wide timeline strip


def test_png_renders_without_a_start_time():
    assert Hypnogram(SPANS, _STAGE_COLOUR).png()[:8] == b"\x89PNG\r\n\x1a\n"


def test_empty_timeline_returns_none():
    assert Hypnogram((), _STAGE_COLOUR).png() is None
    assert Hypnogram((StageSpan("Deep", 0.0, 0.0),), _STAGE_COLOUR).png() is None
