from garmin_sleep_score_notification.avatar import avatar_png


def test_avatar_is_a_png():
    png = avatar_png(64)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_avatar_size_is_configurable():
    from io import BytesIO

    from PIL import Image

    img = Image.open(BytesIO(avatar_png(64)))
    assert img.size == (64, 64)
