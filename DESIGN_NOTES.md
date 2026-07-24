# Design notes (P1) — not the public README, working notes for this build session

## Privacy architecture (resolves a tension the plan doesn't spell out)

Two-tier data flow:
1. **Parse** real vault markdown -> a **local, gitignored** DuckDB (`data/private.duckdb`).
   Real company names stay here (needed to compute channel/tier), but free-text fields that
   no planned analysis needs (JOB_SEARCH "Notes", LEDGER "notes" body, debrief prose bodies)
   are **dropped at parse time**, not just at export time. Don't retain what nothing reads.
2. **Export**: a transform reads the private DB, anonymizes/normalizes, writes the **committed**
   sanitized artifacts (`export/*.parquet` or `.csv`). `sanitize_check.py` greps *these* files.

**Tests are TDD against synthetic, fabricated fixtures** (fake companies, fake amounts,
fake dates) that reproduce the same *messiness* as the real files — never copies of real
rows. This is the only way parser test files (which live in the public repo) can assert
specific values without leaking real ones. A separate, gitignored, locally-run integration
check exercises the real vault file but asserts only *structural* properties (row counts,
no exceptions, required fields non-empty) — never specific real values — so it's safe to
keep even if someone reads the test file later.

## Confirmed real formats (read directly from the live vault 2026-07-24, informs fixtures)

**JOB_SEARCH.md** `## Applications` table:
`| Company | Role | Link | Applied | Status | Follow-up due | Notes |`
- Company: sometimes `~~Struck Through~~` for skipped/withdrawn rows.
- Link column is actually **channel free text**, not a URL: `"LinkedIn (07-10)"`,
  `"Workday MMC"`, `"Jooble (stale)"`, `"Indeed (Harri ATS)"`, `"applied outside Jarvis"`,
  `"MU e-recruitment portal"`, `"amris ATS"`. Needs a classifier, not a literal match.
- Applied: `"2026-07-12"`, `"—"`, `"pre-2026-07-09"`, `"unknown (applied outside Jarvis)"`.
  Treat unparseable forms as null (excluded from response-time calc, still counted in funnel).
- Status: bold markdown + optional emoji + parenthetical date: `"**Rejected** (2026-07-17)"`,
  `"**Applied** ✅"` (no date -> use Applied date), `"**Closed before applying** (2026-07-09)"`,
  `"**Skipped** (2026-07-09)"`.
- Notes: free prose, contains real emails and personal commentary. **Dropped at parse time.**
  No structured "Tier" column exists — derive tier from the **Role title** via keyword match
  (junior/graduate/grad/intern -> entry; senior/staff/manager/lead/principal -> stretch;
  else -> mid/unspecified), not from Notes prose.

**LEDGER.md** table: `| topic | first_raised | times_raised | status | notes |`
- status in {open, done, snoozed} (seen in the wild).
- notes is long free prose. **Dropped at parse time**, except: when status=done, many notes
  begin `"CLOSED YYYY-MM-DD"` or `"CLOSED YYYY-MM-DD ..."` — regex-extract just that leading
  date token as `close_date`, discard the rest.

**FINANCE.md**: prose `## Log` section, dated bullets (`- YYYY-MM-DD - ...` or
`- YYYY-MM-DD (later, same day) - ...`). Extract only: the date, and (if present) an explicit
**already-normalized** buffer percentage the entry itself states, e.g. `"(88%)"`,
`"Buffer now 500/750 (67%)"`, `"jumps from 57% to 88%"` -> take the percentage number(s), never
the surrounding euro figures. Also flag `income_changed: true` for entries whose text matches
`/income|UPS|parents.*(pay|stop|drop)/i` — a boolean event marker, no amount. This matches the
plan's own phrasing exactly: "savings as % of buffer target... income as event markers... No
absolute euro amounts."

**debriefs/*.md**: frontmatter (`updated:` = the date) + fixed emoji section headers
(`🎯 TODAY'S FOCUS`, `🚧 Projects & agents`, `💼 Job search`, `🏋️ Life & discipline`,
`💰 Finance`, `💡 Suggestion`, `📅 Today`, `📬 Inbox`, sometimes `🩺 Health`, `📥 Captures`).
v1 scope (per plan, "text mining explicitly deferred"): filename date, which section
headers are present (booleans), and simple **already-aggregated** counts trivially regexable
from the Inbox line, e.g. `"17 msgs (0 unread, 0 sensitive)"` -> three ints. No other content
read or stored.

## Target row shapes (private DB columns; export drops/anonymizes as noted)

`applications`: id, company (real; export: anon_id "Company A" + sector + tier),
role_title, tier (entry|stretch|unspecified — derived, not free text; "mid" is not a
distinct bucket, an unlabeled role is "unspecified"), channel (derived enum, includes
"director" alongside senior/staff/manager/lead/principal as a stretch-tier keyword),
applied_date (nullable), status (enum), status_date (only from an explicit parenthetical
date on the Status cell — does NOT fall back to applied_date when absent), followup_due
(nullable). NO notes/link-raw/email fields at all — never parsed into the DB.

`ledger_ops`: topic_slug, first_raised, times_raised, status, close_date (nullable).
NO notes field. **Correction (found by adversarial review of the sanitize gate,
2026-07-24): `status` is NOT a closed enum.** `parse_ledger.py` copies the raw markdown
status cell verbatim (its own test deliberately proves an unrecognized value like
"archived" passes through unchanged, rather than erroring) — in practice real LEDGER.md
status values have always been short single words (open/done/snoozed), but nothing
enforces that. This is a live consideration for Task 7's manual export review, not
just a documentation nit: `ledger_ops.csv` has no `company` column, so the gate's
positional anon-pattern check never runs on it, and only the generic regexes / banned
list would catch anything sensitive that somehow ended up in that cell.

`finance_events`: date, buffer_pct (nullable float), income_changed (bool).
NO euro-amount field anywhere in this table, ever — not even in the private DB, since
nothing downstream needs the raw figure and the whole point is minimizing where it lives.

`debrief_days`: date, has_focus, has_projects, has_job_search, has_life, has_finance,
has_suggestion, has_today, has_inbox, has_health, has_captures (bools), inbox_count,
inbox_unread, inbox_sensitive (ints, nullable — read from the Inbox header's own line or
up to 3 lines after it, bounded so a missing summary can't fall through into unrelated
later content).

## Module layout

`src/job_analytics/parse_applications.py` -> `parse(path) -> list[dict]` (rows above)
`src/job_analytics/parse_ledger.py` -> `parse(path) -> list[dict]`
`src/job_analytics/parse_finance.py` -> `parse(path) -> list[dict]`
`src/job_analytics/parse_debriefs.py` -> `parse(dir_path) -> list[dict]` (one dict per file)

Each module: pure functions, no DB/IO side effects beyond reading the given path, so they're
trivially unit-testable against an in-memory string or a tmp_path fixture file.
