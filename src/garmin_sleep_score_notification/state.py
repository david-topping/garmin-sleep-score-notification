from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

RETENTION_DAYS = 7


class SentState:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        try:
            self._data: dict = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

    def _day(self, day: date) -> dict:
        return self._data.setdefault(day.isoformat(), {})

    def sent_recipients(self, person: str, day: date) -> set[str]:
        return set(self._day(day).get(person, {}).get("recipients", []))

    def is_done(self, person: str, day: date, recipients: set[str]) -> bool:
        return bool(recipients) and recipients.issubset(self.sent_recipients(person, day))

    def mark(self, person: str, day: date, score: int, recipient: str) -> None:
        record = self._day(day).setdefault(person, {"score": score, "recipients": []})
        record["score"] = score
        if recipient not in record["recipients"]:
            record["recipients"].append(recipient)

    def save(self) -> None:
        cutoff = (date.today() - timedelta(days=RETENTION_DAYS)).isoformat()
        self._data = {day: rec for day, rec in self._data.items() if day >= cutoff}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True))
        tmp.replace(self.path)
