# Environment variables (names only — this file is safe to publish)

| Variable | Purpose | Required for |
|---|---|---|
| `JOBHUNT_VAULT_PATH` | Absolute path to the local Obsidian vault's `12-jarvis/` folder (source of `JOB_SEARCH.md`, `LEDGER.md`, `FINANCE.md`, `debriefs/`). Never committed; the parsers take it as a runtime argument, not a hardcoded path. | Local refresh / `make refresh` |

No API keys, no secrets. Everything this project reads is local markdown; nothing it writes
goes anywhere but `data/` (gitignored) and `export/` (committed, sanitized).
