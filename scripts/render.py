"""Render charts/*.html from results/*.csv only - never re-queries DuckDB,
never touches export/ or sql/. One function per chart; render_all is a
thin dispatcher.

--------------------------------------------------------------------------
Palette - validated Step 1 (dataviz skill), run by the controller from
the skill's base directory, not re-run here:

    node scripts/validate_palette.js \
        "#2a78d6,#eb6834,#1baf7a,#eda100,#e87ba4" --mode light

Verdict: ALL CHECKS PASS
  - lightness band: pass
  - chroma floor: pass
  - CVD separation, worst adjacent pair: dE 9.1  (>= 8 target)
  - normal-vision floor, worst adjacent pair: dE 19.6 (>= 15 floor)
  - contrast: WARN - 3 of the 5 hexes (aqua, yellow, magenta) sit below
    3:1 against the light chart surface (#fcfcfb). Expected/documented
    behavior for this palette, not a failure. Mandatory mitigation,
    applied throughout this file: every chart that uses one of these
    hues carries a visible direct/segment label or a legend next to the
    mark - these colors never carry a value by hue alone.

Outcome -> hex mapping (fixed order, categorical slots 1-5). This exact
mapping is used everywhere an outcome color appears, so "rejected"
renders in the identical blue on the funnel, channels.html and
tiers.html:

    | Outcome                     | Hex       | Name    |
    |------------------------------|-----------|---------|
    | rejected                     | #2a78d6   | blue    |
    | no_response_yet / n_open     | #eb6834   | orange  |
    | employer_closed / n_closed   | #1baf7a   | aqua    |
    | skipped / n_skipped          | #eda100   | yellow  |
    | unknown                      | #e87ba4   | magenta |
--------------------------------------------------------------------------
"""
import csv
import random
from pathlib import Path

