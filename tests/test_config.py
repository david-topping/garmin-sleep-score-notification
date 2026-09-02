import textwrap

import pytest

from garmin_sleep_score_notification.config import Config, ConfigError


def write(tmp_path, text):
    path = tmp_path / "people.yaml"
    path.write_text(textwrap.dedent(text))
    return path


def test_loads_people_and_fan_out(tmp_path):
    path = write(
        tmp_path,
        """
        people:
          - name: wallace
            token_store: ~/.garmin_tokens/wallace
            recipients:
              - email: wallace@westwallaby.co.uk
              - email: gromit@westwallaby.co.uk
                label: Gromit
          - name: gromit
            token_store: ~/.garmin_tokens/gromit
            recipients:
              - email: gromit@westwallaby.co.uk
        """,
    )
    config = Config.load(path)
    assert [p.name for p in config.people] == ["wallace", "gromit"]
    assert config.people[0].recipients[1].name == "Gromit"
    assert config.people[1].recipients[0].email == "gromit@westwallaby.co.uk"


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        Config.load(tmp_path / "nope.yaml")


def test_no_recipients(tmp_path):
    path = write(
        tmp_path,
        """
        people:
          - name: wallace
            token_store: /t/w
            recipients: []
        """,
    )
    with pytest.raises(ConfigError):
        Config.load(path)


def test_malformed(tmp_path):
    path = write(tmp_path, "people:\n  - name: wallace\n")
    with pytest.raises(ConfigError):
        Config.load(path)
