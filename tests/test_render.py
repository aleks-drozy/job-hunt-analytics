# tests/test_render.py
"""Charts are derived artifacts - smoke-render them from synthetic
results and hold them to the same leak standard as the CSVs, reusing the
sanitize gate's own GENERIC regexes on the generated HTML."""
from pathlib import Path

from scripts.analyze import run_analyses
from scripts.render import render_all
from scripts.sanitize_check import GENERIC
from tests.test_analyze import _fake_export


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
    assert "as of 2026-01-15" in html.lower()


def test_chart_html_passes_the_generic_leak_regexes(tmp_path):
    charts = _rendered(tmp_path)
    for p in charts.glob("*.html"):          # plotly.min.js excluded: *.html only
        text = p.read_text(encoding="utf-8")
        for name, rx in GENERIC:
            assert not rx.search(text), (p.name, name, rx.search(text).group(0))
