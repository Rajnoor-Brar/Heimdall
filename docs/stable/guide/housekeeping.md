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
heimdall records upgrade --dry-run     # the record files below today's format (see the reference for the options)
heimdall library list                  # the points library: its entries, who made and who links them
heimdall diff Demo/jets/01_a 02_b      # two Runs of one Errand: what differs
```

- **`check`** exits 2 when any config is not well: use it before a long sweep, or as a pre-commit hook.
- **`clean`** never removes a result. It lists first and asks (`--yes` elsewhere), and refuses while a job runs.
- **`migrate`** rewrites old forms by line, so comments and layout stay. `--v3` rewrites a v2 file; `--layout` a work dir from before `records/`.
- **Which stack a study was made with:** `[file.meta] versions = { pythia8 = "8.317" }`. A different stack is a warning in `check` and `--plan`, never a refusal.
- **`reproduce`** stops and says what changed when the setup no longer matches the provenance.
- **`records upgrade`** gives each record file below today's format its `format` key, a copy beside it first (`<name>.bak`); it refuses while a job of the work dir goes. A record of a newer format is refused by the commands that read it ([provenance](../internals/provenance.md)).
- **`diff <A>/<E>/<R1> <R2>`** compares two Runs of one Errand from their records, read only: the errand file each ran with key by key (`old → new`), the configuration and `--set`s, any other snapshot file by hash with its changed lines, and for each point both have its identity parts tool by tool (`exe_sha256`, options, card). Equal points are counted, not listed; points only one Run has are named. `<R2>` may be the folder alone. Heimdall's own revision is not a difference. Runs of different Errands, or one Run with itself, are refused.
