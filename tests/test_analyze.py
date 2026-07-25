"""The runner is generic; the funnel SQL is the first real consumer.
Fixture = a synthetic export small enough to hand-compute every number."""
import csv
from scripts.analyze import run_analyses

APPS = """app_id,company,sector,tier,role_family,channel,applied_date,status,status_date,followup_due
A001,Company A,tech,entry,swe,linkedin,2026-01-05,applied,,2026-01-15
A002,Company B,fintech,stretch,quant,workday,2026-01-06,rejected,2026-01-09,
A003,Company C,tech,entry,swe,indeed,2026-01-07,rejected,2026-01-07,
A004,Company D,other,unspecified,other,other,,skipped,2026-01-08,
A005,Company E,bank,unspecified,data,jooble,,closed,2026-01-09,
A006,Company F,tech,entry,ai_ml,linkedin,2026-01-10,unknown,,
"""

def _fake_export(tmp_path):
    ex = tmp_path / "export"; ex.mkdir()
    (ex / "applications.csv").write_text(APPS, encoding="utf-8")
    (ex / "ledger_ops.csv").write_text(
        "op_id,category,first_raised,times_raised,status,close_date\n"
        "L001,project,2026-01-04,2,done,2026-01-06\n"
        "L002,finance,2026-01-05,1,open,\n", encoding="utf-8")
    (ex / "finance_events.csv").write_text(
        "event_date,buffer_pct,income_changed\n"
        "2026-01-05,40.0,False\n2026-01-08,,True\n2026-01-09,95.0,False\n",
        encoding="utf-8")
    (ex / "debrief_days.csv").write_text(
        "day,has_focus,has_projects,has_job_search,has_life,has_finance,"
        "has_suggestion,has_today,has_inbox,has_health,has_captures,"
        "inbox_count,inbox_unread,inbox_sensitive\n"
        "2026-01-05,True,True,True,True,True,True,True,True,False,False,5,1,0\n",
        encoding="utf-8")
    return ex

def _read(results_dir, name):
    with open(results_dir / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def test_runner_executes_all_sql_and_names_outputs(tmp_path):
    ex = _fake_export(tmp_path)
    out = tmp_path / "results"
    counts = run_analyses(ex, "sql", out)
    assert "funnel_links" in counts and "funnel_summary" in counts
    assert (out / "funnel_links.csv").exists()

def test_funnel_links_math(tmp_path):
    ex = _fake_export(tmp_path)
    out = tmp_path / "results"
    run_analyses(ex, "sql", out)
    links = {(r["source"], r["target"]): int(r["value"])
             for r in _read(out, "funnel_links.csv")}
    # 6 tracked: submitted = applied+rejected = 3; skipped 1; closed 1; unknown 1
    assert links[("tracked", "submitted")] == 3
    assert links[("tracked", "skipped")] == 1
    assert links[("tracked", "employer_closed")] == 1
    assert links[("tracked", "untracked_outcome")] == 1
    assert links[("submitted", "rejected")] == 2
    assert links[("submitted", "no_response_yet")] == 1

def test_funnel_summary_computes_interviews_and_as_of_from_data(tmp_path):
    ex = _fake_export(tmp_path)
    out = tmp_path / "results"
    run_analyses(ex, "sql", out)
    s = _read(out, "funnel_summary.csv")[0]
    assert int(s["n_tracked"]) == 6
    assert int(s["n_interviews"]) == 0      # computed, not hardcoded
    assert s["as_of"] == "2026-01-15"       # max date anywhere in applications
