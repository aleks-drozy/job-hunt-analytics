# tests/test_render.py
"""Charts are derived artifacts - smoke-render them from synthetic
results and hold them to the same leak standard as the CSVs, reusing the
sanitize gate's own GENERIC regexes on the generated HTML."""
from pathlib import Path

from scripts.analyze import run_analyses
from scripts.render import INK_PRIMARY, _render_finance, _text_on_fill, render_all
from scripts.sanitize_check import GENERIC
from tests.test_analyze import _fake_export

REPO = Path(__file__).resolve().parents[1]
CHARTS_REAL = REPO / "charts"


def _rendered(tmp_path):
    results = tmp_path / "results"
    run_analyses(_fake_export(tmp_path), "sql", results)
    charts = tmp_path / "charts"
    render_all(results, charts)
    return charts


def test_all_charts_render(tmp_path):
    charts = _rendered(tmp_path)
    expected = {"headline.html", "funnel.html", "time_to_rejection.html",
                "channels.html", "tiers.html", "ops.html", "finance.html"}
    assert expected.issubset({p.name for p in charts.glob("*.html")})


def test_headline_carries_the_computed_zero_not_a_hardcoded_one(tmp_path):
    charts = _rendered(tmp_path)
    html = (charts / "headline.html").read_text(encoding="utf-8")
    assert "0" in html and "interview" in html.lower()
    # as_of = GREATEST(MAX(applied_date), MAX(status_date)) - see
    # test_analyze.py's recomputation; followup_due is excluded.
    assert "as of 2026-01-10" in html.lower()


def test_chart_html_passes_the_generic_leak_regexes(tmp_path):
    charts = _rendered(tmp_path)
    for p in charts.glob("*.html"):          # plotly.min.js excluded: *.html only
        text = p.read_text(encoding="utf-8")
        for name, rx in GENERIC:
            assert not rx.search(text), (p.name, name, rx.search(text).group(0))


def test_real_committed_charts_pass_the_generic_leak_regexes():
    """The synthetic-fixture test above (test_chart_html_passes_the_generic_
    leak_regexes) only ever scans charts rendered from _fake_export - it
    never touches the real, committed charts/*.html files that are what
    actually gets published. Mirrors test_build_dashboard.py's pattern of
    scanning the real on-disk artifact directly."""
    html_files = list(CHARTS_REAL.glob("*.html"))
    assert html_files, "no committed charts/*.html files found at %s" % CHARTS_REAL
    for p in html_files:
        text = p.read_text(encoding="utf-8")
        for name, rx in GENERIC:
            m = rx.search(text)
            assert not m, (p.name, name, m.group(0) if m else None)


def test_text_on_fill_picks_ink_not_white_for_aqua():
    """Regression test for the WCAG contrast fix: the old YIQ
    perceived-brightness heuristic picked WHITE text on aqua (#1baf7a),
    which renders at only 2.82:1 contrast - failing WCAG AA's 4.5:1
    minimum for normal text. A proper relative-luminance contrast
    calculation must pick ink instead (~6.99:1, clearly passing)."""
    assert _text_on_fill("#1baf7a") == INK_PRIMARY


def test_rejected_color_is_identical_across_channel_tier_and_funnel_charts(tmp_path):
    """Cross-task color-identity invariant: 'rejected' must render in the
    identical blue (#2a78d6) on channels.html, tiers.html and
    funnel.html - previously only verified by manual review."""
    charts = _rendered(tmp_path)
    rejected_hex = "#2a78d6"
    for name in ("channels.html", "tiers.html", "funnel.html"):
        html = (charts / name).read_text(encoding="utf-8")
        assert rejected_hex in html, "%s missing rejected color %s" % (name, rejected_hex)


def test_finance_dedupes_income_change_events_sharing_a_date(tmp_path):
    """finance_trajectory.csv can have two rows sharing one event_date
    (a marker-only null-buffer-pct row plus a real buffer-pct row, both
    income_changed=true) - a real shape in the fixture data. Before the
    dedupe fix this drew two overlapping "Income change" labels and two
    overlapping vertical lines at the same x-position. Calls
    _render_finance directly (it only reads finance_trajectory.csv) so
    this stays a narrow, standalone test that can't destabilize the
    shared _rendered() fixture used by the other tests in this file."""
    results = tmp_path / "results"
    results.mkdir()
    (results / "finance_trajectory.csv").write_text(
        "event_date,buffer_pct,income_changed\n"
        "2026-01-05,40.0,False\n"
        "2026-01-08,,True\n"
        "2026-01-08,55.0,True\n"
        "2026-01-09,95.0,False\n",
        encoding="utf-8")
    charts = tmp_path / "charts"
    charts.mkdir()
    _render_finance(results, charts)
    html = (charts / "finance.html").read_text(encoding="utf-8")
    # One marker+text trace entry ("Income change" label)...
    assert html.count('"Income change"') == 1
    # ...and one vertical event-line shape at that date, not two.
    assert html.count('"x0":"2026-01-08","x1":"2026-01-08"') == 1
