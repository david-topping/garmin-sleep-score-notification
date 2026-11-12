import pytest

from garmin_sleep_score_notification.config import ConfigError
from garmin_sleep_score_notification.garmin import auth_setup
from garmin_sleep_score_notification.garmin.auth_setup import AuthSetup

PEOPLE = """\
people:
  - name: wallace
    recipients:
      - email: wallace@westwallaby.co.uk
"""


@pytest.fixture
def people_file(tmp_path, monkeypatch):
    path = tmp_path / "people.yaml"
    path.write_text(PEOPLE)
    monkeypatch.setenv("PEOPLE_FILE", str(path))
    monkeypatch.setenv("GARMIN_TOKENS_DIR", str(tmp_path / "tokens"))
    return path


def test_explicit_token_store_wins(people_file, tmp_path):
    setup = AuthSetup.for_name("gromit", str(tmp_path / "kennel"))
    assert setup.token_store == tmp_path / "kennel"


def test_token_store_comes_from_people_yaml(people_file, tmp_path):
    assert AuthSetup.for_name("wallace", None).token_store == tmp_path / "tokens" / "wallace"


def test_unknown_person_exits_2(people_file, capsys):
    assert auth_setup.main(["feathers"]) == 2
    assert "no person 'feathers'" in capsys.readouterr().err


def test_login_writes_tokens(people_file, tmp_path, monkeypatch):
    dumped = []

    class FakeClient:
        def dump(self, path):
            dumped.append(path)

    class FakeGarmin:
        def __init__(self, **kwargs):
            self.client = FakeClient()

        def login(self, tokenstore=None):
            pass

    monkeypatch.setattr(auth_setup, "Garmin", FakeGarmin)
    monkeypatch.setattr("builtins.input", lambda prompt: "wallace@westwallaby.co.uk")
    monkeypatch.setattr(auth_setup.getpass, "getpass", lambda prompt: "cheese-gromit")

    assert auth_setup.main(["wallace"]) == 0
    assert dumped == [str(tmp_path / "tokens" / "wallace")]
    assert (tmp_path / "tokens" / "wallace").is_dir()
