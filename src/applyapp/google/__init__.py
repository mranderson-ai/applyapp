"""Google API helpers: OAuth, Sheets, Drive, Docs.

Used when JOB_QUEUE or DOCUMENT_STORE is `google`. A fully local run does not
need these. Keep Drive/Docs/Sheets tokens in one desktop OAuth client. Scopes
are full spreadsheets + drive + documents because we both read seeds and write
output Docs. `parse_google_id` accepts a full URL or a raw ID so `.env` can store either.
"""

from applyapp.google.auth import (
    credentials,
    docs_service,
    drive_service,
    parse_google_id,
    sheets_service,
)

__all__ = [
    "credentials",
    "docs_service",
    "drive_service",
    "parse_google_id",
    "sheets_service",
]
