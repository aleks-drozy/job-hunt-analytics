"""The publish gate. Nothing enters export/ (and so nothing reaches the
public repo) unless this scan comes back empty.

Two layers:
- generic + structural rules, committed here, run everywhere incl. CI:
  email shapes, currency shapes, IBAN/phone shapes, exact column
  whitelists per CSV, and the Company-XX anon pattern.
- private lists, local machine only (gitignored): every real company
  name from data/company_map.json plus data/banned_terms.txt lines.
  CI cannot run these (the lists don't exist there) - that is by
  design, the real names must not exist in CI either.

Every invocation first runs a POSITIVE CONTROL: a planted-violation file
is generated and scanned, and if the scanner fails to flag every planted
pattern the run aborts with exit 2. An instrument that cannot see a
planted leak must not be trusted to clear a real export.
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

GENERIC = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("currency", re.compile(r"(?:EUR|GBP|USD|[€£$])\s?\d")),
    ("currency_post", re.compile(r"\d\s?(?:EUR|GBP|USD|€|£)")),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")),
    ("phone", re.compile(r"\+\d{2,3}[\s-]?\d{2,4}[\s-]?\d{3}")),
]

EXPECTED_COLUMNS = {
    "applications.csv": ["app_id", "company", "sector", "tier", "role_family",
                         "channel", "applied_date", "status", "status_date",
                         "followup_due"],
    "ledger_ops.csv": ["op_id", "category", "first_raised", "times_raised",
                       "status", "close_date"],
    "finance_events.csv": ["event_date", "buffer_pct", "income_changed"],
    "debrief_days.csv": ["day", "has_focus", "has_projects", "has_job_search",
                         "has_life", "has_finance", "has_suggestion",
                         "has_today", "has_inbox", "has_health",
                         "has_captures", "inbox_count", "inbox_unread",
                         "inbox_sensitive"],
}
FORBIDDEN_COLUMNS = {"role_title", "topic_slug", "notes", "company_real",
                     "email", "link"}
ANON_RE = re.compile(r"^Company [A-Z]{1,2}$")


def scan(export_dir, banned_terms):
    export_dir = Path(export_dir)
    findings = []
    banned_lower = [b.lower() for b in banned_terms if b.strip()]

    for path in sorted(export_dir.glob("*.csv")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines:
            continue
        header = [h.strip() for h in lines[0].split(",")]

        expected = EXPECTED_COLUMNS.get(path.name)
        if expected is not None and header != expected:
            findings.append("%s:1  [columns]  expected %s got %s"
                            % (path.name, expected, header))
        for col in header:
            if col.lower() in FORBIDDEN_COLUMNS:
                findings.append("%s:1  [forbidden_column]  %s"
                                % (path.name, col))

        company_idx = header.index("company") if "company" in header else None
        for n, line in enumerate(lines, start=1):
            low = line.lower()
            for name, rx in GENERIC:
                m = rx.search(line)
                if m:
                    findings.append("%s:%d  [%s]  %s"
                                    % (path.name, n, name, m.group(0)))
            for term in banned_lower:
                if term in low:
                    findings.append("%s:%d  [banned]  %s"
                                    % (path.name, n, term))
            if company_idx is not None and n > 1 and line.strip():
                cells = line.split(",")
                if len(cells) > company_idx and \
                        not ANON_RE.match(cells[company_idx].strip()):
                    findings.append("%s:%d  [anon_pattern]  %s"
                                    % (path.name, n, cells[company_idx]))
    return findings


def positive_control(workdir=None):
    """Prove the scanner can still see. Returns True only if every planted
    pattern is flagged."""
    planted = ("note\n"
               "reach control-plant@fabricated-control.test\n"
               "EUR 9,876 moved\n"
               "IE29AIBK93115212345678\n"
               "call +353 86 1234567\n"
               "controlbannedco appears here\n")
    with tempfile.TemporaryDirectory(dir=workdir) as td:
        p = Path(td) / "control.csv"
        p.write_text(planted, encoding="utf-8")
        found = scan(Path(td), banned_terms=["ControlBannedCo"])
        rules_hit = {f.split("[", 1)[1].split("]")[0] for f in found}
        return {"email", "currency", "iban", "phone",
                "banned"}.issubset(rules_hit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("--ci", action="store_true",
                    help="generic+structural rules only (no private lists)")
    args = ap.parse_args()

    if not positive_control():
        print("POSITIVE CONTROL FAILED - the scanner itself is broken; "
              "refusing to certify anything")
        return 2

    banned = []
    if not args.ci:
        repo = Path(__file__).resolve().parents[1]
        map_path = repo / "data" / "company_map.json"
        terms_path = repo / "data" / "banned_terms.txt"
        if map_path.exists():
            banned += list(json.loads(
                map_path.read_text(encoding="utf-8"))["companies"].keys())
        if terms_path.exists():
            banned += terms_path.read_text(encoding="utf-8").splitlines()
        if not banned:
            print("WARNING: local mode but no private lists found - "
                  "did you mean --ci? Refusing to pass silently.")
            return 2

    findings = scan(args.export_dir, banned)
    for f in findings:
        print(f)
    print("%d finding(s)" % len(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
