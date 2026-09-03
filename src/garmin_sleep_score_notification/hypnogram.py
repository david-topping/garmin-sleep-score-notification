from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from .garmin import StageSpan

_ORDER = ("Awake", "REM", "Light", "Deep")  # top to bottom, Garmin's order
_S = 2  # supersample for crisp rendering on retina clients
_W, _H = 404 * _S, 150 * _S
_PAD_L, _PAD_R, _PAD_T, _PAD_B = 44 * _S, 4 * _S, 8 * _S, 20 * _S
_GRID, _STEP, _LABEL = "#eceef2", "#aeb4c0", "#7b8394"


class Hypnogram:
    """Sleep-stage timeline as a PNG. Stage colours in from the caller, bytes out.
    No images, no external requests."""

    def __init__(
        self,
        spans: tuple[StageSpan, ...],
        colours: dict[str, str],
        start: datetime | None = None,
    ) -> None:
        self.spans = spans
        self.colours = colours
        self.start = start

    def png(self) -> bytes | None:
        total = max((s.end for s in self.spans), default=0.0)
        if not self.spans or total <= 0:
            return None

        img = Image.new("RGB", (_W, _H), "#ffffff")
        d = ImageDraw.Draw(img)
        font = ImageFont.load_default(9 * _S)
        plot_h = _H - _PAD_T - _PAD_B
        row_h = plot_h / len(_ORDER)

        def x(hours: float) -> float:
            return _PAD_L + (_W - _PAD_L - _PAD_R) * hours / total

        def mid(label: str) -> float:
            return _PAD_T + (_ORDER.index(label) + 0.5) * row_h

        for label in _ORDER:
            d.text((3 * _S, mid(label)), label, font=font, fill=_LABEL, anchor="lm")

        for offset, text in self._ticks(total):
            tx = x(offset)
            d.line((tx, _PAD_T, tx, _PAD_T + plot_h), fill=_GRID, width=_S)
            d.text((tx, _PAD_T + plot_h + 3 * _S), text, font=font, fill=_LABEL, anchor="mt")

        for a, b in zip(self.spans, self.spans[1:]):
            bx = x(b.start)
            d.line((bx, mid(a.label), bx, mid(b.label)), fill=_STEP, width=_S)

        r = 3 * _S
        for s in self.spans:
            x0, x1 = x(s.start), x(s.end)
            y0, y1 = mid(s.label) - row_h * 0.29, mid(s.label) + row_h * 0.29
            box = (x0, y0, max(x1, x0 + _S), y1)
            if x1 - x0 < 2 * r:
                d.rectangle(box, fill=self.colours[s.label])
            else:
                d.rounded_rectangle(box, radius=r, fill=self.colours[s.label])

        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _ticks(self, total: float) -> list[tuple[float, str]]:
        if self.start is None:
            return [(float(h), f"{h}h") for h in range(int(total) + 1)]
        ticks: list[tuple[float, str]] = []
        t = (self.start + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        while (offset := (t - self.start).total_seconds() / 3600) <= total:
            ticks.append((offset, f"{t:%I%p}".lstrip("0").lower()))
            t += timedelta(hours=1)
        return ticks
