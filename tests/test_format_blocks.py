from applyapp.errors import error_message
from applyapp.format_blocks import _today, cover_title_feedback, polish, resume_length_feedback, summary_opening_feedback


def test_resume_adds_summary_caps_bullets_and_middot_contact():
    blocks = polish(
        [
            {"kind": "name", "text": "ALEX RIVERA"},
            {"kind": "contact", "text": "Austin, TX | (555) 010-0100 | alex.rivera@example.com"},
            {"kind": "paragraph", "text": "A four-line summary of real experience."},
            {"kind": "section", "text": "PROFESSIONAL EXPERIENCE"},
            {"kind": "job_header", "text": "Partner Success Manager · Apr 2025 – Present"},
            {"kind": "meta", "text": "Northwind Analytics"},
            *[{"kind": "bullet", "text": f"recent-{i}"} for i in range(6)],
            {"kind": "job_header", "text": "Solutions Engineer Jan 2022 – Mar 2025"},
            *[{"kind": "bullet", "text": f"se-{i}"} for i in range(6)],
            {"kind": "job_header", "text": "Campus Ambassador Jun 2019 – Dec 2021"},
            *[{"kind": "bullet", "text": f"csm-{i}"} for i in range(4)],
            {"kind": "section", "text": "CORE COMPETENCIES"},
            {"kind": "bullet", "text": "Demos"},
            {"kind": "bullet", "text": "Analytics"},
            {"kind": "section", "text": "EDUCATION"},
            {"kind": "paragraph", "text": "Example University"},
        ],
        "resume",
    )
    kinds = [item["kind"] for item in blocks]
    assert kinds[:4] == ["name", "contact", "section", "paragraph"]
    assert blocks[0]["text"] == "Alex Rivera"
    assert " · " in blocks[1]["text"]
    assert "|" not in blocks[1]["text"]
    assert blocks[2]["text"] == "SUMMARY"
    bullets_by_role = []
    current = 0
    for item in blocks:
        if item["kind"] == "job_header":
            bullets_by_role.append(0)
            current = len(bullets_by_role) - 1
            assert "·" not in item["text"].split()[0]
        elif item["kind"] == "bullet":
            bullets_by_role[current] += 1
    assert bullets_by_role == [5, 5, 3]
    assert "SKILLS" in [item["text"] for item in blocks if item["kind"] == "section"]


def test_resume_drops_invented_title_under_the_contact_line():
    blocks = polish(
        [
            {"kind": "name", "text": "Alex Rivera"},
            {"kind": "contact", "text": "Austin, TX | alex.rivera@example.com"},
            {"kind": "target_title", "text": "Principal Partner Engineer, Analytics"},
            {"kind": "section", "text": "SUMMARY"},
            {"kind": "paragraph", "text": "A four-line summary of real experience."},
        ],
        "resume",
    )
    texts = [item["text"] for item in blocks]
    assert texts[:3] == ["Alex Rivera", texts[1], "SUMMARY"]
    assert "Principal" not in " ".join(texts)
    assert "(Analytics)" not in " ".join(
        polish(
            [
                {"kind": "name", "text": "Alex Rivera"},
                {"kind": "contact", "text": "Austin | alex.rivera@example.com"},
                {"kind": "paragraph", "text": "PARTNER ENGINEER (ANALYTICS)"},
                {"kind": "section", "text": "SUMMARY"},
                {"kind": "paragraph", "text": "A real summary."},
            ],
            "resume",
        )[i]["text"]
        for i in range(3)
    )


