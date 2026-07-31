"""Repo-wide leak gate: every tracked text file — not just export/*.csv,
README.md and index.html — passes the generic leak regexes, and (locally,
where the gitignored private lists exist) contains no banned term as a
whole word."""
import subprocess
import unicodedata
from pathlib import Path

import pytest

from scripts.sanitize_check import (GENERIC, _collapse_ws,
                                    compile_banned, load_private_terms)

ROOT = Path(__file__).resolve().parents[1]

# Vendored third-party assets: not ours, minified noise.
VENDORED = {"charts/plotly.min.js"}

# Files whose PURPOSE is fabricated leak-shaped strings (planted positive
# controls, fake fixture emails/amounts). Only the GENERIC layer is waived
# for them; the banned-terms layer has NO exemptions anywhere.
GENERIC_EXEMPT_DIRS = ("tests/",)
GENERIC_EXEMPT_FILES = {"scripts/sanitize_check.py"}


def _tracked_files():
    r = subprocess.run(["git", "ls-files"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, "git ls-files failed: " + r.stderr
    names = [n for n in r.stdout.splitlines() if n and n not in VENDORED]
    # fail closed: a broken git call must not look like a clean repo
    assert len(names) > 40, "suspiciously few tracked files: %d" % len(names)
    return names


def _text_of(rel):
    # Strict decode: an undecodable tracked file must be consciously
    # triaged into VENDORED, never silently skipped.
    return unicodedata.normalize(
        "NFKC", (ROOT / rel).read_text(encoding="utf-8"))


def test_generic_leak_regexes_hold_repo_wide():
    failures, checked = [], 0
    for rel in _tracked_files():
        if rel.startswith(GENERIC_EXEMPT_DIRS) or rel in GENERIC_EXEMPT_FILES:
            continue
        checked += 1
        for i, line in enumerate(_text_of(rel).splitlines(), 1):
            for name, rx in GENERIC:
                m = rx.search(line)
                if m:
                    failures.append("%s:%d [%s] %s" % (rel, i, name, m.group(0)))
    assert checked > 0
    assert not failures, failures


def test_no_banned_term_in_any_tracked_file():
    terms = load_private_terms()
    if not terms:
        pytest.skip("private lists are gitignored and absent (CI); "
                    "the full check runs locally only, by design")
    compiled = compile_banned(terms)
    failures = []
    for rel in _tracked_files():          # no exemptions in this layer
        for i, line in enumerate(_text_of(rel).splitlines(), 1):
            low = _collapse_ws(line.lower())
            for term, rx in compiled:
                if rx.search(low):
                    failures.append("%s:%d [banned] %s" % (rel, i, term))
    assert not failures, failures
