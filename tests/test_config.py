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
          - name: alice
            token_store: ~/.garmin_tokens/alice
            recipients:
              - phone: "+1"
                apikey: a1
              - phone: "+2"
                apikey: a2
                label: Bob
          - name: bob
            token_store: ~/.garmin_tokens/bob
            recipients:
              - phone: "+2"
                apikey: a2
        """,
    )
    config = Config.load(path)
    assert [p.name for p in config.people] == ["alice", "bob"]
    assert config.people[0].recipients[1].name == "Bob"
    assert config.people[1].recipients[0].phone == "+2"


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        Config.load(tmp_path / "nope.yaml")


def test_no_recipients(tmp_path):
    path = write(
        tmp_path,
        """
        people:
          - name: alice
            token_store: /t/a
            recipients: []
        """,
    )
    with pytest.raises(ConfigError):
        Config.load(path)


def test_malformed(tmp_path):
    path = write(tmp_path, "people:\n  - name: alice\n")
    with pytest.raises(ConfigError):
        Config.load(path)