import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Chrome & ink tokens - light mode only (P2 has no dark mode / theme toggle,
# per the Global Constraints; that lands in P3).
# ---------------------------------------------------------------------------
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', sans-serif"

# ---------------------------------------------------------------------------
# Outcome identity - fixed order, never cycled (see palette block above).
# ---------------------------------------------------------------------------
OUTCOME_COLORS = {
    "rejected": "#2a78d6",
    "no_response_yet": "#eb6834",
    "n_open": "#eb6834",
    "employer_closed": "#1baf7a",
    "n_closed": "#1baf7a",
    "skipped": "#eda100",
    "n_skipped": "#eda100",
    "unknown": "#e87ba4",
    "untracked_outcome": "#e87ba4",
}

# The 5 stacked-bar segments, in a fixed order shared by channels.html and
# tiers.html so "rejected" is always first/blue on both charts.
OUTCOME_SEGMENTS = [
    ("n_rejected", "Rejected", OUTCOME_COLORS["rejected"]),
    ("n_open", "No response yet", OUTCOME_COLORS["n_open"]),
    ("n_closed", "Employer closed", OUTCOME_COLORS["n_closed"]),
    ("n_skipped", "Skipped", OUTCOME_COLORS["n_skipped"]),
    ("n_unknown", "Unknown", OUTCOME_COLORS["unknown"]),
]

# Sankey node order/colors. "tracked" and "submitted" are aggregation
# stages, not outcomes, so they get neutral grays rather than an outcome
# hue; the five leaf stages reuse the outcome mapping above.
FUNNEL_NODE_ORDER = ["tracked", "submitted", "skipped", "employer_closed",
                      "untracked_outcome", "rejected", "no_response_yet"]
FUNNEL_NODE_COLOR = {
    "tracked": BASELINE,
    "submitted": INK_MUTED,
    "skipped": OUTCOME_COLORS["skipped"],
    "employer_closed": OUTCOME_COLORS["employer_closed"],
    "untracked_outcome": OUTCOME_COLORS["untracked_outcome"],
    "rejected": OUTCOME_COLORS["rejected"],
    "no_response_yet": OUTCOME_COLORS["no_response_yet"],
}


# ---------------------------------------------------------------------------
# Small helpers shared by every chart function
# ---------------------------------------------------------------------------
def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "rgba(%d,%d,%d,%.2f)" % (r, g, b, alpha)


def _text_on_fill(hex_color):
    """White or ink text for a label set inside a colored fill, chosen by
    the fill's own luminance (YIQ perceived-brightness heuristic) so a
    label inside e.g. the light yellow/magenta/aqua segments always
    clears contrast."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    yiq = (r * 299 + g * 587 + b * 114) / 1000
    return INK_PRIMARY if yiq >= 128 else "#ffffff"


def _jitter(n, amplitude, seed):
    """Deterministic jitter - a fixed-seed PRNG, never the wall clock, so
    reruns on unchanged data are byte-identical."""
    rng = random.Random(seed)
    return [rng.uniform(-amplitude, amplitude) for _ in range(n)]


def _write(fig, path):
    fig.write_html(str(path), include_plotlyjs="directory")


# ---------------------------------------------------------------------------
# charts/headline.html - stat tiles, hand-written HTML, no plotly
# ---------------------------------------------------------------------------
def _render_headline(results_dir, charts_dir):
    row = _read_csv(results_dir / "funnel_summary.csv")[0]
    tiles = [
        ("Tracked", row["n_tracked"]),
        ("Interviews", row["n_interviews"]),
        ("Rejected", row["n_rejected"]),
        ("No response yet", row["n_no_response_yet"]),
    ]
    tile_html = "".join(
        '<div class="tile"><p class="label">%s</p><p class="value">%s</p></div>'
        % (label, value)
        for label, value in tiles
    )
    html = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Headline</title>
<style>
  body {{
    background: {page};
    font-family: {font};
    margin: 0;
    padding: 24px;
  }}
  .tiles {{ display: flex; flex-wrap: wrap; gap: 16px; }}
  .tile {{
    background: {surface};
    border-radius: 8px;
    padding: 20px 24px;
    min-width: 160px;
  }}
  .tile .label {{
    color: {ink_secondary};
    font-size: 13px;
    margin: 0 0 8px;
  }}
  .tile .value {{
    color: {ink_primary};
    font-size: 32px;
    font-weight: 600;
    margin: 0;
  }}
  .asof {{
    color: {ink_muted};
    font-size: 13px;
    margin-top: 16px;
  }}
</style>
</head>
<body>
  <div class="tiles">
    {tiles}
  </div>
  <p class="asof">As of {as_of}</p>
</body>
</html>
""".format(page=PAGE, surface=SURFACE, ink_primary=INK_PRIMARY,
           ink_secondary=INK_SECONDARY, ink_muted=INK_MUTED, font=FONT_FAMILY,
           tiles=tile_html, as_of=row["as_of"])
    (charts_dir / "headline.html").write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# charts/funnel.html - Sankey
# ---------------------------------------------------------------------------
def _render_funnel(results_dir, charts_dir):
    rows = _read_csv(results_dir / "funnel_links.csv")
    rows.sort(key=lambda r: (r["source"], r["target"]))

    present = {r["source"] for r in rows} | {r["target"] for r in rows}
    nodes = [n for n in FUNNEL_NODE_ORDER if n in present]
    nodes += sorted(present - set(nodes))  # defensive: unexpected node names
    idx = {n: i for i, n in enumerate(nodes)}

    incoming = {n: 0 for n in nodes}
    outgoing = {n: 0 for n in nodes}
    for r in rows:
        v = int(r["value"])
        outgoing[r["source"]] += v
        incoming[r["target"]] += v
    # Root nodes (e.g. "tracked") have no incoming link; fall back to
    # their outgoing total so every node still gets an honest count.
    node_value = {n: incoming[n] or outgoing[n] for n in nodes}

    node_labels = ["%s · %d" % (n.replace("_", " "), node_value[n])
                   for n in nodes]
    node_colors = [FUNNEL_NODE_COLOR.get(n, INK_MUTED) for n in nodes]

    link_source = [idx[r["source"]] for r in rows]
    link_target = [idx[r["target"]] for r in rows]
    link_value = [int(r["value"]) for r in rows]
    link_color = [_hex_to_rgba(FUNNEL_NODE_COLOR.get(r["target"], INK_MUTED), 0.35)
                  for r in rows]

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        textfont=dict(color=INK_PRIMARY, family=FONT_FAMILY, size=12),
        node=dict(label=node_labels, color=node_colors, pad=22, thickness=18,
                  line=dict(color=SURFACE, width=2)),
        link=dict(source=link_source, target=link_target, value=link_value,
                  color=link_color),
    ))
    fig.update_layout(
        title=dict(text="Application funnel",
                   font=dict(size=18, color=INK_PRIMARY, family=FONT_FAMILY),
                   x=0, xanchor="left"),
        annotations=[dict(
            text="no_response_yet is censored: still open as of the export "
                 "date, not necessarily ghosted",
            xref="paper", yref="paper", x=0, y=1.1, xanchor="left",
            yanchor="bottom", showarrow=False,
            font=dict(size=12, color=INK_MUTED, family=FONT_FAMILY),
        )],
        margin=dict(t=110, l=10, r=10, b=10),
        paper_bgcolor=PAGE, plot_bgcolor=SURFACE,
        font=dict(family=FONT_FAMILY, color=INK_SECONDARY),
    )
    _write(fig, charts_dir / "funnel.html")


