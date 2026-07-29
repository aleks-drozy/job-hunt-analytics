"""README.md is a public claim, so it gets tested like one. These tests are
about the claims the writeup makes, never about its prose style: headline
numbers must match results/*.csv verbatim, the framing paragraph must read
as descriptive rather than inferential, the LinkedIn caveat and the
censored/ghosted distinction must be present, and the README must pass the
same leak gate the exported CSVs pass. No test here asserts wording beyond
what a claim requires.
"""
import csv
import re
from pathlib import Path

import pytest

from scripts.sanitize_check import GENERIC

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _read_csv_rows(name):
    with open(ROOT / "results" / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_headline_numbers_match_funnel_summary_verbatim():
    row = _read_csv_rows("funnel_summary.csv")[0]
    for key in ("n_tracked", "n_submitted", "n_rejected", "n_no_response_yet"):
        assert row[key] in README, "%s=%s missing from README.md" % (key, row[key])
    assert row["as_of"] in README, "as_of=%s missing from README.md" % row["as_of"]
    assert re.search(r"0 interviews", README), "unhedged '0 interviews' headline not found"


def test_opening_is_the_framing_paragraph():
    head = README[:1800]
    assert "descriptive" in head
    assert ("inferential" in head) or ("significance" in head)
    assert "50" in head


def test_linkedin_caveat_present():
    assert ("nothing came back" in README) or ("no response at all" in README)


def test_censoring_is_labelled_and_ghosted_is_never_unqualified():
    assert "censored" in README.lower()
    for m in re.finditer(r"ghosted", README, flags=re.IGNORECASE):
        preceding = README[max(0, m.start() - 8):m.start()]
        assert re.search(r"\bnot\s+$", preceding, flags=re.IGNORECASE), (
            "'ghosted' appears without an immediately preceding 'not': %r"
            % README[max(0, m.start() - 30):m.end() + 10]
        )


def test_readme_passes_every_generic_leak_regex():
    for name, rx in GENERIC:
        m = rx.search(README)
        assert m is None, "%s regex matched %r in README.md" % (name, m.group(0) if m else None)


def test_no_dead_or_nonexistent_repo_links():
    assert "github.com" not in README.lower()
    assert "github.io" not in README.lower()


def test_banned_terms_absent_if_local_list_exists():
    banned_path = ROOT / "data" / "banned_terms.txt"
    if not banned_path.exists():
        pytest.skip("data/banned_terms.txt is gitignored and absent in CI")
    terms = [t.strip() for t in banned_path.read_text(encoding="utf-8").splitlines() if t.strip()]
    low = README.lower()
    for term in terms:
        assert term.lower() not in low, "banned term %r found in README.md" % term
