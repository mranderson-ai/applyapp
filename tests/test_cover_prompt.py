from applyapp.llm import COVER_LETTER_SYSTEM, CRITIQUE_SYSTEM
from applyapp.models import JobRow
from applyapp.nodes import _generation_prompt
from applyapp.seeds import ROLE_ATS, ROLE_DESIGN, ROLE_FACTS, ROLE_PRIOR, ROLE_VOICE


def _state() -> dict:
    return {
        "job": JobRow(sheet_row=2, job_url="https://jobs.example.com/role"),
        "analysis": {"company": "Northwind", "role_title": "Partner Engineer"},
        "posting_text": "Build partner tools.",
        "posting_title": "Partner Engineer",
        "seed_docs": [
            {
                "name": "Resume & Cover Letter Optimization Paper.md",
                "path": "Agent Project Docs / Resume & Cover Letter Optimization Paper.md",
                "role": ROLE_ATS,
                "text": "PAPER_MARKER cover-letter craft",
            },
            {
                "name": "Accomplishments OPTIMIZED.md",
                "path": "Accomplishments OPTIMIZED.md",
                "role": ROLE_FACTS,
                "text": "FACT_MARKER shipped the partner desk",
            },
            {
                "name": "Human Writings.md",
                "path": "Human Writings.md",
                "role": ROLE_VOICE,
                "text": "VOICE_MARKER Best,",
            },
            {
                "name": "Example Resume.md",
                "path": "Example Resume.md",
                "role": ROLE_PRIOR,
                "text": "PRIOR_MARKER old resume",
            },
            {
                "name": "ApplyApp Document Design.md",
                "path": "Agent Project Docs / ApplyApp Document Design.md",
                "role": ROLE_DESIGN,
                "text": "DESIGN_MARKER navy header",
            },
        ],
    }


def test_cover_letter_sends_the_paper_as_a_project_doc():
    prompt = _generation_prompt(_state(), "cover letter")
    project, _, seeds = prompt.partition("SEED DOCUMENTS:")
    assert "AGENT PROJECT DOCS:" in project
    assert "PAPER_MARKER" in project
    assert "not a biography" in project
    assert "PAPER_MARKER" not in seeds
    assert "VOICE_MARKER" in seeds
    assert "FACT_MARKER" in seeds
    assert "PRIOR_MARKER" in seeds
    assert "VOICE_MARKER" not in project
    assert "FACT_MARKER" not in project
    assert "DESIGN_MARKER" not in prompt


def test_resume_prompt_still_gets_the_paper_without_voice():
    prompt = _generation_prompt(_state(), "resume")
    assert "PAPER_MARKER" in prompt
    assert "FACT_MARKER" in prompt
    assert "PRIOR_MARKER" in prompt
    assert "VOICE_MARKER" not in prompt
    assert "DESIGN_MARKER" not in prompt


def test_cover_and_critique_follow_the_paper_and_match_diction():
    for text in (COVER_LETTER_SYSTEM, CRITIQUE_SYSTEM):
        assert "cover-letter craft" in text
        assert "application materials in general" in text
        assert "Human Writings" in text
        assert "diction" in text
        assert "keyword list" in text
        assert "biography" in text
    assert "like the ATS paper" not in COVER_LETTER_SYSTEM
    assert "not like the resume or the ATS paper" not in CRITIQUE_SYSTEM