# ---------------------------------------------------------------------------
# charts/time_to_rejection.html - dot strip (NOT a histogram)
# ---------------------------------------------------------------------------
def _render_time_to_rejection(results_dir, charts_dir):
    rows = _read_csv(results_dir / "time_to_rejection.csv")
    rows.sort(key=lambda r: (int(r["days_to_rejection"]), r["app_id"]))

    n_excluded = int(rows[0]["n_excluded_missing_dates"]) if rows else 0
    x = [int(r["days_to_rejection"]) for r in rows]
    y = _jitter(len(rows), amplitude=0.35, seed=4001)
    hover = ["%s &middot; %s / %s &middot; %d day(s) to rejection"
             % (r["app_id"], r["channel"], r["tier"], int(r["days_to_rejection"]))
             for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers",
        marker=dict(size=10, color=OUTCOME_COLORS["rejected"],
                    line=dict(color=SURFACE, width=2)),
        hovertext=hover, hoverinfo="text",
    ))

    annotations = []
    if n_excluded:
        annotations.append(dict(
            text="%d rejection(s) excluded - missing applied or status date"
                 % n_excluded,
            xref="paper", yref="paper", x=0, y=1.1, xanchor="left",
            yanchor="bottom", showarrow=False,
            font=dict(size=12, color=INK_MUTED, family=FONT_FAMILY),
        ))
    if rows:
        max_i = max(range(len(rows)), key=lambda i: x[i])
        annotations.append(dict(
            x=x[max_i], y=y[max_i], xref="x", yref="y",
            text="%dd" % x[max_i], showarrow=False, yshift=14,
            font=dict(size=11, color=INK_SECONDARY, family=FONT_FAMILY),
        ))

    fig.update_layout(
        title=dict(text="Time to rejection",
                   font=dict(size=18, color=INK_PRIMARY, family=FONT_FAMILY),
                   x=0, xanchor="left"),
        annotations=annotations,
        margin=dict(t=110 if n_excluded else 80, l=60, r=40, b=60),
        paper_bgcolor=PAGE, plot_bgcolor=SURFACE,
        font=dict(family=FONT_FAMILY, color=INK_SECONDARY),
        showlegend=False,
        xaxis=dict(
            title=dict(text="Days to rejection",
                       font=dict(color=INK_SECONDARY, family=FONT_FAMILY)),
            showgrid=True, gridcolor=GRIDLINE, gridwidth=1, zeroline=False,
            tickfont=dict(color=INK_MUTED)),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False,
                   range=[-1, 1], fixedrange=True),
    )
    _write(fig, charts_dir / "time_to_rejection.html")


