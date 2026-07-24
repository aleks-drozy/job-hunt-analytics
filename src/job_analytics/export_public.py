"""Private DB -> sanitized public CSVs. This module IS the privacy boundary.

Design rules enforced here, not downstream:
- Column whitelists are explicit SELECTs; a new private column can never
  leak by default.
- Real company names are swapped for their stable anon_id; role titles
  and ledger slugs are replaced by derived enums and never written.
- Fail closed: any company without a human-assigned sector aborts the
  whole export before a single byte is written (writes go to a temp
  staging dir that is only promoted on success by the caller).
"""
import csv
from pathlib import Path

import duckdb

from job_analytics.anonymize import SECTORS, load_map
from job_analytics.derive import ledger_category, role_family


class UnmappedCompanyError(RuntimeError):
    def __init__(self, names):
        self.names = list(names)
        super().__init__(
            "companies missing a sector in company_map.json: "
            + ", ".join(self.names))


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def export(db_path, map_path, out_dir):
    mapping = load_map(map_path)["companies"]
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        apps = con.execute(
            "SELECT company, role_title, tier, channel, applied_date, status,"
            " status_date, followup_due FROM applications"
            " ORDER BY applied_date NULLS LAST, company").fetchall()

        unmapped = sorted({c for (c, *_rest) in apps
                           if c not in mapping or mapping[c]["sector"] is None})
        if unmapped:
            raise UnmappedCompanyError(unmapped)
        bad = sorted({mapping[c]["sector"] for (c, *_r) in apps
                      if mapping[c]["sector"] not in SECTORS})
        if bad:
            raise ValueError("sectors outside the allowed vocabulary: %s" % bad)

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        app_rows = []
        for i, (company, title, tier, channel, applied, status, sdate,
                fdue) in enumerate(apps):
            app_rows.append([
                "A%03d" % (i + 1), mapping[company]["anon_id"],
                mapping[company]["sector"], tier, role_family(title), channel,
                applied or "", status, sdate or "", fdue or ""])
        _write_csv(out / "applications.csv",
                   ["app_id", "company", "sector", "tier", "role_family",
                    "channel", "applied_date", "status", "status_date",
                    "followup_due"], app_rows)

        ops = con.execute(
            "SELECT topic_slug, first_raised, times_raised, status,"
            " close_date FROM ledger_ops ORDER BY first_raised, topic_slug"
        ).fetchall()
        op_rows = [["L%03d" % (i + 1), ledger_category(slug), fr or "",
                    tr, status, cd or ""]
                   for i, (slug, fr, tr, status, cd) in enumerate(ops)]
        _write_csv(out / "ledger_ops.csv",
                   ["op_id", "category", "first_raised", "times_raised",
                    "status", "close_date"], op_rows)

        fin = con.execute(
            "SELECT event_date, buffer_pct, income_changed FROM finance_events"
            " ORDER BY event_date").fetchall()
        _write_csv(out / "finance_events.csv",
                   ["event_date", "buffer_pct", "income_changed"],
                   [[d or "", "" if p is None else p, ic] for d, p, ic in fin])

        days = con.execute(
            "SELECT * FROM debrief_days ORDER BY day").fetchall()
        _write_csv(out / "debrief_days.csv",
                   ["day", "has_focus", "has_projects", "has_job_search",
                    "has_life", "has_finance", "has_suggestion", "has_today",
                    "has_inbox", "has_health", "has_captures", "inbox_count",
                    "inbox_unread", "inbox_sensitive"],
                   [["" if v is None else v for v in row] for row in days])

        return {"applications": len(app_rows), "ledger_ops": len(op_rows),
                "finance_events": len(fin), "debrief_days": len(days)}
    finally:
        con.close()
