# tests/test_refresh.py
"""refresh.py's main() needs a real vault to exercise end to end (that's
what test_integration_real_vault.py is for, and it's skipped without
JOBHUNT_VAULT_PATH). To test the NEW post-export-promote wiring (run the
SQL analyses, render charts, gate results/) without a real vault, every
vault-dependent step (build, export) is stubbed with a fake that writes
minimal-but-real files, REPO is monkeypatched to an isolated tmp_path so
nothing here ever touches the real repo's data/export/results/charts,
and the actual scan() from sanitize_check.py is exercised for real
against a fake run_analyses()'s output - proving the gate genuinely reuses
the same `banned` list already built for the export gate, not a fresh
empty one."""
import json
import sys

import duckdb
import pytest

import scripts.refresh as refresh

COMPANY = "Acme Real Name"  # the one "private" name in this fixture; it
                             # must never appear in results/ once analyzed


def _fake_build(vault, db):
    """Stand-in for job_analytics.load_db.build: skips the vault entirely
    and writes a tiny real duckdb file with exactly what main() reads
    immediately afterwards (a `company` column on `applications`)."""
    db = refresh.Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE applications (company VARCHAR)")
    con.execute("INSERT INTO applications VALUES (?)", [COMPANY])
    con.close()
    return {"applications": 1}


def _fake_export(db, map_path, out_dir):
    """Stand-in for job_analytics.export_public.export: writes clean,
    already-anonymized CSVs straight to staging, matching sanitize_check's
    EXPECTED_COLUMNS so the existing (unmodified) export gate passes and
    export/ gets promoted for real."""
    out_dir = refresh.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "applications.csv").write_text(
        "app_id,company,sector,tier,role_family,channel,applied_date,"
        "status,status_date,followup_due\n"
        "A001,Company A,tech,entry,swe,linkedin,2026-01-05,applied,,\n",
        encoding="utf-8")
    (out_dir / "ledger_ops.csv").write_text(
        "op_id,category,first_raised,times_raised,status,close_date\n"
        "L001,project,2026-01-04,1,open,\n", encoding="utf-8")
    (out_dir / "finance_events.csv").write_text(
        "event_date,buffer_pct,income_changed\n"
        "2026-01-05,40.0,False\n", encoding="utf-8")
    (out_dir / "debrief_days.csv").write_text(
        "day,has_focus,has_projects,has_job_search,has_life,has_finance,"
        "has_suggestion,has_today,has_inbox,has_health,has_captures,"
        "inbox_count,inbox_unread,inbox_sensitive\n"
        "2026-01-05,True,True,True,True,True,True,True,True,False,False,"
        "5,1,0\n", encoding="utf-8")
    return {"applications": 1, "ledger_ops": 1, "finance_events": 1,
            "debrief_days": 1}


def _prime_repo(tmp_path, monkeypatch):
    """Isolate refresh.main() from the real repo and from any real vault:
    REPO -> tmp_path, argv gives it a harmless --vault value (build() is
    stubbed so the value is never dereferenced), and data/company_map.json
    is pre-seeded with COMPANY already sectored so ensure_mapped() finds
    nothing missing and main() doesn't stop at the human-input gate."""
    monkeypatch.setattr(refresh, "REPO", tmp_path)
    monkeypatch.setattr(refresh, "build", _fake_build)
    monkeypatch.setattr(refresh, "export", _fake_export)
    monkeypatch.setattr(sys, "argv", ["refresh.py", "--vault", "unused"])

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "company_map.json").write_text(json.dumps({
        "companies": {COMPANY: {"anon_id": "Company A", "sector": "tech"}}
    }), encoding="utf-8")


def test_skips_analyses_when_sql_dir_absent(tmp_path, monkeypatch):
    """The brief's trigger condition: `when REPO / "sql" exists`. No sql/
    dir here, so run_analyses/render_all must never be called."""
    _prime_repo(tmp_path, monkeypatch)

    def _boom(*a, **kw):
        raise AssertionError("must not be called when sql/ is absent")

    monkeypatch.setattr(refresh, "run_analyses", _boom)
    monkeypatch.setattr(refresh, "render_all", _boom)

    assert refresh.main() == 0
    assert (tmp_path / "export" / "applications.csv").exists()  # still promoted
    assert not (tmp_path / "results").exists()


def test_clean_results_pass_and_row_counts_are_printed(tmp_path, monkeypatch, capsys):
    _prime_repo(tmp_path, monkeypatch)
    (tmp_path / "sql").mkdir()  # only its existence matters; run_analyses is stubbed

    calls = {}

    def fake_run_analyses(export_dir, sql_dir, results_dir):
        calls["run_analyses"] = (refresh.Path(export_dir), refresh.Path(sql_dir),
                                  refresh.Path(results_dir))
        results_dir = refresh.Path(results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "summary.csv").write_text(
            "metric,value\nn_tracked,1\n", encoding="utf-8")
        return {"summary": 1}

    def fake_render_all(results_dir, charts_dir):
        calls["render_all"] = (refresh.Path(results_dir), refresh.Path(charts_dir))
        charts_dir = refresh.Path(charts_dir)
        charts_dir.mkdir(parents=True, exist_ok=True)
        (charts_dir / "headline.html").write_text("<html></html>", encoding="utf-8")

    monkeypatch.setattr(refresh, "run_analyses", fake_run_analyses)
    monkeypatch.setattr(refresh, "render_all", fake_render_all)

    assert refresh.main() == 0

    # wired with the exact paths the brief specifies
    assert calls["run_analyses"] == (tmp_path / "export", tmp_path / "sql",
                                     tmp_path / "results")
    assert calls["render_all"] == (tmp_path / "results", tmp_path / "charts")

    out = capsys.readouterr().out
    assert "summary" in out and "1" in out  # the row-counts dict got printed
    assert (tmp_path / "charts" / "headline.html").exists()


def test_banned_term_in_results_fails_the_gate_and_reuses_export_banned_list(
        tmp_path, monkeypatch, capsys):
    """The real scan() runs against a fake run_analyses() output that
    leaks COMPANY - the same private name banned for the export gate,
    never re-derived. Proves reuse, not just "a" banned list."""
    _prime_repo(tmp_path, monkeypatch)
    (tmp_path / "sql").mkdir()

    def fake_run_analyses(export_dir, sql_dir, results_dir):
        results_dir = refresh.Path(results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        (results_dir / "summary.csv").write_text(
            "note\n%s leaked into a computed aggregate\n" % COMPANY,
            encoding="utf-8")
        return {"summary": 1}

    render_called = []

    def fake_render_all(results_dir, charts_dir):
        render_called.append(True)
        refresh.Path(charts_dir).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(refresh, "run_analyses", fake_run_analyses)
    monkeypatch.setattr(refresh, "render_all", fake_render_all)

    assert refresh.main() == 2
    assert render_called == [True]  # brief's order: analyze -> render -> gate
    out = capsys.readouterr().out
    assert "banned" in out
    assert "GATE FAILED" in out
    assert "results NOT committed" in out