# ---------------------------------------------------------------------------
# charts/channels.html and charts/tiers.html - horizontal stacked bars
# ---------------------------------------------------------------------------
def _stacked_outcome_bars(rows, category_col, title, out_path):
    categories = [r[category_col] for r in rows]
    fig = go.Figure()
    for col, label, color in OUTCOME_SEGMENTS:
        counts = [int(r[col]) for r in rows]
        texts = [str(c) if c > 0 else "" for c in counts]
        fig.add_trace(go.Bar(
            name=label, y=categories, x=counts, orientation="h",
            marker=dict(color=color),
            text=texts, textposition="inside", insidetextanchor="middle",
            constraintext="both",
            insidetextfont=dict(color=_text_on_fill(color), family=FONT_FAMILY,
                                 size=12),
            hovertemplate="%{y}<br>" + label + ": %{x}<extra></extra>",
        ))

    # Segment-to-segment gaps: a 2px-wide SURFACE-filled pixel strip
    # dropped on top of the stack at each boundary between two touching
    # (non-zero) segments, per the dataviz skill - "the gap and the ring
    # are the mechanism; a stroke adds data-weight ink that isn't data."
    # A boundary next to a zero-count segment isn't a real visual seam
    # (nothing is drawn there), so those are skipped.
    bargap = 0.5
    half_thickness = (1 - bargap) / 2  # bar occupies (1-bargap) of the
                                        # category's unit band, centered
    for row_idx, r in enumerate(rows):
        counts = [int(r[col]) for col, _, _ in OUTCOME_SEGMENTS]
        nonzero_positions = [i for i, c in enumerate(counts) if c > 0]
        cumulative = []
        running = 0
        for c in counts:
            running += c
            cumulative.append(running)
        for earlier, later in zip(nonzero_positions, nonzero_positions[1:]):
            boundary_x = cumulative[earlier]
            fig.add_shape(
                type="rect", xref="x", yref="y",
                xsizemode="pixel", xanchor=boundary_x, x0=-1, x1=1,
                y0=row_idx - half_thickness, y1=row_idx + half_thickness,
                fillcolor=SURFACE, line_width=0, layer="above",
            )

    n = len(categories)
    fig.update_layout(
        barmode="stack", bargap=bargap,
        title=dict(text=title,
                   font=dict(size=18, color=INK_PRIMARY, family=FONT_FAMILY),
                   x=0, xanchor="left"),
        height=max(220, 110 + n * 48),
        margin=dict(t=90, l=140, r=40, b=60),
        paper_bgcolor=PAGE, plot_bgcolor=SURFACE,
        font=dict(family=FONT_FAMILY, color=INK_SECONDARY),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left",
                    x=0, font=dict(color=INK_SECONDARY, family=FONT_FAMILY)),
        xaxis=dict(
            title=dict(text="Applications",
                       font=dict(color=INK_SECONDARY, family=FONT_FAMILY)),
            showgrid=True, gridcolor=GRIDLINE, gridwidth=1, zeroline=False,
            tickfont=dict(color=INK_MUTED)),
        yaxis=dict(autorange="reversed", showgrid=False,
                   tickfont=dict(color=INK_SECONDARY)),
    )
    _write(fig, out_path)


def _render_channels(results_dir, charts_dir):
    rows = _read_csv(results_dir / "channel_outcomes.csv")
    rows.sort(key=lambda r: (-int(r["n_total"]), r["channel"]))
    _stacked_outcome_bars(rows, "channel", "Applications by channel",
                          charts_dir / "channels.html")


