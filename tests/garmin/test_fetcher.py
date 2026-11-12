from datetime import date

import pytest
from garminconnect import GarminConnectAuthenticationError

from garmin_sleep_score_notification.garmin import GarminError, GarminFetcher, fetcher

DAY = date(2026, 9, 2)


@pytest.fixture
def token_store(tmp_path):
    path = tmp_path / "wallace"
    path.mkdir()
    return path


def fake_garmin(monkeypatch, payload=None, error=None):
    calls = []

    class FakeGarmin:
        def login(self, tokenstore):
            calls.append(("login", tokenstore))
            if isinstance(error, GarminConnectAuthenticationError):
                raise error

        def get_sleep_data(self, day):
            calls.append(("sleep", day))
            if error:
                raise error
            return payload

    monkeypatch.setattr(fetcher, "Garmin", FakeGarmin)
    return calls


def test_fetches_the_day_with_stored_tokens(monkeypatch, token_store, sleep_payload):
    calls = fake_garmin(monkeypatch, payload=sleep_payload)
    summary = GarminFetcher(token_store).fetch(DAY)
    assert summary.score == 84
    assert calls == [("login", str(token_store)), ("sleep", "2026-09-02")]


def test_not_synced_yet_is_none(monkeypatch, token_store):
    fake_garmin(monkeypatch, payload={"dailySleepDTO": None})
    assert GarminFetcher(token_store).fetch(DAY) is None


def test_missing_token_store(tmp_path):
    with pytest.raises(GarminError, match="run auth-setup"):
        GarminFetcher(tmp_path / "gromit").fetch(DAY)


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (GarminConnectAuthenticationError("expired"), "auth failed"),
        (ConnectionError("no route to Wigan"), "fetch failed"),
    ],
)
def test_errors_become_garmin_error(monkeypatch, token_store, error, message):
    fake_garmin(monkeypatch, error=error)
    with pytest.raises(GarminError, match=message):
        GarminFetcher(token_store).fetch(DAY)
