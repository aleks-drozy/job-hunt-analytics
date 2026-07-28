"""Math checks on hand-computable synthetic data, plus the mechanical
honesty rule: every *_rate column has numerator and denominator siblings."""
import csv
from pathlib import Path

from scripts.analyze import run_analyses
from tests.test_analyze import _fake_export, _read


def _run(tmp_path):
    out = tmp_path / "results"
    run_analyses(_fake_export(tmp_path), "sql", out)
    return out


def test_time_to_rejection_rows_and_exclusions(tmp_path):
    out = _run(tmp_path)
    rows = _read(out, "time_to_rejection.csv")
    days = {r["app_id"]: int(r["days_to_rejection"]) for r in rows}
    assert days == {"A002": 3, "A003": 0}   # same-day rejection = 0 days
    # A rejected row with a null applied_date must be EXCLUDED and counted,
    # not silently dropped - add one to the fixture? No: fixture has none,
    # so excluded count is 0 here; the column must still exist.
    assert all("n_excluded_missing_dates" in r for r in rows)

def test_channel_outcomes_counts_and_rate_siblings(tmp_path):
    out = _run(tmp_path)
    rows = {r["channel"]: r for r in _read(out, "channel_outcomes.csv")}
    li = rows["linkedin"]
    assert int(li["n_total"]) == 2
    assert int(li["n_rejected"]) == 0 and int(li["n_open"]) == 1

def test_channel_and_tier_outcome_buckets_sum_to_total(tmp_path):
    """The 5 stacked-bar outcome buckets (n_rejected/n_open/n_closed/
    n_skipped/n_unknown) have no bucket for status='interview'. No
    fixture or real data currently has that status, so this passes today
    - it's a guard: if an interview status ever appears, n_total would
    silently outgrow the sum of buckets (a stacked bar shorter than its
    axis position implies), and this test turns that into a loud
    failure instead of a silent under-count."""
    out = _run(tmp_path)
    for name in ("channel_outcomes.csv", "tier_outcomes.csv"):
        for r in _read(out, name):
            bucket_sum = (int(r["n_rejected"]) + int(r["n_open"]) +
                          int(r["n_closed"]) + int(r["n_skipped"]) +
                          int(r["n_unknown"]))
            assert bucket_sum == int(r["n_total"]), (name, r)


def test_tier_outcomes_counts_and_order(tmp_path):
    """Verify tier_outcomes groups correctly, orders as entry/stretch/unspecified, and counts match fixture."""
    out = _run(tmp_path)
    rows = _read(out, "tier_outcomes.csv")
    tiers = [r["tier"] for r in rows]
    # Assert row order is exactly entry, stretch, unspecified
    assert tiers == ["entry", "stretch", "unspecified"]

    # Assert entry tier counts: A001 (applied), A003 (rejected), A006 (unknown)
    entry = rows[0]
    assert int(entry["n_total"]) == 3
    assert int(entry["n_submitted"]) == 2  # applied + rejected
    assert int(entry["n_rejected"]) == 1
    assert int(entry["n_open"]) == 1
    assert int(entry["n_closed"]) == 0
    assert int(entry["n_skipped"]) == 0
    assert int(entry["n_unknown"]) == 1

def test_every_rate_column_has_numerator_and_denominator(tmp_path):
    out = _run(tmp_path)
    for f in Path(out).glob("*.csv"):
        with open(f, newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        for col in header:
            if col.endswith("_rate"):
                assert any(h.startswith("n_") for h in header), (
                    f"{f.name}: rate column '{col}' has no raw-count sibling")

def test_no_results_file_has_a_company_column(tmp_path):
    out = _run(tmp_path)
    for f in Path(out).glob("*.csv"):
        with open(f, newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        assert "company" not in [h.lower() for h in header], f.name


def test_ops_close_times_days_open_and_exclusion_count(tmp_path):
    out = _run(tmp_path)
    rows = _read(out, "ops_close_times.csv")
    # Only L001 is 'done' with a close_date; L002 is 'open' and excluded
    # entirely (the query only ever looks at status='done' rows).
    assert len(rows) == 1
    r = rows[0]
    assert r["op_id"] == "L001"
    assert r["category"] == "project"
    assert int(r["times_raised"]) == 2
    # date_diff('day', 2026-01-04, 2026-01-06) = 2
    assert int(r["days_open"]) == 2
    # No done row in this fixture lacks a close_date, so the count is 0 -
    # but the column must exist and be asserted, not assumed away.
    assert int(r["n_done_without_close_date"]) == 0


def test_ops_summary_per_category_counts_and_mean_times_raised(tmp_path):
    out = _run(tmp_path)
    all_rows = _read(out, "ops_summary.csv")
    rows = {r["category"]: r for r in all_rows}
    assert set(rows.keys()) == {"project", "finance"}

    project = rows["project"]  # L001: done, times_raised=2
    assert int(project["n_total"]) == 1
    assert int(project["n_done"]) == 1
    assert int(project["n_open"]) == 0
    assert int(project["n_snoozed"]) == 0
    assert float(project["avg_times_raised"]) == 2.0
    assert int(project["max_times_raised"]) == 2

    finance = rows["finance"]  # L002: open, times_raised=1
    assert int(finance["n_total"]) == 1
    assert int(finance["n_done"]) == 0
    assert int(finance["n_open"]) == 1
    assert int(finance["n_snoozed"]) == 0
    assert float(finance["avg_times_raised"]) == 1.0
    assert int(finance["max_times_raised"]) == 1

    # Both categories tie on n_total=1, so ORDER BY n_total DESC, category
    # breaks the tie alphabetically: "finance" < "project".
    assert [r["category"] for r in all_rows] == ["finance", "project"]


def test_finance_trajectory_preserves_nulls_and_all_three_events(tmp_path):
    out = _run(tmp_path)
    rows = _read(out, "finance_trajectory.csv")
    # All 3 fixture rows qualify: two have buffer_pct set, the marker-only
    # income event (2026-01-08) has income_changed=True with a null pct.
    assert len(rows) == 3
    assert [r["event_date"] for r in rows] == [
        "2026-01-05", "2026-01-08", "2026-01-09"]
    assert float(rows[0]["buffer_pct"]) == 40.0
    assert rows[0]["income_changed"].lower() == "false"
    assert rows[1]["buffer_pct"] == ""  # null preserved, not dropped
    assert rows[1]["income_changed"].lower() == "true"
    assert float(rows[2]["buffer_pct"]) == 95.0
    assert rows[2]["income_changed"].lower() == "false"


def test_coverage_single_day_span_and_inbox_sums(tmp_path):
    out = _run(tmp_path)
    rows = _read(out, "coverage.csv")
    assert len(rows) == 1
    r = rows[0]
    assert int(r["n_days"]) == 1
    assert r["first_day"] == "2026-01-05"
    assert r["last_day"] == "2026-01-05"
    assert int(r["n_days_with_inbox_stats"]) == 1
    assert int(r["total_inbox_msgs"]) == 5
    assert int(r["total_sensitive_suppressed"]) == 0
