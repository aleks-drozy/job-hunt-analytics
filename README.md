# Instrumented Job Hunt

**Live dashboard: https://aleks-drozy.github.io/job-hunt-analytics/**

A month of one graduate's job search and AI-assistant operations, parsed from private markdown into an anonymised public dataset, analysed in SQL, published as a static page.

This document covers 50 tracked applications, 65 logged assistant operations, 15 finance log entries, and 19 days of daily debriefs, all from the same person, over the window 2026-07-08 to 2026-07-28. Every number below is descriptive, not inferential: there are no significance tests, no confidence intervals, and no causal claims anywhere in this repository. At this sample size, a rate computed over, say, 4 applications describes those 4 applications and nothing else — it generalises to no channel, no tier, and no future application.

0 interviews from 50 tracked applications: 43 submitted, 15 rejected, 28 with no response yet, as of 2026-07-21.

That is the whole result. The rest of this document is about how that number was produced, what it does and does not mean, and what broke on the way to publishing it.

## Status

| | |
|---|---|
| Data window | 2026-07-08 to 2026-07-28 (19 days) |
| Applications tracked | 50 |
| Interviews | 0 |
| Ledger operations | 65 |
| Analyses | 9 SQL queries (`sql/`) |
| Charts | 7 (`charts/`) |
| Tests | 164 passed, 1 skipped (138 baseline + 7 for this writeup + 19 for the dashboard) |
| Dashboard | `index.html`, static HTML, no server |

## What the data is

Four sources feed the public export, each with a fixed row count:

- **Applications** — 50 rows ([`export/applications.csv`](export/applications.csv)): anonymised company, sector, tier, channel, dates, status.
- **Ledger operations** — 65 rows ([`export/ledger_ops.csv`](export/ledger_ops.csv)): the AI assistant's own task ledger — category, times raised, status, close date.
- **Finance events** — 15 rows ([`export/finance_events.csv`](export/finance_events.csv)): a normalised savings-buffer percentage and an income-change marker, dated.
- **Debrief days** — 19 rows ([`export/debrief_days.csv`](export/debrief_days.csv)): which sections a daily debrief contained, plus pre-aggregated inbox counts.

Four things are deliberately excluded, and none of them are gaps in the pipeline:

- **Fitness.** Zero sessions were logged in the window. That is stated as zero, not padded with placeholder rows to look complete.
- **Role titles.** A title plus a company plus a date is enough to re-identify an application by search; titles never leave the private database.
- **Ledger topic slugs.** The raw topic text names real companies and real people; only a derived category (six buckets) is exported.
- **Monetary amounts.** No euro figure, absolute or otherwise, ever leaves the private database — only a normalised percentage of a savings target is exported. Nothing downstream needs the raw figure, so nothing downstream stores it.

## Privacy architecture

Private markdown → a local, gitignored DuckDB → an anonymising export step → `scripts/sanitize_check.py`, a CI gate → the committed `export/*.csv` files this document is built from.

The gate was attacked before it was trusted. An adversarial review of the gate found 8 real defects, each fixed with its own red-before/green-after regression test — 5 leak paths and 3 fail-open defects in the gate's own self-check. The worst leak path was a hand-crafted CSV row with one extra, unquoted field: because nothing validated a row's cell count against its header, that extra field could carry a real company name straight past every other check, silently. All 8 were fixed, each with its own regression test (`tests/test_sanitize_check.py`), and the gate was independently re-verified before this export existed at all.

## What the numbers say

**Funnel.** Of 50 tracked applications: 43 submitted, 5 closed by the employer before a submission went in, 1 skipped, 1 with an untracked outcome. Of the 43 submitted, 15 were rejected and 28 have had no response yet — censored, not ghosted: still open as of 2026-07-21, not a null result.

**Time to rejection.** 10 of the 15 rejections carry both an applied date and a status date; the other 5 are excluded from this figure and counted, not silently dropped. Those 10 came back between 0 and 5 days after applying, six of them within 2 days.

