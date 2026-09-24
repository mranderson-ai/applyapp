from applyapp.google.sheets import job_field_writes, jobs_from_grid
from applyapp.models import JobRow

HEADERS = [
    "Job Postings",
    "Company",
    "Role",
    "Organization",
    "Level",
    "Resume",
    "Cover Letter",
    "Status",
    "Error",
]


def test_pending_and_processing_are_runnable():
    rows = [
        HEADERS,
        ["https://jobs.example.com/a", "Northwind", "Partner", "", "", "", "", "pending", ""],
        ["https://jobs.example.com/b", "Contoso", "SE", "", "", "", "", "processing", ""],
        ["https://jobs.example.com/c", "X", "Y", "", "", "http://docs", "", "ready_for_review", ""],
        ["https://jobs.example.com/d", "Z", "W", "", "", "", "", "error", "boom"],
        ["not-a-url", "", "", "", "", "", "", "pending", ""],
    ]
    jobs = jobs_from_grid(rows)
    assert [job.sheet_row for job in jobs] == [2, 3]
    assert jobs[0].company == "Northwind"
    assert jobs[1].status == "processing"


def test_blank_status_with_url_is_pending():
    rows = [
        HEADERS,
        ["https://jobs.example.com/a", "Acme", "AE", "", "", "", "", "", ""],
    ]
    jobs = jobs_from_grid(rows)
    assert len(jobs) == 1
    assert jobs[0].status == ""


def test_posting_text_is_kept_with_company_and_role():
    headers = [
        "Job Postings",
        "Company",
        "Role",
        "Posting Text",
        "Organization",
        "Level",
        "Resume",
        "Cover Letter",
        "Status",
        "Error",
    ]
    description = "Own the partner sales cycle. " * 20
    rows = [
        headers,
        [
            "https://jobs.example.com/a",
            "Northwind",
            "Solutions Engineer",
            description,
            "",
            "Senior",
            "",
            "",
            "pending",
            "",
        ],
    ]
    jobs = jobs_from_grid(rows)
    assert len(jobs) == 1
    assert jobs[0].posting_text == description.strip()
    assert jobs[0].company == "Northwind"
    assert jobs[0].role == "Solutions Engineer"


def test_blank_role_is_not_invented_when_a_description_was_pasted():
    headers = ["Job Postings", "Company", "Role", "Posting Text", "Organization", "Level", "Status"]
    rows = [
        headers,
        ["https://jobs.example.com/a", "Northwind", "", "A real description. " * 20, "Sales", "Senior", "pending"],
    ]
    jobs = jobs_from_grid(rows)
    assert jobs[0].role == ""
    assert jobs[0].posting_text.startswith("A real description.")


def test_writes_company_role_and_error():
    job = JobRow(
        sheet_row=2,
        job_url="https://jobs.example.com/a",
        company_col=1,
        role_col=2,
        resume_col=5,
        cover_col=6,
        status_col=7,
        error_col=8,
    )
    writes = dict(
        job_field_writes(
            job,
            {
                "status": "ready_for_review",
                "company": "Northwind",
                "role": "Partner Consultant",
                "error": "",
                "resume_doc_url": "https://docs.google.com/document/d/abc",
            },
        )
    )
    assert writes["B2"] == "Northwind"
    assert writes["C2"] == "Partner Consultant"
    assert writes["H2"] == "ready_for_review"
    assert writes["I2"] == ""
    assert writes["F2"].endswith("/abc")
