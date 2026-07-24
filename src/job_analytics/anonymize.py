# src/job_analytics/anonymize.py
"""Stable company anonymization via a PRIVATE, gitignored mapping file.

data/company_map.json holds {real name -> {anon_id, sector}}. IDs are
assigned once, on first appearance, and never change afterwards - the
living-dashboard requirement: "Company C" must mean the same company in
every refresh. Sectors are HUMAN knowledge: the pipeline assigns
sector=None to new companies and the exporter refuses to run until a
person has filled every sector in. Fail closed, never guess.
"""
import json
import os
from pathlib import Path

SECTORS = frozenset({
    "fintech", "bank", "big_tech", "tech", "consultancy", "edtech",
    "healthtech", "recruiting_agency", "logistics", "retail",
    "public_sector", "university", "other",
})

_EMPTY = {"companies": {}}


def _anon_id(i):
    letters = ""
    i += 1  # 1-based for the letter math
    while i > 0:
        i, rem = divmod(i - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return "Company " + letters


def load_map(path):
    path = Path(path)
    if not path.exists():
        return json.loads(json.dumps(_EMPTY))  # fresh copy
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_mapped(mapping, companies):
    known = mapping["companies"]
    for name in companies:
        if name not in known:
            known[name] = {"anon_id": _anon_id(len(known)), "sector": None}
    return [n for n in companies if known[n]["sector"] is None]


def save_map(mapping, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(mapping, indent=1, sort_keys=True),
                   encoding="utf-8")
    os.replace(tmp, path)
