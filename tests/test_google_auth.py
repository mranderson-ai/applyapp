import json

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from applyapp.cli import _doctor, main
from applyapp.config import Settings
from applyapp.google.auth import SCOPES, credentials, token_health


def _settings(tmp_path) -> Settings:
    return Settings(
        job_queue="local",
        document_store="local",
        local_jobs_path=str(tmp_path / "jobs.xlsx"),
        local_seed_dir=str(tmp_path / "seeds"),
        local_output_dir=str(tmp_path / "out"),
        google_token_path=tmp_path / "token.json",
        google_credentials_path=tmp_path / "credentials.json",
    )


def _write_expired_token(path) -> None:
    path.write_text(
        json.dumps(
            {
                "token": "ya29.old",
                "refresh_token": "1//old-refresh",
                "client_id": "client.apps.googleusercontent.com",
                "client_secret": "secret",
                "scopes": SCOPES,
                "expiry": "2000-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )


def _write_client(path) -> None:
    path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "client.apps.googleusercontent.com",
                    "project_id": "applyapp",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "client_secret": "secret",
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
        encoding="utf-8",
    )


def _reject_refresh(self, request):
    raise RefreshError("invalid_grant: Token has been expired or revoked.")


def test_auth_refresh_rejection_opens_browser_and_saves_a_new_token(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    _write_expired_token(settings.google_token_path)
    _write_client(settings.google_credentials_path)
    monkeypatch.setattr("applyapp.google.auth.Credentials.refresh", _reject_refresh)
    fresh = Credentials(
        token="ya29.new",
        refresh_token="1//new-refresh",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="client.apps.googleusercontent.com",
        client_secret="secret",
        scopes=SCOPES,
    )
    opened = {"called": False}

    def fake_local(flow):
        opened["called"] = True
        return fresh

    monkeypatch.setattr("applyapp.google.auth._run_local_auth", fake_local)
    creds = credentials(settings, interactive=True)
    assert opened["called"]
    assert creds.refresh_token == "1//new-refresh"
    saved = json.loads(settings.google_token_path.read_text(encoding="utf-8"))
    assert saved["refresh_token"] == "1//new-refresh"
    assert saved["token"] == "ya29.new"
    assert (settings.google_token_path.stat().st_mode & 0o777) == 0o600


def test_unattended_refresh_rejection_still_raises(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    _write_expired_token(settings.google_token_path)
    _write_client(settings.google_credentials_path)
    monkeypatch.setattr("applyapp.google.auth.Credentials.refresh", _reject_refresh)

    def fail_local(flow):
        raise AssertionError("browser sign-in opened")

    monkeypatch.setattr("applyapp.google.auth._run_local_auth", fail_local)
    with pytest.raises(RefreshError, match="invalid_grant"):
        credentials(settings)
    saved = json.loads(settings.google_token_path.read_text(encoding="utf-8"))
    assert saved["refresh_token"] == "1//old-refresh"


def test_token_health_reports_a_rejected_refresh_without_a_browser(monkeypatch, tmp_path):
    settings = _settings(tmp_path)
    _write_expired_token(settings.google_token_path)
    monkeypatch.setattr("applyapp.google.auth.Credentials.refresh", _reject_refresh)

    def fail_local(flow):
        raise AssertionError("browser sign-in opened")

    monkeypatch.setattr("applyapp.google.auth._run_local_auth", fail_local)
    code, detail = token_health(settings)
    assert code == "refresh_failed"
    assert "invalid_grant" in detail
    saved = json.loads(settings.google_token_path.read_text(encoding="utf-8"))
    assert saved["token"] == "ya29.old"


def test_doctor_inspects_the_token_without_signing_in(monkeypatch, tmp_path, capsys):
    settings = Settings(
        job_queue="google",
        document_store="local",
        google_sheet_id="sheet-id",
        local_seed_dir=str(tmp_path / "seeds"),
        local_output_dir=str(tmp_path / "out"),
        google_credentials_path=tmp_path / "credentials.json",
        google_token_path=tmp_path / "token.json",
    )
    (tmp_path / "seeds").mkdir()
    (tmp_path / "out").mkdir()
    monkeypatch.setattr(
        "applyapp.cli.token_health",
        lambda _settings: ("refresh_failed", "Token refresh failed. (invalid_grant)"),
    )

    def fail_credentials(*_args, **_kwargs):
        raise AssertionError("doctor opened a browser")

    monkeypatch.setattr("applyapp.cli.credentials", fail_credentials)
    assert _doctor(settings) == 1
    assert "invalid_grant" in capsys.readouterr().out


def test_auth_command_requests_interactive_sign_in(monkeypatch, capsys):
    seen = {}

    def fake_credentials(settings, interactive=False):
        seen["interactive"] = interactive

    monkeypatch.setattr("applyapp.cli.get_settings", lambda: Settings(job_queue="local", document_store="local"))
    monkeypatch.setattr("applyapp.cli.credentials", fake_credentials)
    assert main(["auth"]) == 0
    assert seen["interactive"] is True
    assert "Google token saved" in capsys.readouterr().out
