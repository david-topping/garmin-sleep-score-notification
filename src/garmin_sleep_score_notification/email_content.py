from __future__ import annotations

from datetime import date
from html import escape
from urllib.parse import quote

from .garmin import SleepSummary

_QUALIFIER_COLOUR = {
    "Excellent": "#2f8a4e",
    "Good": "#2f8a4e",
    "Fair": "#d98324",
    "Poor": "#c0392b",
}


class SleepEmail:
    CHART_CID = "sleepring"

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

    @property
    def chart_url(self) -> str:
        stages = [st for st in self.summary.breakdown() if st.label != "Awake"]
        data = ",".join(str(round(st.duration.total_seconds() / 60)) for st in stages)
        colours = ",".join(f"'{st.colour}'" for st in stages)
        labels = ",".join(f"'{st.label}'" for st in stages)
        centre = SleepSummary.hm(self.summary.asleep)
        config = (
            "{type:'doughnut',"
            f"data:{{labels:[{labels}],datasets:[{{data:[{data}],"
            f"backgroundColor:[{colours}],borderWidth:0}}]}},"
            "options:{cutoutPercentage:70,legend:{display:false},"
            "plugins:{datalabels:{display:false},doughnutlabel:{labels:["
            f"{{text:'{centre}',font:{{size:26,weight:'bold'}},color:'#1f2430'}},"
            "{text:'total sleep',font:{size:12},color:'#9099a5'}]}}}}"
        )
        return "https://quickchart.io/chart?w=260&h=260&bkg=white&c=" + quote(config)

    @property
    def html(self) -> str:
        s = self.summary
        qcolour = _QUALIFIER_COLOUR.get(s.qualifier, "#3d4350")
        alt = ", ".join(
            f"{st.label} {SleepSummary.hm(st.duration)}"
            for st in s.breakdown()
            if st.label != "Awake"
        )
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
      <div style="text-align:center;margin:16px 0 6px;">
        <img src="cid:{self.CHART_CID}" width="200" height="200" alt="{alt}" style="display:block;margin:0 auto;border:0;">
      </div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;margin-top:8px;">
        {rows}
        <tr><td colspan="2" style="padding:9px 0 0;border-top:1px solid #edeff2;color:#3d4350;font-weight:600;">Total sleep</td>
        <td colspan="2" style="padding:9px 0 0;border-top:1px solid #edeff2;text-align:right;color:#1f2430;font-weight:700;">{SleepSummary.hm(s.asleep)}</td></tr>
      </table>
    </td></tr>
    <tr><td style="padding:14px 8px;text-align:center;font-size:11px;color:#b3b8c0;">Garmin Connect &middot; garmin-sleep-notify</td></tr>
  </table>
</div>"""
