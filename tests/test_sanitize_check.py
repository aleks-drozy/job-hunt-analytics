"""The gate itself gets the adversarial treatment: every rule must be
shown CATCHING a planted violation, not just passing clean data."""
import csv
import subprocess
import sys
from pathlib import Path

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
