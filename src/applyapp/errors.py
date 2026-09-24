"""Turn exceptions into a single queue Error cell.

Desktop/LaunchAgent users never see a Cursor traceback. Flatten cause/context
(providers often wrap the useful message) and cap at 500 characters so the
Sheet cell, and the jobs.xlsx cell, stay a single readable line. Provider
errors sometimes echo an API key or bearer token; those are stripped first.
"""

from __future__ import annotations

import re

_SECRET = re.compile(
    r"sk-ant-[A-Za-z0-9_-]+"
    r"|sk-[A-Za-z0-9_-]{10,}"
    r"|ya29\.[A-Za-z0-9_.-]+"
    r"|1//[A-Za-z0-9_-]+"
    r"|Bearer\s+\S+"
    r"|(api[_-]?key|access_token|refresh_token|client_secret|authorization)"
    r"(['\"\s:=]+)[^\s,'\"}&]+",
    re.IGNORECASE,
)


def redact_secrets(text: str) -> str:
    """Replace API keys and OAuth tokens with a placeholder."""
    return _SECRET.sub("[redacted]", text)


def error_message(exc: BaseException) -> str:
    """Flatten an exception chain into one line for the Error column."""
    chunks: list[str] = []
    current: BaseException | None = exc
    seen = 0
    while current is not None and seen < 4:
        text = " ".join(str(current).split()) or type(current).__name__
        if text not in chunks:
            chunks.append(text)
        current = current.__cause__ or current.__context__
        seen += 1
    return redact_secrets(" | ".join(chunks))[:500]
