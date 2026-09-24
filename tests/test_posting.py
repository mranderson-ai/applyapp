import pytest

from applyapp.config import Settings
from applyapp.models import JobRow
from applyapp.nodes import _lock_pasted_identity, fetch_posting
from applyapp.posting import (
    ashby_board_url,
    ashby_job_url,
    ashby_orgs_in_source,
    ashby_posting_from_html,
    embedded_job_url,
    posting_body_error,
    posting_title_from_html,
)


def test_posting_title_comes_from_the_page_not_a_rewritten_heading():
    html = '<meta property="og:title" content="Partner Engineer, Analytics" />'
    assert posting_title_from_html(html) == "Partner Engineer, Analytics"
    page = "<title>Job Application for Partner Engineer  at Northwind</title>"
    assert posting_title_from_html(page) == "Partner Engineer"


def test_careers_page_navigation_is_not_a_job_description():
    footer = """
Products
Platform
We're Hiring
Join a team that strives to do their best work every day.
© 2026 Ashby, Inc.
Privacy Policy
Careers
"""
    assert "JavaScript" in posting_body_error(footer)
    description = (
        "Partner Engineer partners with revenue leaders to scope the business case for Northwind and to decide whether the product is worth the rollout.\n\n"
        "You will run working sessions with economic buyers, translate product capabilities into the metrics they already track, and leave each evaluation with a written recommendation the buying team can share.\n"
    )
    assert posting_body_error(description) == ""


def test_ashby_embed_script_contains_the_posting():
    html = """
    <title>Careers | Ashby</title>
    <script>window.__appData = {
      "posting": {
        "title": "Partner Engineer",
        "descriptionHtml": "<h2>About this role</h2><p>As Northwind's first dedicated Partner Engineer, you'll own how we sell value and build the frameworks the team uses with buyers across a long evaluation, from the first working session through a written recommendation.</p><p>You will sit with Solutions Engineering and write the recommendation the buying team shares after each working session, including the metrics they already track and the rollout decision they need to make.</p>"
      }
    };</script>
    """
    text, title = ashby_posting_from_html(html)
    assert title == "Partner Engineer"
    assert "first dedicated Partner Engineer" in text
    assert posting_body_error(text) == ""
    assert ashby_posting_from_html("<html><p>No embed here, just a short careers footer.</p></html>") is None


def test_embedded_board_url_is_taken_from_the_page():
    job_id = "11111111-2222-4333-8444-555555555555"
    board = f"https://jobs.ashbyhq.com/Northwind/{job_id}"
    shell = f'<iframe src="{board}?embed=js"></iframe><p>Careers</p>'
    assert embedded_job_url("https://northwind.example/careers", shell) == f"{board}?embed=js"
    script = f"https://example.com/careers?ashby_jid={job_id}"
    html = '<script src="https://jobs.ashbyhq.com/Northwind/embed?version=2"></script>'
    assert embedded_job_url(script, html) == board
    assert embedded_job_url("https://example.com/careers", "<p>Privacy Policy</p>") == ""


def test_ashby_embed_script_names_the_board_when_the_page_does_not():
    job_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    script = (
        'let h="https://jobs.ashbyhq.com/".concat(encodeURIComponent("Northwind Analytics"),"/embed?version=2");'
    )
    assert ashby_orgs_in_source(script) == ["Northwind Analytics"]
    assert ashby_job_url(job_id, "Northwind Analytics") == (
        f"https://jobs.ashbyhq.com/Northwind%20Analytics/{job_id}"
    )
    assert ashby_orgs_in_source("https://jobs.ashbyhq.com/Northwind/embed?version=2") == ["Northwind"]


def test_ashby_careers_page_points_at_the_job_board():
    url = "https://www.ashbyhq.com/careers?ashby_jid=11111111-2222-4333-8444-555555555555&utm_source=newsletter"
    assert ashby_board_url(url) == "https://jobs.ashbyhq.com/Ashby/11111111-2222-4333-8444-555555555555"
    assert ashby_board_url("https://jobs.ashbyhq.com/Ashby/11111111-2222-4333-8444-555555555555") == ""
    assert ashby_board_url("https://job-boards.greenhouse.io/northwind/jobs/123") == ""


def _pasted_job(**overrides) -> JobRow:
    description = "Own the partner sales cycle with economic buyers. " * 12
    fields = {
        "sheet_row": 10,
        "job_url": "https://jobs.example.com/northwind/partner-engineer",
        "company": "Northwind",
        "role": "Partner Engineer",
        "posting_text": description,
    }
    fields.update(overrides)
    return JobRow(**fields)


def test_pasted_description_uses_company_and_role_as_the_official_title():
    result = fetch_posting({"job": _pasted_job()}, Settings())
    assert result["posting_from_paste"] is True
    assert result["posting_title"] == "Partner Engineer"
    assert "partner sales cycle" in result["posting_text"]


def test_pasted_description_requires_company_and_role():
    with pytest.raises(RuntimeError, match="Company and Role"):
        fetch_posting({"job": _pasted_job(company="", role="")}, Settings())


def test_short_paste_is_rejected():
    with pytest.raises(RuntimeError, match="too short"):
        fetch_posting({"job": _pasted_job(posting_text="Partner Engineer")}, Settings())


def test_blank_posting_text_still_fetches_the_page(monkeypatch):
    monkeypatch.setattr(
        "applyapp.nodes.download_posting",
        lambda url, max_chars: ("Fetched description " * 30, "From The Page"),
    )
    result = fetch_posting({"job": _pasted_job(posting_text="  ")}, Settings())
    assert result["posting_from_paste"] is False
    assert result["posting_title"] == "From The Page"


def test_pasted_identity_replaces_a_renamed_title():
    analysis = {"company": "Wrong Co", "role_title": "Principal Partner Engineer (AI)"}
    locked = _lock_pasted_identity(analysis, _pasted_job(), True)
    assert locked["company"] == "Northwind"
    assert locked["role_title"] == "Partner Engineer"
