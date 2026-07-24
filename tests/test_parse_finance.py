"""Tests for job_analytics.parse_finance.

All fixture data below is 100% fabricated (invented company-free prose,
invented euro figures, invented dates). It reproduces the *shape* of the real
FINANCE.md `## Log` section -- dated bullets, occasional "(later, same day)"
suffix, mixed prose about buffers/targets and euro amounts -- but no fixture
value here is copied from any real file.

The privacy contract under test: parse() may extract a normalized
buffer_pct (0-100) and an income_changed boolean, and nothing else. It must
be structurally impossible for a raw euro figure to survive into the
returned dicts.
"""
from __future__ import annotations

from job_analytics.parse_finance import parse

# A decoy bullet placed outside the "## Log" section on every fixture. If the
# parser is scoping correctly, this date/percentage/euro-figure must never
# appear in results, no matter what the Log-section body contains.
_DECOY_DATE = "2099-01-01"


def _write_finance_md(tmp_path, log_body: str):
    content = (
        "# Finance Tracker (fabricated test fixture)\n\n"
        "## Overview\n"
        f"- {_DECOY_DATE} - Decoy bullet outside the Log section, buffer at "
        "(99%) and salary changed, EUR 9,999 mentioned.\n\n"
        "## Log\n"
        f"{log_body}"
        "\n## Notes\n"
        f"- {_DECOY_DATE} - Another decoy bullet after Log, buffer at (13%) "
        "and salary confirmed, EUR 8,888 mentioned.\n"
    )
    path = tmp_path / "FINANCE.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_explicit_parenthetical_percentage_near_buffer(tmp_path):
    body = (
        "- 2026-01-05 - Transferred savings into the buffer account, buffer "
        "now sits at (71%) after covering the invented Northwind invoice.\n"
    )
    path = _write_finance_md(tmp_path, body)

    result = parse(path)

    assert len(result) == 1
    entry = result[0]
    assert entry["date"] == "2026-01-05"
    assert entry["buffer_pct"] == 71.0
    assert _DECOY_DATE not in [e["date"] for e in result]


def test_from_x_to_y_percentage_takes_the_later_value(tmp_path):
    body = (
        "- 2026-01-06 - Buffer jumps from 40% to 95% after the invented "
        "freelance invoice cleared.\n"
    )
    path = _write_finance_md(tmp_path, body)

    result = parse(path)

    assert len(result) == 1
    assert result[0]["buffer_pct"] == 95.0


def test_no_percentage_entry_has_null_buffer_pct_and_never_leaks_euro_figures(tmp_path):
    body = (
        "- 2026-01-07 - Rent came out at EUR 1,850 and I moved an extra "
        "430 EUR into savings from the invented freelance payout of "
        "2,600 EUR.\n"
    )
    path = _write_finance_md(tmp_path, body)

    result = parse(path)

    assert len(result) == 1
    entry = result[0]
    assert entry["buffer_pct"] is None

    # Privacy regression test: none of the fabricated euro figures may
    # survive into the parsed output in any form.
    serialized = str(entry)
    assert "1,850" not in serialized
    assert "430" not in serialized
    assert "2,600" not in serialized
    assert "EUR" not in serialized


def test_income_change_pattern_matches(tmp_path):
    body = (
        "- 2026-01-08 - Salary payslip confirmed early this month after "
        "payroll changed its processing dates.\n"
    )
    path = _write_finance_md(tmp_path, body)

    result = parse(path)

    assert len(result) == 1
    assert result[0]["income_changed"] is True


def test_income_change_pattern_does_not_false_positive(tmp_path):
    body = (
        "- 2026-01-09 - Grabbed groceries and paid the invented electricity "
        "bill on time, nothing eventful.\n"
    )
    path = _write_finance_md(tmp_path, body)

    result = parse(path)

    assert len(result) == 1
    assert result[0]["income_changed"] is False


def test_later_same_day_suffix_still_parses_base_iso_date(tmp_path):
    body = (
        "- 2026-01-10 (later, same day) - Second buffer check of the day, "
        "now steady at (60%).\n"
    )
    path = _write_finance_md(tmp_path, body)

    result = parse(path)

    assert len(result) == 1
    assert result[0]["date"] == "2026-01-10"
    assert result[0]["buffer_pct"] == 60.0


def test_only_log_section_bullets_are_parsed_decoys_excluded(tmp_path):
    body = (
        "- 2026-01-11 - First real entry, buffer holding at (50%).\n"
        "- 2026-01-12 - Second real entry, salary changed slightly.\n"
    )
    path = _write_finance_md(tmp_path, body)

    result = parse(path)

    dates = [e["date"] for e in result]
    assert dates == ["2026-01-11", "2026-01-12"]
    assert _DECOY_DATE not in dates
    # The decoy bullets' 99%/13% must never leak into a real entry either.
    assert 99.0 not in [e["buffer_pct"] for e in result]
    assert 13.0 not in [e["buffer_pct"] for e in result]


def test_wrapped_entry_spanning_multiple_physical_lines_still_extracts_percentage(tmp_path):
    # Regression: found against the real vault, not the synthetic fixtures.
    # Real FINANCE.md log entries are long prose that wraps across several
    # physical lines in the markdown source (normal editor line-wrapping),
    # e.g.:
    #   - 2026-01-14 - snapshot update: moved some money around, stocks
    #     shifted a little too. Buffer jumps from 40% to 95% of the
    #     target -- largest move yet.
    # A continuation line does not itself start with "- YYYY-MM-DD", so the
    # entry-matching regex must join it onto the entry it belongs to rather
    # than silently ignore it -- which is what was happening: buffer_pct
    # came back None for every real entry whose percentage happened to sit
    # on a wrapped line rather than the bullet's opening line.
    body = (
        "- 2026-01-14 - snapshot update: moved some money around, stocks\n"
        "  shifted a little too. Buffer jumps from 40% to 95% of the\n"
        "  target -- largest move yet.\n"
        "- 2026-01-15 - a normal single-line entry, buffer steady (30%).\n"
    )
    path = _write_finance_md(tmp_path, body)

    result = parse(path)

    assert len(result) == 2
    assert result[0]["date"] == "2026-01-14"
    assert result[0]["buffer_pct"] == 95.0
    assert result[1]["date"] == "2026-01-15"
    assert result[1]["buffer_pct"] == 30.0


def test_wrapped_entry_income_change_marker_on_a_continuation_line_is_found(tmp_path):
    body = (
        "- 2026-01-16 - long note about groceries and a small purchase,\n"
        "  nothing eventful here really, just filler text to wrap the\n"
        "  line. Income changed today, new source confirmed.\n"
    )
    path = _write_finance_md(tmp_path, body)

    result = parse(path)

    assert len(result) == 1
    assert result[0]["income_changed"] is True


def test_entry_dict_shape_is_minimal(tmp_path):
    body = "- 2026-01-13 - Plain entry with no percentage and no income event.\n"
    path = _write_finance_md(tmp_path, body)

    result = parse(path)

    assert len(result) == 1
    assert set(result[0].keys()) == {"date", "buffer_pct", "income_changed"}
