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
- **D3 Dropped** (the user, 2026-11-01: "Let heimdall run and runs be, since they executes/list runs of an errand"):
  `heimdall run` executes an errand's Runs and `heimdall runs` lists them; the registry, `runs.py` and
  `HEIMDALL_RUNS` keep their names. An invocation is still called a job where prose needs the word.
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
| E5 | dropped (D3) | — | — |
| E6 | Brookhaven and High-Energy migrated (`--apply`), left uncommitted for the user; main fast-forwarded | — | only when no job is live |

Each phase: built, its tests run light, committed by named paths with its V-row; this file's map and log written
at each commit. The runs-together, report and tag code of I-108–I-113 is renamed with the rest.

## 5. Execution map

| Phase | V-row | Commit | State |
|---|---|---|---|
| E0 this plan, the inventory | — | | written |
| E1 the dialect: `[errand]`, `[errand].assignment`, dotted names, the schema, v3, the walkers, `[run]` refused; the migration (`heimdall migrate --names`: configs, snapshots, provenance, documents), the fixture's configs and the starter by it; docs 00–06's examples | V225 | 8293eeb | done |
| E2 plot documents: `[source].assignment`, `[source].errand`, read and written; a report title's `{assignment}`, `{errand}`; the old ones refused | V226 | 9e9658f | done |
| E3 the code identifiers (D2): `Errand`, `.assignment` (Errand, Doc, RunFolders, Source), `errand` for every local, parameter and attribute holding one, `assignment` for an assignment's name, by scope; `Doc.name` kept | V227 | 32eee41 | done |
| E4 the words: docs 00–06, README, docs/framework/, help, messages, hints, schema notes, the template, tool folders' docs; `--project` → `--assignment` (the old flag refused, naming it), `heimdall cd ASSIGNMENT`, the template's `{{A}}`/`{{a}}` | V228 | ccd1fdf | done |

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
- 2026-11-01: E3 built (V227). `RunConfig` → `Errand`, `.project` → `.assignment` on it, `RunFolders`, `Doc`,
  `report.Source`; `Planned.run`, `Compared.run` and every local/parameter holding an errand → `errand` (a scope-aware
  AST rename, about 1400 sites in 42 files; `run` left where it is a job, a bus key, a Run's folder or a function);
  `project` → `assignment` where it holds an assignment's name (`paths.resolve(assignment=)`, `across_path(assignment,
  errand)`, …). Beyond the plan: **`Doc.name` kept**, not `Doc.errand`: plot.py takes an `Errand` or a `Doc` alike and
  reads `.name` of either (`_curve_label`, the titles), and `Errand.name` stays (D2); the `[errand]` table's dict is
  `errand` too (`config.parse`, `_marks`, `_layers`, migrate); `_project_of` → `_assignment_of`, `run_style` →
  `errand_style`, `_run_of` → `_errand_of`, `report._run_sources` → `_errand_sources`. Left for E4: the CLI's
  `--project`, `ls [project]` and `setup.setup(project=)` (the flag's name), prose and messages ("run TOML",
  `<P>/<run>`); a record's `points.json`/`provenance.json` keys `run`, `project` (data, not code). The fixture was
  already rewritten in E1. Fast suite: the one known failure; slow: the five known. Next: E4 (V228).
- 2026-11-01: E4 built (V228), by a workflow agent stopped by a usage limit partway and finished by hand: the
  vocabulary in docs 00–06, docs/README.md, docs/framework/, CLI help, messages and hints, schema notes, the work dir
  template (README, CLAUDE.md, heimdall.toml, the starter), tool folders' docs; `heimdall setup --assignment A`
  (`--project` refused with the new form), `heimdall cd ASSIGNMENT`, the template's `{{A}}`, `{{a}}`; the last
  `<run>/<cfg>` placeholders `<E>/<R>`. Kept: the migration's own rules and refusals, `points.json`'s and
  `provenance.json`'s `run`/`project` keys (data), heimdall.toml's `[run]` (the command's settings), D3's names.
  **Pause** (the plan's): before E5 (D3, the user's yes) and E6 (the work dirs, when no job is live).
- 2026-11-01: D3 dropped by the user (`heimdall run`/`runs` stay: they execute and list an errand's Runs); E5 with it.
- 2026-11-01: the read-only review of E1–E4: the four phases right, Brookhaven's configs, snapshots and documents
  rewritten right in memory; nine edge-case defects of the migration fixed (V229, with the user's "bare names
  beside the file" change). E6 waits for the last Brookhaven job (pid 308787, 55/56, the user: let it finish).
- 2026-11-01: E6. Main fast-forwarded to `context` (3a46bb6; Copilot's uncommitted files equal to c45b6d0 dropped first), the live Paint rebuilt. `heimdall migrate --names --apply` in Brookhaven (149 files: configs, record snapshots, provenance sets, plot documents) and High-Energy (2), left uncommitted; backups (each work dir's diff before, a tarball of every file it rewrote) in `~/Himinbjorg/forge/backups/names-2026-11-01/`. `heimdall check` after: Brookhaven's `legacy/` files say `assignment = "PhotoProduction"` in `configs/legacy/` (as `project` did before), and `eic/zeus` has a `[cfgs.dis_generator_pdf.data.map]` without its file (the user's edit of that morning): both as they were. I-112 closed.
