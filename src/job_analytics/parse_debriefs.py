"""Parser for daily debrief markdown files.

Scope is deliberately narrow (per project plan: "text mining explicitly deferred"
for v1). This module reads only structure - which fixed emoji section headers are
present - and a handful of pre-aggregated integers out of the Inbox line. It never
reads or returns prose/narrative content from any section body.
"""
import re
from datetime import date as _date
from pathlib import Path

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_real_date(value):
    try:
        _date.fromisoformat(value)
        return True
    except ValueError:
        return False


_SECTION_HEADERS = {
    "has_focus": "🎯 TODAY'S FOCUS",
    "has_projects": "🚧 Projects & agents",
    "has_job_search": "💼 Job search",
    "has_life": "🏋️ Life & discipline",
    "has_finance": "💰 Finance",
    "has_suggestion": "💡 Suggestion",
    "has_today": "📅 Today",
    "has_inbox": "📬 Inbox",
    "has_health": "🩺 Health",
    "has_captures": "📥 Captures",
}

_INBOX_COUNT_RE = re.compile(
    r"(\d+)\s*(?:msgs|messages)\D*?(\d+)\s*unread\D*?(\d+)\s*sensitive",
    re.IGNORECASE,
)

_FRONTMATTER_UPDATED_RE = re.compile(r"^updated:\s*(\S+)", re.MULTILINE)


def _extract_date(filename_stem, text):
    if _DATE_RE.match(filename_stem) and _is_real_date(filename_stem):
        return filename_stem
    match = _FRONTMATTER_UPDATED_RE.search(text)
    if match:
        return match.group(1)
    return None


def _extract_inbox_counts(text):
    lines = text.splitlines()
    header = _SECTION_HEADERS["has_inbox"]

    for i, line in enumerate(lines):
        if header not in line:
            continue

        # The summary sentence is either inline on the header line itself, or
        # on the next non-blank line. Only those candidates are inspected -
        # never the rest of the section body.
        candidates = [line]
        for next_line in lines[i + 1:]:
            if next_line.strip():
                candidates.append(next_line)
            break

        for candidate in candidates:
            match = _INBOX_COUNT_RE.search(candidate)
            if match:
                return int(match.group(1)), int(match.group(2)), int(match.group(3))
        break

    return None, None, None


def parse(dir_path):
    dir_path = Path(dir_path)
    rows = []

    for file_path in sorted(dir_path.glob("*.md")):
        stem = file_path.stem
        if not _DATE_RE.match(stem):
            continue

        text = file_path.read_text(encoding="utf-8")
        date = _extract_date(stem, text)

        row = {"date": date}
        for key, header in _SECTION_HEADERS.items():
            row[key] = header in text

        inbox_count, inbox_unread, inbox_sensitive = _extract_inbox_counts(text)
        row["inbox_count"] = inbox_count
        row["inbox_unread"] = inbox_unread
        row["inbox_sensitive"] = inbox_sensitive

        rows.append(row)

    return rows
