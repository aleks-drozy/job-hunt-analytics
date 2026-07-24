# tests/test_anonymize.py
"""The anonymizer's two jobs: IDs that never change between runs, and a
fail-closed posture on sectors (a human fills those in; the pipeline
refuses to guess)."""
import json
from job_analytics.anonymize import (
    SECTORS, _anon_id, ensure_mapped, load_map, save_map,
)


def test_anon_id_sequence_covers_past_z():
    assert _anon_id(0) == "Company A"
    assert _anon_id(25) == "Company Z"
    assert _anon_id(26) == "Company AA"
    assert _anon_id(27) == "Company AB"
    assert _anon_id(51) == "Company AZ"
    assert _anon_id(52) == "Company BA"


def test_new_companies_get_sequential_ids_and_no_sector(tmp_path):
    path = tmp_path / "company_map.json"
    mapping = load_map(path)
    missing = ensure_mapped(mapping, ["Acme Robotics", "Northwind Systems"])
    assert mapping["companies"]["Acme Robotics"]["anon_id"] == "Company A"
    assert mapping["companies"]["Northwind Systems"]["anon_id"] == "Company B"
    assert missing == ["Acme Robotics", "Northwind Systems"]  # sectors unset


def test_existing_company_keeps_its_id_across_runs(tmp_path):
    path = tmp_path / "company_map.json"
    mapping = load_map(path)
    ensure_mapped(mapping, ["Acme Robotics"])
    mapping["companies"]["Acme Robotics"]["sector"] = "tech"
    save_map(mapping, path)

    reloaded = load_map(path)
    missing = ensure_mapped(reloaded, ["Globex Corp", "Acme Robotics"])
    assert reloaded["companies"]["Acme Robotics"]["anon_id"] == "Company A"
    assert reloaded["companies"]["Globex Corp"]["anon_id"] == "Company B"
    assert missing == ["Globex Corp"]  # Acme's sector is set, Globex's isn't


def test_save_and_reload_roundtrip(tmp_path):
    path = tmp_path / "company_map.json"
    mapping = load_map(path)
    ensure_mapped(mapping, ["Initech Ltd"])
    mapping["companies"]["Initech Ltd"]["sector"] = "fintech"
    save_map(mapping, path)
    assert json.loads(path.read_text(encoding="utf-8"))["companies"]["Initech Ltd"]["sector"] == "fintech"


def test_sector_vocabulary_is_closed():
    assert "fintech" in SECTORS and "bank" in SECTORS and "other" in SECTORS
    assert "made_up_sector" not in SECTORS
