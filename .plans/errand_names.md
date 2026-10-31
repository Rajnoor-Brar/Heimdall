# `<Assignment>/<Errand>/<Run>`: the result levels' names (I-112)

Asked by the user on 2026-10-31: "Make sure this terminology convention is followed for names :
<Assignment>/<Errand>/<Run>". Answered the same day (four questions, each the recommended option): everything,
migrated; the run TOML becomes an errand file with an `[errand]` table; a Run's tag (I-113, built first); an
ignored axis is no axis across Runs (I-113). This file holds the inventory (§1), the vocabulary (§2), what is
decided beyond the answers (§3), the phases (§4) and the execution map (§5).

## 1. Inventory (branch `context` at I-113, `git grep -c`)

| Kind | Sites (runner · tools/plot · schema · docs 00–06 · tests · template) |
|---|---|
| `[run]` tables and `run.<key>` (the TOML table, `--set run.x=`, attribute access on a RunConfig) | 262 · 0 · 44 · 114 · 358 · 4 |
| `project` (the word, as `<P>` and as a variable/attribute) | 183 · 3 · 14 · 57 · 122 · 1 |
| `RunConfig` (the class) | 9 · 0 · 0 · 3 · 3 · 0 |
| "run TOML", "run config" | 86 · 0 · 12 · 99 · 26 · 6 |
| `<P>/<run>` and `<P>/<name>` addresses | 71 · 0 · 9 · 78 · 6 · 3 |
| `heimdall runs`, the registry (`runs/`, `HEIMDALL_RUNS`, `runs_root`) | 37 · 0 · 1 · 27 · 32 · 0 |
| "a run" / "the run" in prose (an invocation, mostly) | 236 · 23 · 49 · 245 · 86 · 7 |

**Outside Heimdall** (written only by `heimdall migrate --names`, in E6): Brookhaven's and High-Energy's
`configs/**/*.toml` (`[run]`, `[run.cfgs.*]`, dotted `run.` imports, `--set` lines in scripts and notes), their
`results/**/plot.toml` (`[source].project`, `[source].run`), `records/**/config/` (the snapshot each record keeps,
read by `heimdall log`, `plot` and `status` from a record), their CLAUDE.md and notes; the machine root's
`runs/` (the registry; live while a job runs).

## 2. The vocabulary

| Level | Today | Now |
|---|---|---|
| `configs/<A>/`, `results/<A>/` | a project, `<P>` | an **Assignment**, `<A>` |
| `configs/<A>/<E>.toml` and `results/<A>/<E>/` | a run TOML, `[run]`, its name | an **Errand**: an errand file, `[errand]`, `[errand].name`; `<E>` |
| `results/<A>/<E>/<NN_cfg>/` (with its record and cache) | a configuration folder, "a run" | a **Run**, `<R>` |
| one `[errand.cfgs.<cfg>]` | a configuration | a configuration (unchanged: the recipe a Run executes) |
| one invocation of `heimdall run` | a run, a job | a **job** (decided, §3) |

The address of a Run is `<A>/<E>/<R>` everywhere a command takes or prints one.

## 3. Decided (beyond the user's answers; bold, and said here so they can be undone)

- **D1 Keys.** `[run]` → `[errand]`, `[run.cfgs.<cfg>]` → `[errand.cfgs.<cfg>]` (v3's top-level `[cfgs.<cfg>]`
  unchanged), `[run].project` → `[errand].assignment`; every other `[run]` key keeps its name under `[errand]`
  (`sweep_runs` included: it does make a Run of each configuration). Dotted names follow: `--set errand.threads=8`,
  `import` keys `errand.cfgs.x`, `heimdall explain errand.<key>`. A plot document's `[source].project` →
  `[source].assignment`, `[source].run` → `[source].errand`. A clean break, as I-109: the old forms are refused
  with the one command that rewrites them (`heimdall migrate --names`).
