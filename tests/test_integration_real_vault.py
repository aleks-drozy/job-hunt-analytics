"""Runs ONLY when JOBHUNT_VAULT_PATH is set (never in CI). Asserts
structure and sanity of the real parse - never specific real values, so
this file stays clean to publish."""
import os

import pytest

VAULT = os.environ.get("JOBHUNT_VAULT_PATH")
pytestmark = pytest.mark.skipif(not VAULT, reason="JOBHUNT_VAULT_PATH not set")


def test_real_vault_parses_without_exceptions_and_plausible_shapes(tmp_path):
    from job_analytics.load_db import build
    counts = build(VAULT, tmp_path / "private.duckdb")
    assert counts["applications"] > 20          # ~30 known at plan time
    assert counts["ledger_ops"] > 30            # 65+ known at plan time
    assert counts["finance_events"] > 5
    assert counts["debrief_days"] > 10
    # every parsed application has the mandatory fields non-empty
    import duckdb
    con = duckdb.connect(str(tmp_path / "private.duckdb"), read_only=True)
    nulls = con.execute(
        "SELECT count(*) FROM applications WHERE company IS NULL"
        " OR company = '' OR status IS NULL OR tier IS NULL").fetchone()[0]
    con.close()
    assert nulls == 0
