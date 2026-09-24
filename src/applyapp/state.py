"""LangGraph state for one queue row (Sheet or jobs.xlsx).

`total=False` so early nodes can return a partial dict. Keys accumulate as the
graph runs: posting + seeds → analysis → drafts → critique → formatted blocks →
output URLs (Google Docs or local .docx). The compiled graph merges each node's
returned dict into this state.
"""

from typing import Any, TypedDict

from applyapp.models import JobRow


class JobState(TypedDict, total=False):
    job: JobRow
    posting_text: str
    posting_title: str
    posting_from_paste: bool
    seed_docs: list[dict[str, str]]
    seed_skipped: list[str]
    analysis: dict[str, Any]
    resume: dict[str, Any]
    cover_letter: dict[str, Any]
    critique: dict[str, Any]
    formatted_resume: dict[str, Any]
    formatted_cover_letter: dict[str, Any]
    revision_count: int
    output_folder_id: str
    output_folder_url: str
    resume_doc_url: str
    cover_letter_doc_url: str
    qa_doc_url: str
    error: str
