"""Generates the repo-root index.html from results/*.csv at build time -
not fetched at runtime. That means: it works over file://, it makes zero
network requests, and every number on the page is pytest-assertable
because it was assembled by collect_facts() below, not typed into a
template by hand.

Pipeline this sits at the end of: export/*.csv -> sql/*.sql ->
results/*.csv -> charts/*.html (scripts/render.py) -> this file. Reads
only results/*.csv (for the facts) and charts/ (for the six chart
filenames it embeds as <iframe>; charts/headline.html is never iframed -
its four stat tiles are re-rendered natively in S1 below from
results/funnel_summary.csv, so the page's most important numbers don't
depend on plotly loading). Never edits results/ or charts/, never
queries the vault, never re-derives anything analyze.py or render.py
already computed.

Determinism: no wall-clock reads anywhere in this module - the as_of
date and every other date on the page comes from a CSV cell. Two runs
against unchanged CSVs produce byte-identical output.

Light mode only: the six embedded charts are baked light by
scripts/render.py against a validated light palette (see that module's
docstring). A dark page around light iframes would require re-rendering
every chart against a second, separately-validated dark palette - out of
scope here. The colophon at the bottom of the page says so. Because
nothing on this page moves (no charts here are drawn by this module, no
transitions, no JS at all), prefers-reduced-motion needs no branch in
the CSS below - there is nothing to turn off.

Chrome carries no data hue: the five validated categorical hues used
inside the iframes (see scripts/render.py) never appear in this file's
CSS. Page chrome is neutral ink/muted/rule only, matching the tokens
scripts/render.py uses for chart chrome so the page and the charts read
as one document, not two.
"""
import csv
from pathlib import Path

# ---------------------------------------------------------------------------
# Chrome tokens - identical to scripts/render.py's SURFACE/PAGE/INK_* family,
# so the page chrome and the embedded charts share one palette.
# ---------------------------------------------------------------------------
PAPER = "#f9f9f7"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#52514e"
FAINT = "#898781"
RULE = "#e1e0d9"
RULE_STRONG = "#c3c2b7"

EM_DASH = "—"

# The six P2 charts embedded as iframes, in page order, with the height
# each needs (plotly is responsive:true so width self-manages; height is
# not auto and must be given explicitly) and a real accessible title.
# charts/headline.html is deliberately absent from this list - see the
# module docstring.
CHART_IFRAMES = [
    ("funnel", 470, "Sankey diagram of the application funnel, "
                     "from tracked applications to final outcome"),
    ("time_to_rejection", 470, "Dot strip of days elapsed before each "
                                "timed rejection"),
    ("channels", 420, "Horizontal stacked bars of outcomes by channel"),
    ("tiers", 300, "Horizontal stacked bars of outcomes by tier"),
    ("ops", 500, "Dot strip of ops resolution time by category"),
    ("finance", 470, "Step line of financial buffer percentage over time, "
                      "with income-change markers"),
]
CHART_NAMES = [name for name, _height, _title in CHART_IFRAMES]


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _one_row(path):
    rows = _read_csv(path)
    if len(rows) != 1:
        raise ValueError("%s: expected exactly 1 row, found %d"
                          % (path.name, len(rows)))
    return rows[0]


def _row_where(rows, col, value, label):
    for r in rows:
        if r[col] == value:
            return r
    raise ValueError("%s: no row where %s == %r" % (label, col, value))


def _link_value(rows, source, target):
    for r in rows:
        if r["source"] == source and r["target"] == target:
            return r["value"]
    raise ValueError(
        "funnel_links.csv: missing pair (source=%r, target=%r)"
        % (source, target))


def _constant_column(rows, col, label):
    """Every row of this table repeats the same value in `col` (a
    file-level count denormalized onto every row). Assert that and
    return it once."""
    values = {r[col] for r in rows}
    if len(values) != 1:
        raise ValueError("%s: column %r is not identical on every row: %r"
                          % (label, col, sorted(values)))
    return next(iter(values))


def _require_equal(left_label, left_val, right_label, right_val):
    if left_val != right_val:
        raise ValueError("%s (%s) != %s (%s)"
                          % (left_label, left_val, right_label, right_val))


