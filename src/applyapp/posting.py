"""Download a public job posting and turn HTML into plain text.

Greenhouse/Ashby/Lever pages are the expected sources. We pretend to be a
browser because some boards 403 a bare Python user-agent. Trafilatura pulls the
article body; if it returns almost nothing (JS-heavy or oddly marked-up pages)
we fall back to a naive HTML text dump. Ashby job boards put the description in
`window.__appData` inside a script tag, which those extractors skip, so that
JSON is read directly. Playwright is deliberately out of V1 — pages that still
have no description should land in Error for a human to paste a better URL.
"""

import json
import logging
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx
import trafilatura

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class _TextExtractor(HTMLParser):
    """Last-resort extractor: skip script/style, keep visible text nodes."""
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def text(self) -> str:
        return "\n".join(self._chunks)


def fetch_posting_text(url: str, max_chars: int) -> str:
    """GET `url` and return clipped posting text. Empty string means we got HTML noise only."""
    text, _title = fetch_posting(url, max_chars)
    return text


def fetch_posting(url: str, max_chars: int) -> tuple[str, str]:
    """Return `(plain_text, official_title)`. Title comes from the page, not the model."""
    with httpx.Client(follow_redirects=True, timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
        html = _download_html(client, url)
        text, title = extract_posting(html)
        embed = ""
        if posting_body_error(text):
            embed = embedded_job_url(url, html) or ashby_job_url_from_scripts(client, url, html)
        if embed:
            logger.info("Page had no job description; fetching embedded board %s", embed)
            html = _download_html(client, embed)
            text, title = extract_posting(html)
    if not text:
        logger.warning("No extractable text at %s", url)
    elif posting_body_error(text):
        logger.warning("Posting text at %s is navigation, not a job description", url)
    return text[:max_chars], title


def _download_html(client: httpx.Client, url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


def extract_posting(html: str) -> tuple[str, str]:
    """Prefer Ashby's embedded posting JSON, then visible article text."""
    embedded = ashby_posting_from_html(html)
    if embedded and not posting_body_error(embedded[0]):
        return embedded
    title = posting_title_from_html(html)
    extracted = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    if len(extracted.strip()) < 200:
        fallback = _TextExtractor()
        fallback.feed(html)
        extracted = fallback.text()
    extracted = re.sub(r"\n{3,}", "\n\n", extracted).strip()
    return extracted, title


_EMBEDDED_BOARD = re.compile(
    r"https://(?:jobs\.ashbyhq\.com|job-boards\.greenhouse\.io|boards\.greenhouse\.io|jobs\.lever\.co)/[^\s\"'<>]+",
    re.I,
)
_JOB_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def embedded_job_url(page_url: str, html: str) -> str:
    """The job-board URL this page embeds, when the page itself is only a shell.

    Looks for an iframe, script, or link to Ashby, Greenhouse, or Lever. A job id
    already in the page URL has to match. Ashby's own marketing site is the one
    shell that names `ashby_jid` and does not include the board address.
    """
    page = page_url.split("#")[0].rstrip("/")
    ids = set(_JOB_UUID.findall(page_url))
    query = parse_qs(urlparse(page_url).query)
    for key in ("ashby_jid", "gh_jid"):
        ids.update(item.strip() for item in query.get(key, []) if item.strip())

    candidates: list[str] = []
    for match in _EMBEDDED_BOARD.finditer(html):
        found = match.group(0).rstrip(".,);")
        if found.split("#")[0].rstrip("/") == page:
            continue
        candidates.append(found)

    for found in candidates:
        if any(job_id and job_id in found for job_id in ids):
            return found

    orgs: list[str] = []
    for found in candidates:
        parsed = urlparse(found)
        if "jobs.ashbyhq.com" not in parsed.netloc.lower():
            continue
        parts = [part for part in parsed.path.split("/") if part]
        if not parts or parts[0].lower() == "embed":
            continue
        if parts[0] not in orgs:
            orgs.append(parts[0])
    if len(orgs) == 1 and len(ids) == 1:
        return f"https://jobs.ashbyhq.com/{orgs[0]}/{next(iter(ids))}"

    if len(candidates) == 1 and _JOB_UUID.search(candidates[0]):
        return candidates[0]
    return ashby_board_url(page_url)


_ASHBY_ORG_CONCAT = re.compile(
    r"""jobs\.ashbyhq\.com/["']\s*\.concat\(\s*encodeURIComponent\(\s*["']([^"']+)["']"""
)
_ASHBY_ORG_PATH = re.compile(r"https://jobs\.ashbyhq\.com/([^/\"'\\?\s]+)")
_SCRIPT_SRC = re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']", re.I)


def ashby_orgs_in_source(source: str) -> list[str]:
    """Board names an Ashby embed script uses to build jobs.ashbyhq.com/{org}/embed."""
    found: list[str] = []
    for match in _ASHBY_ORG_CONCAT.finditer(source):
        org = match.group(1).strip()
        if org and org not in found:
            found.append(org)
    for match in _ASHBY_ORG_PATH.finditer(source):
        org = unquote(match.group(1)).strip()
        if not org or org.lower() in {"embed", "api"} or org.startswith("$"):
            continue
        if org not in found:
            found.append(org)
    return found


def ashby_job_url(job_id: str, org: str) -> str:
    return f"https://jobs.ashbyhq.com/{quote(org, safe='')}/{job_id}"


def ashby_job_url_from_scripts(client: httpx.Client, page_url: str, html: str) -> str:
    """Follow an Ashby embed whose board name lives in a JavaScript file, not the HTML.

    Superhuman's careers page is a shell with `ashby_jid` and `<div id="ashby_embed">`.
    The company name is inside a script the page loads, which then injects the iframe.
    """
    job_id = (parse_qs(urlparse(page_url).query).get("ashby_jid") or [""])[0].strip()
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", job_id):
        return ""
    if "ashby" not in html.lower():
        return ""
    orgs = ashby_orgs_in_source(html)
    if len(orgs) == 1:
        return ashby_job_url(job_id, orgs[0])
    if len(orgs) > 1:
        return ""
    for src in _script_urls(page_url, html):
        try:
            script = client.get(src).text
        except httpx.HTTPError:
            logger.warning("Could not read script %s while looking for an Ashby embed", src)
            continue
        if "ashby" not in script.lower():
            continue
        found = ashby_orgs_in_source(script)
        for org in found:
            if org not in orgs:
                orgs.append(org)
        if len(orgs) == 1:
            return ashby_job_url(job_id, orgs[0])
        if len(orgs) > 1:
            return ""
    return ""


def _script_urls(page_url: str, html: str) -> list[str]:
    parsed = urlparse(page_url)
    found: list[str] = []
    for match in _SCRIPT_SRC.finditer(html):
        src = match.group(1).strip()
        if src.startswith("//"):
            src = f"{parsed.scheme}:{src}"
        elif src.startswith("/"):
            src = f"{parsed.scheme}://{parsed.netloc}{src}"
        elif not src.startswith("http"):
            continue
        if src not in found:
            found.append(src)
        if len(found) >= 40:
            break
    return found


def ashby_board_url(url: str) -> str:
    """Ashby's own careers site embeds the job board and does not include the description.

    `ashby_jid` is the posting id. The board behind www.ashbyhq.com is `Ashby`.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]
    if host.startswith("jobs.") or not host.endswith("ashbyhq.com"):
        return ""
    job_id = (parse_qs(parsed.query).get("ashby_jid") or [""])[0].strip()
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", job_id):
        return ""
    return f"https://jobs.ashbyhq.com/Ashby/{job_id}"


def ashby_posting_from_html(html: str) -> tuple[str, str] | None:
    """Read `window.__appData.posting`, which the embedded job board renders in the browser."""
    marker = "window.__appData = "
    start = html.find(marker)
    if start < 0:
        return None
    try:
        data, _end = json.JSONDecoder().raw_decode(html[start + len(marker) :])
    except json.JSONDecodeError:
        logger.warning("Ashby page had __appData that was not valid JSON")
        return None
    posting = data.get("posting") if isinstance(data, dict) else None
    if not isinstance(posting, dict):
        return None
    title = _clean_title(str(posting.get("title") or ""))
    description = _html_to_text(str(posting.get("descriptionHtml") or ""))
    if not title and not description:
        return None
    return description, title


def _html_to_text(html: str) -> str:
    cleaned = re.sub(r"<(?:br|p|div|li|h[1-6]|tr|ul|ol)[^>]*>", "\n", html, flags=re.I)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return "\n".join(line.strip() for line in cleaned.splitlines() if line.strip())


def posting_body_error(text: str) -> str:
    """Reject a careers-page shell so the row errors instead of writing documents.

    A real posting has paragraphs. Navigation, a title line, or an embedded board
    the reader could not open all fail this check. An empty string is handled by
    the caller as "could not extract text."
    """
    prose = [line.strip() for line in text.splitlines() if len(line.strip()) >= 80]
    if sum(len(line) for line in prose) >= 200:
        return ""
    return (
        "Could not extract a job description. The page returned navigation or a title, "
        "not the posting. The job body is usually loaded with JavaScript. "
        "Paste the full description into Posting Text, fill Company and Role with the "
        "employer and the official title, clear Status, and run the row again."
    )


def pasted_description_error(text: str) -> str:
    """Reject a title-only paste. Real descriptions are paragraphs, not one line."""
    body = " ".join(text.split())
    if len(body) >= 200:
        return ""
    return (
        "Posting Text is too short to be a job description. "
        "Paste the full description from the page, including responsibilities and requirements."
    )


def posting_title_from_html(html: str) -> str:
    """The board's own job title. This is the only title a cover letter may use."""
    for pattern in (
        r'property="og:title"\s+content="([^"]+)"',
        r'content="([^"]+)"\s+property="og:title"',
    ):
        match = re.search(pattern, html, re.I)
        if match and match.group(1).strip():
            return _clean_title(match.group(1))
    heading = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    if heading:
        title = _clean_title(re.sub(r"<[^>]+>", "", heading.group(1)))
        if title:
            return title
    page = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    if page:
        text = _clean_title(re.sub(r"<[^>]+>", "", page.group(1)))
        match = re.search(r"Job Application for (.+?) at ", text)
        if match:
            return match.group(1).strip()
    return ""


def _clean_title(value: str) -> str:
    return " ".join(value.replace("&#39;", "'").replace("&amp;", "&").split())
