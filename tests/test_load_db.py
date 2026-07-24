"""Loader is a full rebuild: parse all four sources into a fresh DuckDB.
The fixture builds a tiny fake vault in tmp_path - every value fabricated."""
import duckdb
from job_analytics.load_db import build

APPS_MD = """# Tracker

## Applications
| Company | Role | Link | Applied | Status | Follow-up due | Notes |
|---|---|---|---|---|---|---|
| Acme Robotics | Graduate Software Engineer | LinkedIn (01-05) | 2026-01-05 | **Applied** ✅ | 2026-01-15 | some throwaway prose |
| Northwind Systems | Senior Quant Developer | Workday | 2026-01-06 | **Rejected** (2026-01-09) | — | more prose |

## Next section
"""

LEDGER_MD = """# Ledger

| topic | first_raised | times_raised | status | notes |
|---|---|---|---|---|
| widget-tracker-ci-fail | 2026-01-04 | 2 | done | CLOSED 2026-01-06 fixed the widget pipeline |
| bank-feed-heartbeat-gap | 2026-01-05 | 1 | open | still watching this |
"""

FINANCE_MD = """# Finance

## Log
- 2026-01-05 - buffer at 40% of target after EUR 1,234 moved around.
- 2026-01-06 - income changed: new freelance payment started this week.
"""

DEBRIEF_MD = """---
updated: 2026-01-06
---

## 🎯 TODAY'S FOCUS
Fabricated focus line.

## 📬 Inbox
5 msgs (1 unread, 0 sensitive)
"""


def _fake_vault(tmp_path):
    (tmp_path / "JOB_SEARCH.md").write_text(APPS_MD, encoding="utf-8")
    (tmp_path / "LEDGER.md").write_text(LEDGER_MD, encoding="utf-8")
    (tmp_path / "FINANCE.md").write_text(FINANCE_MD, encoding="utf-8")
    d = tmp_path / "debriefs"
    d.mkdir()
    (d / "2026-01-06.md").write_text(DEBRIEF_MD, encoding="utf-8")
    return tmp_path


def test_build_creates_all_four_tables_with_expected_rows(tmp_path):
    vault = _fake_vault(tmp_path)
    db = tmp_path / "private.duckdb"
    counts = build(vault, db)
    assert counts == {"applications": 2, "ledger_ops": 2,
                      "finance_events": 2, "debrief_days": 1}

    con = duckdb.connect(str(db), read_only=True)
    apps = con.execute(
        "SELECT company, tier, channel, status FROM applications ORDER BY company"
    ).fetchall()
    assert apps[0] == ("Acme Robotics", "entry", "linkedin", "applied")
    assert apps[1][3] == "rejected"
    led = con.execute(
        "SELECT topic_slug, close_date IS NOT NULL FROM ledger_ops ORDER BY topic_slug"
    ).fetchall()
    assert ("widget-tracker-ci-fail", True) in led
    con.close()


def test_build_is_a_full_rebuild_not_an_append(tmp_path):
    vault = _fake_vault(tmp_path)
    db = tmp_path / "private.duckdb"
    build(vault, db)
    counts = build(vault, db)  # second run over identical input
    assert counts["applications"] == 2  # not 4
