from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from garminconnect import Garmin

from . import configure_logging
from .config import Config, ConfigError


class AuthSetup:
    def __init__(self, name: str, token_store: Path) -> None:
        self.name = name
        self.token_store = token_store

    @classmethod
    def for_name(cls, name: str, token_store: str | None) -> AuthSetup:
        if token_store:
            return cls(name, Path(token_store).expanduser())
        for person in Config.load().people:
            if person.name == name:
                return cls(name, person.token_store)
        raise ConfigError(f"no person {name!r} in people.yaml (or pass --token-store)")

    def run(self) -> None:
        print(f"Garmin login for {self.name!r} -> {self.token_store}")
        email = input("Email: ").strip()
        password = getpass.getpass("Password: ")

        garmin = Garmin(email=email, password=password, prompt_mfa=self._mfa)
        garmin.login()

        self.token_store.mkdir(parents=True, exist_ok=True)
        garmin.client.dump(str(self.token_store))
        Garmin().login(tokenstore=str(self.token_store))
        print(f"OK: tokens written to {self.token_store}")

    @staticmethod
    def _mfa() -> str:
        return input("MFA code: ").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="garmin-auth-setup")
    parser.add_argument("name")
    parser.add_argument("--token-store")
    args = parser.parse_args(argv)

    configure_logging()
    try:
        AuthSetup.for_name(args.name, args.token_store).run()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
