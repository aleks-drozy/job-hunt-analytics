"""Run every committed sql/*.sql against DuckDB views over export/*.csv,
writing one results/<name>.csv per query.

The SQL runs against the PUBLIC export only - never the private DB. That
is P2's own exit criterion from the master plan: every figure must be
reproducible from the sanitized dataset alone, by anyone.

nullstr='' is load-bearing: the exporter writes empty cells for null
dates/percentages, and without it DuckDB reads them as empty strings and
date arithmetic silently fails.
"""
import sys
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]

_VIEWS = {
    "applications": "applications.csv",
    "ledger_ops": "ledger_ops.csv",
    "finance_events": "finance_events.csv",
    "debrief_days": "debrief_days.csv",
}


def run_analyses(export_dir, sql_dir, results_dir):
    export_dir, sql_dir = Path(export_dir), Path(sql_dir)
    if not sql_dir.is_absolute():
        # Tests pass "sql" bare; resolve against the repo, not the cwd,
        # so the suite passes regardless of where pytest was invoked from.
        sql_dir = REPO / sql_dir
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect()
    try:
        for view, filename in _VIEWS.items():
            csv_path = str(export_dir / filename).replace("'", "''")
            con.execute(
                "CREATE VIEW %s AS SELECT * FROM read_csv('%s', header=true,"
                " nullstr='')" % (view, csv_path))
        counts = {}
        for sql_path in sorted(sql_dir.glob("*.sql")):
            name = sql_path.stem.split("_", 1)[1]  # 01_funnel_links -> funnel_links
            query = sql_path.read_text(encoding="utf-8")
            rel = con.sql(query)
            out = results_dir / (name + ".csv")
            rel.write_csv(str(out), header=True)
            counts[name] = len(rel.fetchall())
        return counts
    finally:
        con.close()


if __name__ == "__main__":
    result = run_analyses(REPO / "export", REPO / "sql", REPO / "results")
    for name, n in result.items():
        print("%s: %d row(s)" % (name, n))
    sys.exit(0)
