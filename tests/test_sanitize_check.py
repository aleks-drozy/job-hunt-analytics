"""The gate itself gets the adversarial treatment: every rule must be
shown CATCHING a planted violation, not just passing clean data."""
import csv
import re
import subprocess
import sys
from pathlib import Path

import scripts.sanitize_check as sanitize_check
from scripts.sanitize_check import positive_control, scan

PY = sys.executable


def _clean_export(tmp_path):
    out = tmp_path / "export"
    out.mkdir()
    with open(out / "applications.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["app_id", "company", "sector", "tier", "role_family",
                    "channel", "applied_date", "status", "status_date",
                    "followup_due"])
        w.writerow(["A001", "Company A", "tech", "entry", "swe", "linkedin",
                    "2026-01-05", "applied", "", "2026-01-15"])
    with open(out / "ledger_ops.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["op_id", "category", "first_raised", "times_raised",
                    "status", "close_date"])
        w.writerow(["L001", "project", "2026-01-04", "2", "done", "2026-01-06"])
    return out


def test_clean_export_passes(tmp_path):
    assert scan(_clean_export(tmp_path), banned_terms=[]) == []


def test_email_and_currency_are_caught(tmp_path):
    out = _clean_export(tmp_path)
    (out / "extra.csv").write_text(
        "note\nping someone@fabricated-mail.test about EUR 1,234 today\n",
        encoding="utf-8")
    findings = scan(out, banned_terms=[])
    assert any("email" in f for f in findings)
    assert any("currency" in f for f in findings)


def test_banned_term_is_caught_case_insensitively(tmp_path):
    out = _clean_export(tmp_path)
    (out / "extra.csv").write_text("col\nACME robotics slipped through\n",
                                   encoding="utf-8")
    findings = scan(out, banned_terms=["Acme Robotics"])
    assert any("banned" in f for f in findings)


