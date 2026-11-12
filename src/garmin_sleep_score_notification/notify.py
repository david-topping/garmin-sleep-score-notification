from __future__ import annotations

import argparse
import logging
import re
import sys
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from . import configure_logging
from .config import Config, ConfigError, Person
from .email import EmailError, EmailSender, SleepEmail, Standing
from .garmin import GarminError, GarminFetcher, SleepSummary
from .state import SentState
from .uptime_kuma import UptimeKuma

log = logging.getLogger("garmin_sleep")

AVERAGE_DAYS = 7


def average_clock(times: list[str]) -> str | None:
    if not times:
        return None
    minutes = [int(t[:2]) * 60 + int(t[3:5]) for t in times]
    mean = round(sum(minutes) / len(minutes))
    return f"{mean // 60:02d}:{mean % 60:02d}"


class Notifier:
    def __init__(
        self,
        config: Config,
        sender: EmailSender | None = None,
        monitor: UptimeKuma | None = None,
    ) -> None:
        self.config = config
        self.sender = sender or EmailSender(config.resend_api_key, config.email_from)
        self.monitor = monitor or UptimeKuma(config.uptime_kuma_push_url)
        self.failures = 0

    def run(self) -> int:
        try:
            return self._run()
        except Exception as exc:
            log.exception("run failed")
            self.monitor.down(f"run failed: {type(exc).__name__}")
            return 1

    def _run(self) -> int:
        self.state = SentState(self.config.state_file)
        day = self._today()
        log.info("run for %s, %d people", day, len(self.config.people))
        self.unexpected: list[str] = []
        pending = []
        for person in self.config.people:
            if self.state.is_done(person.name, day, {r.email for r in person.recipients}):
                log.info("%s: already sent today", person.name)
            else:
                pending.append(person)

        self.fetched: dict[str, SleepSummary] = {}
        for person in pending:
            self._guard(person, lambda: self._fetch_into(person, day))
        for person in pending:
            if person.name in self.fetched:
                self._guard(person, lambda: self._send(person, day, self.fetched[person.name]))

        self.state.save()
        if self.unexpected:
            self.monitor.down("unexpected error: " + ", ".join(self.unexpected))
        elif not self.failures:
            self.monitor.up(self._status(day))
        return 1 if self.failures else 0

    def _guard(self, person: Person, step: Callable[[], None]) -> None:
        try:
            step()
        except Exception as exc:
            log.exception("%s: unexpected error", person.name)
            self.failures += 1
            self.unexpected.append(f"{person.name}: {type(exc).__name__}")

    def _status(self, day: date) -> str:
        sent, waiting = [], []
        for person in self.config.people:
            done = self.state.is_done(person.name, day, {r.email for r in person.recipients})
            (sent if done else waiting).append(person.name)
        return f"ok, sent: {', '.join(sent) or '-'}, waiting: {', '.join(waiting) or '-'}"

    def dry_run(self, preview_dir: Path | None = None) -> int:
        self.state = SentState(self.config.state_file)
        day = self._today()
        self.fetched = {}
        for person in self.config.people:
            self._fetch_into(person, day)
        for person in self.config.people:
            summary = self.fetched.get(person.name)
            if summary is None:
                continue
            for recipient in person.recipients:
                email = self._email(person, day, summary, recipient.email)
                log.info("%s: would email %s: %s", person.name, recipient.name, email.subject)
                if preview_dir:
                    self._write_preview(preview_dir, f"{person.name}-to-{recipient.name}", email)
        return 0

    @staticmethod
    def _write_preview(directory: Path, name: str, email: SleepEmail) -> None:
        name = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
        directory.mkdir(parents=True, exist_ok=True)
        html = email.html
        for a in email.attachments:
            filename = f"{name}-{a.filename}"
            (directory / filename).write_bytes(a.content)
            html = html.replace(f"cid:{a.content_id}", filename)
        (directory / f"{name}.html").write_text(html)
        (directory / f"{name}.txt").write_text(email.text)
        log.info("preview written to %s", directory / f"{name}.html")

    def _email(self, person: Person, day: date, summary: SleepSummary, reader: str) -> SleepEmail:
        previous = self.state.score(person.name, day - timedelta(days=1))
        return SleepEmail(person.name, day, summary, previous, self._leaderboard(day, reader))

    def _leaderboard(self, day: date, reader: str) -> list[Standing]:
        return [
            self._standing(p, day, p.email.lower() == reader.lower())
            for p in self.config.people
            if p.is_sent_to(reader) or (p.email and p.email.lower() == reader.lower())
        ]

    def _standing(self, person: Person, day: date, is_reader: bool) -> Standing:
        summary = self.fetched.get(person.name)
        today = summary.as_record() if summary else self.state.record(person.name, day)
        earlier = [self.state.record(person.name, day - timedelta(days=n)) for n in range(1, AVERAGE_DAYS)]
        week = [today, *earlier]
        scores = [r["score"] for r in week if isinstance(r.get("score"), int)]
        wakes = [r["wake"] for r in week if r.get("wake")]
        avg_score = round(sum(scores) / len(scores)) if scores else None
        return Standing(person.name, avg_score, average_clock(wakes), is_reader)

    def _fetch_into(self, person: Person, day: date) -> None:
        try:
            summary = GarminFetcher(person.token_store).fetch(day)
        except GarminError as exc:
            log.error("%s: %s", person.name, exc)
            self.failures += 1
            return
        if summary is None:
            log.info("%s: no sleep score yet, will retry next run", person.name)
            return
        self.fetched[person.name] = summary

    def _send(self, person: Person, day: date, summary: SleepSummary) -> None:
        record = summary.as_record()
        already = self.state.sent_recipients(person.name, day)
        attachments = None
        for recipient in person.recipients:
            if recipient.email in already:
                continue
            email = self._email(person, day, summary, recipient.email)
            if attachments is None:
                attachments = email.attachments
            try:
                self.sender.send(
                    recipient.email, email.subject, email.text, email.html, attachments
                )
            except EmailError as exc:
                log.error("%s -> %s: send failed (%s), will retry", person.name, recipient.name, exc)
                self.failures += 1
                continue
            self.state.mark(person.name, day, record, recipient.email)
            log.info("%s -> %s: sent score %d", person.name, recipient.name, summary.score)

        self.state.save()

    def _today(self) -> date:
        if self.config.timezone:
            try:
                from zoneinfo import ZoneInfo

                return datetime.now(ZoneInfo(self.config.timezone)).date()
            except Exception:
                log.warning("bad TIMEZONE %r, using system time", self.config.timezone)
        return datetime.now().astimezone().date()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="garmin-sleep-notify")
    parser.add_argument("--people-file")
    parser.add_argument("--dry-run", action="store_true", help="fetch and log, send nothing")
    parser.add_argument(
        "--preview", type=Path, metavar="DIR", help="dry run that also writes each email to DIR"
    )
    args = parser.parse_args(argv)

    configure_logging()
    try:
        config = Config.load(args.people_file)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    notifier = Notifier(config)
    if args.dry_run or args.preview:
        return notifier.dry_run(args.preview)
    return notifier.run()


if __name__ == "__main__":
    sys.exit(main())
