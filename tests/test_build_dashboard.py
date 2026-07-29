# tests/test_build_dashboard.py
"""index.html is a generated artifact - it is built once, at refresh time,
from results/*.csv, not fetched at runtime. These tests hold the builder
to the same standards as the rest of P2/P3: every displayed number must
trace to a literal CSV cell (collect_facts is pure and testable), every
invariant between the CSVs is checked and fails loudly, and the rendered
page is held to the same leak/privacy bar as everything else in this
repo, plus a determinism check (no wall-clock reads, byte-identical
rebuilds)."""
import csv
import re
import shutil
from pathlib import Path

import pytest

from scripts.build_dashboard import (
    CHART_NAMES,
    build_dashboard,
    collect_facts,
    render_dashboard,
)
from scripts.sanitize_check import GENERIC

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
CHARTS = REPO / "charts"

# ---------------------------------------------------------------------------
# The real, verified committed numbers (results/*.csv as of the P3 baseline).
# ---------------------------------------------------------------------------
EXPECTED_FACTS = {
    "n_tracked": "50", "n_submitted": "43", "n_rejected": "15",
    "n_no_response_yet": "28", "n_interviews": "0", "as_of": "2026-07-21",

    "link_tracked_submitted": "43", "link_tracked_employer_closed": "5",
    "link_tracked_skipped": "1", "link_tracked_untracked_outcome": "1",
    "link_submitted_rejected": "15", "link_submitted_no_response_yet": "28",

    "n_days": "19", "first_day": "2026-07-08", "last_day": "2026-07-28",
    "n_days_with_inbox_stats": "8", "total_inbox_msgs": "191",
    "total_sensitive_suppressed": "7",

    "n_rejections_timed": "10", "rejection_days_min": "0",
    "rejection_days_max": "5", "n_excluded_missing_dates": "5",

    "n_channels": "6",
    "channel_n_list": "other 22, company_portal 8, linkedin 8, indeed 5, "
                      "workday 4, jooble 3",
    "linkedin_n_total": "8", "linkedin_n_submitted": "8",
    "linkedin_n_rejected": "0",
    "workday_n_total": "4", "workday_n_rejected": "3",

    "entry_n_total": "11", "entry_n_rejected": "3",
    "stretch_n_total": "6", "stretch_n_rejected": "1",
    "unspecified_n_total": "33", "unspecified_n_rejected": "11",

    "n_ops_total": "65", "n_ops_done": "41", "n_ops_open": "22",
    "n_ops_snoozed": "2", "n_ops_categories": "6",

    "n_ops_timed": "24", "ops_days_open_min": "0", "ops_days_open_max": "6",
    "n_done_without_close_date": "17",

    "buffer_first_pct": "66.0", "buffer_first_date": "2026-07-10",
    "buffer_last_pct": "88.0", "buffer_last_date": "2026-07-24",
    "n_income_change_dates": "2",
}


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _copy_results(tmp_path):
    dest = tmp_path / "results"
    shutil.copytree(RESULTS, dest)
    return dest


def _mutate_csv(path, match_col, match_val, target_col, new_val):
    rows = _read_csv(path)
    header = rows[0].keys() if rows else []
    found = False
    for r in rows:
        if r[match_col] == match_val:
            r[target_col] = new_val
            found = True
    assert found, "fixture bug: no row with %s == %r" % (match_col, match_val)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(header))
        w.writeheader()
        w.writerows(rows)


def _real_channel_rows():
    return _read_csv(RESULTS / "channel_outcomes.csv")


def _real_html():
    facts = collect_facts(RESULTS)
    return render_dashboard(facts, _real_channel_rows())


# ---------------------------------------------------------------------------
# collect_facts correctness
# ---------------------------------------------------------------------------
def test_facts_match_committed_csvs_cell_by_cell():
    facts = collect_facts(RESULTS)
    assert facts == EXPECTED_FACTS


def test_real_results_satisfy_every_invariant():
    # Doesn't raise - the assertion above already proves this, but this
    # test names the property explicitly for anyone scanning test names.
    collect_facts(RESULTS)


def test_zero_interviews_headline_is_read_from_data_not_hardcoded(tmp_path):
    results = _copy_results(tmp_path)
    _mutate_csv(results / "funnel_summary.csv", "n_tracked", "50",
                "n_interviews", "3")
    facts = collect_facts(results)
    assert facts["n_interviews"] == "3"


def test_channel_total_mismatch_raises_value_error_naming_both_sides(tmp_path):
    results = _copy_results(tmp_path)
    _mutate_csv(results / "channel_outcomes.csv", "channel", "other",
                "n_total", "99")
    with pytest.raises(ValueError) as exc:
        collect_facts(results)
    msg = str(exc.value)
    assert "channel_outcomes" in msg
    assert "n_tracked" in msg or "funnel_summary" in msg


