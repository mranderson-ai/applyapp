"""Human-editable visual system for ApplyApp resumes and cover letters.

Typography numbers here are what both writers apply: Google Docs and the local
.docx. Edit this file and the seed `ApplyApp Document Design` together if you change
the look. STYLES keys must match BlockKind in models.py. Navy is #1A2B44 from
the spec (not a darker navy we tried first). Spacing is tight on purpose: 11pt
body plus five roles only fits two pages if section/bullet gaps stay small.
"""

from __future__ import annotations

NAVY = {"red": 0.102, "green": 0.169, "blue": 0.267}  # #1A2B44
CHARCOAL = {"red": 0.133, "green": 0.133, "blue": 0.133}  # #222222
BLACK = {"red": 0.102, "green": 0.102, "blue": 0.102}  # #1A1A1A
RULE = {"red": 0.102, "green": 0.169, "blue": 0.267}

FONT = "Calibri"
MARGIN_PT = 54  # 0.75 in

STYLES = {
    # kind → Docs paragraph+text style. `bullet`/`border_bottom`/`uppercase` are renderer flags.
    "name": {
        "font_size": 20,
        "bold": True,
        "color": NAVY,
        "align": "CENTER",
        "space_before": 0,
        "space_after": 2,
        "line_spacing": 1.0,
    },
    "contact": {
        "font_size": 10,
        "bold": False,
        "color": CHARCOAL,
        "align": "CENTER",
        "space_before": 0,
        "space_after": 6,
        "line_spacing": 1.08,
    },
    "target_title": {
        "font_size": 11,
        "bold": True,
        "italic": True,
        "color": CHARCOAL,
        "align": "CENTER",
        "space_before": 0,
        "space_after": 6,
        "line_spacing": 1.08,
    },
    "section": {
        "font_size": 11.5,
        "bold": True,
        "color": NAVY,
        "align": "START",
        "space_before": 6,
        "space_after": 2,
        "line_spacing": 1.2,
        "border_bottom": True,
        "uppercase": True,
    },
    "job_header": {
        "font_size": 11,
        "bold": True,
        "color": BLACK,
        "align": "START",
        "space_before": 4,
        "space_after": 0,
        "line_spacing": 1.08,
        "right_tab": True,
    },
    "meta": {
        "font_size": 10.5,
        "bold": False,
        "italic": True,
        "color": CHARCOAL,
        "align": "START",
        "space_before": 0,
        "space_after": 1,
        "line_spacing": 1.08,
    },
    "paragraph": {
        "font_size": 11,
        "bold": False,
        "color": BLACK,
        "align": "START",
        "space_before": 0,
        "space_after": 6,
        "line_spacing": 1.12,
    },
    "bullet": {
        "font_size": 11,
        "bold": False,
        "color": BLACK,
        "align": "START",
        "space_before": 0,
        "space_after": 0,
        "line_spacing": 1.08,
        "bullet": True,
    },
    "spacer": {
        "font_size": 10.5,
        "bold": False,
        "color": BLACK,
        "align": "START",
        "space_before": 0,
        "space_after": 8,
        "line_spacing": 1.0,
    },
}

SPEC_TITLE = "ApplyApp Document Design"

