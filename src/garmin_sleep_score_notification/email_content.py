from __future__ import annotations

from datetime import date, timedelta
from html import escape

from .donut import Donut
from .garmin import SleepSummary

_STAGE_COLOUR = {"Deep": "#2f4b7c", "Light": "#5b8def", "REM": "#7b61ff", "Awake": "#e8a33d"}
_QUALIFIER_COLOUR = {
    "Excellent": "#2f8a4e",
    "Good": "#2f8a4e",
    "Fair": "#d98324",
    "Poor": "#c0392b",
}


def hm(td: timedelta) -> str:
    total = int(td.total_seconds())
    return f"{total // 3600}h {total % 3600 // 60:02d}m"


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
            f"Total sleep: {hm(s.asleep)}",
            "",
        ]
        lines += [f"  {st.label:<6} {hm(st.duration):>7}" for st in s.breakdown()]
        return "\n".join(lines) + "\n"

    def _donut_svg(self) -> str:
        asleep = self.summary.asleep.total_seconds()
        segments = [
            (_STAGE_COLOUR[st.label], st.duration.total_seconds() / asleep if asleep else 0.0)
            for st in self.summary.breakdown()
            if st.label != "Awake"
        ]
        return Donut(segments, hm(self.summary.asleep), "TOTAL SLEEP").svg()

    @property
    def html(self) -> str:
        s = self.summary
        qcolour = _QUALIFIER_COLOUR.get(s.qualifier, "#3d4350")
        rows = "".join(
            f'<tr>'
            f'<td style="padding:6px 0;width:16px;"><span style="display:inline-block;width:10px;'
            f'height:10px;border-radius:3px;background:{_STAGE_COLOUR[st.label]};"></span></td>'
            f'<td style="padding:6px 10px;color:#4a5160;">{st.label}</td>'
            f'<td style="padding:6px 0;text-align:right;color:#2b303b;font-weight:600;">'
            f'{hm(st.duration)}</td>'
            f'<td style="padding:6px 0 6px 14px;text-align:right;color:#7b8394;width:46px;">'
            f'{str(st.percent) + "%" if st.label != "Awake" else "&mdash;"}</td>'
            f'</tr>'
            for st in s.breakdown()
        )
        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="color-scheme" content="light only">
<meta name="supported-color-schemes" content="light only">
</head>
<body style="margin:0;padding:0;background:#f4f5f7;color-scheme:light only;">
<div style="margin:0;padding:24px 12px;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:460px;margin:0 auto;">
    <tr><td style="background:#ffffff;border:1px solid #e6e9ee;border-radius:14px;padding:28px 28px 22px;">
      <div style="font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:#7b8394;font-weight:700;">Sleep Score</div>
      <div style="font-size:15px;color:#4a5160;margin-top:5px;">{escape(self.person)} &middot; {self.day:%a %d %b}</div>
      <div style="margin:14px 0 2px;">
        <span style="font-size:52px;font-weight:700;color:{qcolour};line-height:1;">{s.score}</span>
        <span style="font-size:19px;color:#7b8394;font-weight:600;">/ 100</span>
        <span style="font-size:16px;font-weight:700;color:{qcolour};margin-left:8px;">{s.qualifier}</span>
      </div>
      <div style="text-align:center;margin:14px 0 4px;">{self._donut_svg()}</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;margin-top:8px;">
        {rows}
        <tr><td colspan="2" style="padding:9px 0 0;border-top:1px solid #e6e9ee;color:#4a5160;font-weight:600;">Total sleep</td>
        <td colspan="2" style="padding:9px 0 0;border-top:1px solid #e6e9ee;text-align:right;color:#2b303b;font-weight:700;">{hm(s.asleep)}</td></tr>
      </table>
    </td></tr>
    <tr><td style="padding:14px 8px;text-align:center;font-size:11px;color:#9aa0ac;">Garmin Connect &middot; garmin-sleep-notify</td></tr>
  </table>
</div>
</body>
</html>"""