def test_tier_total_mismatch_raises_value_error_naming_both_sides(tmp_path):
    results = _copy_results(tmp_path)
    _mutate_csv(results / "tier_outcomes.csv", "tier", "entry",
                "n_total", "99")
    with pytest.raises(ValueError) as exc:
        collect_facts(results)
    msg = str(exc.value)
    assert "tier_outcomes" in msg
    assert "n_tracked" in msg or "funnel_summary" in msg


def test_missing_funnel_link_pair_raises_value_error(tmp_path):
    results = _copy_results(tmp_path)
    rows = _read_csv(results / "funnel_links.csv")
    rows = [r for r in rows if not (r["source"] == "tracked"
                                     and r["target"] == "submitted")]
    with open(results / "funnel_links.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source", "target", "value"])
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(ValueError) as exc:
        collect_facts(results)
    assert "tracked" in str(exc.value) and "submitted" in str(exc.value)


def test_more_than_one_funnel_summary_row_raises_value_error(tmp_path):
    results = _copy_results(tmp_path)
    text = (results / "funnel_summary.csv").read_text(encoding="utf-8")
    (results / "funnel_summary.csv").write_text(
        text + text.splitlines()[1] + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        collect_facts(results)


# ---------------------------------------------------------------------------
# render_dashboard correctness (pure - operates on the real facts/rows)
# ---------------------------------------------------------------------------
def test_every_fact_value_appears_in_the_rendered_html():
    facts = collect_facts(RESULTS)
    html = render_dashboard(facts, _real_channel_rows())
    for key, value in facts.items():
        assert value in html, "fact %s=%r missing from rendered HTML" % (key, value)


def test_no_unfilled_placeholder_survives():
    html = _real_html()
    unfilled = re.findall(r"\{(%s)\}" % "|".join(EXPECTED_FACTS.keys()), html)
    assert not unfilled, "unfilled template placeholder(s): %s" % unfilled


def test_exactly_six_iframes_referencing_existing_chart_files_headline_excluded():
    html = _real_html()
    srcs = re.findall(r'<iframe[^>]+src="([^"]+)"', html)
    assert len(srcs) == 6
    assert len(CHART_NAMES) == 6
    for src in srcs:
        assert src.startswith("charts/")
        chart_path = REPO / src
        assert chart_path.exists(), "%s does not exist" % chart_path
    assert not any(src.endswith("headline.html") for src in srcs)


def test_every_iframe_has_a_title_attribute():
    html = _real_html()
    iframe_tags = re.findall(r"<iframe[^>]*>", html)
    assert len(iframe_tags) == 6
    for tag in iframe_tags:
        assert 'title="' in tag, tag


def test_no_none_or_nan_in_output_joobles_null_rate_is_an_em_dash():
    html = _real_html()
    assert "None" not in html
    assert not re.search(r"\bnan\b", html, flags=re.IGNORECASE)
    # jooble has 3 tracked, 0 submitted, 0 rejected, and an undefined
    # (empty-cell) rejection rate - must render as an em dash, not
    # None/nan/0.0%.
    assert "<td>jooble</td><td>3</td><td>0</td><td>0</td><td>—</td>" in html


def test_linkedin_caveat_present():
    html = _real_html()
    assert "That is not a good result: nothing came back at all." in html


def test_no_github_or_absolute_urls_anywhere():
    html = _real_html()
    for banned in ("github.com", "github.io", "http://", "https://"):
        assert banned not in html


def test_page_passes_the_generic_leak_regexes():
    html = _real_html()
    for name, rx in GENERIC:
        m = rx.search(html)
        assert not m, (name, m.group(0) if m else None)


def test_local_banned_terms_not_present():
    terms_path = REPO / "data" / "banned_terms.txt"
    if not terms_path.exists():
        pytest.skip("data/banned_terms.txt is gitignored/local-only; "
                    "absent in CI, so this check is skipped there")
    html = _real_html().lower()
    for line in terms_path.read_text(encoding="utf-8").splitlines():
        term = line.strip().lower()
        if term:
            assert term not in html, "banned term leaked: %s" % term


# ---------------------------------------------------------------------------
# build_dashboard IO wrapper + determinism
# ---------------------------------------------------------------------------
def test_build_dashboard_writes_a_file_and_returns_its_path(tmp_path):
    out = tmp_path / "index.html"
    result = build_dashboard(RESULTS, CHARTS, out)
    assert result == out
    assert out.exists()
    assert out.read_text(encoding="utf-8") == _real_html()


def test_build_dashboard_is_byte_identical_across_two_runs(tmp_path):
    out1 = tmp_path / "one.html"
    out2 = tmp_path / "two.html"
    build_dashboard(RESULTS, CHARTS, out1)
    build_dashboard(RESULTS, CHARTS, out2)
    assert out1.read_bytes() == out2.read_bytes()


def test_builder_source_has_no_wall_clock_reads():
    source = (REPO / "scripts" / "build_dashboard.py").read_text(encoding="utf-8")
    for forbidden in ("datetime", "time.time", "date.today", "now("):
        assert forbidden not in source, "found forbidden wall-clock token: %s" % forbidden
