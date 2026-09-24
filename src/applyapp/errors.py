"""Turn exceptions into a single queue Error cell.

Desktop/LaunchAgent users never see a Cursor traceback. Flatten cause/context
(providers often wrap the useful message) and cap at 500 characters so the
Sheet cell, and the jobs.xlsx cell, stay a single readable line.
"""

from __future__ import annotations


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
    return " | ".join(chunks)[:500]