- **D2 Code.** `RunConfig` → `Errand`, its `project` → `assignment`, `name` stays (the errand's name); a variable
  holding one is `errand`; `Doc.project`/`Doc.name` → `assignment`/`errand`; `RunFolders` keeps its name (it is
  a Run's folders) with `project` → `assignment`; `paths`' helpers taking `(project, name)` take
  `(assignment, errand)`. The verb `heimdall run`, `run_one`, `cmd_run` stay (they run Runs).
- **D3 Jobs** (proposed; built only when the user says so, E5). An invocation of `heimdall run` is a job, the word `heimdall stop` and `heimdall runs`' help
  already use: `heimdall runs` → `heimdall jobs` (`heimdall runs` stops, naming it, as V74 did for `plot FILE`);
  the registry `$HEIMDALL_MACHINE/runs/` → `jobs/`, `HEIMDALL_RUNS` → `HEIMDALL_JOBS`, `runs.py` → `jobs.py`.
  The registry moves only when no job is live (`heimdall migrate --names` refuses otherwise, naming them).
- **D4 Kept as they are:** `--across` ("an Errand's Runs together"), `[from].runs` and `@run` (globs and names of
  Run folders), `run.jsonl` (a Run's own log), `sweep_runs`, `heimdall run`, a record (`records/<A>/<E>/<R>/`).
  History (07's rows, done plans, `docs/audit_*`) is never rewritten.
- **D5 Old records** keep working: `heimdall migrate --names` rewrites each record's `config/` snapshot and each
  plot document's `[source]`; no point identity moves (a snapshot is not hashed; the cards are unchanged).

## 4. Phases

| Phase | What | V-row | Then |
|---|---|---|---|
| E1 | the dialect: `[errand]`, `[errand].assignment`, dotted names, the schema and its docs (04 regenerated), v3, imports, `--set`, `explain`; `[run]` refused with the hint | V225 | straight on |
| E2 | plot documents and records: `[source].assignment`/`errand`, read and written; old ones refused with the hint | V226 | straight on |
| E3 | code identifiers (D2), mechanical, ranks unchanged; the fixtures' configs rewritten (E4's migration, written first) with their tests | V227 | straight on |
| E4 | `heimdall migrate --names` (configs, snapshots, documents); docs 00–06, help and messages swept to the vocabulary; the fast and slow suites | V228 | **pause**: before any work dir is touched, and for D3 (it renames a command the user uses daily) |
| E5 | jobs (D3), when the user says so: `heimdall jobs`, `jobs.py`, `HEIMDALL_JOBS`, the registry's folder | V229 | straight on |
| E6 | Brookhaven and High-Energy migrated (`--apply`), left uncommitted for the user; the machine's registry moved (D3); main fast-forwarded | — | only when no job is live |

Each phase: built, its tests run light, committed by named paths with its V-row; this file's map and log written
at each commit. The runs-together, report and tag code of I-108–I-113 is renamed with the rest.

## 5. Execution map

| Phase | V-row | Commit | State |
|---|---|---|---|
| E0 this plan, the inventory | — | | written |
| E1 the dialect: `[errand]`, `[errand].assignment`, dotted names, the schema, v3, the walkers, `[run]` refused; the migration (`heimdall migrate --names`: configs, snapshots, provenance, documents), the fixture's configs and the starter by it; docs 00–06's examples | V225 | 8293eeb | done |
| E2 plot documents: `[source].assignment`, `[source].errand`, read and written; a report title's `{assignment}`, `{errand}`; the old ones refused | V226 | | done |

## 6. Log

- 2026-11-01: E1 built (V225). `[run]` → `[errand]`, `[run].project` → `[errand].assignment`, every other key's
  name kept; refused in the old names with `heimdall migrate --names rewrites it` (`v3.refuse_old_names`, at
  `config._form` and `parse`; `--set run.x`, an import's `run.…` keys, `explain run.x` each with today's form). The
  migration written now, for E3: `migrate.errand_changes` after I-109's `names_changes` (configs by `errand_text`,
  scripts' `--set`, records' snapshots with their digests and sets, points' provenance sets, plot documents'
  `[source]`, folders' report.toml; never `modules/`). Beyond the plan: a report title's `{project}`/`{run}` →
  `{assignment}`/`{errand}` (E2); provenance's `sets` rewritten too (what `heimdall reproduce` reruns); the
  fixture migrated by `errand_changes` alone, so I-91's held `hep run` comments stay; heimdall.toml's and
  machine.toml's `[run] keep`/`log` kept (the command's settings, not the errand file); `tests/reference/v2_configs/`
  read through `errand_text` by the tests that compare against it. Fast suite: the one known failure; slow: the
  five known. Next: E2 (V226).
- 2026-11-01: E2 built (V226): `[source]` names `errand` and `assignment`, written by every writer of a document and
  read by both loaders; an old document refused with the hint (`plotdoc.refuse_old_source`), its keys renamed by
  the migration's `source_text`. A report title's `{project}`/`{run}` are `{assignment}`/`{errand}` (they are filled
  from `[source]`), the old ones refused by `config.check_report`. `Doc.project`/`Doc.name` and `RunConfig.project`
  keep their names for E3. Fast suite: the one known failure. Next: E3 (V227), the code identifiers (D2).
