"""Deterministic typesetter — the last writer before the Doc or .docx is saved.

The format model's tree is sloppy (extra spacers, RE: lines, six bullets, ALL CAPS
name). This module is the source of layout truth so an unattended run does not
need a human restyle. It may drop extra bullets and extra skills to hold two
pages; it may not invent employers or metrics.

Google Docs has no usable right-tab API (`tabStops` 400), so job dates are padded
with spaces using Calibri width estimates. The local .docx writer turns that
padding back into a real right-aligned tab.
"""

import re
from datetime import date
from typing import Any

MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
DATE_TAIL = re.compile(
    rf"(?:\t|\s+)({MONTH}\s+\d{{4}}\s*[–\-—]\s*(?:Present|{MONTH}\s+\d{{4}}))\s*$",
    re.I,
)
DATE_LINE = re.compile(rf"^{MONTH}\s+\d{{1,2}},\s+\d{{4}}$", re.I)
SKILL_HEADINGS = {
    "skills",
    "core competencies",
    "technical skills",
    "technical & tools",
    "technical and tools",
}
SECTION_ALIASES = {
    "professional summary": "SUMMARY",
    "summary": "SUMMARY",
    "professional experience": "EXPERIENCE",
    "work experience": "EXPERIENCE",
    "experience": "EXPERIENCE",
    "core competencies": "SKILLS",
    "skills": "SKILLS",
    "technical skills": "SKILLS",
    "technical & tools": "SKILLS",
    "technical and tools": "SKILLS",
    "education": "EDUCATION",
}
CONTACT_SEP = " · "
# Calibri 11pt: letters are wider than spaces, so pad by estimated width.
LETTER_PT = 5.6
SPACE_PT = 2.8
CONTENT_WIDTH_PT = 504  # US Letter minus 0.75 in margins


def polish(
    blocks: list[Any],
    kind: str,
    header_from: list[dict[str, str]] | None = None,
    company: str = "",
) -> list[dict[str, str]]:
    """Normalize a typesetter tree. Cover letters reuse the resume name/contact header."""
    items = [_as_dict(block) for block in blocks if _as_dict(block).get("kind")]
    items = [_normalize_item(item) for item in items]
    items = _drop_extra_spacers(items)
    if kind == "resume":
        items = _merge_contacts(items)
        items = _title_case_name(items)
        items = _drop_header_title(items)
        items = _normalize_sections(items)
        items = _ensure_summary(items)
        items = _promote_role_paragraphs(items)
        items = _split_job_header_dates(items)
        items = _skills_as_paragraph(items)
        items = _merge_skill_sections(items)
        items = _education_one_line(items)
        items = _cap_role_bullets(items)
        items = _strip_spacers(items)
    else:
        name, contact = _header_from(header_from or items)
        items = _strip_leading_header(items)
        items = _cover_body(items, company)
        items = [
            {"kind": "name", "text": name},
            {"kind": "contact", "text": contact},
        ] + items
        items = _cover_signature(items, name)
        items = _drop_extra_spacers(items)
    return items


def blocks_from_google_doc(doc: dict[str, Any]) -> list[dict[str, str]]:
    """Infer block kinds from an existing Docs API document (alignment, bullets, rules)."""
    blocks: list[dict[str, str]] = []
    for element in doc.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        text = "".join(
            run.get("textRun", {}).get("content", "") for run in paragraph.get("elements", [])
        ).replace("\n", "").strip()
        style = paragraph.get("paragraphStyle") or {}
        first = next(
            (
                run.get("textRun", {}).get("textStyle") or {}
                for run in paragraph.get("elements", [])
                if run.get("textRun")
            ),
            {},
        )
        bold = bool(first.get("bold"))
        italic = bool(first.get("italic"))
        align = style.get("alignment")
        if not text:
            blocks.append({"kind": "spacer", "text": ""})
            continue
        if paragraph.get("bullet"):
            blocks.append({"kind": "bullet", "text": text})
            continue
        if style.get("borderBottom"):
            blocks.append({"kind": "section", "text": text})
            continue
        if align == "CENTER":
            if bold and not italic:
                blocks.append({"kind": "name", "text": text})
            elif italic:
                blocks.append({"kind": "target_title", "text": text})
            else:
                blocks.append({"kind": "contact", "text": text})
            continue
        if DATE_TAIL.search(text) and bold:
            blocks.append({"kind": "job_header", "text": text})
            continue
        if italic and len(text) < 140:
            blocks.append({"kind": "meta", "text": text})
            continue
        blocks.append({"kind": "paragraph", "text": text})
    return blocks


