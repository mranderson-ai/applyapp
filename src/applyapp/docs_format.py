"""Google Docs batchUpdate builder.

Local output uses the same `design.STYLES` in `docx_format.py`. This module is
only the Docs API request list.

Docs indexes are 1-based; a new document already contains a terminating newline.
We insert the body at index 1, then apply paragraph styles, then bullets, then
text styles last. Named styles applied earlier used to wipe navy/bold. Text
ranges exclude the trailing newline of each paragraph — styling through `\n`
was wiping the run. We also drop the final `\n` of the inserted body so we do
not get an extra blank page.

`tabStops` are not used: the Docs API rejects them (400 Unallowed field). Dates
are padded with spaces in format_blocks instead.
"""

from typing import Any

from applyapp.design import FONT, MARGIN_PT, STYLES

CONTENT_WIDTH_PT = 612 - (2 * MARGIN_PT)


def build_styled_doc_requests(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One insert + margin update + per-paragraph styles for `create_styled_doc`."""
    body, spans = _compose(blocks)
    requests: list[dict[str, Any]] = [
        {"insertText": {"location": {"index": 1}, "text": body}},
        {
            "updateDocumentStyle": {
                "documentStyle": {
                    "marginTop": _pt(MARGIN_PT),
                    "marginBottom": _pt(MARGIN_PT),
                    "marginLeft": _pt(MARGIN_PT),
                    "marginRight": _pt(MARGIN_PT),
                },
                "fields": "marginTop,marginBottom,marginLeft,marginRight",
            }
        },
    ]

    bullet_start: int | None = None
    bullet_end: int | None = None
    paragraph_requests: list[dict[str, Any]] = []
    text_requests: list[dict[str, Any]] = []
    bullet_requests: list[dict[str, Any]] = []

    for kind, start, end in spans:
        style = STYLES.get(kind, STYLES["paragraph"])
        paragraph_requests.append(_paragraph_style(start, end, style))
        if end - start > 1:
            # Exclude the paragraph's trailing newline or Google drops the run style.
            text_requests.append(_text_style(start, end - 1, style))
        if style.get("bullet"):
            if bullet_start is None:
                bullet_start = start
            bullet_end = end
        else:
            if bullet_start is not None and bullet_end is not None:
                bullet_requests.append(_bullets(bullet_start, bullet_end))
            bullet_start = None
            bullet_end = None
    if bullet_start is not None and bullet_end is not None:
        bullet_requests.append(_bullets(bullet_start, bullet_end))

    requests.extend(paragraph_requests)
    requests.extend(bullet_requests)
    # Text styles last: applying them before paragraph named styles used to reset color/weight.
    requests.extend(text_requests)
    return requests


def _compose(blocks: list[dict[str, Any]]) -> tuple[str, list[tuple[str, int, int]]]:
    parts: list[str] = []
    spans: list[tuple[str, int, int]] = []
    cursor = 1
    for block in blocks:
        kind = block.get("kind") or "paragraph"
        text = (block.get("text") or "").strip()
        style = STYLES.get(kind, STYLES["paragraph"])
        if style.get("uppercase") and text:
            text = text.upper()
        if kind == "spacer":
            text = ""
        line = text + "\n"
        start = cursor
        end = cursor + len(line)
        spans.append((kind, start, end))
        parts.append(line)
        cursor = end
    body = "".join(parts)
    if body.endswith("\n"):
        # Empty Docs already end with a paragraph mark; keeping ours adds a blank page.
        body = body[:-1]
    return body, spans


def _pt(magnitude: float) -> dict[str, Any]:
    return {"magnitude": magnitude, "unit": "PT"}


def _text_style(start: int, end: int, style: dict[str, Any]) -> dict[str, Any]:
    rgb = style.get("color") or {"red": 0, "green": 0, "blue": 0}
    text_style: dict[str, Any] = {
        "weightedFontFamily": {"fontFamily": FONT, "weight": 700 if style.get("bold") else 400},
        "fontSize": _pt(style["font_size"]),
        "bold": bool(style.get("bold")),
        "italic": bool(style.get("italic")),
        "foregroundColor": {"color": {"rgbColor": rgb}},
    }
    return {
        "updateTextStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "textStyle": text_style,
            "fields": "weightedFontFamily,fontSize,bold,italic,foregroundColor",
        }
    }


def _paragraph_style(start: int, end: int, style: dict[str, Any]) -> dict[str, Any]:
    paragraph: dict[str, Any] = {
        "alignment": style.get("align") or "START",
        "spaceAbove": _pt(style.get("space_before") or 0),
        "spaceBelow": _pt(style.get("space_after") or 0),
        "lineSpacing": 100 * float(style.get("line_spacing") or 1.15),
    }
    fields = "alignment,spaceAbove,spaceBelow,lineSpacing"
    if style.get("border_bottom"):
        paragraph["borderBottom"] = {
            "color": {"color": {"rgbColor": STYLES["section"]["color"]}},
            "width": _pt(0.75),
            "dashStyle": "SOLID",
            "padding": _pt(1),
        }
        fields += ",borderBottom"
    return {
        "updateParagraphStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "paragraphStyle": paragraph,
            "fields": fields,
        }
    }


def _bullets(start: int, end: int) -> dict[str, Any]:
    return {
        "createParagraphBullets": {
            "range": {"startIndex": start, "endIndex": end},
            "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
        }
    }
