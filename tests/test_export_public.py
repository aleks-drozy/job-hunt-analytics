"""The exporter is the privacy boundary. These tests assert what LEAVES:
exact column whitelists, anon-pattern company values, and the two
fail-closed paths (missing sector, invalid sector)."""
import csv

import duckdb
import pytest

from job_analytics.anonymize import load_map, save_map
from job_analytics.export_public import UnmappedCompanyError, export
from job_analytics.load_db import build
from tests.test_load_db import _fake_vault


def _built(tmp_path):
    vault = _fake_vault(tmp_path)
    db = tmp_path / "private.duckdb"
    build(vault, db)
    return db


def _mapped(tmp_path, sector="tech"):
    m = load_map(tmp_path / "map.json")
    m["companies"]["Acme Robotics"] = {"anon_id": "Company A", "sector": sector}
    m["companies"]["Northwind Systems"] = {"anon_id": "Company B", "sector": "fintech"}
    save_map(m, tmp_path / "map.json")
    return tmp_path / "map.json"


def test_export_refuses_when_a_sector_is_missing_and_writes_nothing(tmp_path):
    db = _built(tmp_path)
    map_path = _mapped(tmp_path, sector=None)
    out = tmp_path / "export"
    with pytest.raises(UnmappedCompanyError) as e:
        export(db, map_path, out)
    assert "Acme Robotics" in str(e.value)
    assert not out.exists() or not any(out.iterdir())


def test_export_refuses_an_unknown_sector(tmp_path):
    db = _built(tmp_path)
    map_path = _mapped(tmp_path, sector="not_a_real_sector")
    with pytest.raises(ValueError):
        export(db, map_path, tmp_path / "export")


def test_export_columns_and_anonymization(tmp_path):
    db = _built(tmp_path)
    map_path = _mapped(tmp_path)
    out = tmp_path / "export"
    counts = export(db, map_path, out)
    assert counts["applications"] == 2

    with open(out / "applications.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0].keys()) == [
        "app_id", "company", "sector", "tier", "role_family", "channel",
        "applied_date", "status", "status_date", "followup_due"]
    companies = {r["company"] for r in rows}
    assert companies == {"Company A", "Company B"}
    families = {r["company"]: r["role_family"] for r in rows}
    assert families["Company A"] == "swe"      # Graduate Software Engineer
    assert families["Company B"] == "quant"    # Senior Quant Developer
    joined = " ".join(",".join(r.values()) for r in rows)
    assert "Acme" not in joined and "Northwind" not in joined
    assert "Graduate Software Engineer" not in joined  # titles never leave

    with open(out / "ledger_ops.csv", newline="", encoding="utf-8") as f:
        led = list(csv.DictReader(f))
    assert list(led[0].keys()) == [
        "op_id", "category", "first_raised", "times_raised", "status",
        "close_date"]
    assert {r["category"] for r in led} == {"project", "finance"}
    assert "widget-tracker-ci-fail" not in " ".join(
        ",".join(r.values()) for r in led)  # slugs never leave