def test_cover_inserts_greeting_and_signoff_when_the_draft_omits_them():
    resume = polish(
        [
            {"kind": "name", "text": "Alex (Al) Rivera"},
            {"kind": "contact", "text": "Austin | a@b.com"},
            {"kind": "section", "text": "SUMMARY"},
            {"kind": "paragraph", "text": "Summary"},
        ],
        "resume",
    )
    cover = polish(
        [
            {"kind": "paragraph", "text": "September 22, 2026"},
            {"kind": "paragraph", "text": "I'm reaching out about the role."},
            {"kind": "paragraph", "text": "Worth a conversation?"},
        ],
        "cover",
        header_from=resume,
        company="Northwind",
    )
    texts = [item["text"] for item in cover]
    assert texts[2] == _today()
    assert texts[3] == "Dear Northwind Team,"
    assert texts[-2:] == ["Best,", "Alex (Al) Rivera"]
    nicknamed = polish(
        [
            {"kind": "paragraph", "text": "September 22, 2026"},
            {"kind": "paragraph", "text": "I'm reaching out about the role."},
            {"kind": "paragraph", "text": "Best,"},
            {"kind": "paragraph", "text": "Al Rivera"},
        ],
        "cover",
        header_from=resume,
        company="Northwind",
    )
    assert [item["text"] for item in nicknamed][-2:] == ["Best,", "Alex (Al) Rivera"]


def test_cover_strips_re_and_rewrites_sincerely():
    resume = polish(
        [
            {"kind": "name", "text": "Alex Rivera"},
            {"kind": "contact", "text": "Austin | alex.rivera@example.com"},
            {"kind": "section", "text": "SUMMARY"},
            {"kind": "paragraph", "text": "Summary"},
        ],
        "resume",
    )
    cover = polish(
        [
            {"kind": "paragraph", "text": "October 24, 2026"},
            {"kind": "paragraph", "text": "Northwind"},
            {"kind": "paragraph", "text": "RE: Partner role"},
            {"kind": "paragraph", "text": "Dear Hiring Manager,"},
            {"kind": "paragraph", "text": "Body of the letter."},
            {"kind": "paragraph", "text": "Sincerely,"},
            {"kind": "paragraph", "text": "Alex Rivera"},
        ],
        "cover",
        header_from=resume,
        company="Northwind",
    )
    texts = [item["text"] for item in cover]
    assert texts[0] == "Alex Rivera"
    assert " · " in texts[1]
    assert "Dear Northwind Team," in texts
    assert not any(text.startswith("RE:") for text in texts)
    assert "Sincerely," not in texts
    assert "Best," in texts


def test_summary_must_open_with_a_held_title_and_the_letter_uses_the_posting_title():
    resume = """
SUMMARY
Principal Partner Engineer with three years in analytics.
EXPERIENCE
Solutions Engineer    Jan 2022 – Mar 2025
- a
"""
    note = summary_opening_feedback(resume, "Partner Engineer, Analytics")
    assert "principal" in note
    assert summary_opening_feedback(
        resume.replace("Principal Partner Engineer", "Solutions Engineer"),
        "Partner Engineer, Analytics",
    ) == ""
    assert "parenthetical" in cover_title_feedback(
        "I'm reaching out about the Partner Engineer (Analytics) role.",
        "Partner Engineer",
    )
    assert cover_title_feedback(
        "I'm reaching out about the Partner Engineer role.",
        "Partner Engineer",
    ) == ""
    assert "seniority" in cover_title_feedback(
        "I'm reaching out about the Principal Partner Engineer role.",
        "Partner Engineer",
    )
    assert cover_title_feedback(
        "I'm reaching out about the Principal Partner Engineer role.",
        "Principal Partner Engineer",
    ) == ""
    assert cover_title_feedback(
        "I'm reaching out about the Partner Engineer (Analytics) role.",
        "Partner Engineer (Analytics)",
    ) == ""
    assert "parenthetical" in cover_title_feedback(
        "I'm reaching out about the Partner Engineer (Analytics) (Remote) role.",
        "Partner Engineer (Analytics)",
    )


def test_resume_length_feedback_flags_overlong_roles():
    note = resume_length_feedback(
        """
Partner Success Manager — Apr 2025 – Present
- a
- b
- c
- d
- e
- f
Solutions Engineer — Jan 2022 – Mar 2025
- a
- b
- c
- d
- e
- f
Campus Ambassador — Jun 2019 – Dec 2021
- a
- b
- c
- d
"""
    )
    assert "keep 5" in note
    assert "keep 3" in note


def test_error_message_is_sheet_safe():
    try:
        raise RuntimeError("credit balance is too low\nsee docs") from ValueError("inner")
    except RuntimeError as exc:
        text = error_message(exc)
    assert "credit balance is too low" in text
    assert "\n" not in text
    assert len(text) <= 500
