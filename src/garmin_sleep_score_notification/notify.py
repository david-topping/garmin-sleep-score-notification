from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime

from . import configure_logging
from .config import Config, ConfigError, Person
from .email_content import SleepEmail
from .garmin import GarminError, GarminFetcher, SleepSummary
from .mailer import EmailError, EmailSender
from .state import SentState
from .uptime_kuma import UptimeKuma

log = logging.getLogger("garmin_sleep")


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
        unexpected = []
        for person in self.config.people:
            try:
                self._process(person, day)
            except Exception as exc:
                log.exception("%s: unexpected error", person.name)
                self.failures += 1
                unexpected.append(f"{person.name}: {type(exc).__name__}")
        if unexpected:
            self.monitor.down("unexpected error: " + ", ".join(unexpected))
        else:
            self._heartbeat(day)
        self.state.save()
        return 1 if self.failures else 0

    def _heartbeat(self, day: date) -> None:
        people = self.config.people
        if self.state.heartbeat_pushed(day):
            return
        if not all(self.state.is_done(p.name, day, {r.email for r in p.recipients}) for p in people):
            return
        if self.monitor.up(f"{day}: sent {', '.join(p.name for p in people)}"):
            self.state.mark_heartbeat(day)

    def dry_run(self) -> int:
        day = self._today()
        for person in self.config.people:
            summary = self._fetch(person, day)
            if summary is None:
                continue
            email = SleepEmail(person.name, day, summary)
            recipients = ", ".join(r.name for r in person.recipients)
            log.info("%s: would email [%s]: %s", person.name, recipients, email.subject)
        return 0

    def _fetch(self, person: Person, day: date) -> SleepSummary | None:
        try:
            summary = GarminFetcher(person.token_store).fetch(day)
        except GarminError as exc:
            log.error("%s: %s", person.name, exc)
            self.failures += 1
            return None
        if summary is None:
            log.info("%s: no sleep score yet, will retry next run", person.name)
        return summary

    def _process(self, person: Person, day: date) -> None:
        recipients = {r.email for r in person.recipients}
        if self.state.is_done(person.name, day, recipients):
            log.info("%s: already sent today", person.name)
            return

        summary = self._fetch(person, day)
        if summary is None:
            return

        email = SleepEmail(person.name, day, summary)
        attachments = email.attachments
        record = summary.as_record()
        already = self.state.sent_recipients(person.name, day)
        for recipient in person.recipients:
            if recipient.email in already:
                continue
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
