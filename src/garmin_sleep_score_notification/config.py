from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Recipient:
    email: str
    label: str = ""

    @property
    def name(self) -> str:
        return self.label or self.email

    @classmethod
    def from_dict(cls, d: dict) -> Recipient:
        return cls(str(d["email"]).strip(), str(d.get("label", "")).strip())


@dataclass(frozen=True)
class Person:
    name: str
    token_store: Path
    recipients: tuple[Recipient, ...]

    @classmethod
    def from_dict(cls, d: dict, tokens_dir: Path) -> Person:
        name = str(d["name"])
        token_store = Path(d["token_store"]) if d.get("token_store") else tokens_dir / name
        return cls(
            name,
            token_store.expanduser(),
            tuple(Recipient.from_dict(r) for r in d["recipients"]),
        )


@dataclass(frozen=True)
class Config:
    people: tuple[Person, ...]
    state_file: Path
    timezone: str | None
    resend_api_key: str
    email_from: str
    uptime_kuma_push_url: str | None = None

    @classmethod
    def load(cls, people_file: str | os.PathLike[str] | None = None) -> Config:
        load_dotenv()
        path = Path(
            people_file or os.getenv("PEOPLE_FILE") or PROJECT_ROOT / "people.yaml"
        ).expanduser()
        if not path.exists():
            raise ConfigError(f"{path} not found. Copy people.example.yaml to people.yaml")

        tokens_dir = Path(os.getenv("GARMIN_TOKENS_DIR") or "~/.garmin_tokens")
        try:
            people = tuple(Person.from_dict(p, tokens_dir) for p in yaml.safe_load(path.read_text())["people"])
        except (KeyError, TypeError) as exc:
            raise ConfigError(f"{path}: malformed config ({exc})") from exc

        if not people:
            raise ConfigError(f"{path}: no people configured")
        for person in people:
            if not person.recipients:
                raise ConfigError(f"{path}: {person.name!r} has no recipients")

        return cls(
            people=people,
            state_file=Path(
                os.getenv("STATE_FILE") or PROJECT_ROOT / "state" / "sent_state.json"
            ).expanduser(),
            timezone=os.getenv("TIMEZONE") or os.getenv("TZ") or None,
            resend_api_key=os.getenv("RESEND_API_KEY", ""),
            email_from=os.getenv("EMAIL_FROM", "Garmin Sleep <onboarding@resend.dev>"),
            uptime_kuma_push_url=os.getenv("UPTIME_KUMA_PUSH_URL") or None,
        )
