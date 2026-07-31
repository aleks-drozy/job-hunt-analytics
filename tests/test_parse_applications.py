"""Tests for job_analytics.parse_applications, run against fully FABRICATED
markdown fixtures (never real vault content) that reproduce the messiness of
the real "## Applications" table: strikethrough rows, mixed date formats,
bold+emoji status cells, and short/malformed rows.
"""

import pytest

from job_analytics.parse_applications import parse

HEADER = "| Company | Role | Link | Applied | Status | Follow-up due | Notes |"
SEP = "|---|---|---|---|---|---|---|"


def _write(tmp_path, rows, section_title="## Applications"):
    lines = [section_title, "", HEADER, SEP, *rows]
    path = tmp_path / "JOB_SEARCH.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_clean_applied_row(tmp_path):
    row = "| Acme Robotics | Data Analyst | LinkedIn (07-10) | 2026-07-12 | **Applied** ✅ | 2026-07-19 | reached out to recruiter |"
    path = _write(tmp_path, [row])
    result = parse(path)
    assert len(result) == 1
    r = result[0]
    assert r["company"] == "Acme Robotics"
    assert r["role_title"] == "Data Analyst"
    assert r["tier"] == "unspecified"
    assert r["channel"] == "linkedin"
    assert r["applied_date"] == "2026-07-12"
    assert r["status"] == "applied"
    assert r["status_date"] is None
    assert r["followup_due"] == "2026-07-19"


def test_rejected_row_with_status_date(tmp_path):
    row = "| Northwind Systems | Senior Data Analyst | Workday NWS | 2026-07-05 | **Rejected** (2026-07-17) | — | polite rejection email |"
    path = _write(tmp_path, [row])
    r = parse(path)[0]
    assert r["company"] == "Northwind Systems"
    assert r["tier"] == "stretch"
    assert r["channel"] == "workday"
    assert r["applied_date"] == "2026-07-05"
    assert r["status"] == "rejected"
    assert r["status_date"] == "2026-07-17"
    assert r["followup_due"] is None


def test_struck_through_skipped_row_strips_markup(tmp_path):
    row = "| ~~Globex Corp~~ | Junior Business Analyst | Indeed (Harri ATS) | 2026-07-01 | **Skipped** (2026-07-09) | — | role got pulled |"
    path = _write(tmp_path, [row])
    r = parse(path)[0]
    assert r["company"] == "Globex Corp"
    assert "~" not in r["company"]
    assert r["tier"] == "entry"
    assert r["channel"] == "indeed"
    assert r["status"] == "skipped"
    assert r["status_date"] == "2026-07-09"


def test_bold_wrapped_company_name_strips_markup(tmp_path):
    # Regression: found against the real vault, not the synthetic fixtures --
    # a company cell can itself be bold-wrapped (e.g. to flag it visually in
    # the tracker), and the anon-ID mapping treats company name as an exact
    # key, so "**Acme Robotics**" and "Acme Robotics" must not become two
    # different companies.
    row = "| **Acme Robotics** | Store Assistant | Vacansee | 2026-07-01 | **Applied** ✅ | — | declined via message |"
    path = _write(tmp_path, [row])
    r = parse(path)[0]
    assert r["company"] == "Acme Robotics"
    assert "*" not in r["company"]


@pytest.mark.parametrize(
    "applied_cell",
    ["—", "pre-2026-07-09", "unknown (applied outside Jarvis)", ""],
)
def test_unparseable_applied_date_forms_return_null_not_a_guess(tmp_path, applied_cell):
    row = f"| Initech Ltd | Business Analyst | Jooble (stale) | {applied_cell} | **Applied** ✅ | 2026-07-20 | n/a |"
    path = _write(tmp_path, [row])
    r = parse(path)[0]
    assert r["applied_date"] is None
    # row must still be counted in the funnel even with a null applied_date
    assert r["company"] == "Initech Ltd"
    assert r["channel"] == "jooble"


@pytest.mark.parametrize("keyword", ["Junior", "Graduate", "Grad", "Intern"])
def test_entry_tier_keywords_in_role_title(tmp_path, keyword):
    row = f"| Wayne Analytics | {keyword} Data Analyst | LinkedIn | 2026-07-01 | **Applied** ✅ | — | note |"
    path = _write(tmp_path, [row])
    r = parse(path)[0]
    assert r["tier"] == "entry"


