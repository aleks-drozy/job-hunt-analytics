"""Parser for the "## Applications" table in a JOB_SEARCH.md-style vault file.

Pure function, no DB or other IO side effects beyond reading the given path:

    parse(path) -> list[dict]

Each dict is shaped:
    {company, role_title, tier, channel, applied_date, status, status_date,
     followup_due}

Design decisions (documented per the module contract):

- The "Link" column is free-text CHANNEL info, not a URL. `_classify_channel`
  maps it to one of: linkedin | workday | indeed | jooble | company_portal |
  agency | other. Unrecognized/ambiguous text (including "applied outside
  Jarvis" on its own) falls through to "other".
- Date columns (Applied, Follow-up due) are returned as a clean ISO date
  string when the cell IS one (`YYYY-MM-DD`), and `None` for every other
  form seen in the wild ("-", "pre-2026-07-09", "unknown (...)", blank).
  We never guess a precise date for a fuzzy one. A row with a null
  applied_date is still returned (still counted in any funnel over the
  result list) -- it is not dropped.
- Status text has bold markdown, sometimes an emoji, sometimes a trailing
  "(YYYY-MM-DD)". That parenthetical -- if present -- becomes `status_date`.
  When it is absent (e.g. "**Applied** (no date)"), `status_date` is left as
  `None`. It deliberately does NOT fall back to `applied_date`: the two are
  different facts (when the application went in vs. when the status last
  changed) and callers that want a display fallback should do that
  themselves against the return value.
- Any "Closed ..." status variant (e.g. "Closed before applying", "Closed
  (listing gone)") normalizes to the single enum value "closed".
- Tier is derived ONLY from the role title text (never from Notes, which
  this module does not read at all): junior/graduate/grad/intern -> "entry";
  senior/staff/manager/lead/principal/director -> "stretch"; else
  "unspecified".
- The "Notes" column is discarded entirely -- it is never read into any
  field of the returned dict.
- Rows are tolerated even when shorter than the full 7-column header (e.g.
  a row missing "Follow-up due" and/or "Notes" entirely): missing trailing
  cells are treated as empty, never a crash.
"""

from __future__ import annotations

import re
from pathlib import Path

_STRIKETHROUGH_RE = re.compile(r"~~(.*?)~~")
_BOLD_RE = re.compile(r"\*\*(.*?)\*\*")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SEPARATOR_ROW_RE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")

_ENTRY_KEYWORDS = ("junior", "graduate", "grad", "intern")
_STRETCH_KEYWORDS = ("senior", "staff", "manager", "lead", "principal", "director")

_STATUS_PREFIXES = (
    ("closed", "closed"),
    ("applied", "applied"),
    ("rejected", "rejected"),
    ("skipped", "skipped"),
)


def parse(path) -> list[dict]:
    """Parse the "## Applications" table at `path` into a list of row dicts."""
    text = Path(path).read_text(encoding="utf-8")
    rows = list(_extract_table_rows(text))
    return [_parse_row(cells) for cells in rows]


def _extract_table_rows(text: str):
    """Yield the raw cell lists for each data row of the Applications table.

    Skips the section's header row, its `|---|---|...` separator row, and any
    blank/whitespace-only rows. Stops once a new "## " section begins.
    """
    lines = text.splitlines()
    in_section = False
    table_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_section:
                break
            if stripped.lower().startswith("## applications"):
                in_section = True
            continue
        if in_section and stripped.startswith("|"):
            table_lines.append(stripped)

    if len(table_lines) < 2:
        return

    # table_lines[0] is the header row, table_lines[1] is normally the
    # `|---|---|...` separator -- but tolerate stray extra separator/blank
    # rows anywhere by filtering them out rather than assuming position.
    for line in table_lines[1:]:
        if _SEPARATOR_ROW_RE.match(line):
            continue
        cells = _split_row(line)
        if not any(cell for cell in cells):
            continue
        yield cells


def _split_row(line: str) -> list[str]:
    inner = line.strip()
    if inner.startswith("|"):
        inner = inner[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return [cell.strip() for cell in inner.split("|")]


def _parse_row(cells: list[str]) -> dict:
    def cell(i: int) -> str:
        return cells[i] if i < len(cells) else ""

    company = _clean_company_name(cell(0))
    role_title = cell(1).strip()
    channel = _classify_channel(cell(2))
    applied_date = _parse_iso_date(cell(3))
    status, status_date = _parse_status(cell(4))
    followup_due = _parse_iso_date(cell(5))
    # cell(6), Notes, is intentionally never read.

    return {
        "company": company,
        "role_title": role_title,
        "tier": _derive_tier(role_title),
        "channel": channel,
        "applied_date": applied_date,
        "status": status,
        "status_date": status_date,
        "followup_due": followup_due,
    }


def _clean_company_name(text: str) -> str:
    """Strip markdown emphasis wrapping a company cell (strikethrough for a
    skipped/withdrawn row, or bold used to flag a row visually) so the same
    real company never parses to two different string keys depending on
    which emphasis happened to be applied that day -- the anon-ID mapping
    treats company name as an exact key.
    """
    stripped = text.strip()
    match = _STRIKETHROUGH_RE.search(stripped)
    if match:
        stripped = match.group(1).strip()
    match = _BOLD_RE.search(stripped)
    if match:
        stripped = match.group(1).strip()
    return stripped


def _derive_tier(role_title: str) -> str:
    lower = role_title.lower()
    if any(keyword in lower for keyword in _ENTRY_KEYWORDS):
        return "entry"
    if any(keyword in lower for keyword in _STRETCH_KEYWORDS):
        return "stretch"
    return "unspecified"


def _classify_channel(text: str) -> str:
    lower = text.lower()
    if "linkedin" in lower:
        return "linkedin"
    if "workday" in lower:
        return "workday"
    if "indeed" in lower:
        return "indeed"
    if "jooble" in lower:
        return "jooble"
    if "agency" in lower or "recruiter" in lower:
        return "agency"
    if (
        "portal" in lower
        or "e-recruitment" in lower
        or "careers." in lower
        or re.search(r"\bats\b", lower)
    ):
        return "company_portal"
    return "other"


def _parse_iso_date(text: str) -> str | None:
    candidate = text.strip()
    if _ISO_DATE_RE.match(candidate):
        return candidate
    return None


def _parse_status(text: str) -> tuple[str, str | None]:
    stripped = text.strip()
    bold_match = _BOLD_RE.search(stripped)
    label = bold_match.group(1).strip() if bold_match else stripped
    label_lower = label.lower()

    status = "unknown"
    for prefix, enum_value in _STATUS_PREFIXES:
        if label_lower.startswith(prefix):
            status = enum_value
            break

    date_match = _DATE_RE.search(stripped)
    status_date = date_match.group(0) if date_match else None

    return status, status_date
