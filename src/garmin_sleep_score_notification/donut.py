from __future__ import annotations

import math

_OUTER, _INNER = 52.0, 34.0


class Donut:
    """Inline-SVG donut chart with centred text. No images, no external requests."""

    def __init__(self, segments: list[tuple[str, float]], title: str, subtitle: str) -> None:
        self.segments = segments  # (colour, fraction of the ring) in draw order
        self.title = title
        self.subtitle = subtitle

    def svg(self) -> str:
        sectors, angle = [], 0.0
        for colour, frac in self.segments:
            sweep = min(frac * 360, 359.99)
            if sweep > 0.5:
                sectors.append(self._sector(colour, angle, angle + sweep))
            angle += frac * 360
        return (
            '<svg width="180" height="180" viewBox="0 0 120 120" '
            'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Sleep stage breakdown">'
            f'{"".join(sectors)}'
            f'<text x="60" y="58" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="15" font-weight="bold" fill="#2b303b">{self.title}</text>'
            f'<text x="60" y="71" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="7" letter-spacing="0.5" fill="#7b8394">{self.subtitle}</text>'
            "</svg>"
        )

    def _sector(self, colour: str, start: float, end: float) -> str:
        large = 1 if end - start > 180 else 0
        d = (
            f"M {self._point(_OUTER, start)} "
            f"A {_OUTER} {_OUTER} 0 {large} 1 {self._point(_OUTER, end)} "
            f"L {self._point(_INNER, end)} "
            f"A {_INNER} {_INNER} 0 {large} 0 {self._point(_INNER, start)} Z"
        )
        return f'<path d="{d}" fill="{colour}" stroke="#ffffff" stroke-width="1.5"/>'

    @staticmethod
    def _point(radius: float, angle: float) -> str:
        a = math.radians(angle - 90)
        return f"{60 + radius * math.cos(a):.2f} {60 + radius * math.sin(a):.2f}"