def _render_tiers(results_dir, charts_dir):
    rows = _read_csv(results_dir / "tier_outcomes.csv")
    tier_rank = {"entry": 0, "stretch": 1}
    rows.sort(key=lambda r: (tier_rank.get(r["tier"], 2), r["tier"]))
    _stacked_outcome_bars(rows, "tier", "Applications by tier",
                          charts_dir / "tiers.html")


# ---------------------------------------------------------------------------
# charts/ops.html - dot strip by category
# ---------------------------------------------------------------------------
def _render_ops(results_dir, charts_dir):
    rows = _read_csv(results_dir / "ops_close_times.csv")
    rows.sort(key=lambda r: (int(r["days_open"]), r["op_id"]))

    n_no_close = int(rows[0]["n_done_without_close_date"]) if rows else 0
    categories = sorted({r["category"] for r in rows})
    cat_idx = {c: i for i, c in enumerate(categories)}
    jit = _jitter(len(rows), amplitude=0.28, seed=4002)
    x = [int(r["days_open"]) for r in rows]
    y = [cat_idx[r["category"]] + jit[i] for i, r in enumerate(rows)]
    hover = ["%s &middot; %s &middot; %d day(s) open &middot; raised %sx"
             % (r["op_id"], r["category"], int(r["days_open"]), r["times_raised"])
             for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers",
        marker=dict(size=10, color=OUTCOME_COLORS["rejected"],
                    line=dict(color=SURFACE, width=2)),
        hovertext=hover, hoverinfo="text",
    ))

    annotations = [dict(
        text="%d closed op(s) lack a machine-readable close date" % n_no_close,
        xref="paper", yref="paper", x=0, y=1.1, xanchor="left",
        yanchor="bottom", showarrow=False,
        font=dict(size=12, color=INK_MUTED, family=FONT_FAMILY),
    )]
    if rows:
        max_i = max(range(len(rows)), key=lambda i: x[i])
        annotations.append(dict(
            x=x[max_i], y=y[max_i], xref="x", yref="y",
            text="%dd" % x[max_i], showarrow=False, yshift=14,
            font=dict(size=11, color=INK_SECONDARY, family=FONT_FAMILY),
        ))

    fig.update_layout(
        title=dict(text="Ops resolution time by category",
                   font=dict(size=18, color=INK_PRIMARY, family=FONT_FAMILY),
                   x=0, xanchor="left"),
        annotations=annotations,
        margin=dict(t=110, l=140, r=40, b=60),
        height=max(240, 140 + len(categories) * 56),
        paper_bgcolor=PAGE, plot_bgcolor=SURFACE,
        font=dict(family=FONT_FAMILY, color=INK_SECONDARY),
        showlegend=False,
        xaxis=dict(
            title=dict(text="Days open",
                       font=dict(color=INK_SECONDARY, family=FONT_FAMILY)),
            showgrid=True, gridcolor=GRIDLINE, gridwidth=1, zeroline=False,
            tickfont=dict(color=INK_MUTED)),
        yaxis=dict(tickmode="array", tickvals=list(range(len(categories))),
                   ticktext=categories,
                   range=[-0.6, max(0, len(categories) - 1) + 0.6],
                   showgrid=False, tickfont=dict(color=INK_SECONDARY)),
    )
    _write(fig, charts_dir / "ops.html")


