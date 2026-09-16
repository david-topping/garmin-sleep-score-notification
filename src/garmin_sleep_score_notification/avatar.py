from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

_BG = "#5b8def"
_MOON = "#ffffff"


def avatar_png(size: int = 256) -> bytes:
    img = Image.new("RGB", (size, size), _BG)
    d = ImageDraw.Draw(img)
    r = size * 0.32
    cx, cy = size / 2, size / 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=_MOON)
    offset = r * 0.55
    d.ellipse((cx - r + offset, cy - r, cx + r + offset, cy + r), fill=_BG)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