**Channel.** Six channels, by tracked-application count (not submission count — a channel's applications aren't all submitted): other 22, company_portal 8, linkedin 8, indeed 5, workday 4, jooble 3. The rejection rate by channel ranges from 0% (linkedin) to 75% (workday), and neither number means what it looks like it means. LinkedIn's 0% is over 8 submitted applications with nothing came back at all — not a good result, a null one. Workday's 75% is three rejections out of four applications, not a large sample. Jooble shows no rate at all, because none of its 3 tracked applications were ever submitted.

**Tier.** entry 11 applications (3 rejected), stretch 6 (1 rejected), unspecified 33 (11 rejected). Unspecified carries most of the volume because tier is derived from the role title, and most titles simply don't state a level — an artefact of the data, not a strategy of applying only to unlabeled roles.

**Assistant operations.** 65 logged operations across 6 categories: 41 closed, 22 open, 2 snoozed. Of the 41 closed, 24 have a machine-readable close date and 17 don't. Average times raised per operation ranges from 1.5 (project) to 3.33 (life) across category.

**Finance.** The savings buffer moved 66% → 67% → 57% → 88% of target across the window, with an income-change marker on two separate dates. Percentages only — no amount appears anywhere in this repository.

## What the data cannot say

A batch of applications in this window had no human reply channel at all — not a rejection, not an interview, nothing addressable. The evidence for that lives in private ledger notes and emails that were deliberately never exported, so it stays an observation here, unquantified. The alternative was a number nobody outside the private vault could check, and that seemed worse than no number.

The assistant that produced this dataset also logged its own misses, in words, without slugs: a CV wording error it introduced and didn't catch before the application went out; drift between what the ledger claimed was closed and what was actually true; a classification that keyed on nothing but an email subject line. An assistant that logs its own failures is the only reason this dataset contains any failure data at all.

Interviews are a stat tile, not a funnel stage — `COUNT(*) WHERE status='interview'`, computed fresh on every run, so the tile moves the day one lands rather than waiting on a schema change.

Four things were explicitly descoped rather than attempted:

- An "acknowledged" application stage — no such field exists in the source data.
- A quantified count for the no-reply-channel finding above.
- Interviews as anything more than a tile.
- Budget adherence reframed as a normalised buffer trajectory instead of a target-vs-actual currency comparison.

## What review found

The published "as of" date originally included a future, scheduled follow-up date, so the page claimed data currency ten days past the last real observation. Caught in review, corrected to 2026-07-21.

The finance parser silently returned null for every one of the 15 real entries — log entries wrap across physical lines, and the extraction regex only ever matched a single line — until a run against the real vault exposed it. An earlier "done" would have shipped a finance chart with no data in it.

Company names carrying bold markdown, not just strikethrough, would have split one real company into two different anonymous IDs, because the anonymiser treats the company string as an exact key.

The sanitize gate's row-length gap described above: a hand-crafted extra CSV field could carry a real name past every regex because nothing validated a row's cell count against its header.

A stacked-bar chart faked its segment gaps with a border stroke around each bar — a named anti-pattern, since the stroke only looked like separation because the plot background happened to match the stroke colour. It was replaced with real pixel-sized gap shapes.

A chart label's text colour was chosen by perceived brightness instead of WCAG relative luminance, failed the AA contrast threshold at 2.82:1, and was fixed to 6.99:1.

## How it is built

```
private markdown → parse → private DuckDB → anonymise → sanitize_check.py gate
  → export/*.csv → sql/*.sql (DuckDB) → results/*.csv → charts/*.html (plotly) → index.html
```

Stack: Python standard-library parsers, DuckDB, Plotly, pytest, GitHub Actions.

```
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m pytest
.venv/Scripts/python scripts/refresh.py
```

Every figure in this document is computed from the committed anonymised export ([`export/`](export/)) alone. No private file is needed to reproduce any number here, any SQL result in [`results/`](results/), or any chart in [`charts/`](charts/). The dashboard itself is [`index.html`](index.html) in the repository root.
