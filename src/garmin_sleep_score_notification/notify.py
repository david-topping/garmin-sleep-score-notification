from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime

from . import configure_logging
from .config import Config, ConfigError, Person
from .garmin import GarminError, GarminFetcher, SleepSummary
from .mailer import EmailError, EmailSender
from .state import SentState

log = logging.getLogger("garmin_sleep")


class Notifier:
    def __init__(self, config: Config, sender: EmailSender | None = None) -> None:
        self.config = config
        self.sender = sender or EmailSender(config.resend_api_key, config.email_from)
        self.state = SentState(config.state_file)
        self.failures = 0

    def run(self) -> int:
        day = self._today()
        log.info("run for %s, %d people", day, len(self.config.people))
        for person in self.config.people:
            try:
                self._process(person, day)
            except Exception:
                log.exception("%s: unexpected error", person.name)
                self.failures += 1
        self.state.save()
        return 1 if self.failures else 0

    def dry_run(self) -> int:
        day = self._today()
        for person in self.config.people:
            try:
                summary = GarminFetcher(person.token_store).fetch(day)
            except GarminError as exc:
                log.error("%s: %s", person.name, exc)
                continue
            if summary is None:
                log.info("%s: no sleep score yet", person.name)
                continue
            recipients = ", ".join(r.name for r in person.recipients)
            log.info(
                "%s: would email [%s]: %s / %s",
                person.name,
                recipients,
                self._subject(person, summary),
                self._body(person, summary, day),
            )
        return 0

    def _process(self, person: Person, day: date) -> None:
        recipients = {r.email for r in person.recipients}
        if self.state.is_done(person.name, day, recipients):
            log.info("%s: already sent today", person.name)
            return

        try:
            summary = GarminFetcher(person.token_store).fetch(day)
        except GarminError as exc:
            log.error("%s: %s", person.name, exc)
            self.failures += 1
            return

        if summary is None:
            log.info("%s: no sleep score yet, will retry next run", person.name)
            return

        subject = self._subject(person, summary)
        body = self._body(person, summary, day)
        already = self.state.sent_recipients(person.name, day)
        for recipient in person.recipients:
            if recipient.email in already:
                continue
            try:
                self.sender.send(recipient.email, subject, body)
            except EmailError as exc:
                log.error("%s -> %s: send failed (%s), will retry", person.name, recipient.name, exc)
                self.failures += 1
                continue
            self.state.mark(person.name, day, summary.score, recipient.email)
            log.info("%s -> %s: sent score %d", person.name, recipient.name, summary.score)

        self.state.save()

    @staticmethod
    def _subject(person: Person, summary: SleepSummary) -> str:
        return f"{person.name}'s Garmin sleep score: {summary.score}/100"

    @staticmethod
    def _body(person: Person, summary: SleepSummary, day: date) -> str:
        return (
            f"{person.name}'s Garmin sleep for {day:%a %d %b}\n\n"
            f"Score: {summary.score}/100\n"
            f"{summary.stages()}\n"
        )

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
    args = parser.parse_args(argv)

    configure_logging()
    try:
        config = Config.load(args.people_file)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    notifier = Notifier(config)
    return notifier.dry_run() if args.dry_run else notifier.run()


if __name__ == "__main__":
    sys.exit(main())
