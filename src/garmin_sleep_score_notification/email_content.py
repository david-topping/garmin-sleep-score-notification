from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from html import escape

from .garmin import SleepSummary
from .hypnogram import Hypnogram

_STAGE_COLOUR = {"Deep": "#2f4b7c", "Light": "#5b8def", "REM": "#7b61ff", "Awake": "#e8a33d"}
_TIMELINE_CID = "sleep-timeline"
_QUALIFIER_COLOUR = {
    "Excellent": "#2f8a4e",
    "Good": "#2f8a4e",
    "Fair": "#d98324",
    "Poor": "#c0392b",
}


def hm(td: timedelta) -> str:
    total = int(td.total_seconds())
    return f"{total // 3600}h {total % 3600 // 60:02d}m"


@dataclass(frozen=True)
class Attachment:
    filename: str
    content: bytes
    content_id: str


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

    @property
    def attachments(self) -> list[Attachment]:
        png = Hypnogram(
            self.summary.timeline, _STAGE_COLOUR, self.summary.start_local
        ).png()
        if png is None:
            return []
        return [Attachment("sleep-timeline.png", png, _TIMELINE_CID)]

    def _timeline_img(self) -> str:
        if not self.summary.timeline:
            return ""
        alt = escape(", ".join(f"{st.label} {hm(st.duration)}" for st in self.summary.breakdown()))
        return (
            f'<div style="margin:6px 0 2px;"><img src="cid:{_TIMELINE_CID}" width="404" '
            f'alt="Sleep stage timeline: {alt}" '
            f'style="display:block;margin:0 auto;max-width:100%;height:auto;border:0;"></div>'
        )

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
      {self._timeline_img()}
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
