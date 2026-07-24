"""Tests for parse_ledger.py against fabricated, synthetic LEDGER.md fixtures.

All topic slugs, dates, company names, and notes prose below are invented for
testing structural messiness (status variants, CLOSED-date extraction, markdown
inside notes) - none of it is drawn from the real vault. Fabricated companies
reuse the same fake universe as test_parse_debriefs.py (Acme Robotics,
Northwind Systems) for consistency.
"""
from job_analytics.parse_ledger import parse


def write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_open_row_parses_basic_fields(tmp_path):
    path = write(
        tmp_path,
        "LEDGER.md",
        """# Ledger

| topic | first_raised | times_raised | status | notes |
|---|---|---|---|---|
| widget-catalog-sync-0705 | 2026-07-05 | 3 | open | Still waiting on Acme Robotics to confirm the sync token rotation. |
""",
    )

    rows = parse(path)

    assert len(rows) == 1
    row = rows[0]
    assert row["topic_slug"] == "widget-catalog-sync-0705"
    assert row["first_raised"] == "2026-07-05"
    assert row["times_raised"] == 3
    assert row["status"] == "open"
    assert row["close_date"] is None
    assert "notes" not in row


def test_done_row_extracts_closed_date_and_drops_rest_of_notes(tmp_path):
    path = write(
        tmp_path,
        "LEDGER.md",
        """# Ledger

| topic | first_raised | times_raised | status | notes |
|---|---|---|---|---|
| invoice-widget-mismatch-0701 | 2026-07-01 | 5 | done | CLOSED 2026-07-10: turned out the Northwind Systems export had a stale currency code, patched the mapping table and reran the batch job twice before totals matched. |
""",
    )

    rows = parse(path)

    assert len(rows) == 1
    row = rows[0]
    assert row["topic_slug"] == "invoice-widget-mismatch-0701"
    assert row["status"] == "done"
    assert row["close_date"] == "2026-07-10"
    assert "notes" not in row

    # Privacy assertion: nothing beyond the leading CLOSED date survives.
    serialized = repr(row)
    assert "Northwind Systems" not in serialized
    assert "stale currency code" not in serialized
    assert "mapping table" not in serialized


def test_done_row_without_closed_prefix_has_null_close_date(tmp_path):
    path = write(
        tmp_path,
        "LEDGER.md",
        """# Ledger

| topic | first_raised | times_raised | status | notes |
|---|---|---|---|---|
| acme-portal-timeout-0630 | 2026-06-30 | 2 | done | Turns out this was resolved organically when Acme Robotics upgraded their ATS; never got a formal close note. |
""",
    )

    rows = parse(path)

    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "done"
    assert row["close_date"] is None
    assert "notes" not in row


def test_snoozed_row_and_unrecognized_status_pass_through(tmp_path):
    path = write(
        tmp_path,
        "LEDGER.md",
        """# Ledger

| topic | first_raised | times_raised | status | notes |
|---|---|---|---|---|
| northwind-billing-sync-0715 | 2026-07-15 | 1 | snoozed | Revisit after Q3 planning; low priority. |
| acme-cold-outreach-archive-0602 | 2026-06-02 | 4 | archived | Not one of the three documented statuses, must not crash the parser. |
""",
    )

    rows = parse(path)

    assert len(rows) == 2
    snoozed_row, archived_row = rows
    assert snoozed_row["status"] == "snoozed"
    assert snoozed_row["close_date"] is None
    assert archived_row["status"] == "archived"
    assert archived_row["close_date"] is None


def test_markdown_formatting_in_notes_does_not_break_row_splitting(tmp_path):
    path = write(
        tmp_path,
        "LEDGER.md",
        """# Ledger

| topic | first_raised | times_raised | status | notes |
|---|---|---|---|---|
| acme-onboarding-flow-0620 | 2026-06-20 | 6 | open | Blocked by **Acme Robotics** — need to confirm `webhook_secret` rotation. See [[Northwind Systems Vendor Notes]] for context, multiple sentences here too. |
| northwind-followup-0621 | 2026-06-21 | 1 | open | Simple row right after a markdown-heavy one, to prove row splitting stayed intact. |
""",
    )

    rows = parse(path)

    assert len(rows) == 2
    first, second = rows
    assert first["topic_slug"] == "acme-onboarding-flow-0620"
    assert first["times_raised"] == 6
    assert "notes" not in first
    assert second["topic_slug"] == "northwind-followup-0621"
    assert second["first_raised"] == "2026-06-21"
    assert second["times_raised"] == 1


def test_times_raised_zero(tmp_path):
    path = write(
        tmp_path,
        "LEDGER.md",
        """# Ledger

| topic | first_raised | times_raised | status | notes |
|---|---|---|---|---|
| acme-cold-outreach-0610 | 2026-06-10 | 0 | open | Never followed up, logged only for tracking purposes. |
""",
    )

    rows = parse(path)

    assert len(rows) == 1
    row = rows[0]
    assert row["times_raised"] == 0
    assert row["times_raised"] is not False  # guard against bool/int mixups
    assert row["status"] == "open"
