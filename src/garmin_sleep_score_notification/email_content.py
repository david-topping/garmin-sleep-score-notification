from __future__ import annotations

import math
from datetime import date
from html import escape

from .garmin import SleepSummary

_QUALIFIER_COLOUR = {
    "Excellent": "#2f8a4e",
    "Good": "#2f8a4e",
    "Fair": "#d98324",
    "Poor": "#c0392b",
}


class SleepEmail:
    def __init__(self, person: str, day: date, summary: SleepSummary) -> None:
        self.person = person.title()
        self.day = day
        self.summary = summary

    @property
    def subject(self) -> str:
        return f"{self.person}'s Sleep Score {self.summary.score}/100 {self.day:%d/%m/%y}"

    @property
    def text(self) -> str:
        s = self.summary
        lines = [
            f"{self.person}'s Garmin sleep for {self.day:%A %d %B}",
            "",
            f"Score: {s.score}/100 ({s.qualifier})",
            f"Total sleep: {SleepSummary.hm(s.asleep)}",
            "",
        ]
        lines += [f"  {st.label:<6} {SleepSummary.hm(st.duration):>7}" for st in s.breakdown()]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _point(radius: float, angle: float) -> str:
        a = math.radians(angle - 90)
        return f"{60 + radius * math.cos(a):.2f} {60 + radius * math.sin(a):.2f}"

    def _sector(self, colour: str, start: float, end: float) -> str:
        outer, inner = 52.0, 34.0
        large = 1 if end - start > 180 else 0
        d = (
            f"M {self._point(outer, start)} "
            f"A {outer} {outer} 0 {large} 1 {self._point(outer, end)} "
            f"L {self._point(inner, end)} "
            f"A {inner} {inner} 0 {large} 0 {self._point(inner, start)} Z"
        )
        return f'<path d="{d}" fill="{colour}" stroke="#ffffff" stroke-width="1.5"/>'

    def _donut_svg(self) -> str:
        stages = [st for st in self.summary.breakdown() if st.label != "Awake"]
        asleep = self.summary.asleep.total_seconds()
        sectors, angle = [], 0.0
        for st in stages:
            frac = st.duration.total_seconds() / asleep if asleep else 0.0
            sweep = min(frac * 360, 359.99)
            if sweep > 0.5:
                sectors.append(self._sector(st.colour, angle, angle + sweep))
            angle += frac * 360
        total = SleepSummary.hm(self.summary.asleep)
        return (
            '<svg width="180" height="180" viewBox="0 0 120 120" '
            'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Sleep stage breakdown">'
            f'{"".join(sectors)}'
            f'<text x="60" y="58" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" '
            f'font-size="15" font-weight="bold" fill="#1f2430">{total}</text>'
            '<text x="60" y="71" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" '
            'font-size="7" letter-spacing="0.5" fill="#9099a5">TOTAL SLEEP</text>'
            "</svg>"
        )

    @property
    def html(self) -> str:
        s = self.summary
        qcolour = _QUALIFIER_COLOUR.get(s.qualifier, "#3d4350")
        rows = "".join(
            f'<tr>'
            f'<td style="padding:6px 0;width:16px;"><span style="display:inline-block;width:10px;'
            f'height:10px;border-radius:3px;background:{st.colour};"></span></td>'
            f'<td style="padding:6px 10px;color:#3d4350;">{st.label}</td>'
            f'<td style="padding:6px 0;text-align:right;color:#1f2430;font-weight:600;">'
            f'{SleepSummary.hm(st.duration)}</td>'
            f'<td style="padding:6px 0 6px 14px;text-align:right;color:#9099a5;width:46px;">'
            f'{str(st.percent) + "%" if st.label != "Awake" else "&mdash;"}</td>'
            f'</tr>'
            for st in s.breakdown()
        )
        return f"""\
<div style="margin:0;padding:24px 12px;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:460px;margin:0 auto;">
    <tr><td style="background:#ffffff;border-radius:14px;padding:28px 28px 22px;">
      <div style="font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:#9099a5;font-weight:700;">Sleep Score</div>
      <div style="font-size:15px;color:#3d4350;margin-top:5px;">{escape(self.person)} &middot; {self.day:%a %d %b}</div>
      <div style="margin:14px 0 2px;">
        <span style="font-size:52px;font-weight:700;color:#1f2430;line-height:1;">{s.score}</span>
        <span style="font-size:19px;color:#9099a5;font-weight:600;">/ 100</span>
        <span style="font-size:16px;font-weight:700;color:{qcolour};margin-left:8px;">{s.qualifier}</span>
      </div>
      <div style="text-align:center;margin:14px 0 4px;">{self._donut_svg()}</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;margin-top:8px;">
        {rows}
        <tr><td colspan="2" style="padding:9px 0 0;border-top:1px solid #edeff2;color:#3d4350;font-weight:600;">Total sleep</td>
        <td colspan="2" style="padding:9px 0 0;border-top:1px solid #edeff2;text-align:right;color:#1f2430;font-weight:700;">{SleepSummary.hm(s.asleep)}</td></tr>
      </table>
    </td></tr>
    <tr><td style="padding:14px 8px;text-align:center;font-size:11px;color:#b3b8c0;">Garmin Connect &middot; garmin-sleep-notify</td></tr>
  </table>
</div>"""
