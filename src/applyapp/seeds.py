"""Classify source files and pack them into the model context budget.

Seeds (LOCAL_SEED_DIR) are the applicant's own material: voice and prior resumes.
Agent project docs are not seeds. They are the optimization paper, the document
design spec, and Job Roles (the accomplishments dataset). Filename and folder
rules decide each file's role. The OPTIMIZED accomplishments workbook wins over
the unoptimized twin. Prior resumes are capped so they cannot crowd out Job Roles.
`PURPOSE` is injected into the prompt so the model does not treat Human Writings
as a biography or the design spec as keywords.
"""

from dataclasses import dataclass, field

ROLE_VOICE = "human_writings"
ROLE_FACTS = "accomplishments"
ROLE_ATS = "ats_guidance"
ROLE_DESIGN = "document_design"
ROLE_PRIOR = "prior_resume"
ROLE_SKIP = "skip"
ROLE_FACTS_LEGACY = "accomplishments_legacy"

PURPOSE = {
    ROLE_VOICE: (
        "VOICE AND TONE ONLY. These are the applicant's real job-search writings "
        "(cover letters, recruiter emails, LinkedIn outreach). Imitate diction, "
        "rhythm, and personality in cover letters. Do not mine this file as the "
        "source of employment facts unless the same fact appears in accomplishments "
        "or a prior resume."
    ),
    ROLE_FACTS: (
        "CANONICAL FACTS. Job Roles: AI-optimized accomplishments for historical roles. "
        "Each spreadsheet tab or markdown section is one role. This is the primary "
        "truth source for employers, titles, dates, metrics, tools, and outcomes. "
        "Prefer this dataset over prior resumes when they conflict."
    ),
    ROLE_ATS: (
        "MANDATORY CRAFT RULES. Thought leadership on writing resumes that survive "
        "ATS / HR-AI screening. Follow this when shaping structure, headings, "
        "keywords, and bullet style. This is how to write, not a biography."
    ),
    ROLE_DESIGN: (
        "VISUAL SYSTEM. Layout, type, hierarchy, and cover-letter shape. "
        "Used in the format step before the Doc or .docx is written. Not a source of career facts."
    ),
    ROLE_PRIOR: (
        "STARTING POINT ONLY. Resumes the applicant has actually used. Do not copy "
        "them. Produce a stronger, posting-specific version: keep true facts, "
        "improve targeting, ATS structure, and impact. Contact info and education "
        "may be taken from these if missing elsewhere."
    ),
}

LOAD_ORDER = (ROLE_FACTS, ROLE_ATS, ROLE_DESIGN, ROLE_VOICE, ROLE_PRIOR)
ROLE_CAPS = {
    ROLE_PRIOR: 8_000,
}


@dataclass
class SeedDoc:
    name: str
    path: str
    role: str
    text: str


@dataclass
class SeedLibrary:
    docs: list[SeedDoc] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def by_role(self, role: str) -> list[SeedDoc]:
        return [doc for doc in self.docs if doc.role == role]

    def has(self, role: str) -> bool:
        return any(doc.role == role for doc in self.docs)


def classify(name: str, parents: list[str]) -> str:
    """Map a seed file to a role. Order matters: ATS/design before generic 'resume'."""
    n = _norm(name)
    folder = _norm(" / ".join(parents))
    if "resume optimization" in n or "hr ai paper" in n or "optimization paper" in n:
        return ROLE_ATS
    if "document design" in n:
        return ROLE_DESIGN
    if "human writings" in n:
        return ROLE_VOICE
    if "accomplishment" in n and "optimized" in n:
        return ROLE_FACTS
    if "accomplishment" in n:
        return ROLE_FACTS_LEGACY
    if "job role" in folder:
        return ROLE_FACTS if "optimized" in n else ROLE_FACTS_LEGACY
    if "resume" in n:
        return ROLE_PRIOR
    if folder.startswith("accomplishments") and not n.endswith(".xlsx"):
        return ROLE_PRIOR
    if n.endswith((".pdf", ".docx")):
        return ROLE_PRIOR
    return ROLE_SKIP


def build_library(files: list[dict], max_chars: int) -> SeedLibrary:
    """Drop skips, prefer OPTIMIZED facts, then fill LOAD_ORDER until `max_chars`."""
    library = SeedLibrary()
    classified: list[tuple[dict, str]] = []
    for file in files:
        role = classify(file["name"], file.get("parents") or [])
        if role == ROLE_SKIP:
            library.skipped.append(_label(file))
            continue
        classified.append((file, role))

    has_optimized = any(role == ROLE_FACTS for _, role in classified)
    selected: list[tuple[dict, str]] = []
    for file, role in classified:
        if role == ROLE_FACTS_LEGACY and has_optimized:
            library.skipped.append(_label(file) + " (unoptimized; preferring OPTIMIZED dataset)")
            continue
        if role == ROLE_FACTS_LEGACY:
            role = ROLE_FACTS
        selected.append((file, role))

    remaining = max_chars
    for role in LOAD_ORDER:
        for file, file_role in selected:
            if file_role != role or remaining <= 0:
                continue
            text = (file.get("text") or "").strip()
            if not text:
                library.skipped.append(_label(file) + " (empty or unreadable)")
                continue
            cap = ROLE_CAPS.get(role, remaining)
            clipped = text[: min(remaining, cap)]
            library.docs.append(
                SeedDoc(
                    name=file["name"],
                    path=_label(file),
                    role=role,
                    text=clipped,
                )
            )
            remaining -= len(clipped)
    return library


def format_library(library: SeedLibrary, roles: tuple[str, ...] | None = None) -> str:
    """Prompt chunk: each role gets its PURPOSE blurb so the model does not misuse the file."""
    wanted = set(roles or LOAD_ORDER)
    blocks: list[str] = []
    for role in LOAD_ORDER:
        if role not in wanted:
            continue
        docs = library.by_role(role)
        if not docs:
            continue
        heading = role.replace("_", " ").upper()
        parts = [f"# {heading}\nPurpose: {PURPOSE[role]}"]
        for doc in docs:
            parts.append(f"## {doc.path}\n{doc.text}")
        blocks.append("\n\n".join(parts))
    return "\n\n".join(blocks)


def summary(library: SeedLibrary) -> str:
    lines = [f"{doc.role}: {doc.path} ({len(doc.text)} chars)" for doc in library.docs]
    if library.skipped:
        lines.append("skipped: " + "; ".join(library.skipped))
    return " | ".join(lines) if lines else "no seeds"


def _norm(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("|", " ").split())


def _label(file: dict) -> str:
    parents = file.get("parents") or []
    if parents:
        return " / ".join(parents + [file["name"]])
    return file["name"]
