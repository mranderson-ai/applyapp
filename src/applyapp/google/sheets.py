"""Google Sheet backend for the job queue.

`queue.py` chooses Sheet vs jobs.xlsx. Header discovery lives here and is shared:
names, not column letters, because the sheet may include Organization, Level,
Resume, and Cover Letter. Status `processing` is treated as pending so a crashed
run is retried instead of stuck forever. `field_columns` is the single map of
update kwargs → columns; the Sheet turns those into A1 cells and the workbook
writes them in place.
"""

from datetime import datetime, timezone
from urllib.parse import urlparse

from applyapp.config import Settings
from applyapp.google.auth import parse_google_id, sheets_service
from applyapp.models import JobRow

URL_HEADERS = ("job postings", "job_url", "job url", "url", "link", "posting")
COMPANY_HEADERS = ("company", "employer")
ORG_HEADERS = ("organization", "org")
ROLE_HEADERS = ("role", "title", "job title")
POSTING_TEXT_HEADER = "Posting Text"
POSTING_TEXT_HEADERS = ("posting text", "job description", "pasted description")
POSTING_TEXT_NOTE = (
    "When the page cannot be read, paste the full job description here. "
    "Company must be the employer and Role must be the official title, copied exactly. "
    "Clear Status and run the row again. Leave this blank when the link can be read."
)
LEVEL_HEADERS = ("level", "seniority")
RESUME_HEADERS = ("resume",)
COVER_HEADERS = ("cover letter", "cover_letter", "coverletter")
STATUS_HEADERS = ("status",)
ERROR_HEADERS = ("error",)
OUTPUT_HEADERS = ("output_folder_url", "output", "folder")
PROCESSED_HEADERS = ("processed_at", "processed")
PENDING_STATUSES = {"", "pending", "processing"}  # processing = reclaim after a crash


def _sheet_id(settings: Settings) -> str:
    raw = settings.google_sheet_id.strip()
    sheet_id = parse_google_id(raw)
    if sheet_id:
        return sheet_id
    if raw:
        raise RuntimeError("GOOGLE_SHEET_ID must be a Google URL or file id.")
    raise RuntimeError("GOOGLE_SHEET_ID is missing.")


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def _col_index(headers: list[str], names: tuple[str, ...]) -> int | None:
    normalized = [_norm(header) for header in headers]
    for name in names:
        if name in normalized:
            return normalized.index(name)
    return None


def _a1(col_index: int, row: int) -> str:
    col = col_index + 1
    letters = ""
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


def _is_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _read_grid(settings: Settings) -> list[list[str]]:
    service = sheets_service(settings)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=_sheet_id(settings), range="A:Z")
        .execute()
    )
    return result.get("values") or []


def fetch_pending_jobs(settings: Settings) -> list[JobRow]:
    ensure_posting_text_column(settings)
    return jobs_from_grid(_read_grid(settings))


def jobs_from_grid(rows: list[list[str]]) -> list[JobRow]:
    """Pure ingest (no network) so tests can cover header mapping and pending rules."""
    if not rows:
        return []
    headers = rows[0]
    url_col = _col_index(headers, URL_HEADERS)
    company_col = _col_index(headers, COMPANY_HEADERS)
    org_col = _col_index(headers, ORG_HEADERS)
    role_col = _col_index(headers, ROLE_HEADERS)
    posting_text_col = _col_index(headers, POSTING_TEXT_HEADERS)
    level_col = _col_index(headers, LEVEL_HEADERS)
    resume_col = _col_index(headers, RESUME_HEADERS)
    cover_col = _col_index(headers, COVER_HEADERS)
    status_col = _col_index(headers, STATUS_HEADERS)
    error_col = _col_index(headers, ERROR_HEADERS)
    output_col = _col_index(headers, OUTPUT_HEADERS)
    processed_col = _col_index(headers, PROCESSED_HEADERS)

    jobs: list[JobRow] = []
    for index, row in enumerate(rows[1:], start=2):
        def cell(col: int | None) -> str:
            if col is None or col >= len(row):
                return ""
            return str(row[col]).strip()

        job_url = cell(url_col)
        if not _is_url(job_url):
            job_url = next((item.strip() for item in row if _is_url(str(item))), "")
        if not job_url:
            continue

        status = cell(status_col).lower()
        resume_link = cell(resume_col)
        cover_link = cell(cover_col)
        already_done = bool(resume_link or cover_link)
        if status_col is None:
            if already_done:
                continue
        elif status not in PENDING_STATUSES:
            continue

        company = cell(company_col) or cell(org_col)
        role = cell(role_col)
        posting_text = cell(posting_text_col)
        level = cell(level_col)
        # A pasted description uses the Role cell as the official title, so do not
        # invent one from Level when that cell is waiting for the human's title.
        if not role and level and not posting_text:
            role = f"{level} {cell(org_col)}".strip()

        jobs.append(
            JobRow(
                sheet_row=index,
                job_url=job_url,
                company=company,
                role=role,
                posting_text=posting_text,
                status=status,
                processed_at=cell(processed_col),
                output_folder_url=cell(output_col),
                error=cell(error_col),
                resume_col=resume_col,
                cover_col=cover_col,
                status_col=status_col,
                error_col=error_col,
                output_col=output_col,
                processed_col=processed_col,
                company_col=company_col,
                role_col=role_col,
            )
        )
    return jobs


