"""Parser for LEDGER.md's markdown table.

Reads the `| topic | first_raised | times_raised | status | notes |` table and
returns one dict per row: {topic_slug, first_raised, times_raised, status,
close_date}.

The `notes` column is long free prose and is intentionally discarded entirely
(never returned, not even truncated) except for one narrow regex extraction:
when status is "done" and notes begins with a literal "CLOSED YYYY-MM-DD"
pattern, that date is pulled out as `close_date`. Everything else in notes -
including trailing text on that same line - is dropped.
"""
import re

_CLOSED_RE = re.compile(r"^CLOSED\s+(\d{4}-\d{2}-\d{2})")

_ROW_RE = re.compile(
    r"^\|(?P<topic>[^|]*)\|(?P<first_raised>[^|]*)\|(?P<times_raised>[^|]*)\|"
    r"(?P<status>[^|]*)\|(?P<notes>.*)\|\s*$"
)


def _is_separator_row(cells):
    """True for a markdown table separator row like | --- | --- | ... |."""
    return all(re.fullmatch(r":?-{2,}:?", cell.strip()) for cell in cells if cell.strip())


def parse(path):
    text = open(path, encoding="utf-8").read()

    rows = []
    header_seen = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue

        match = _ROW_RE.match(stripped)
        if not match:
            continue

        cells = [
            match.group("topic").strip(),
            match.group("first_raised").strip(),
            match.group("times_raised").strip(),
            match.group("status").strip(),
            match.group("notes").strip(),
        ]

        if not header_seen:
            # First matching row is the header (topic/first_raised/...).
            header_seen = True
            continue

        if _is_separator_row(cells):
            continue

        topic_slug, first_raised, times_raised_raw, status, notes = cells

        close_date = None
        if status == "done":
            closed_match = _CLOSED_RE.match(notes)
            if closed_match:
                close_date = closed_match.group(1)

        rows.append(
            {
                "topic_slug": topic_slug,
                "first_raised": first_raised,
                "times_raised": int(times_raised_raw),
                "status": status,
                "close_date": close_date,
            }
        )

    return rows
