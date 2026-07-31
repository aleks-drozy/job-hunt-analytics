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

Rows are parsed with csv.reader (not str.split(",")) so quoted commas
and quoting in general are handled per RFC4180, and every data row's
cell count is checked against the header - a row with a smuggled extra
field is a finding ([row_length]) even if none of the other rules
happen to fire on it. Every line is Unicode-NFKC-normalized before any
regex or substring check runs, so fullwidth homoglyphs (e.g. the
fullwidth '@') can't be used to dodge the generic shape checks.
"""
import argparse
import csv
import io
import json
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

GENERIC = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("currency", re.compile(r"(?:EUR|GBP|USD|[€£$])\s*\d")),
    ("currency_post", re.compile(r"\d\s*(?:EUR|GBP|USD|€|£)")),
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


def _collapse_ws(s):
    """Collapse any run of whitespace (including NBSP and other Unicode
    whitespace) to a single ASCII space, so 'Acme  Robotics' (double
    space, or NBSP, or a tab) still matches 'Acme Robotics'."""
    return re.sub(r"\s+", " ", s)


def compile_banned(terms):
    """Compile each banned term into a (term, regex) pair using lookaround
    word-boundary matching: `(?<!\\w)term(?!\\w)`, NOT `\\bterm\\b`.

    This matters: several real banned entries end in a non-word character
    (company_map keys ending in `)` for parenthesized-acronym entries).
    `re.escape(term) + r"\\b"` requires a word char inside the closing
    paren's edge, so it silently never matches those terms -- a false
    negative in a privacy gate. Lookarounds give correct "not glued to a
    word character" semantics for any term shape, while still killing the
    "3-char term inside a longer word" false positive (e.g. a term 'vex'
    must not fire on 'convex' or 'mixups').
    """
    return [
        (term, re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)"))
        for term in (_collapse_ws(b.lower()) for b in terms if b.strip())
    ]


def load_private_terms():
    """Load the gitignored, local-machine-only banned-term lists: every
    real company name from data/company_map.json plus data/banned_terms.txt
    lines. Returns an empty list if the private lists don't exist (e.g. in
    CI, by design)."""
    repo = Path(__file__).resolve().parents[1]
    map_path = repo / "data" / "company_map.json"
    terms_path = repo / "data" / "banned_terms.txt"
    terms = []
    if map_path.exists():
        terms += list(json.loads(
            map_path.read_text(encoding="utf-8"))["companies"].keys())
    if terms_path.exists():
        terms += terms_path.read_text(encoding="utf-8").splitlines()
    return terms


def scan(export_dir, banned_terms):
    export_dir = Path(export_dir)
    findings = []

    if not export_dir.is_dir():
        findings.append("<export_dir>  [missing_export_dir]  %s does not "
                        "exist or is not a directory" % export_dir)
        return findings

    csv_paths = sorted(export_dir.glob("*.csv"))
    if not csv_paths:
        findings.append("<export_dir>  [empty_export_dir]  no CSV files "
                        "found in %s" % export_dir)
        return findings

    banned_res = compile_banned(banned_terms)

    for path in csv_paths:
        raw_text = path.read_text(encoding="utf-8")
        # Normalize fullwidth/compatibility Unicode (e.g. fullwidth '@' or
        # fullwidth digits) to their ASCII equivalents before any check
        # runs, so homoglyph substitution can't dodge the regexes below.
        text = unicodedata.normalize("NFKC", raw_text)
        lines = text.splitlines()
        if not lines:
            continue

        # Parse with the csv module (not str.split(",")) so quoted commas
        # are respected rather than assumed away.
        rows = list(csv.reader(io.StringIO(text)))
        header = [h.strip() for h in rows[0]] if rows else []

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
            for name, rx in GENERIC:
                m = rx.search(line)
                if m:
                    findings.append("%s:%d  [%s]  %s"
                                    % (path.name, n, name, m.group(0)))
            low = _collapse_ws(line.lower())
            for term, term_re in banned_res:
                if term_re.search(low):
                    findings.append("%s:%d  [banned]  %s"
                                    % (path.name, n, term))

            if n > 1 and line.strip():
                row = rows[n - 1] if n - 1 < len(rows) else None
                if row is None or len(row) != len(header):
                    findings.append("%s:%d  [row_length]  expected %d "
                                    "field(s), got %d"
                                    % (path.name, n, len(header),
                                       0 if row is None else len(row)))
                elif company_idx is not None and len(row) > company_idx:
                    if not ANON_RE.match(row[company_idx].strip()):
                        findings.append("%s:%d  [anon_pattern]  %s"
                                        % (path.name, n, row[company_idx]))
    return findings


def positive_control(workdir=None):
    """Prove the scanner can still see. Returns True only if every planted
    pattern is flagged."""
    control_notes = ("note\n"
                     "reach control-plant@fabricated-control.test\n"
                     "EUR 9,876 moved\n"
                     "9876 EUR\n"
                     "IE29AIBK93115212345678\n"
                     "call +353 86 1234567\n"
                     "controlbannedco appears here\n")
    # A realistically-named CSV so the structural rules (column
    # whitelist, forbidden columns, row length, anon-id pattern) get
    # planted-and-checked too, not just the generic regex rules.
    control_applications = (
        "app_id,company,role_title\n"
        "A001,Not An Anon Company,Graduate Engineer\n"
        "A002,Company A,Extra,Field\n"
    )
    with tempfile.TemporaryDirectory(dir=workdir) as td:
        (Path(td) / "control.csv").write_text(control_notes,
                                              encoding="utf-8")
        (Path(td) / "applications.csv").write_text(control_applications,
                                                    encoding="utf-8")
        found = scan(Path(td), banned_terms=["ControlBannedCo"])
        rules_hit = {f.split("[", 1)[1].split("]")[0] for f in found}
        return {"email", "currency", "currency_post", "iban", "phone",
                "banned", "columns", "forbidden_column", "anon_pattern",
                "row_length"}.issubset(rules_hit)


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
        banned = load_private_terms()
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
