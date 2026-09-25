"""Where source files are read and where finished documents are written.

`google` is Drive, the default: seed Docs and styled Google Docs out.
`local` reads seeds from LOCAL_SEED_DIR and agent project docs from
LOCAL_AGENT_DOCS_DIR, then writes formatted .docx files into LOCAL_OUTPUT_DIR.
Seeds are the applicant's writings and prior resumes. Agent project docs are
the optimization paper, the document design spec, and Job Roles. The job queue
is separate (`JOB_QUEUE`, Sheet or jobs.xlsx). Both stores return the same
file dicts (`name`, `parents`, `text`) and URL strings the queue can store.
"""

import logging
from pathlib import Path

from applyapp.config import Settings
from applyapp.docx_format import write_plain_docx, write_styled_docx
from applyapp.google import drive as gdrive

STORES = ("google", "local")
logger = logging.getLogger(__name__)


def list_seed_documents(settings: Settings) -> list[dict]:
    """Every seed file with extracted text, regardless of store."""
    store = _store(settings)
    if store == "local":
        return _local_seeds(settings)
    return gdrive.list_seed_documents(settings)


def list_agent_documents(settings: Settings) -> list[dict]:
    """Optimization paper, document design, and Job Roles. Empty when that folder is unset."""
    store = _store(settings)
    if store == "local":
        raw = settings.local_agent_docs_dir.strip()
        if not raw:
            return []
        return _local_files(Path(raw).expanduser().resolve(), "LOCAL_AGENT_DOCS_DIR")
    folder = settings.google_agent_docs_folder_id.strip()
    if not folder:
        return []
    return gdrive.list_folder_documents(settings, folder, "GOOGLE_AGENT_DOCS_FOLDER_ID")


def list_context_documents(settings: Settings) -> list[dict]:
    """Seeds plus agent project docs. The caller classifies each file."""
    return list_seed_documents(settings) + list_agent_documents(settings)


def create_output_folder(settings: Settings, name: str) -> tuple[str, str]:
    """Return `(folder_id, url)`. Local ids are absolute paths."""
    store = _store(settings)
    if store == "local":
        folder = _output_root(settings) / gdrive.slug(name)
        folder.mkdir(parents=True, exist_ok=True)
        return str(folder), folder.resolve().as_uri()
    return gdrive.create_output_folder(settings, name)


def create_styled_doc(settings: Settings, folder_id: str, title: str, blocks: list[dict]) -> str:
    """Write a styled Google Doc, or a formatted .docx with the same block tree."""
    if _store(settings) == "local":
        path = _local_path(settings, folder_id, title)
        write_styled_docx(path, blocks)
        return path.resolve().as_uri()
    return gdrive.create_styled_doc(settings, folder_id, title, blocks)


def create_text_doc(settings: Settings, folder_id: str, title: str, body: str) -> str:
    """Write a plain Google Doc, or a .docx (QA notes)."""
    if _store(settings) == "local":
        path = _local_path(settings, folder_id, title)
        write_plain_docx(path, body.strip() + "\n")
        return path.resolve().as_uri()
    return gdrive.create_text_doc(settings, folder_id, title, body)


def storage_checks(settings: Settings) -> list[tuple[str, bool, str]]:
    """Doctor lines for the document store. The Sheet queue is checked separately."""
    store = settings.document_store.strip().lower() or "google"
    if store not in STORES:
        return [("DOCUMENT_STORE", False, f"must be google or local, not {store!r}")]
    if store == "local":
        seed = settings.local_seed_dir.strip()
        output = settings.local_output_dir.strip()
        seed_ok = bool(seed) and Path(seed).expanduser().is_dir()
        docs = settings.local_agent_docs_dir.strip()
        docs_ok = True if not docs else Path(docs).expanduser().is_dir()
        return [
            ("DOCUMENT_STORE", True, "local"),
            ("LOCAL_SEED_DIR", seed_ok, seed or "missing"),
            (
                "LOCAL_AGENT_DOCS_DIR",
                docs_ok,
                docs or "using the copies shipped with ApplyApp",
            ),
            ("LOCAL_OUTPUT_DIR", bool(output), output or "missing"),
        ]
    return [
        ("DOCUMENT_STORE", True, "google"),
        ("GOOGLE_SEED_FOLDER_ID", bool(settings.google_seed_folder_id), ""),
        (
            "GOOGLE_AGENT_DOCS_FOLDER_ID",
            True,
            settings.google_agent_docs_folder_id or "using the copies shipped with ApplyApp",
        ),
        ("GOOGLE_OUTPUT_FOLDER_ID", bool(settings.google_output_folder_id), ""),
    ]


def storage_errors(settings: Settings) -> list[str]:
    """Names of document-store checks that failed."""
    return [name for name, passed, _detail in storage_checks(settings) if not passed]


def _store(settings: Settings) -> str:
    store = settings.document_store.strip().lower() or "google"
    if store not in STORES:
        raise RuntimeError(f"DOCUMENT_STORE must be google or local, not {store!r}.")
    return store


def _local_seeds(settings: Settings) -> list[dict]:
    root = Path(settings.local_seed_dir).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError(f"LOCAL_SEED_DIR is not a directory: {root}")
    return _local_files(root, "LOCAL_SEED_DIR")


def _local_files(root: Path, label: str) -> list[dict]:
    if not root.is_dir():
        raise RuntimeError(f"{label} is not a directory: {root}")
    loaded: list[dict] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.name.startswith(".")):
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            logger.warning("Skipping %s because it is outside %s", path.name, label)
            continue
        if resolved.stat().st_size > gdrive.MAX_SEED_BYTES:
            logger.warning("Skipping %s because it is larger than the file limit", path.name)
            continue
        parents = list(path.relative_to(root).parent.parts)
        if parents == ["."]:
            parents = []
        loaded.append(
            {
                "name": path.name,
                "parents": parents,
                "text": gdrive.text_from_bytes(path.name, resolved.read_bytes()),
            }
        )
    return loaded


def _output_root(settings: Settings) -> Path:
    raw = settings.local_output_dir.strip()
    if not raw:
        raise RuntimeError("LOCAL_OUTPUT_DIR is missing.")
    return Path(raw).expanduser().resolve()


def _local_path(settings: Settings, folder_id: str, title: str) -> Path:
    """Finished files stay inside LOCAL_OUTPUT_DIR, even if a title tries to leave it."""
    root = _output_root(settings)
    folder = Path(folder_id).expanduser().resolve()
    path = (folder / f"{gdrive.slug(title)}.docx").resolve()
    if not folder.is_relative_to(root) or not path.is_relative_to(root):
        raise RuntimeError("Refusing to write outside LOCAL_OUTPUT_DIR.")
    return path
