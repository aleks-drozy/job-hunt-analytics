"""Full rebuild of the PRIVATE DuckDB from the vault markdown.

This database is gitignored and never leaves the machine. It is rebuilt
from scratch on every refresh (delete + recreate) - the vault files are
the single source of truth and append-style loading would just invite
drift. Dates arrive from the parsers as ISO strings or None; DuckDB
casts them on insert via explicit CAST in the INSERT statements.
"""
from pathlib import Path

import duckdb

from job_analytics.parse_applications import parse as parse_apps
from job_analytics.parse_debriefs import parse as parse_debriefs
from job_analytics.parse_finance import parse as parse_finance
from job_analytics.parse_ledger import parse as parse_ledger

_DDL = """
CREATE TABLE applications (
  app_seq INTEGER NOT NULL,
  company VARCHAR NOT NULL,
  role_title VARCHAR NOT NULL,
  tier VARCHAR NOT NULL,
  channel VARCHAR NOT NULL,
  applied_date DATE,
  status VARCHAR NOT NULL,
  status_date DATE,
  followup_due DATE
);
CREATE TABLE ledger_ops (
  op_seq INTEGER NOT NULL,
  topic_slug VARCHAR NOT NULL,
  first_raised DATE,
  times_raised INTEGER NOT NULL,
  status VARCHAR NOT NULL,
  close_date DATE
);
CREATE TABLE finance_events (
  event_date DATE,
  buffer_pct DOUBLE,
  income_changed BOOLEAN NOT NULL
);
CREATE TABLE debrief_days (
  day DATE,
  has_focus BOOLEAN, has_projects BOOLEAN, has_job_search BOOLEAN,
  has_life BOOLEAN, has_finance BOOLEAN, has_suggestion BOOLEAN,
  has_today BOOLEAN, has_inbox BOOLEAN, has_health BOOLEAN,
  has_captures BOOLEAN,
  inbox_count INTEGER, inbox_unread INTEGER, inbox_sensitive INTEGER
);
"""


def build(vault_path, db_path):
    vault = Path(vault_path)
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    apps = parse_apps(vault / "JOB_SEARCH.md")
    ops = parse_ledger(vault / "LEDGER.md")
    fin = parse_finance(vault / "FINANCE.md")
    days = parse_debriefs(vault / "debriefs")

    con = duckdb.connect(str(db_path))
    try:
        con.execute(_DDL)
        for i, r in enumerate(apps):
            con.execute(
                "INSERT INTO applications VALUES (?,?,?,?,?,CAST(? AS DATE),?,"
                "CAST(? AS DATE),CAST(? AS DATE))",
                [i + 1, r["company"], r["role_title"], r["tier"], r["channel"],
                 r["applied_date"], r["status"], r["status_date"],
                 r["followup_due"]])
        for i, r in enumerate(ops):
            con.execute(
                "INSERT INTO ledger_ops VALUES (?,?,CAST(? AS DATE),?,?,"
                "CAST(? AS DATE))",
                [i + 1, r["topic_slug"], r["first_raised"], r["times_raised"],
                 r["status"], r["close_date"]])
        for r in fin:
            con.execute("INSERT INTO finance_events VALUES (CAST(? AS DATE),?,?)",
                        [r["date"], r["buffer_pct"], r["income_changed"]])
        for r in days:
            con.execute(
                "INSERT INTO debrief_days VALUES (CAST(? AS DATE),?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [r["date"], r["has_focus"], r["has_projects"],
                 r["has_job_search"], r["has_life"], r["has_finance"],
                 r["has_suggestion"], r["has_today"], r["has_inbox"],
                 r["has_health"], r["has_captures"], r["inbox_count"],
                 r["inbox_unread"], r["inbox_sensitive"]])
        return {"applications": len(apps), "ledger_ops": len(ops),
                "finance_events": len(fin), "debrief_days": len(days)}
    finally:
        con.close()
