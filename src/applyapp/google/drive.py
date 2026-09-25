"""Drive seed ingest and output Doc creation.

`documents.py` calls this when DOCUMENT_STORE=google. `text_from_bytes` is also
how a local seed folder reads PDF, Word, and Excel files.

Seeds are walked recursively. Native Google files are exported; binaries are
downloaded. The accomplishments xlsx uses INDEX/MATCH formulas; `data_only=True`
is empty unless Excel cached values, so `_xlsx_eval` interprets a small formula
subset. Output Docs are created empty then `batchUpdate`'d with styled requests
from docs_format.py — we never upload DOCX, so ATS parsers see real headings.
"""

import io
import re
import zipfile
from pathlib import Path
from typing import Any

from googleapiclient.http import MediaIoBaseDownload
from openpyxl import load_workbook
from pypdf import PdfReader

from applyapp.config import Settings
from applyapp.docs_format import build_styled_doc_requests
from applyapp.google.auth import docs_service, drive_service, parse_google_id

GOOGLE_DOC = "application/vnd.google-apps.document"
GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
FOLDER = "application/vnd.google-apps.folder"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
}


MAX_SEED_BYTES = 8_000_000
_MAX_XLSX_ROWS = 10_000
_MAX_XLSX_COLS = 64
_MAX_FORMULA_DEPTH = 32


def _folder_id(value: str, label: str) -> str:
    raw = value.strip()
    folder_id = parse_google_id(raw)
    if folder_id:
        return folder_id
    if raw:
        raise RuntimeError(f"{label} must be a Google URL or file id.")
    raise RuntimeError(f"{label} is missing.")


def list_seed_documents(settings: Settings) -> list[dict[str, Any]]:
    """Every non-folder file under the seed folder, with extracted `text`."""
    return list_folder_documents(settings, settings.google_seed_folder_id, "GOOGLE_SEED_FOLDER_ID")


def list_folder_documents(settings: Settings, folder_value: str, label: str) -> list[dict[str, Any]]:
    """Every non-folder file under one Drive folder, with extracted `text`."""
    drive = drive_service(settings)
    folder_id = _folder_id(folder_value, label)
    files = _iter_files(drive, folder_id, parents=[])
    loaded: list[dict[str, Any]] = []
    for file in files:
        text = _read_file(drive, file)
        loaded.append({**file, "text": text})
    return loaded


def create_output_folder(settings: Settings, name: str) -> tuple[str, str]:
    drive = drive_service(settings)
    parent = _folder_id(settings.google_output_folder_id, "GOOGLE_OUTPUT_FOLDER_ID")
    created = (
        drive.files()
        .create(
            body={"name": name, "mimeType": FOLDER, "parents": [parent]},
            fields="id, webViewLink",
        )
        .execute()
    )
    return created["id"], created.get("webViewLink", "")


def create_text_doc(settings: Settings, folder_id: str, title: str, body: str) -> str:
    drive = drive_service(settings)
    docs = docs_service(settings)
    created = (
        drive.files()
        .create(
            body={"name": title, "mimeType": GOOGLE_DOC, "parents": [folder_id]},
            fields="id, webViewLink",
        )
        .execute()
    )
    doc_id = created["id"]
    text = body.strip() + "\n"
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": text}}]},
    ).execute()
    return created.get("webViewLink", "")


def create_styled_doc(settings: Settings, folder_id: str, title: str, blocks: list[dict]) -> str:
    """Create a Google Doc and apply ApplyApp styles. Returns the webViewLink."""
    drive = drive_service(settings)
    docs = docs_service(settings)
    created = (
        drive.files()
        .create(
            body={"name": title, "mimeType": GOOGLE_DOC, "parents": [folder_id]},
            fields="id, webViewLink",
        )
        .execute()
    )
    doc_id = created["id"]
    requests = build_styled_doc_requests(blocks)
    if requests:
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    return created.get("webViewLink", "")


def replace_styled_doc(settings: Settings, doc_id: str, blocks: list[dict]) -> None:
    """Overwrite an existing Doc in place. Kept for a future 'reformat' command;
    the unattended pipeline always creates new Docs so Sheet links stay append-only."""
    docs = docs_service(settings)
    doc = docs.documents().get(documentId=doc_id).execute()
    end_index = doc.get("body", {}).get("content", [{}])[-1].get("endIndex") or 2
    requests: list[dict[str, Any]] = []
    if end_index > 2:
        requests.append(
            {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index - 1}}}
        )
    requests.extend(build_styled_doc_requests(blocks))
    if requests:
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()