# ---------------------------------------------------------------------------
# collect_facts - pure. Every returned value is a display-ready string
# taken verbatim from a CSV cell, or a min/max/sum/row-count computed
# over exactly one column. Raises ValueError (naming both sides) on any
# cross-CSV invariant breach - never silently defaults.
# ---------------------------------------------------------------------------
def collect_facts(results_dir):
    results_dir = Path(results_dir)
    facts = {}

    # -- funnel_summary.csv (exactly one row) --------------------------
    summary = _one_row(results_dir / "funnel_summary.csv")
    facts["n_tracked"] = summary["n_tracked"]
    facts["n_submitted"] = summary["n_submitted"]
    facts["n_rejected"] = summary["n_rejected"]
    facts["n_no_response_yet"] = summary["n_no_response_yet"]
    facts["n_interviews"] = summary["n_interviews"]
    facts["as_of"] = summary["as_of"]
    n_tracked = int(facts["n_tracked"])
    n_submitted = int(facts["n_submitted"])
    n_rejected = int(facts["n_rejected"])
    n_no_response_yet = int(facts["n_no_response_yet"])

    # -- funnel_links.csv ------------------------------------------------
    link_rows = _read_csv(results_dir / "funnel_links.csv")
    facts["link_tracked_submitted"] = _link_value(link_rows, "tracked", "submitted")
    facts["link_tracked_employer_closed"] = _link_value(link_rows, "tracked", "employer_closed")
    facts["link_tracked_skipped"] = _link_value(link_rows, "tracked", "skipped")
    facts["link_tracked_untracked_outcome"] = _link_value(link_rows, "tracked", "untracked_outcome")
    facts["link_submitted_rejected"] = _link_value(link_rows, "submitted", "rejected")
    facts["link_submitted_no_response_yet"] = _link_value(link_rows, "submitted", "no_response_yet")

    link_tracked_sum = (int(facts["link_tracked_submitted"])
                         + int(facts["link_tracked_employer_closed"])
                         + int(facts["link_tracked_skipped"])
                         + int(facts["link_tracked_untracked_outcome"]))
    _require_equal("funnel_links tracked-edge sum", link_tracked_sum,
                   "funnel_summary n_tracked", n_tracked)
    link_submitted_sum = (int(facts["link_submitted_rejected"])
                           + int(facts["link_submitted_no_response_yet"]))
    _require_equal("funnel_links submitted-edge sum", link_submitted_sum,
                   "funnel_summary n_submitted", n_submitted)
    _require_equal("funnel_links tracked->submitted", int(facts["link_tracked_submitted"]),
                   "funnel_summary n_submitted", n_submitted)
    _require_equal("funnel_links submitted->rejected", int(facts["link_submitted_rejected"]),
                   "funnel_summary n_rejected", n_rejected)
    _require_equal("funnel_links submitted->no_response_yet",
                   int(facts["link_submitted_no_response_yet"]),
                   "funnel_summary n_no_response_yet", n_no_response_yet)

    # -- coverage.csv (exactly one row) ----------------------------------
    coverage = _one_row(results_dir / "coverage.csv")
    facts["n_days"] = coverage["n_days"]
    facts["first_day"] = coverage["first_day"]
    facts["last_day"] = coverage["last_day"]
    facts["n_days_with_inbox_stats"] = coverage["n_days_with_inbox_stats"]
    facts["total_inbox_msgs"] = coverage["total_inbox_msgs"]
    facts["total_sensitive_suppressed"] = coverage["total_sensitive_suppressed"]

    # -- time_to_rejection.csv -------------------------------------------
    ttr_rows = _read_csv(results_dir / "time_to_rejection.csv")
    facts["n_rejections_timed"] = str(len(ttr_rows))
    if ttr_rows:
        days = [int(r["days_to_rejection"]) for r in ttr_rows]
        facts["rejection_days_min"] = str(min(days))
        facts["rejection_days_max"] = str(max(days))
    else:
        facts["rejection_days_min"] = "0"
        facts["rejection_days_max"] = "0"
    facts["n_excluded_missing_dates"] = _constant_column(
        ttr_rows, "n_excluded_missing_dates", "time_to_rejection.csv")
    rejections_timed_sum = (int(facts["n_rejections_timed"])
                             + int(facts["n_excluded_missing_dates"]))
    _require_equal("time_to_rejection n_rejections_timed+n_excluded_missing_dates",
                   rejections_timed_sum, "funnel_summary n_rejected", n_rejected)

    # -- channel_outcomes.csv ---------------------------------------------
    channel_rows = _read_csv(results_dir / "channel_outcomes.csv")
    facts["n_channels"] = str(len(channel_rows))
    facts["channel_n_list"] = ", ".join(
        "%s %s" % (r["channel"], r["n_total"]) for r in channel_rows)
    channel_total_sum = sum(int(r["n_total"]) for r in channel_rows)
    _require_equal("channel_outcomes n_total sum", channel_total_sum,
                   "funnel_summary n_tracked", n_tracked)
    linkedin = _row_where(channel_rows, "channel", "linkedin", "channel_outcomes.csv")
    facts["linkedin_n_total"] = linkedin["n_total"]
    facts["linkedin_n_submitted"] = linkedin["n_submitted"]
    facts["linkedin_n_rejected"] = linkedin["n_rejected"]
    workday = _row_where(channel_rows, "channel", "workday", "channel_outcomes.csv")
    facts["workday_n_total"] = workday["n_total"]
    facts["workday_n_rejected"] = workday["n_rejected"]

    # -- tier_outcomes.csv --------------------------------------------------
    tier_rows = _read_csv(results_dir / "tier_outcomes.csv")
    tier_total_sum = sum(int(r["n_total"]) for r in tier_rows)
    _require_equal("tier_outcomes n_total sum", tier_total_sum,
                   "funnel_summary n_tracked", n_tracked)
    entry = _row_where(tier_rows, "tier", "entry", "tier_outcomes.csv")
    facts["entry_n_total"] = entry["n_total"]
    facts["entry_n_rejected"] = entry["n_rejected"]
    stretch = _row_where(tier_rows, "tier", "stretch", "tier_outcomes.csv")
    facts["stretch_n_total"] = stretch["n_total"]
    facts["stretch_n_rejected"] = stretch["n_rejected"]
    unspecified = _row_where(tier_rows, "tier", "unspecified", "tier_outcomes.csv")
    facts["unspecified_n_total"] = unspecified["n_total"]
    facts["unspecified_n_rejected"] = unspecified["n_rejected"]

    # -- ops_summary.csv ------------------------------------------------
    ops_rows = _read_csv(results_dir / "ops_summary.csv")
    facts["n_ops_total"] = str(sum(int(r["n_total"]) for r in ops_rows))
    facts["n_ops_done"] = str(sum(int(r["n_done"]) for r in ops_rows))
    facts["n_ops_open"] = str(sum(int(r["n_open"]) for r in ops_rows))
    facts["n_ops_snoozed"] = str(sum(int(r["n_snoozed"]) for r in ops_rows))
    facts["n_ops_categories"] = str(len(ops_rows))

    # -- ops_close_times.csv ---------------------------------------------
    oct_rows = _read_csv(results_dir / "ops_close_times.csv")
    facts["n_ops_timed"] = str(len(oct_rows))
    if oct_rows:
        days_open = [int(r["days_open"]) for r in oct_rows]
        facts["ops_days_open_min"] = str(min(days_open))
        facts["ops_days_open_max"] = str(max(days_open))
    else:
        facts["ops_days_open_min"] = "0"
        facts["ops_days_open_max"] = "0"
    facts["n_done_without_close_date"] = _constant_column(
        oct_rows, "n_done_without_close_date", "ops_close_times.csv")
    ops_timed_sum = int(facts["n_ops_timed"]) + int(facts["n_done_without_close_date"])
    _require_equal("ops_close_times n_ops_timed+n_done_without_close_date",
                   ops_timed_sum, "ops_summary n_ops_done", int(facts["n_ops_done"]))

    # -- finance_trajectory.csv -------------------------------------------
    fin_rows = _read_csv(results_dir / "finance_trajectory.csv")
    if not fin_rows:
        raise ValueError("finance_trajectory.csv: no rows")
    facts["buffer_first_pct"] = fin_rows[0]["buffer_pct"]
    facts["buffer_first_date"] = fin_rows[0]["event_date"]
    facts["buffer_last_pct"] = fin_rows[-1]["buffer_pct"]
    facts["buffer_last_date"] = fin_rows[-1]["event_date"]
    income_change_dates = {r["event_date"] for r in fin_rows
                            if r["income_changed"].strip().lower() == "true"}
    facts["n_income_change_dates"] = str(len(income_change_dates))

    return facts


