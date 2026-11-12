from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from mjml import mjml2html

from ..garmin import SleepSummary
from .hypnogram import Hypnogram

STAGE_COLOUR = {"Deep": "#2f4b7c", "Light": "#5b8def", "REM": "#7b61ff", "Awake": "#e8a33d"}
QUALIFIER_COLOUR = {
    "Excellent": "#2f8a4e",
    "Good": "#2f8a4e",
    "Fair": "#d98324",
    "Poor": "#c0392b",
}
TIMELINE_CID = "sleep-timeline"

_templates = Environment(
    loader=PackageLoader(__package__, "templates"),
    autoescape=select_autoescape(["mjml.j2"]),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def hm(td: timedelta) -> str:
    total = int(td.total_seconds())
    return f"{total // 3600}h {total % 3600 // 60:02d}m"


@dataclass(frozen=True)
class Attachment:
    filename: str
    content: bytes
    content_id: str


class SleepEmail:
    def __init__(
        self,
        person: str,
        day: date,
        summary: SleepSummary,
        previous_score: int | None = None,
    ) -> None:
        self.person = person.title()
        self.day = day
        self.summary = summary
        self.previous_score = previous_score

    @property
    def subject(self) -> str:
        return f"{self.person}'s Sleep Score {self.summary.score}/100 {self.day:%d/%m/%y}"

    @property
    def text(self) -> str:
        return _templates.get_template("sleep.txt.j2").render(self._context())

    @property
    def html(self) -> str:
        # fonts={}: MJML otherwise injects a Google Fonts link for Roboto, an external request.
        source = _templates.get_template("sleep.mjml.j2").render(self._context())
        return mjml2html(source, fonts={})

    @property
    def attachments(self) -> list[Attachment]:
        png = Hypnogram(self.summary.timeline, STAGE_COLOUR, self.summary.start_local).png()
        if png is None:
            return []
        return [Attachment("sleep-timeline.png", png, TIMELINE_CID)]

    def _delta(self) -> tuple[str, str] | None:
        if self.previous_score is None:
            return None
        diff = self.summary.score - self.previous_score
        if diff > 0:
            return f"▲ {diff} vs yesterday", QUALIFIER_COLOUR["Good"]
        if diff < 0:
            return f"▼ {-diff} vs yesterday", QUALIFIER_COLOUR["Poor"]
        return "Same as yesterday", "#7b8394"

    def _context(self) -> dict:
        s = self.summary
        stages = [
            {
                "label": st.label,
                "duration": hm(st.duration),
                "percent": None if st.label == "Awake" else st.percent,
                "colour": STAGE_COLOUR[st.label],
            }
            for st in s.breakdown()
        ]
        return {
            "person": self.person,
            "day": self.day,
            "score": s.score,
            "qualifier": s.qualifier,
            "colour": QUALIFIER_COLOUR.get(s.qualifier, "#3d4350"),
            "delta": self._delta(),
            "stages": stages,
            "total": hm(s.asleep),
            "timeline_cid": TIMELINE_CID if s.timeline else None,
            "timeline_alt": ", ".join(f"{st['label']} {st['duration']}" for st in stages),
        }