@pytest.mark.parametrize(
    "keyword",
    ["Senior", "Staff", "Manager", "Lead", "Principal", "Director"],
)
def test_stretch_tier_keywords_in_role_title(tmp_path, keyword):
    row = f"| Stark Data Co | {keyword} Analytics Engineer | LinkedIn | 2026-07-01 | **Applied** ✅ | — | note |"
    path = _write(tmp_path, [row])
    r = parse(path)[0]
    assert r["tier"] == "stretch"


def test_unspecified_tier_when_no_keyword_matches(tmp_path):
    row = "| Wonka Systems | Data Analyst | LinkedIn | 2026-07-01 | **Applied** ✅ | — | note |"
    path = _write(tmp_path, [row])
    r = parse(path)[0]
    assert r["tier"] == "unspecified"


@pytest.mark.parametrize(
    "channel_cell,expected",
    [
        ("LinkedIn (07-10)", "linkedin"),
        ("Workday NWS", "workday"),
        ("Indeed (Harri ATS)", "indeed"),
        ("Jooble (stale)", "jooble"),
        ("careers.northwind.com", "company_portal"),
        ("GCU e-recruitment portal", "company_portal"),
        ("Pied Piper Staffing Agency", "agency"),
        ("applied outside Jarvis", "other"),
    ],
)
def test_channel_free_text_classification(tmp_path, channel_cell, expected):
    row = f"| Hooli Metrics | Data Analyst | {channel_cell} | 2026-07-01 | **Applied** ✅ | — | note |"
    path = _write(tmp_path, [row])
    r = parse(path)[0]
    assert r["channel"] == expected


@pytest.mark.parametrize(
    "status_cell,expected_status,expected_date",
    [
        ("**Closed before applying** (2026-07-09)", "closed", "2026-07-09"),
        ("**Closed (listing gone)** (2026-07-17)", "closed", "2026-07-17"),
    ],
)
def test_closed_variants_normalize_to_closed(tmp_path, status_cell, expected_status, expected_date):
    row = f"| Soylent Analytics | Data Analyst | LinkedIn | 2026-07-01 | {status_cell} | — | note |"
    path = _write(tmp_path, [row])
    r = parse(path)[0]
    assert r["status"] == expected_status
    assert r["status_date"] == expected_date


def test_missing_followup_due_and_notes_columns_does_not_crash(tmp_path):
    # Malformed/short row: only 5 cells present (no Follow-up due, no Notes column at all).
    row = "| Umbrella Dynamics | QA Analyst | Indeed (Harri ATS) | 2026-07-15 | **Applied** ✅ |"
    path = _write(tmp_path, [row])
    result = parse(path)
    assert len(result) == 1
    r = result[0]
    assert r["company"] == "Umbrella Dynamics"
    assert r["followup_due"] is None
    assert r["status"] == "applied"


def test_notes_column_is_never_returned(tmp_path):
    row = "| Massive Dynamic | Data Analyst | LinkedIn | 2026-07-01 | **Applied** ✅ | — | this-note-must-never-appear-in-output |"
    path = _write(tmp_path, [row])
    r = parse(path)[0]
    assert "notes" not in r
    for value in r.values():
        assert value != "this-note-must-never-appear-in-output"


def test_header_separator_and_blank_rows_are_skipped(tmp_path):
    rows = [
        "",
        "| Aperture Science Data | Data Analyst | LinkedIn | 2026-07-01 | **Applied** ✅ | — | note |",
        "|  |  |  |  |  |  |  |",
        "| Tyrell Analytics | Data Analyst | LinkedIn | 2026-07-02 | **Applied** ✅ | — | note |",
    ]
    path = _write(tmp_path, rows)
    result = parse(path)
    companies = [r["company"] for r in result]
    assert companies == ["Aperture Science Data", "Tyrell Analytics"]


def test_all_rows_counted_in_funnel_even_with_nulls(tmp_path):
    rows = [
        "| Cyberdyne Systems | Data Analyst | LinkedIn | — | **Applied** ✅ | — | note |",
        "| Wayne Analytics | Senior Data Analyst | Workday | 2026-07-03 | **Rejected** (2026-07-10) | — | note |",
    ]
    path = _write(tmp_path, rows)
    result = parse(path)
    assert len(result) == 2