def field_columns(job: JobRow) -> dict[str, int | None]:
    """Update kwargs → column index. None means that header was not on the sheet."""
    return {
        "status": job.status_col,
        "error": job.error_col,
        "output_folder_url": job.output_col,
        "processed_at": job.processed_col,
        "resume_doc_url": job.resume_col,
        "cover_letter_doc_url": job.cover_col,
        "company": job.company_col,
        "role": job.role_col,
    }


def job_field_writes(job: JobRow, changes: dict[str, str]) -> list[tuple[str, str]]:
    """Map update_job kwargs to A1 cells. Skip fields whose header was never found."""
    updates: list[tuple[str, str]] = []
    for field, col in field_columns(job).items():
        if field in changes and col is not None:
            updates.append((_a1(col, job.sheet_row), changes[field]))
    return updates


def update_job(settings: Settings, job: JobRow, **changes: str) -> JobRow:
    updated = job.model_copy(update=changes)
    updates = job_field_writes(updated, changes)

    if not updates:
        return updated

    service = sheets_service(settings)
    data = [{"range": cell, "values": [[value]]} for cell, value in updates]
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=_sheet_id(settings),
        body={"valueInputOption": "RAW", "data": data},
    ).execute()
    return updated


def posting_text_insert_at(headers: list[str]) -> int | None:
    """0-based index for a new Posting Text column, or None when it already exists.

    The column sits immediately after Role so Company, Role, and the pasted
    description stay together. Sheets that have no Role column get it appended.
    """
    if _col_index(headers, POSTING_TEXT_HEADERS) is not None:
        return None
    role_col = _col_index(headers, ROLE_HEADERS)
    if role_col is not None:
        return role_col + 1
    filled = [index for index, header in enumerate(headers) if str(header).strip()]
    return (filled[-1] + 1) if filled else 0


def ensure_posting_text_column(settings: Settings) -> None:
    """Add Posting Text to the live Sheet when the header is missing."""
    service = sheets_service(settings)
    spreadsheet_id = _sheet_id(settings)
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties",
    ).execute()
    sheets = meta.get("sheets") or []
    if not sheets:
        return
    props = sheets[0]["properties"]
    gid = props["sheetId"]
    title = props["title"].replace("'", "''")
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"'{title}'!1:1")
        .execute()
    )
    headers = (result.get("values") or [[]])[0]
    insert_at = posting_text_insert_at(headers)
    if insert_at is None:
        return
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": gid,
                            "dimension": "COLUMNS",
                            "startIndex": insert_at,
                            "endIndex": insert_at + 1,
                        },
                        "inheritFromBefore": True,
                    }
                },
                {
                    "updateCells": {
                        "range": {
                            "sheetId": gid,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": insert_at,
                            "endColumnIndex": insert_at + 1,
                        },
                        "rows": [
                            {
                                "values": [
                                    {
                                        "userEnteredValue": {"stringValue": POSTING_TEXT_HEADER},
                                        "note": POSTING_TEXT_NOTE,
                                    }
                                ]
                            }
                        ],
                        "fields": "userEnteredValue,note",
                    }
                },
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": gid,
                            "dimension": "COLUMNS",
                            "startIndex": insert_at,
                            "endIndex": insert_at + 1,
                        },
                        "properties": {"pixelSize": 360},
                        "fields": "pixelSize",
                    }
                },
            ]
        },
    ).execute()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