# ---------------------------------------------------------------------------
# render_dashboard - pure. channel_rows is the raw list of dicts from
# channel_outcomes.csv, kept OUT of the flat facts dict on purpose (its
# rejection_rate column needs an empty->em-dash substitution that would
# make the raw fact string not appear verbatim in the output, which would
# break the "every fact value appears in the HTML" test if it lived in
# facts instead).
# ---------------------------------------------------------------------------
def _rate_cell(raw_rate):
    v = raw_rate.strip()
    return "%s%%" % v if v else EM_DASH


def _channel_table(channel_rows):
    body_rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (r["channel"], r["n_total"], r["n_submitted"], r["n_rejected"],
           _rate_cell(r["rejection_rate"]))
        for r in channel_rows
    )
    return (
        '<div class="scroll"><table>'
        "<caption>Per-channel outcomes, from results/channel_outcomes.csv"
        " - jooble has no submissions, so its rejection rate is undefined"
        " (shown as %s, never 0%%)</caption>"
        "<thead><tr><th>Channel</th><th>Total</th><th>Submitted</th>"
        "<th>Rejected</th><th>Rejection rate</th></tr></thead>"
        "<tbody>%s</tbody></table></div>"
        % (EM_DASH, body_rows)
    )


STYLE = """
:root{
  --paper:#f9f9f7;
  --surface:#fcfcfb;
  --ink:#0b0b0b;
  --muted:#52514e;
  --faint:#898781;
  --rule:#e1e0d9;
  --rule-strong:#c3c2b7;
  --sans:system-ui,-apple-system,'Segoe UI',sans-serif;
  --mono:ui-monospace,Consolas,monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 var(--sans)}
::selection{background:var(--ink);color:var(--paper)}
a{color:var(--ink);text-decoration:underline;text-underline-offset:2px}
a:hover{color:var(--muted)}
:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
main{max-width:52rem;margin:0 auto;padding:0 1.25rem 4rem}
.prose{max-width:68ch}
header{padding-top:clamp(1.6rem,5vw,2.6rem)}
.overline{font:600 .72rem/1 var(--mono);letter-spacing:.18em;
  text-transform:uppercase;color:var(--muted)}
h1{font:600 clamp(2rem,6vw,3.2rem)/1.08 var(--sans);letter-spacing:-.01em;
  margin:.4rem 0 .9rem}
.rules{border-top:3px solid var(--rule-strong);border-bottom:1px solid var(--rule-strong);
  height:6px;margin:.2rem 0 1rem}
.masthead-meta{display:flex;gap:.5rem 1.4rem;flex-wrap:wrap;
  font:.8rem/1.5 var(--mono);color:var(--muted)}
.masthead-meta a{color:inherit}
h2{font:600 .78rem/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;
  color:var(--muted);margin:clamp(2.2rem,6vw,2.8rem) 0 1rem;
  display:flex;align-items:center;gap:.7rem}
h2::after{content:"";flex:1;border-top:1px solid var(--rule)}
h2 .no{color:var(--muted)}
h3{font:600 .95rem var(--sans);margin:1.3rem 0 .4rem;color:var(--ink)}
p{margin:.5rem 0}
.framing{border:1px solid var(--rule);padding:1.1rem 1.25rem;margin-top:1.2rem;
  background:var(--surface)}
.framing p{margin:.3rem 0}
.note{color:var(--muted);font-size:.92rem}
.tiles{display:flex;flex-wrap:wrap;border-top:1px solid var(--rule);
  border-left:1px solid var(--rule)}
.tile{flex:1 1 150px;border-right:1px solid var(--rule);
  border-bottom:1px solid var(--rule);padding:1rem 1.15rem}
.tile .label{font:.76rem var(--mono);color:var(--muted);margin:0 0 .4rem;
  text-transform:uppercase;letter-spacing:.05em}
.tile .value{font:600 clamp(1.6rem,4vw,2.15rem) var(--mono);
  font-variant-numeric:tabular-nums;margin:0;color:var(--ink)}
.tile.emph{border-top:3px solid var(--ink)}
.tile.emph .value{font-size:clamp(1.9rem,5vw,2.6rem)}
.caption{color:var(--muted);font-size:.92rem;margin-top:.7rem;max-width:68ch}
.chart-frame{border:1px solid var(--rule);margin-top:1rem}
iframe{width:100%;border:0;background:var(--surface);display:block}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font:.85rem var(--mono);
  font-variant-numeric:tabular-nums;margin-top:.6rem}
caption{text-align:left;font:.76rem var(--mono);color:var(--muted);
  padding-bottom:.4rem;max-width:68ch}
th,td{text-align:right;padding:.4rem .5rem;border-bottom:1px solid var(--rule);
  white-space:nowrap}
th:first-child,td:first-child{text-align:left;padding-left:0}
td:last-child,th:last-child{padding-right:0}
thead th{font-weight:600;color:var(--muted);border-bottom:2px solid var(--rule-strong)}
ul.cannot,ol.repro{padding-left:1.2rem;max-width:68ch}
ul.cannot li,ol.repro li{margin:.4rem 0}
footer{margin-top:3rem}
.colophon{border-top:3px solid var(--rule-strong);padding-top:.9rem;
  font:.78rem/1.7 var(--mono);color:var(--muted);max-width:68ch}
/* This page has no motion of any kind - no transitions, no keyframes, no
   script - so a prefers-reduced-motion branch would be dead CSS; there is
   nothing here to turn off. */
"""


