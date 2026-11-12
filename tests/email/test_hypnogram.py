from datetime import datetime
from io import BytesIO

import pytest
from PIL import Image

from garmin_sleep_score_notification.email.content import STAGE_COLOUR
from garmin_sleep_score_notification.email.hypnogram import Hypnogram
from garmin_sleep_score_notification.garmin import StageSpan


@pytest.mark.parametrize("start", [datetime(2026, 9, 1, 23, 0), None])
def test_png_is_a_wide_strip(spans, start):
    png = Hypnogram(spans, STAGE_COLOUR, start).png()
    img = Image.open(BytesIO(png))
    assert img.format == "PNG"
    assert img.size == (896, 300)


def test_stages_are_drawn_in_their_colours(spans):
    img = Image.open(BytesIO(Hypnogram(spans, STAGE_COLOUR).png())).convert("RGB")
    colours = {"#%02x%02x%02x" % rgb for _, rgb in img.getcolors(maxcolors=100_000)}
    assert set(STAGE_COLOUR.values()) <= colours


@pytest.mark.parametrize("spans", [(), (StageSpan("Deep", 0.0, 0.0),)])
def test_empty_timeline_returns_none(spans):
    assert Hypnogram(spans, STAGE_COLOUR).png() is None