def _as_dict(block: Any) -> dict[str, str]:
    if isinstance(block, dict):
        return {"kind": str(block.get("kind") or "paragraph"), "text": str(block.get("text") or "")}
    return {"kind": str(getattr(block, "kind", "paragraph")), "text": str(getattr(block, "text", "") or "")}


def _normalize_item(item: dict[str, str]) -> dict[str, str]:
    raw = item.get("text") or ""
    kind = item.get("kind") or "paragraph"
    if kind == "job_header":
        text = re.sub(r"[ \t]{2,}", "  ", raw.strip())
        text = text.replace(" - ", " – ").replace(" — ", " – ")
        return {"kind": kind, "text": text}
    if kind == "contact":
        return {"kind": kind, "text": _contact_line([raw])}
    text = " ".join(raw.split())
    if kind == "section":
        return {"kind": kind, "text": text}
    if kind == "paragraph" and _looks_like_target_title(text):
        return {"kind": "target_title", "text": text}
    return {"kind": kind, "text": text}


def _looks_like_target_title(text: str) -> bool:
    if len(text) > 90:
        return False
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    return sum(char.isupper() for char in letters) / len(letters) > 0.7


def _drop_extra_spacers(items: list[dict[str, str]]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    prev_spacer = False
    for item in items:
        is_spacer = item["kind"] == "spacer" or (item["kind"] != "bullet" and not item["text"])
        if is_spacer:
            if prev_spacer:
                continue
            cleaned.append({"kind": "spacer", "text": ""})
            prev_spacer = True
            continue
        cleaned.append(item)
        prev_spacer = False
    while cleaned and cleaned[0]["kind"] == "spacer":
        cleaned.pop(0)
    while cleaned and cleaned[-1]["kind"] == "spacer":
        cleaned.pop()
    return cleaned


def _strip_spacers(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return [item for item in items if item["kind"] != "spacer" and (item["kind"] == "bullet" or item["text"])]


def _contact_line(parts: list[str]) -> str:
    tokens: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for piece in re.split(r"\s*[|•·]\s*", part):
            piece = " ".join(piece.split()).strip(" .")
            key = piece.lower()
            if piece and key not in seen:
                seen.add(key)
                tokens.append(piece)
    return CONTACT_SEP.join(tokens)


def _merge_contacts(items: list[dict[str, str]]) -> list[dict[str, str]]:
    contacts: list[str] = []
    rest: list[dict[str, str]] = []
    seen_body = False
    for item in items:
        if not seen_body and item["kind"] == "contact":
            contacts.append(item["text"])
            continue
        if item["kind"] not in {"name", "contact", "spacer"}:
            seen_body = True
        rest.append(item)
    if not contacts:
        return items
    merged = _contact_line(contacts)
    out: list[dict[str, str]] = []
    inserted = False
    for item in rest:
        if not inserted and item["kind"] != "name":
            out.append({"kind": "contact", "text": merged})
            inserted = True
        out.append(item)
        if item["kind"] == "name" and not inserted:
            out.append({"kind": "contact", "text": merged})
            inserted = True
    if not inserted:
        out.append({"kind": "contact", "text": merged})
    return out


def _title_case_name(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for item in items:
        if item["kind"] == "name":
            out.append({"kind": "name", "text": _name_case(item["text"])})
        else:
            out.append(item)
    return out


def _name_case(text: str) -> str:
    pieces = []
    for word in text.split():
        if word.startswith("(") and word.endswith(")") and len(word) > 2:
            inner = word[1:-1]
            pieces.append(f"({inner[:1].upper()}{inner[1:].lower()})")
        else:
            pieces.append(word[:1].upper() + word[1:].lower())
    return " ".join(pieces)


def _normalize_sections(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for item in items:
        if item["kind"] != "section":
            out.append(item)
            continue
        key = item["text"].lower().replace("&", "and").strip()
        out.append({"kind": "section", "text": SECTION_ALIASES.get(key, item["text"])})
    return out


def _ensure_summary(items: list[dict[str, str]]) -> list[dict[str, str]]:
    """If the opening body is a bare paragraph, insert the SUMMARY heading the spec requires."""
    out: list[dict[str, str]] = []
    i = 0
    while i < len(items) and items[i]["kind"] in {"name", "contact", "target_title", "spacer"}:
        out.append(items[i])
        i += 1
    if i < len(items) and items[i]["kind"] == "paragraph":
        out.append({"kind": "section", "text": "SUMMARY"})
        out.append(items[i])
        i += 1
    out.extend(items[i:])
    return out


def _promote_role_paragraphs(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for index, item in enumerate(items):
        if item["kind"] == "paragraph" and _preceded_by_role(items, index) and _followed_by_bullets(items, index):
            out.append({"kind": "bullet", "text": item["text"]})
        else:
            out.append(item)
    return out


def _preceded_by_role(items: list[dict[str, str]], index: int) -> bool:
    for item in reversed(items[:index]):
        if item["kind"] in {"job_header", "meta"}:
            return True
        if item["kind"] == "spacer":
            continue
        return False
    return False


def _followed_by_bullets(items: list[dict[str, str]], index: int) -> bool:
    for item in items[index + 1 :]:
        if item["kind"] == "bullet":
            return True
        if item["kind"] == "spacer":
            continue
        return False
    return False


def _split_job_header_dates(items: list[dict[str, str]]) -> list[dict[str, str]]:
    """Put dates on the same line as the title by padding spaces (Docs forbids tabStops)."""
    out = []
    for item in items:
        if item["kind"] != "job_header":
            out.append(item)
            continue
        text = item["text"].replace(" - ", " – ").replace(" — ", " – ")
        match = DATE_TAIL.search(text)
        if match:
            left = text[: match.start()].strip(" |·•-")
            right = match.group(1).replace("-", "–").replace("—", "–")
            gap_pt = CONTENT_WIDTH_PT * 0.92 - (len(left) + len(right)) * LETTER_PT
            gap = max(4, int(gap_pt / SPACE_PT))
            out.append({"kind": "job_header", "text": f"{left}{' ' * gap}{right}"})
        else:
            out.append({"kind": "job_header", "text": text})
    return out


def _skills_as_paragraph(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    i = 0
    while i < len(items):
        item = items[i]
        out.append(item)
        heading = item["text"].lower().replace("&", "and")
        if item["kind"] == "section" and any(name in heading for name in SKILL_HEADINGS):
            pieces: list[str] = []
            i += 1
            while i < len(items) and items[i]["kind"] in {"bullet", "paragraph"}:
                if items[i]["text"]:
                    pieces.extend(_skill_tokens(items[i]["text"]))
                i += 1
            if pieces:
                out.append({"kind": "paragraph", "text": _two_line_skills(pieces)})
            continue
        i += 1
    return out


def _skill_tokens(text: str) -> list[str]:
    parts = re.split(r"\s*[•;|]\s*|\s*,\s*", text)
    return [part.rstrip(".").strip() for part in parts if part.strip()]


def _two_line_skills(skills: list[str]) -> str:
    """Keep SKILLS to about two lines so Education stays on page two."""
    unique: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        key = skill.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(skill)
    kept: list[str] = []
    for skill in unique:
        candidate = ", ".join(kept + [skill])
        if kept and len(candidate) > 190:
            break
        kept.append(skill)
    return ", ".join(kept)


def _merge_skill_sections(items: list[dict[str, str]]) -> list[dict[str, str]]:
    """Collapse CORE COMPETENCIES + TECHNICAL & TOOLS into one SKILLS block before EDUCATION."""
    skills: list[str] = []
    rest: list[dict[str, str]] = []
    i = 0
    while i < len(items):
        item = items[i]
        heading = item["text"].lower().replace("&", "and")
        if item["kind"] == "section" and any(name in heading for name in SKILL_HEADINGS):
            i += 1
            if i < len(items) and items[i]["kind"] == "paragraph":
                skills.extend(_skill_tokens(items[i]["text"]))
                i += 1
            continue
        rest.append(item)
        i += 1
    if not skills:
        return rest
    seen: set[str] = set()
    unique: list[str] = []
    for skill in skills:
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            unique.append(skill)
    block = [
        {"kind": "section", "text": "SKILLS"},
        {"kind": "paragraph", "text": _two_line_skills(unique)},
    ]
    for index, item in enumerate(rest):
        if item["kind"] == "section" and "education" in item["text"].lower():
            return rest[:index] + block + rest[index:]
    return rest + block


def _cap_role_bullets(items: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep 5 bullets on the two latest roles, 3 on older ones so polish can hold two pages."""
    out: list[dict[str, str]] = []
    role = -1
    kept = 0
    for item in items:
        if item["kind"] == "job_header":
            role += 1
            kept = 0
        if item["kind"] == "bullet":
            kept += 1
            if kept > (5 if role < 2 else 3):
                continue
        out.append(item)
    return out


def summary_opening_feedback(resume_text: str, posting_role: str) -> str:
    """Fail a summary that opens with the posting title or a seniority the candidate has not held."""
    summary = _section_paragraph(resume_text, "SUMMARY")
    if not summary:
        return ""
    opening = summary.split(" with ")[0].strip()
    held = _held_titles(resume_text)
    problems: list[str] = []
    for word in ("principal", "staff", "distinguished", "fellow"):
        if re.search(rf"\b{word}\b", opening, re.I) and not any(re.search(rf"\b{word}\b", title, re.I) for title in held):
            problems.append(f'"{word}" is not in any held job title')
    for extra in re.findall(r"\(([^)]+)\)", opening):
        if not any(extra.lower() in title.lower() for title in held):
            problems.append(f'"({extra})" is not part of a held job title')
    posting = " ".join(posting_role.split())
    if posting and _opens_with_title(opening, posting) and not any(_opens_with_title(title, posting) or _opens_with_title(opening, title) for title in held):
        problems.append(f'the summary opens with the posting title "{posting}" instead of a role actually held')
    if not problems:
        return ""
    return (
        "SUMMARY must open with the most relevant job title the candidate has actually held, "
        "not the role they are applying for:\n- " + "\n- ".join(problems)
    )


def cover_title_feedback(cover_text: str, posting_role: str) -> str:
    """The letter must use the page's job title.

    Seniority and parentheticals are part of the title when the page includes them
    ("Principal Engineer", "Product Manager (AI)"). They are a problem only when the
    letter glues them onto a title that does not already contain them.
    """
    posting = " ".join(posting_role.split())
    if not posting:
        return ""
    exact = f'Name the posting title exactly as "{posting}".'
    if posting.lower() not in cover_text.lower():
        return f"{exact} The letter does not use that title."
    # Match only a parenthetical or seniority word sitting outside the full official
    # title. "Principal" or "(AI)" inside that title is not an addition.
    if re.search(re.escape(posting) + r"\s*\([^)]+\)", cover_text, re.I):
        return f"{exact} Do not add a parenthetical."
    if re.search(r"\b(?:Principal|Staff|Distinguished|Senior|Lead)\s+" + re.escape(posting), cover_text, re.I):
        return f"{exact} Do not add seniority."
    return ""


def _section_paragraph(text: str, heading: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if line.upper() != heading:
            continue
        for follow in lines[index + 1 :]:
            if follow:
                return follow
    return ""


def _held_titles(text: str) -> list[str]:
    titles: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        match = DATE_TAIL.search(line)
        if not match:
            continue
        title = line[: match.start()].strip(" |·•-\t")
        if title:
            titles.append(title)
    return titles


def _opens_with_title(text: str, title: str) -> bool:
    return _norm_title(text).startswith(_norm_title(title)) and bool(_norm_title(title))


def _norm_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def resume_length_feedback(text: str) -> str:
    """Deterministic two-page check used by critique before format/upload."""
    role_date = re.compile(
        rf"{MONTH}\s+\d{{4}}\s*[–\-—]\s*(?:Present|{MONTH}\s+\d{{4}})",
        re.I,
    )
    bullet = re.compile(r"^\s*(?:[-*•]|–)\s+\S")
    roles: list[list[object]] = []
    current: list[object] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if role_date.search(line):
            current = [line, 0]
            roles.append(current)
            continue
        if current is not None and bullet.match(line):
            current[1] = int(current[1]) + 1
    problems = []
    for index, (title, count) in enumerate(roles):
        cap = 5 if index < 2 else 3
        if count > cap:
            problems.append(f"{title}: {count} bullets; keep {cap} strongest true ones.")
    if not problems:
        return ""
    return (
        "Resume would exceed two pages. Cut bullets (do not invent replacements):\n"
        + "\n".join(f"- {item}" for item in problems)
    )


def _education_one_line(items: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    i = 0
    while i < len(items):
        item = items[i]
        out.append(item)
        if item["kind"] == "section" and "education" in item["text"].lower():
            lines: list[str] = []
            i += 1
            while i < len(items) and items[i]["kind"] in {"paragraph", "meta", "job_header"}:
                if items[i]["text"]:
                    lines.append(items[i]["text"])
                i += 1
            if lines:
                out.append({"kind": "paragraph", "text": ", ".join(lines)})
            continue
        i += 1
    return out


def _header_from(items: list[dict[str, str]]) -> tuple[str, str]:
    name = next((item["text"] for item in items if item["kind"] == "name"), "Applicant")
    contacts = [item["text"] for item in items if item["kind"] == "contact" and item["text"]]
    return _name_case(name), _contact_line(contacts)


def _strip_leading_header(items: list[dict[str, str]]) -> list[dict[str, str]]:
    stripped = list(items)
    while stripped and stripped[0]["kind"] in {"name", "contact", "spacer", "target_title"}:
        stripped.pop(0)
    return stripped


def _today() -> str:
    today = date.today()
    return f"{today.strftime('%B')} {today.day}, {today.year}"


def _cover_body(items: list[dict[str, str]], company: str = "") -> list[dict[str, str]]:
    """Date (today), greeting, body. Drop company-only and RE: lines the typesetter likes to add."""
    body: list[dict[str, str]] = []
    seen_greeting = False
    for item in items:
        text = item["text"]
        lowered = text.lower()
        if not text or item["kind"] == "spacer":
            continue
        if DATE_LINE.match(text):
            body.append({"kind": "paragraph", "text": _today()})
            continue
        if lowered.startswith("dear "):
            seen_greeting = True
            body.append({"kind": "paragraph", "text": text})
            continue
        if not seen_greeting and (lowered.startswith("re:") or _company_only(text)):
            continue
        body.append({"kind": "paragraph", "text": text})
    if not body:
        return [{"kind": "paragraph", "text": _today()}]
    if DATE_LINE.match(body[0]["text"]) is None:
        body = [{"kind": "paragraph", "text": _today()}] + body
    return _ensure_greeting(body, company)


def _company_only(text: str) -> bool:
    if text.lower().startswith("dear ") or re.search(r"[.!?]", text):
        return False
    words = text.split()
    return 1 <= len(words) <= 4 and len(text) <= 40


SCRIPT_CLOSES = {
    "sincerely",
    "sincerely yours",
    "yours truly",
    "respectfully",
    "regards",
    "kind regards",
    "warm regards",
}


def _team_greeting(company: str) -> str:
    """House greeting. Company comes from the queue row or the analysis."""
    name = " ".join(company.split())
    if not name:
        name = "Hiring"
    return f"Dear {name} Team,"


def _ensure_greeting(items: list[dict[str, str]], company: str = "") -> list[dict[str, str]]:
    """Replace whatever greeting the model wrote with Dear {Company} Team."""
    greeting = {"kind": "paragraph", "text": _team_greeting(company)}
    for index, item in enumerate(items):
        if item["text"].lower().startswith("dear "):
            updated = list(items)
            updated[index] = greeting
            return updated
    if items and DATE_LINE.match(items[0]["text"]):
        return [items[0], greeting, *items[1:]]
    return [greeting, *items]


def _close_token(text: str) -> str:
    return text.strip().rstrip(",").lower()


def _is_signoff_name(text: str, name: str) -> bool:
    """True when `text` is the letterhead name or a nickname already written in it.

    "Alex (Al) Rivera" also matches "Alex Rivera" and "Al Rivera".
    The nickname comes from the document, not from a built-in list of people.
    """
    return _close_token(text) in _name_forms(name)


def _name_forms(name: str) -> set[str]:
    forms = {name.strip().lower()}
    base = re.sub(r"\s*\([^)]*\)", "", name).strip()
    if base:
        forms.add(base.lower())
    nickname = re.search(r"\(([^)]+)\)", name)
    parts = base.split()
    if nickname and len(parts) >= 2:
        forms.add(f"{nickname.group(1).strip()} {parts[-1]}".lower())
    return {form for form in forms if form}


def _cover_signature(items: list[dict[str, str]], name: str) -> list[dict[str, str]]:
    """Every letter ends Best, then the letterhead name. Rewrite Sincerely; insert the close if it is missing."""
    out = list(items)
    for index in range(len(out) - 1, max(-1, len(out) - 8), -1):
        if _close_token(out[index]["text"]) in SCRIPT_CLOSES:
            out[index] = {"kind": "paragraph", "text": "Best,"}
            break
    has_best = any(_close_token(item["text"]) == "best" for item in out)
    name_at_end = bool(out) and _is_signoff_name(out[-1]["text"], name)
    if not has_best:
        if name_at_end:
            out.insert(-1, {"kind": "paragraph", "text": "Best,"})
        else:
            out.extend(
                [
                    {"kind": "paragraph", "text": "Best,"},
                    {"kind": "paragraph", "text": name},
                ]
            )
        return out
    if name_at_end:
        out[-1] = {"kind": "paragraph", "text": name}
        return out
    out.append({"kind": "paragraph", "text": name})
    return out


def _drop_header_title(items: list[dict[str, str]]) -> list[dict[str, str]]:
    """Drop a posting-title line under the contact row.

    The spec allows that line only when it is a true description of the person.
    The format model treats it as the job being applied for and invents words
    ("Principal", "(AI)"). The other resumes go straight to SUMMARY, which is
    the line that carries positioning.
    """
    out: list[dict[str, str]] = []
    dropped = False
    seen_header = False
    for item in items:
        if item["kind"] in {"name", "contact"}:
            out.append(item)
            seen_header = True
            continue
        if item["kind"] == "target_title":
            continue
        if seen_header and not dropped and _posting_title_line(item):
            dropped = True
            continue
        out.append(item)
        if item["kind"] == "section":
            dropped = True
    return out


def _posting_title_line(item: dict[str, str]) -> bool:
    text = item["text"].strip()
    if item["kind"] == "section" and text.upper() in {"SUMMARY", "EXPERIENCE", "SKILLS", "EDUCATION"}:
        return False
    if item["kind"] not in {"paragraph", "section", "meta", "target_title"}:
        return False
    if not text or len(text) > 80 or re.search(r"[.!?]", text):
        return False
    return 1 <= len(text.split()) <= 12