def render_dashboard(facts, channel_rows, charts_dir_name="charts"):
    f = facts

    head = (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Instrumented Job Hunt</title>\n"
        '<meta name="description" content="A descriptive dashboard over '
        "one graduate's job hunt - n = %s applications, %s operations, "
        '%s days of coverage. No inference, no company names, no external '
        'requests.">\n'
        "<style>%s</style>\n</head>\n<body>\n<main>\n"
        % (f["n_tracked"], f["n_ops_total"], f["n_days"], STYLE)
    )

    masthead = (
        "<header>\n"
        '<p class="overline">One graduate &middot; one month &middot; '
        'n = %s</p>\n'
        "<h1>Instrumented Job Hunt</h1>\n"
        '<div class="rules" aria-hidden="true"></div>\n'
        '<p class="masthead-meta">'
        "<span>%s to %s &middot; %s days of coverage</span>"
        "<span>As of %s</span>"
        '<a href="README.md">The full writeup</a>'
        "</p>\n</header>\n"
        % (f["n_tracked"], f["first_day"], f["last_day"], f["n_days"], f["as_of"])
    )

    framing = (
        '<div class="framing prose">\n'
        "<p>This page is descriptive, not inferential. At n = %s "
        "applications, %s operations and %s days of coverage, nothing "
        "here supports a significance test, a confidence interval, or a "
        "causal claim - a single person's one-month sample doesn't carry "
        "that kind of weight. Every figure below comes from the "
        "committed, anonymised CSVs in results/, cell for cell.</p>\n"
        "</div>\n"
        % (f["n_tracked"], f["n_ops_total"], f["n_days"])
    )

    tiles = "".join(
        '<div class="tile%s"><p class="label">%s</p><p class="value">%s</p></div>'
        % (cls, label, value)
        for cls, label, value in [
            ("", "Tracked", f["n_tracked"]),
            ("", "Submitted", f["n_submitted"]),
            ("", "Rejected", f["n_rejected"]),
            ("", "No response yet", f["n_no_response_yet"]),
            (" emph", "Interviews", f["n_interviews"]),
        ]
    )
    s1 = (
        '<section id="s1">\n'
        '<h2><span class="no">&sect;1</span> Headline</h2>\n'
        '<div class="tiles">%s</div>\n'
        '<p class="caption">"No response yet" is censored, not ghosted: '
        "these applications are still open as of %s, not confirmed dead.</p>\n"
        "</section>\n"
        % (tiles, f["as_of"])
    )

    s2 = (
        '<section id="s2">\n'
        '<h2><span class="no">&sect;2</span> Funnel</h2>\n'
        '<div class="chart-frame"><iframe src="%s/funnel.html" '
        'title="%s" height="470" loading="lazy" scrolling="no"></iframe></div>\n'
        '<p class="caption">Of %s tracked applications: %s submitted, '
        "%s closed by the employer before ever being submitted, %s "
        "skipped, and %s reached an outcome the export couldn't "
        "classify cleanly. Of the %s submitted: %s rejected, %s "
        "with no response yet. ‘Employer closed’ conflates a posting "
        "withdrawn by the employer with one filled by someone else - the "
        "export doesn't distinguish the two.</p>\n"
        "</section>\n"
        % (charts_dir_name, CHART_IFRAMES[0][2], f["n_tracked"],
           f["link_tracked_submitted"], f["link_tracked_employer_closed"],
           f["link_tracked_skipped"], f["link_tracked_untracked_outcome"],
           f["link_tracked_submitted"], f["link_submitted_rejected"],
           f["link_submitted_no_response_yet"])
    )

    s3 = (
        '<section id="s3">\n'
        '<h2><span class="no">&sect;3</span> Time to rejection</h2>\n'
        '<div class="chart-frame"><iframe src="%s/time_to_rejection.html" '
        'title="%s" height="470" loading="lazy" scrolling="no"></iframe></div>\n'
        '<p class="caption">%s of %s rejections had both an applied date '
        "and a status date and could be timed; %s are excluded from the "
        "chart for missing one of those dates - excluded, not dropped: "
        "they are still counted in the %s above. Timed rejections ranged "
        "%s-%s days.</p>\n"
        "</section>\n"
        % (charts_dir_name, CHART_IFRAMES[1][2], f["n_rejections_timed"],
           f["n_rejected"], f["n_excluded_missing_dates"], f["n_rejected"],
           f["rejection_days_min"], f["rejection_days_max"])
    )

    s4 = (
        '<section id="s4">\n'
        '<h2><span class="no">&sect;4</span> Channels</h2>\n'
        '<div class="chart-frame"><iframe src="%s/channels.html" '
        'title="%s" height="420" loading="lazy" scrolling="no"></iframe></div>\n'
        '<p class="caption">Applications sorted into %s channels: %s. '
        "LinkedIn shows a %s rejection rate across %s submitted "
        "applications (%s of %s rejected). That is not a good result: "
        "nothing came back at all. Workday, by contrast, shows %s of %s "
        "rejected.</p>\n%s\n"
        "</section>\n"
        % (charts_dir_name, CHART_IFRAMES[2][2], f["n_channels"],
           f["channel_n_list"],
           _rate_cell(_row_where(channel_rows, "channel", "linkedin",
                                  "channel_outcomes.csv")["rejection_rate"]),
           f["linkedin_n_submitted"], f["linkedin_n_rejected"],
           f["linkedin_n_total"], f["workday_n_rejected"], f["workday_n_total"],
           _channel_table(channel_rows))
    )

    s5 = (
        '<section id="s5">\n'
        '<h2><span class="no">&sect;5</span> Tiers</h2>\n'
        '<div class="chart-frame"><iframe src="%s/tiers.html" '
        'title="%s" height="300" loading="lazy" scrolling="no"></iframe></div>\n'
        '<p class="caption">Entry: %s of %s rejected. Stretch: %s of %s '
        "rejected. Unspecified: %s of %s rejected - unspecified carries "
        "most of the volume because tier is derived from role titles, and "
        "most role titles don't state a level.</p>\n"
        "</section>\n"
        % (charts_dir_name, CHART_IFRAMES[3][2],
           f["entry_n_rejected"], f["entry_n_total"],
           f["stretch_n_rejected"], f["stretch_n_total"],
           f["unspecified_n_rejected"], f["unspecified_n_total"])
    )

    s6 = (
        '<section id="s6">\n'
        '<h2><span class="no">&sect;6</span> Operations</h2>\n'
        '<div class="chart-frame"><iframe src="%s/ops.html" '
        'title="%s" height="500" loading="lazy" scrolling="no"></iframe></div>\n'
        '<p class="caption">%s operations across %s categories: %s closed, '
        "%s open, %s snoozed. Of the closed ones, %s carry a "
        "machine-readable close date (%s do not); those that do took %s-%s "
        "days.</p>\n"
        "</section>\n"
        % (charts_dir_name, CHART_IFRAMES[4][2], f["n_ops_total"],
           f["n_ops_categories"], f["n_ops_done"], f["n_ops_open"],
           f["n_ops_snoozed"], f["n_ops_timed"], f["n_done_without_close_date"],
           f["ops_days_open_min"], f["ops_days_open_max"])
    )

    s7 = (
        '<section id="s7">\n'
        '<h2><span class="no">&sect;7</span> Finance</h2>\n'
        '<div class="chart-frame"><iframe src="%s/finance.html" '
        'title="%s" height="470" loading="lazy" scrolling="no"></iframe></div>\n'
        '<p class="caption">Buffer moved from %s%% of target on %s to %s%% '
        "on %s, with income-change markers on %s distinct dates. No "
        "monetary amount exists anywhere in this repository, by design - "
        "only the percentage of a private target.</p>\n"
        "</section>\n"
        % (charts_dir_name, CHART_IFRAMES[5][2], f["buffer_first_pct"],
           f["buffer_first_date"], f["buffer_last_pct"], f["buffer_last_date"],
           f["n_income_change_dates"])
    )

    s8 = (
        '<section id="s8">\n'
        '<h2><span class="no">&sect;8</span> What this cannot tell you</h2>\n'
        '<ul class="cannot prose">\n'
        "<li>The sample is small and covers one month, one person, and "
        "one job market - none of this generalises.</li>\n"
        "<li>Several of the rates above are computed over small "
        "denominators (single digits up to the thirties); a couple of "
        "applications going differently would move a percentage a lot.</li>\n"
        "<li>‘No response yet’ is censored at the export date, not a "
        "confirmed non-response - some of it will still convert.</li>\n"
        "<li>Tier (entry/stretch) is inferred from role titles, not "
        "self-reported, and most titles don't state a level.</li>\n"
        "<li>‘Closed’ in the funnel conflates postings withdrawn by "
        "the employer with postings filled by someone else.</li>\n"
        "<li>Nothing on this page is causal. A channel or tier with a "
        "higher rejection rate is not shown to cause worse outcomes.</li>\n"
        "</ul>\n"
        "</section>\n"
    )

    s9 = (
        '<section id="s9">\n'
        '<h2><span class="no">&sect;9</span> Reproduce it</h2>\n'
        '<ol class="repro prose">\n'
        '<li><a href="export/">export/*.csv</a> - the anonymised, gate-'
        "scanned export.</li>\n"
        '<li><a href="sql/">sql/*.sql</a> - the analyses run over that '
        "export.</li>\n"
        '<li><a href="results/">results/*.csv</a> - the outputs, gate-'
        "scanned again before being committed.</li>\n"
        '<li><a href="charts/">charts/*.html</a> - one standalone plotly '
        "document per chart, rendered from results/ only.</li>\n"
        "<li>This page - generated from results/ only by "
        "scripts/build_dashboard.py, re-rendering nothing.</li>\n"
        "</ol>\n"
        '<p class="caption">Coverage: %s days (%s to %s). Inbox activity '
        "was logged on %s of those days (%s messages seen, %s suppressed "
        "as sensitive before export).</p>\n"
        "</section>\n"
        % (f["n_days"], f["first_day"], f["last_day"],
           f["n_days_with_inbox_stats"], f["total_inbox_msgs"],
           f["total_sensitive_suppressed"])
    )

    footer = (
        "<footer>\n"
        '<div class="colophon">\n'
        "<p>Light mode only: the six charts above are baked light against "
        "a validated palette; a dark page around light iframes would need "
        "a second, separately-validated dark palette for every chart, "
        "which is out of scope here. This page makes no external "
        "requests - it is pure static HTML generated at build time, "
        "loading nothing but the local charts/ files above. It contains "
        "no company names: every field on it is either an aggregate "
        "count or an anonymised category from the committed export.</p>\n"
        "</div>\n</footer>\n"
    )

    tail = "</main>\n</body>\n</html>\n"

    return (head + masthead + framing + s1 + s2 + s3 + s4 + s5 + s6 + s7
            + s8 + s9 + footer + tail)


# ---------------------------------------------------------------------------
# build_dashboard - the IO wrapper. Reads results/*.csv, writes out_path.
# ---------------------------------------------------------------------------
def build_dashboard(results_dir, charts_dir, out_path):
    results_dir = Path(results_dir)
    charts_dir = Path(charts_dir)
    out_path = Path(out_path)

    facts = collect_facts(results_dir)
    channel_rows = _read_csv(results_dir / "channel_outcomes.csv")
    html = render_dashboard(facts, channel_rows, charts_dir_name=charts_dir.name)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parents[1]
    build_dashboard(REPO / "results", REPO / "charts", REPO / "index.html")
