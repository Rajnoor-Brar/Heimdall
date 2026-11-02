---
id: housekeeping
summary: check, status, clean, migrate, reproduce, and pinning which stack a study was made with
code: framework/runner/house.py, framework/runner/migrate.py
---

# Housekeeping

```bash
heimdall check                         # every config: validated, every point planned; runs nothing
heimdall ls Demo                       # every config and its configurations (* = what heimdall run runs)
heimdall status Demo/jets              # each point: complete, stale, failed (and why), stopped or to run
heimdall status --stack                # each package's version
heimdall clean Demo/jets --dry-run     # what the runner made and no plan uses
heimdall migrate Demo/jets             # a diff of the file in today's forms; --apply writes it
heimdall reproduce records/…/<point>/provenance.json   # the point again, beside it, compared
```

- **`check`** exits 2 when any config is not well: use it before a long sweep, or as a pre-commit hook.
- **`clean`** never removes a result. It lists first and asks (`--yes` elsewhere), and refuses while a job runs.
- **`migrate`** rewrites old forms by line, so comments and layout stay. `--v3` rewrites a v2 file; `--layout` a work dir from before `records/`.
- **Which stack a study was made with:** `[file.meta] versions = { pythia8 = "8.317" }`. A different stack is a warning in `check` and `--plan`, never a refusal.
- **`reproduce`** stops and says what changed when the setup no longer matches the provenance.