def slug(value: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", value).strip()
    cleaned = re.sub(r"[-\s]+", "-", cleaned)
    return cleaned[:60] or "untitled"


def _iter_files(drive, folder_id: str, parents: list[str]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    page_token = None
    query = f"'{folder_id}' in parents and trashed = false"
    while True:
        response = (
            drive.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token,
                pageSize=100,
            )
            .execute()
        )
        batch = response.get("files") or []
        page_token = response.get("nextPageToken")
        for file in batch:
            if file.get("mimeType") == FOLDER:
                collected.extend(_iter_files(drive, file["id"], parents + [file["name"]]))
            else:
                collected.append({**file, "parents": parents})
        if not page_token:
            break
    return collected


def text_from_bytes(name: str, data: bytes) -> str:
    """Extract text from a local file. Google-native Docs and Sheets are not in this path."""
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(data)
    if suffix == ".xlsx":
        return _xlsx_text(data) if _zip_is_safe(data) else ""
    if suffix == ".docx":
        return _docx_text(data) if _zip_is_safe(data) else ""
    if suffix in {".txt", ".md", ".markdown", ".csv", ".json"}:
        return data.decode("utf-8", errors="replace")
    return ""


def _read_file(drive, file: dict[str, Any]) -> str:
    mime = file.get("mimeType", "")
    file_id = file["id"]
    if mime == GOOGLE_DOC:
        exported = drive.files().export(fileId=file_id, mimeType="text/plain").execute()
        return _as_text(exported)
    if mime == GOOGLE_SHEET:
        exported = drive.files().export(fileId=file_id, mimeType="text/csv").execute()
        return f"### Tab: (csv export)\n{_as_text(exported)}"
    if mime == "application/pdf":
        return _pdf_text(_download_bytes(drive, file_id))
    if mime == XLSX:
        data = _download_bytes(drive, file_id)
        return _xlsx_text(data) if _zip_is_safe(data) else ""
    if mime == DOCX:
        data = _download_bytes(drive, file_id)
        return _docx_text(data) if _zip_is_safe(data) else ""
    if mime in TEXT_TYPES or mime.startswith("text/"):
        return _download_bytes(drive, file_id).decode("utf-8", errors="replace")
    return ""


def _download_bytes(drive, file_id: str) -> bytes:
    request = drive.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
        if buffer.tell() > MAX_SEED_BYTES:
            raise RuntimeError("Seed file is too large to load.")
    return buffer.getvalue()


def _as_text(exported: bytes | str) -> str:
    if isinstance(exported, bytes):
        text = exported.decode("utf-8", errors="replace")
    else:
        text = str(exported)
    return text[:MAX_SEED_BYTES]


def _zip_is_safe(data: bytes) -> bool:
    """Reject archives whose uncompressed size is far larger than the file on disk."""
    if len(data) > MAX_SEED_BYTES:
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            total = 0
            for info in archive.infolist():
                total += info.file_size
                if info.file_size > 32_000_000 or total > 32_000_000:
                    return False
    except zipfile.BadZipFile:
        return False
    return True


def _pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _xlsx_text(data: bytes) -> str:
    workbook = load_workbook(io.BytesIO(data), data_only=False, read_only=True)
    try:
        grids = {sheet.title: _xlsx_grid(sheet) for sheet in workbook.worksheets}
        titles = [sheet.title for sheet in workbook.worksheets]
    finally:
        workbook.close()

    cache: dict[tuple[str, int, int], Any] = {}
    blocks: list[str] = []
    for title in titles:
        rows: list[str] = []
        grid = grids[title]
        for r_idx, raw_row in enumerate(grid):
            cells = [
                _xlsx_display(grids, title, r_idx, c_idx, cache)
                for c_idx in range(len(raw_row))
            ]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            blocks.append(f"### Tab: {title}\n" + "\n".join(rows))
    return "\n\n".join(blocks)


def _xlsx_grid(sheet) -> list[list[Any]]:
    """Cap rows and columns so a hostile workbook cannot expand without limit.

    Trailing empty cells are dropped. A small sheet must not grow to the cap.
    """
    rows: list[list[Any]] = []
    for row in sheet.iter_rows(max_col=_MAX_XLSX_COLS):
        values = [cell.value for cell in row]
        while values and values[-1] in (None, ""):
            values.pop()
        rows.append(values)
        if len(rows) >= _MAX_XLSX_ROWS:
            break
    return rows


class _FormulaError(Exception):
    pass


def _xlsx_display(
    grids: dict[str, list[list[Any]]],
    sheet: str,
    row: int,
    col: int,
    cache: dict[tuple[str, int, int], Any],
    stack: tuple[tuple[str, int, int], ...] = (),
) -> str:
    value = _xlsx_eval(grids, sheet, row, col, cache, stack)
    if value is None or value == "":
        return ""
    return str(value).strip()


def _xlsx_eval(
    grids: dict[str, list[list[Any]]],
    sheet: str,
    row: int,
    col: int,
    cache: dict[tuple[str, int, int], Any],
    stack: tuple[tuple[str, int, int], ...] = (),
) -> Any:
    """Evaluate one cell. Formulas are resolved so role tabs stay consistent with Master."""
    key = (sheet, row, col)
    if len(stack) > _MAX_FORMULA_DEPTH:
        raise _FormulaError("formula too deep")
    if key in cache:
        return cache[key]
    if key in stack:
        raise _FormulaError("circular reference")
    grid = grids.get(sheet)
    if grid is None or row >= len(grid) or col >= len(grid[row]):
        cache[key] = ""
        return ""
    raw = grid[row][col]
    if raw is None:
        cache[key] = ""
        return ""
    if not (isinstance(raw, str) and raw.startswith("=")):
        cache[key] = raw
        return raw
    try:
        value = _eval_expr(raw[1:], grids, sheet, row, col, cache, stack + (key,))
    except _FormulaError:
        value = ""
    cache[key] = value
    return value


def _eval_expr(
    expr: str,
    grids: dict[str, list[list[Any]]],
    sheet: str,
    row: int,
    col: int,
    cache: dict[tuple[str, int, int], Any],
    stack: tuple[tuple[str, int, int], ...],
) -> Any:
    expr = expr.strip()
    if not expr:
        return ""
    while len(expr) >= 2 and expr.startswith("(") and expr.endswith(")") and _balanced(expr[1:-1]):
        expr = expr[1:-1].strip()

    upper = expr.upper()
    for name, fn in (("IFERROR", _eval_iferror), ("INDEX", _eval_index), ("MATCH", _eval_match)):
        if upper.startswith(name + "(") and expr.endswith(")"):
            args = _split_args(expr[len(name) + 1 : -1])
            return fn(args, grids, sheet, row, col, cache, stack)

    if len(expr) >= 2 and expr[0] == '"' and expr[-1] == '"':
        return expr[1:-1].replace('""', '"')
    try:
        if "." in expr:
            return float(expr)
        return int(expr)
    except ValueError:
        pass
    return _eval_ref(expr, grids, sheet, row, col, cache, stack)


def _eval_iferror(
    args: list[str],
    grids: dict[str, list[list[Any]]],
    sheet: str,
    row: int,
    col: int,
    cache: dict[tuple[str, int, int], Any],
    stack: tuple[tuple[str, int, int], ...],
) -> Any:
    fallback = args[1] if len(args) > 1 else '""'
    try:
        return _eval_expr(args[0], grids, sheet, row, col, cache, stack)
    except _FormulaError:
        return _eval_expr(fallback, grids, sheet, row, col, cache, stack)


def _eval_index(
    args: list[str],
    grids: dict[str, list[list[Any]]],
    sheet: str,
    row: int,
    col: int,
    cache: dict[tuple[str, int, int], Any],
    stack: tuple[tuple[str, int, int], ...],
) -> Any:
    if len(args) < 2:
        raise _FormulaError("INDEX needs a range and row")
    target_sheet, start_col, end_col, start_row, end_row = _parse_range(args[0], sheet)
    row_num = _eval_expr(args[1], grids, sheet, row, col, cache, stack)
    try:
        offset = int(row_num) - 1
    except (TypeError, ValueError):
        raise _FormulaError("INDEX row is not a number") from None
    col_num = 1
    if len(args) > 2 and args[2].strip():
        col_val = _eval_expr(args[2], grids, sheet, row, col, cache, stack)
        try:
            col_num = int(col_val)
        except (TypeError, ValueError):
            raise _FormulaError("INDEX column is not a number") from None
    abs_row = start_row + offset
    abs_col = start_col + col_num - 1
    if abs_col > end_col or abs_row > end_row or abs_row < start_row or abs_col < start_col:
        raise _FormulaError("INDEX out of range")
    return _xlsx_eval(grids, target_sheet, abs_row, abs_col, cache, stack)


def _eval_match(
    args: list[str],
    grids: dict[str, list[list[Any]]],
    sheet: str,
    row: int,
    col: int,
    cache: dict[tuple[str, int, int], Any],
    stack: tuple[tuple[str, int, int], ...],
) -> int:
    if len(args) < 2:
        raise _FormulaError("MATCH needs a lookup value and range")
    lookup = _norm_match(_eval_expr(args[0], grids, sheet, row, col, cache, stack))
    target_sheet, start_col, end_col, start_row, end_row = _parse_range(args[1], sheet)
    grid = grids.get(target_sheet) or []
    last = min(end_row, len(grid) - 1)
    for r_idx in range(start_row, last + 1):
        for c_idx in range(start_col, end_col + 1):
            if c_idx >= len(grid[r_idx]):
                continue
            candidate = _norm_match(_xlsx_eval(grids, target_sheet, r_idx, c_idx, cache, stack))
            if candidate == lookup:
                return r_idx - start_row + 1
    raise _FormulaError("MATCH not found")


def _eval_ref(
    expr: str,
    grids: dict[str, list[list[Any]]],
    sheet: str,
    row: int,
    col: int,
    cache: dict[tuple[str, int, int], Any],
    stack: tuple[tuple[str, int, int], ...],
) -> Any:
    match = _CELL_REF.match(expr.strip())
    if not match:
        raise _FormulaError(f"unsupported formula: {expr}")
    target_sheet = match.group(1) or match.group(2) or sheet
    target_col = _col_index(match.group(3)) - 1
    target_row = int(match.group(4).replace("$", "")) - 1
    return _xlsx_eval(grids, target_sheet, target_row, target_col, cache, stack)


_CELL_REF = re.compile(r"^(?:(?:'([^']+)'|([A-Za-z0-9._]+))!)?\$?([A-Z]+)\$?(\d+)$", re.I)
_COL_RANGE = re.compile(r"^(?:'([^']+)'|([A-Za-z0-9._]+))!\$?([A-Z]+):\$?([A-Z]+)$", re.I)
_CELL_RANGE = re.compile(
    r"^(?:'([^']+)'|([A-Za-z0-9._]+))!\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)$",
    re.I,
)


def _parse_range(expr: str, default_sheet: str) -> tuple[str, int, int, int, int]:
    expr = expr.strip()
    match = _COL_RANGE.match(expr)
    if match:
        sheet = match.group(1) or match.group(2) or default_sheet
        start_col = _col_index(match.group(3)) - 1
        end_col = _col_index(match.group(4)) - 1
        return sheet, start_col, end_col, 0, 1_048_575
    match = _CELL_RANGE.match(expr)
    if match:
        sheet = match.group(1) or match.group(2) or default_sheet
        start_col = _col_index(match.group(3)) - 1
        start_row = int(match.group(4)) - 1
        end_col = _col_index(match.group(5)) - 1
        end_row = int(match.group(6)) - 1
        return sheet, start_col, end_col, start_row, end_row
    match = _CELL_REF.match(expr)
    if match:
        sheet = match.group(1) or match.group(2) or default_sheet
        col = _col_index(match.group(3)) - 1
        row = int(match.group(4).replace("$", "")) - 1
        return sheet, col, col, row, row
    raise _FormulaError(f"unsupported range: {expr}")


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters.replace("$", "").upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def _split_args(text: str) -> list[str]:
    args: list[str] = []
    buf: list[str] = []
    depth = 0
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    buf.append(text[i + 1])
                    i += 2
                    continue
                quote = ""
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        args.append("".join(buf).strip())
    return args


def _balanced(text: str) -> bool:
    depth = 0
    quote = ""
    for i, ch in enumerate(text):
        if quote:
            if ch == quote and (i + 1 >= len(text) or text[i + 1] != quote):
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not quote


def _norm_match(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _docx_text(data: bytes) -> str:
    from docx import Document

    document = Document(io.BytesIO(data))
    parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)
