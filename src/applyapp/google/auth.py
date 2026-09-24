"""Google OAuth for a Desktop client.

`credentials.json` is the downloaded Desktop OAuth client (gitignored).
`token.json` is the user's refresh token after `applyapp auth`. While the Cloud
project stays in Testing, Google expires that refresh token after ~7 days —
publish the consent screen for unattended 7am runs.

`token_health` is for `applyapp doctor`: inspect/refresh without opening a browser.
`credentials()` will open a browser if there is no usable token (first run only).
"""

import re
import subprocess
import webbrowser
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from applyapp.config import Settings, tighten_private_file, write_private_text
from applyapp.errors import redact_secrets

# Drive is the full-file scope because seed and output folders are chosen by URL.
# token.json can therefore read and change any Drive file that Google account can
# open. It is written so only this user can read it, and it must stay out of git.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]
_GOOGLE_ID = re.compile(r"[A-Za-z0-9_-]{8,}")


def parse_google_id(value: str) -> str:
    """Accept a Docs/Drive/Sheets URL or a bare ID. Empty when missing or not an id.

    Free-form text is rejected so a folder value cannot change the Drive query.
    """
    value = value.strip()
    if not value:
        return ""
    for pattern in (
        r"/spreadsheets/d/([A-Za-z0-9_-]+)",
        r"/folders/([A-Za-z0-9_-]+)",
        r"/document/d/([A-Za-z0-9_-]+)",
        r"[?&]id=([A-Za-z0-9_-]+)",
    ):
        match = re.search(pattern, value)
        if match and _GOOGLE_ID.fullmatch(match.group(1)):
            return match.group(1)
    if _GOOGLE_ID.fullmatch(value):
        return value
    return ""


def token_health(settings: Settings) -> tuple[str, str]:
    """Inspect the saved OAuth token without opening a browser.

    Returns (code, detail) where code is ok, missing, needs_auth, or refresh_failed.
    """
    token_path = Path(settings.google_token_path)
    if not token_path.exists():
        return "missing", f"No token at {token_path}. Run `python -m applyapp auth`."
    tighten_private_file(token_path)
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds.valid:
        return "ok", "Google token is valid."
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            write_private_text(token_path, creds.to_json())
            return "ok", "Google token refreshed."
        except Exception as exc:
            detail = redact_secrets(str(exc))
            return (
                "refresh_failed",
                "Token refresh failed. If the OAuth app is still in Testing, "
                f"Google expires refresh tokens after 7 days. Re-run `python -m applyapp auth`. ({detail})",
            )
    return "needs_auth", "Google token is missing a refresh token. Run `python -m applyapp auth`."


def credentials(settings: Settings) -> Credentials:
    creds_path = Path(settings.google_credentials_path)
    token_path = Path(settings.google_token_path)
    tighten_private_file(creds_path)
    tighten_private_file(token_path)
    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        write_private_text(token_path, creds.to_json())
        return creds
    if not creds_path.exists():
        raise RuntimeError(
            f"Missing Google OAuth client file at {creds_path}. "
            "Download a Desktop app OAuth client as credentials.json."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = _run_local_auth(flow)
    write_private_text(token_path, creds.to_json())
    return creds


def _run_local_auth(flow: InstalledAppFlow) -> Credentials:
    """Localhost OAuth callback. Also print the URL because some environments
    (Cursor's agent terminal) cannot open a browser window."""
    original_open = webbrowser.open

    def open_url(url: str, new: int = 0, autoraise: bool = True) -> bool:
        print("\nAuthorize ApplyApp in your browser. If a window did not open, paste this URL:\n")
        print(url)
        print()
        try:
            subprocess.run(["/usr/bin/open", url], check=False)
        except OSError:
            original_open(url, new=new, autoraise=autoraise)
        return True

    webbrowser.open = open_url  # type: ignore[method-assign]
    try:
        return flow.run_local_server(
            port=0,
            open_browser=True,
            access_type="offline",
            prompt="consent",
            authorization_prompt_message="Waiting for Google sign-in at:\n{url}\n",
        )
    finally:
        webbrowser.open = original_open  # type: ignore[method-assign]


def sheets_service(settings: Settings):
    return build("sheets", "v4", credentials=credentials(settings), cache_discovery=False)


def drive_service(settings: Settings):
    return build("drive", "v3", credentials=credentials(settings), cache_discovery=False)


def docs_service(settings: Settings):
    return build("docs", "v1", credentials=credentials(settings), cache_discovery=False)