def test_structural_rules_catch_forbidden_columns_and_bad_anon_ids(tmp_path):
    out = _clean_export(tmp_path)
    # a role_title column must never exist in the export
    with open(out / "applications.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["app_id", "company", "role_title"])
        w.writerow(["A001", "Some Real-Looking Name", "Graduate Engineer"])
    findings = scan(out, banned_terms=[])
    assert any("forbidden_column" in f for f in findings)
    assert any("anon_pattern" in f for f in findings)


def test_positive_control_flags_all_planted_patterns(tmp_path):
    assert positive_control(tmp_path) is True


def test_cli_exit_codes(tmp_path):
    out = _clean_export(tmp_path)
    r = subprocess.run([PY, "scripts/sanitize_check.py", str(out), "--ci"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    (out / "extra.csv").write_text("x\nmail me at leak@fabricated.test\n",
                                   encoding="utf-8")
    r = subprocess.run([PY, "scripts/sanitize_check.py", str(out), "--ci"],
                       capture_output=True, text=True)
    assert r.returncode == 1
    assert "email" in r.stdout


# --- Adversarial-attack regression tests -----------------------------------
# Each of these reproduces one REAL RISK finding from the sanitize_check.py
# gate audit and proves it is now caught. Verified red-before/green-after by
# checking out ac0b4a1 (pre-fix HEAD) and re-running each test individually
# with `.venv/Scripts/python.exe -m pytest tests/test_sanitize_check.py -k
# <name>` -- every one of them failed against that commit and passes here.


def test_extra_unquoted_field_bypass_is_caught(tmp_path):
    """sanitize_check_scan_comma_naive_audit: a data row with one extra
    unquoted comma-delimited field hides a real company name at a column
    position scan() never inspected, because row cell count was never
    checked against the header. `A001,Company A,RealBankCorp Ltd leaked
    here,fintech,...` used to return zero findings."""
    out = _clean_export(tmp_path)
    with open(out / "applications.csv", "a", newline="", encoding="utf-8") as f:
        f.write("A001,Company A,RealBankCorp Ltd leaked here,fintech,entry,"
                 "swe,linkedin,2026-01-01,applied,2026-01-01,\n")
    findings = scan(out, banned_terms=[])
    assert any("row_length" in f for f in findings), findings
    assert findings != []


def test_fullwidth_at_sign_email_is_caught(tmp_path):
    """sanitize_check_scan_adversarial_review: a fullwidth commercial-at
    (U+FF20) defeats the ASCII-only email regex."""
    out = _clean_export(tmp_path)
    (out / "extra.csv").write_text(
        "note\nreach contact＠fabricated.test for details\n",
        encoding="utf-8")
    findings = scan(out, banned_terms=[])
    assert any("email" in f for f in findings), findings


def test_double_nbsp_currency_is_caught(tmp_path):
    """sanitize_check_scan_adversarial_review: two consecutive NBSPs
    between the currency symbol and the digits were missed because the
    currency/currency_post patterns used \\s? (0-or-1) not \\s* (0-or-more)."""
    out = _clean_export(tmp_path)
    (out / "extra.csv").write_text(
        "note\nfigure was EUR  9999 total\n", encoding="utf-8")
    findings = scan(out, banned_terms=[])
    assert any("currency" in f for f in findings), findings


def test_banned_term_double_space_is_caught(tmp_path):
    """sanitize_check_scan_adversarial_review: a banned company name with
    extra internal whitespace ('Acme  Robotics', double space) was missed
    because the substring check never collapsed whitespace runs."""
    out = _clean_export(tmp_path)
    (out / "extra.csv").write_text(
        "note\nAcme  Robotics slipped through with double space\n",
        encoding="utf-8")
    findings = scan(out, banned_terms=["Acme Robotics"])
    assert any("banned" in f for f in findings), findings


def test_positive_control_catches_broken_currency_post(monkeypatch):
    """sanitize_check_positive_control_audit: currency_post had no planted
    example and wasn't in the required rules_hit set, so breaking its
    regex was invisible to the self-test."""
    patched = [(name, (re.compile(r"ZZZ_NEVER_MATCHES_ANYTHING_ZZZ")
                        if name == "currency_post" else rx))
               for name, rx in sanitize_check.GENERIC]
    monkeypatch.setattr(sanitize_check, "GENERIC", patched)
    assert positive_control() is False


def test_positive_control_catches_disabled_structural_rules(monkeypatch):
    """sanitize_check_positive_control_audit: none of columns,
    forbidden_column, or anon_pattern were exercised by positive_control(),
    so fully disabling them was invisible to the self-test."""
    monkeypatch.setattr(sanitize_check, "FORBIDDEN_COLUMNS", set())
    monkeypatch.setattr(sanitize_check, "EXPECTED_COLUMNS", {})
    monkeypatch.setattr(sanitize_check, "ANON_RE", re.compile(r".*"))
    assert positive_control() is False


def test_missing_export_dir_fails_closed():
    """sanitize_check_positive_control_audit: a nonexistent export_dir
    used to glob to zero files and report '0 finding(s)' / exit 0, a false
    pass indistinguishable from a genuinely clean export."""
    r = subprocess.run(
        [PY, "scripts/sanitize_check.py", "C:\\does\\not\\exist", "--ci"],
        capture_output=True, text=True)
    assert r.returncode != 0, r.stdout + r.stderr


def test_empty_export_dir_fails_closed(tmp_path):
    empty = tmp_path / "empty_export"
    empty.mkdir()
    r = subprocess.run([PY, "scripts/sanitize_check.py", str(empty), "--ci"],
                       capture_output=True, text=True)
    assert r.returncode != 0, r.stdout + r.stderr


def test_banned_term_word_boundary_true_positive_and_negative(tmp_path):
    """Word-boundary matching: a short banned term standing alone is a
    finding; the same term buried inside a longer word is not (the audit
    found a 3-char term false-positived on 'groups'/'mixups')."""
    out = _clean_export(tmp_path)
    (out / "extra.csv").write_text(
        "note\n"
        "shift at vex again this week\n"       # line 2: standalone -> caught
        "convexity mixups in study groups\n",  # line 3: substring -> ignored
        encoding="utf-8")
    findings = scan(out, banned_terms=["vex"])
    banned = [f for f in findings if "[banned]" in f]
    assert any("extra.csv:2" in f for f in banned), findings
    assert not any("extra.csv:3" in f for f in banned), findings


def test_banned_term_ending_in_non_word_char_still_caught(tmp_path):
    """Regression pinning the lookaround choice: a term ending in ')'
    (real company_map keys do) would NEVER match under re.escape(term)+r'\\b'."""
    out = _clean_export(tmp_path)
    (out / "extra.csv").write_text(
        "note\nrow mentions Fictional Corp (FC) verbatim\n", encoding="utf-8")
    findings = scan(out, banned_terms=["Fictional Corp (FC)"])
    assert any("[banned]" in f for f in findings), findings
