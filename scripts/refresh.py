"""One-command refresh: vault -> private DB -> sanitized export.

Order is load -> map -> export(staging) -> gate -> promote. The gate runs
in LOCAL mode (private lists required); export/ is only touched after a
clean scan, so the committed directory can never hold unchecked data.
Exit codes: 0 ok, 2 gate/control failure, 3 human input needed (sectors).
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

import duckdb  # noqa: E402

from job_analytics.anonymize import ensure_mapped, load_map, save_map  # noqa: E402
from job_analytics.export_public import UnmappedCompanyError, export  # noqa: E402
from job_analytics.load_db import build  # noqa: E402
from scripts.sanitize_check import positive_control, scan  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.environ.get("JOBHUNT_VAULT_PATH"))
    args = ap.parse_args()
    if not args.vault:
        print("set JOBHUNT_VAULT_PATH or pass --vault")
        return 3

    db = REPO / "data" / "private.duckdb"
    map_path = REPO / "data" / "company_map.json"
    counts = build(args.vault, db)
    print("private DB rebuilt:", counts)

    con = duckdb.connect(str(db), read_only=True)
    companies = [r[0] for r in con.execute(
        "SELECT DISTINCT company FROM applications ORDER BY company").fetchall()]
    con.close()

    mapping = load_map(map_path)
    missing = ensure_mapped(mapping, companies)
    save_map(mapping, map_path)
    if missing:
        print("\nHUMAN INPUT NEEDED - fill in 'sector' for these companies")
        print("in data/company_map.json (allowed values in anonymize.SECTORS),")
        print("then rerun. Names below stay on this machine only:")
        for name in missing:
            print("  -", name)
        return 3

    staging = REPO / "export" / ".staging"
    if staging.exists():
        shutil.rmtree(staging)
    try:
        export_counts = export(db, map_path, staging)
    except UnmappedCompanyError as e:
        print("export refused:", e)
        return 3

    if not positive_control():
        print("POSITIVE CONTROL FAILED - refusing to certify")
        return 2
    banned = list(json.loads(map_path.read_text(encoding="utf-8"))
                  ["companies"].keys())
    terms = REPO / "data" / "banned_terms.txt"
    if terms.exists():
        banned += terms.read_text(encoding="utf-8").splitlines()
    findings = scan(staging, banned)
    if findings:
        for f in findings:
            print(f)
        print("GATE FAILED - staging NOT promoted")
        return 2

    for f in staging.glob("*.csv"):
        shutil.copy2(f, REPO / "export" / f.name)
    shutil.rmtree(staging)
    print("export promoted:", export_counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