# ---------------------------------------------------------------------------
# charts/finance.html - step line (line_shape='hv')
# ---------------------------------------------------------------------------
def _render_finance(results_dir, charts_dir):
    rows = _read_csv(results_dir / "finance_trajectory.csv")
    rows.sort(key=lambda r: r["event_date"])

    line_rows = [r for r in rows if r["buffer_pct"].strip() != ""]
    event_rows = [r for r in rows
                  if r["income_changed"].strip().lower() == "true"]
    n_series = int(bool(line_rows)) + int(bool(event_rows))
    show_legend = n_series >= 2

    fig = go.Figure()
    if line_rows:
        xs = [r["event_date"] for r in line_rows]
        ys = [float(r["buffer_pct"]) for r in line_rows]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines", line_shape="hv",
            line=dict(color=OUTCOME_COLORS["rejected"], width=2),
            name="Buffer % of target",
            hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        ))
        # End-dot + value label on the last observation only - selective
        # labeling, not a number on every point.
        fig.add_trace(go.Scatter(
            x=[xs[-1]], y=[ys[-1]], mode="markers+text",
            marker=dict(size=10, color=OUTCOME_COLORS["rejected"],
                        line=dict(color=SURFACE, width=2)),
            text=["%.0f%%" % ys[-1]], textposition="top center",
            textfont=dict(color=INK_SECONDARY, family=FONT_FAMILY, size=12),
            showlegend=False, hoverinfo="skip",
        ))

    if event_rows:
        fig.add_trace(go.Scatter(
            x=[r["event_date"] for r in event_rows], y=[100] * len(event_rows),
            mode="markers+text",
            marker=dict(size=10, symbol="diamond",
                        color=OUTCOME_COLORS["no_response_yet"],
                        line=dict(color=SURFACE, width=2)),
            text=["Income change"] * len(event_rows), textposition="bottom center",
            textfont=dict(color=INK_SECONDARY, family=FONT_FAMILY, size=11),
            name="Income changed",
            hovertemplate="%{x}: income changed<extra></extra>",
        ))
        for r in event_rows:
            fig.add_shape(type="line", xref="x", yref="y",
                          x0=r["event_date"], x1=r["event_date"], y0=0, y1=100,
                          line=dict(color=OUTCOME_COLORS["no_response_yet"],
                                    width=1))

    if rows:
        fig.add_shape(type="line", xref="x", yref="y",
                      x0=rows[0]["event_date"], x1=rows[-1]["event_date"],
                      y0=100, y1=100, line=dict(color=BASELINE, width=1))
        fig.add_annotation(x=rows[-1]["event_date"], y=100, xref="x", yref="y",
                           text="100% target", showarrow=False,
                           xanchor="right", yanchor="bottom",
                           font=dict(size=11, color=INK_MUTED,
                                     family=FONT_FAMILY))

    fig.update_layout(
        title=dict(text="Financial buffer over time",
                   font=dict(size=18, color=INK_PRIMARY, family=FONT_FAMILY),
                   x=0, xanchor="left"),
        showlegend=show_legend,
        margin=dict(t=80, l=60, r=60, b=60),
        paper_bgcolor=PAGE, plot_bgcolor=SURFACE,
        font=dict(family=FONT_FAMILY, color=INK_SECONDARY),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left",
                    x=0, font=dict(color=INK_SECONDARY, family=FONT_FAMILY)),
        xaxis=dict(
            type="date",
            title=dict(text="Date",
                       font=dict(color=INK_SECONDARY, family=FONT_FAMILY)),
            showgrid=True, gridcolor=GRIDLINE, gridwidth=1, zeroline=False,
            tickfont=dict(color=INK_MUTED)),
        yaxis=dict(
            range=[0, 100],
            title=dict(text="Buffer % of target",
                       font=dict(color=INK_SECONDARY, family=FONT_FAMILY)),
            showgrid=True, gridcolor=GRIDLINE, gridwidth=1, zeroline=False,
            tickfont=dict(color=INK_MUTED)),
    )
    _write(fig, charts_dir / "finance.html")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
def render_all(results_dir, charts_dir):
    results_dir = Path(results_dir)
    charts_dir = Path(charts_dir)
    charts_dir.mkdir(parents=True, exist_ok=True)

    _render_headline(results_dir, charts_dir)
    _render_funnel(results_dir, charts_dir)
    _render_time_to_rejection(results_dir, charts_dir)
    _render_channels(results_dir, charts_dir)
    _render_tiers(results_dir, charts_dir)
    _render_ops(results_dir, charts_dir)
    _render_finance(results_dir, charts_dir)


if __name__ == "__main__":
    REPO = Path(__file__).resolve().parents[1]
    render_all(REPO / "results", REPO / "charts")