SPEC_BODY = """
ApplyApp Document Design
Draft for human edit — visual system for resumes and cover letters
Status: first draft. Edit freely. ApplyApp applies these rules in a format step immediately before writing the Google Doc or local .docx.

Purpose
This document is the look-and-feel spec. It is not a biography and not ATS keyword advice.
- Resume Optimization for HR AI Paper = how to write content that parsers and recruiters respect
- Human Writings = voice for cover letters
- This file = how both documents should look on the page

Design principle
One quiet, expensive-looking page. Hierarchy from type, weight, and whitespace — not from color blocks, icons, columns, or tables. A hiring manager should be able to scan the resume in 15 seconds. A recruiter’s ATS should still parse every heading and bullet.

Shared visual system (resume and cover letter)
- Page: US Letter. Margins 0.75 in all sides.
- Typeface: Calibri throughout (Arial if Calibri is missing). No second display font.
- Ink: navy (#1A2B44) for the name and section labels; charcoal for contact/meta; near-black for body.
- No tables, text boxes, headers/footers, photos, icons, skill bars, or multiple columns.
- No justified text. Left align body. Center the name and contact line only.
- No “Page 1 of 1” footers. Resume target: one page if true experience allows, two pages only if every bullet earns its place.
- Cover letter: one page.

Resume layout
1. Name — 20 pt, bold, navy, centered.
2. Contact — 10 pt, charcoal, centered, one line: City/State · phone · email · LinkedIn (plain URL, no icon). Separate with a middot (·). Do not label “Email:”.
3. No job title under the contact line. Go straight to SUMMARY. A centered posting title there is omitted: the model invents words such as "Principal" or "(AI)", and SUMMARY already states the positioning.
   - SUMMARY section: 3–4 lines, 11 pt, left aligned, no bullets. Open with the most relevant job title the candidate has actually held, not the title they are applying for. Do not upgrade that title or borrow extra words from the posting. The cover letter is where the posting title is named, and it must be named exactly.
4. Section labels — 11.5 pt, bold, navy, ALL CAPS, left aligned, with a 0.75 pt navy rule under the label. Order unless the posting clearly demands otherwise:
   SUMMARY
   EXPERIENCE
   SKILLS
   EDUCATION
   (Add TECHNICAL PROJECTS or CERTIFICATIONS only when the posting needs them and the seeds support them.)
5. Each role in EXPERIENCE
   - Line 1 (job_header): Job Title, Company — 11 pt bold. Dates right-aligned on the same visual line if possible; if not, put dates on the meta line. Format dates as Mon YYYY – Mon YYYY or Mon YYYY – Present.
   - Line 2 (meta): City, ST · team/scope in 10 pt italic charcoal. Skip if nothing true to say.
   - Bullets: 11 pt, disc bullets, 0.25 in indent. Action + scope + result. One line when possible, two lines max. No periods stacked as paragraphs. 3–6 bullets per role; more only for the role closest to this posting.
6. SKILLS — one or two lines of comma-separated true skills, grouped (e.g. GTM, platforms, methods). No charts.
7. EDUCATION — degree, school, year if claimed in seeds. No coursework filler.

Cover letter layout
Match the resume header (same name, contact, type, navy). Then:
1. Date — 11 pt, left, Month D, YYYY
2. Spacer
3. Greeting — 11 pt. Always “Dear {Company} Team,” using the company name from the posting. No “Dear Hiring Manager,” and no “To whom it may concern.”
4. Body — 3 or 4 short paragraphs, 11 pt, 1.15 line spacing, 8 pt space after each paragraph, 250–400 words total.
   - Para 1: the posting title copied exactly (keep “Principal”, “(AI)”, or any other word that is already in that title; do not insert one that is not), the company, one specific reason this posting fits real experience.
   - Para 2–3: two or three true accomplishments mapped to the posting. Do not recap the whole resume.
   - Final para: a clear ask for a conversation. No desperation, no “I am passionate about synergy.”
5. Close — “Best,” or whatever Human Writings actually uses, then the applicant’s name. No scripted “Sincerely yours” unless that is their voice.

Voice vs. layout
Cover letter sentences follow Human Writings. Cover letter shape follows this file. Do not let the ATS paper make the letter sound like a keyword dump.

What the format step may and may not do
May: split lines into the block types above, apply ALL CAPS to section labels, normalize date punctuation, insert the shared header, turn hyphen lines into real bullets.
May not: invent employers, dates, metrics, skills, or a new target title; lengthen the letter past ~400 words; add a second page for decoration; change facts to fit a prettier line break.

Edit checklist
- If you hate Calibri, change the typeface here (keep it a system font Google Docs has).
- If you want a hairline under the name instead of under sections, say so.
- If cover letters should include company address / “Dear Ramp Hiring Team,” add that.
- Keep this document’s title as “ApplyApp Document Design” so the agent keeps classifying it as the design spec.
""".strip()
