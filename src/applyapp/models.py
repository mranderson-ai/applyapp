"""Pydantic shapes: queue rows, model structured output, and document block kinds.

Each LLM step is asked to return JSON matching these models (`with_structured_output`),
whichever provider that step uses. That keeps analyze / write / critique / format
from emitting free-form prose we cannot write into a Doc or .docx. `JobRow` stores
0-based column indexes so later writes hit the headers ingest discovered. The
Sheet and jobs.xlsx share that mapping.
"""

import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class JobRow(BaseModel):
    """One application queue row plus the column indexes used to write back."""

    sheet_row: int
    job_url: str
    company: str = ""
    role: str = ""
    # Full job description pasted by hand when the page cannot be read.
    posting_text: str = ""
    status: str = ""
    processed_at: str = ""
    output_folder_url: str = ""
    error: str = ""
    # Column indexes are None when that header is absent from the Sheet.
    resume_col: int | None = None
    cover_col: int | None = None
    status_col: int | None = None
    error_col: int | None = None
    output_col: int | None = None
    processed_col: int | None = None
    company_col: int | None = None
    role_col: int | None = None


class JobAnalysis(BaseModel):
    """Posting vs seeds. `gaps_do_not_fabricate` is the anti-hallucination list."""

    company: str
    role_title: str
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    keywords_for_ats: list[str] = Field(default_factory=list)
    overlap_with_seeds: list[str] = Field(default_factory=list)
    gaps_do_not_fabricate: list[str] = Field(default_factory=list)
    posting_tone: str = ""
    summary: str = ""


class TailoredDocument(BaseModel):
    """Resume or cover letter draft before typesetting."""

    title: str
    full_text: str
    grounded_claims: list[str] = Field(default_factory=list)
    omitted_requirements: list[str] = Field(
        default_factory=list,
        description="Job requirements not supported by seed documents, left out on purpose.",
    )


class Critique(BaseModel):
    """Critic pass. Either boolean can fail and send the writer around again."""

    resume_pass: bool
    cover_letter_pass: bool
    grammar_notes: str = ""
    accuracy_notes: str = ""
    relevance_notes: str = ""
    tone_notes: str = ""
    resume_feedback: str = ""
    cover_letter_feedback: str = ""


# These kinds are the only visual vocabulary Google Docs styling understands.
BlockKind = Literal[
    "name",
    "contact",
    "target_title",
    "section",
    "job_header",
    "meta",
    "paragraph",
    "bullet",
    "spacer",
]


class DocBlock(BaseModel):
    """One paragraph in the typesetter schema. `kind` picks a style in design.py."""

    kind: BlockKind
    text: str = ""


class FormattedDocument(BaseModel):
    blocks: list[DocBlock] = Field(default_factory=list)

    @field_validator("blocks", mode="before")
    @classmethod
    def _blocks_may_arrive_as_json(cls, value: object) -> object:
        """Sonnet 5 sometimes returns the block list as a JSON string."""
        if not isinstance(value, str):
            return value
        parsed = json.loads(value)
        if isinstance(parsed, dict) and "blocks" in parsed:
            return parsed["blocks"]
        return parsed
