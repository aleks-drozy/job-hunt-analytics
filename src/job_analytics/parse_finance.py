"""Parser for FINANCE.md's ``## Log`` section.

Extracts only privacy-safe, already-normalized fields from free-prose dated
bullet entries: the entry date, an explicit buffer/target percentage (if the
entry states one), and a boolean income-change event marker.

PRIVACY CONTRACT: this module must never extract or retain a raw euro
figure, anywhere, in any form. It is enforced structurally, not by later
filtering -- the only regexes here look for "%" tokens or plain keyword
proximity; no euro/currency pattern is ever matched, captured, or stored,
and the returned dict shape has no room for one (date, buffer_pct,
income_changed -- nothing else).
"""
from __future__ import annotations

import re
from typing import Optional

# A dated log bullet, e.g.:
#   "- 2026-01-05 - transferred savings, buffer now sits at (71%)."
#   "- 2026-01-05 (later, same day) - topped up again, now steady."
# The optional parenthetical right after the date (e.g. "(later, same day)")
# is swallowed and discarded -- only the leading ISO date is kept.
_ENTRY_RE = re.compile(
    r'^\s*-\s*(\d{4}-\d{2}-\d{2})\s*(?:\([^)]*\))?\s*-\s*(.*\S)\s*$'
)

_HEADING_RE = re.compile(r'^\s*#{1,6}\s')
_LOG_HEADING_RE = re.compile(r'^\s*#{1,6}\s*Log\b', re.IGNORECASE)

_PCT_RE = re.compile(r'(\d{1,3}(?:\.\d+)?)\s*%')
_PAREN_PCT_RE = re.compile(r'\((\d{1,3}(?:\.\d+)?)\s*%\)')
_BUFFER_TARGET_RE = re.compile(r'buffer|target', re.IGNORECASE)

_INCOME_CHANGE_RE = re.compile(
    r'\b(income|salary|pay(?:check|slip)?|UPS|parents?)\b.{0,40}'
    r'\b(chang\w*|stop\w*|drop\w*|start\w*|confirm\w*|rebuil\w*)',
    re.IGNORECASE,
)

# How close (in characters) a "%" token must be to the word "buffer" or
# "target" to count as describing that percentage.
_PROXIMITY_WINDOW = 80


def _extract_buffer_pct(text: str) -> Optional[float]:
    """Find an explicit, already-computed buffer/target percentage, if any.

    Never computes a percentage from euro figures -- only ever recognizes an
    existing "NN%" token already present in the prose, either near the words
    "buffer"/"target" or as a standalone "(NN%)" parenthetical in the back
    half of the entry. When multiple percentages qualify (e.g. "jumps from
    40% to 95%"), the LATER one in the text wins. Returns None if no
    qualifying percentage is found -- never a guess.
    """
    candidates: list[tuple[int, float]] = []

    buffer_target_spans = [m.span() for m in _BUFFER_TARGET_RE.finditer(text)]

    for m in _PCT_RE.finditer(text):
        start, end = m.span()
        near_buffer_or_target = any(
            (start - _PROXIMITY_WINDOW) <= bt_end and bt_start <= (end + _PROXIMITY_WINDOW)
            for bt_start, bt_end in buffer_target_spans
        )
        if near_buffer_or_target:
            candidates.append((start, float(m.group(1))))

    midpoint = len(text) / 2
    for m in _PAREN_PCT_RE.finditer(text):
        start, _end = m.span()
        if start >= midpoint:
            candidates.append((start, float(m.group(1))))

    if not candidates:
        return None

    candidates.sort(key=lambda c: c[0])
    return candidates[-1][1]


def _income_changed(text: str) -> bool:
    return _INCOME_CHANGE_RE.search(text) is not None


def parse(path) -> list[dict]:
    """Parse the ``## Log`` section of a FINANCE.md file.

    Returns one dict per dated bullet entry found under the Log heading
    (bullets outside that section, e.g. under other headings, are ignored),
    shaped exactly:

        {"date": "YYYY-MM-DD", "buffer_pct": float | None, "income_changed": bool}

    No euro amounts, no raw prose, and no other fields are ever included.
    """
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    entries: list[dict] = []
    in_log_section = False

    for raw_line in lines:
        line = raw_line.rstrip('\n')

        if _LOG_HEADING_RE.match(line):
            in_log_section = True
            continue

        if in_log_section and _HEADING_RE.match(line):
            in_log_section = False
            continue

        if not in_log_section:
            continue

        m = _ENTRY_RE.match(line)
        if not m:
            continue

        date, entry_text = m.group(1), m.group(2)
        entries.append({
            'date': date,
            'buffer_pct': _extract_buffer_pct(entry_text),
            'income_changed': _income_changed(entry_text),
        })

    return entries
