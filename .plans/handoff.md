# Handoff, 2026-11-01: the state, and the context for the next three pieces of work

Written before three pieces of work begin: **the scoring system reworked**, **the docs overhauled with a documenting
convention**, and **a points library** (a pooled collection of points per Assignment that any Errand and Run can use
when the configuration matches). §1 is where things stand, §2 the rules that bind, §3–§5 the context each piece
needs: what exists, where it lives, what it touches, and the questions to settle first. Nothing in §3–§5 is
decided; it is the map, read from the code at `46aafb7`.

## 1. Where things stand

**Heimdall.** `main` = `46aafb7`, **not pushed** (origin/main is far behind). The working tree is clean but for
`.codex/` (untracked, not ours: leave it). Branches kept: `context` (= `3a46bb6`, merged), `copilot` (`c45b6d0`,
Copilot's four changes, merged), `look`, `names`, `report` (older, merged). No worktrees. Latest V-row: **V234**.

**Done this cycle** (each a V-row in [docs/07_Record.md](../docs/07_Record.md) and its own commit):

| Issue | What | V |
|---|---|---|
| I-111 | a report's context first (what was run, how the numbers are made) | V218 |
| I-114 | Copilot's changes reviewed (33 findings) and fixed: axis ranges, overflow marks, the runs listing, the watch keys | V219–V222 |
| I-113 | Run tags (`--tag`, the `tag` key, `heimdall tag`), `@tag` across Runs, `[from].ignore` | V223–V224 |
| I-112 | `<Assignment>/<Errand>/<Run>`: `[errand]`, `[errand].assignment`, `[source].assignment`/`errand`, the code, the words; `heimdall migrate --names` | V225–V228 |
| — | bare names (cards, imports, master, filters, styles) are found beside the file naming them | V229 |
| I-115 | `p` pauses a run (twice: force), live runs indexed, `watch -i N`, `runs --resume N`, `--forget N`; the review's 8 defects | V230–V232 |
| — | a range only cuts what is drawn: Paint draws bars and bands reaching into the frame | V233 |
| I-09 | a combined run's plot stage and a listed row's curve order no longer crash (two "known" slow failures were bugs) | V234 |

**Work dirs** (the user's; Heimdall never commits there):
- **Brookhaven** and **High-Energy** were migrated by `heimdall migrate --names --apply` (149 and 2 files):
  **uncommitted**, on top of the user's own uncommitted edits. Before the migration each work dir's `git diff` and
  a tarball of every file it rewrote were saved in `~/Himinbjorg/forge/backups/names-2026-11-01/`. That folder
  also holds the Paint binary from before the rebuild, and the untracked `Copilot_Changes.md` that the merge
  displaced.
- `heimdall check` in Brookhaven fails on two things the migration did not cause:
  - `configs/legacy/*` say `assignment = "PhotoProduction"` but sit in `configs/legacy/` (they said `project` before);
  - `eic/zeus.toml` has `[cfgs.dis_generator_pdf.data.map]` without its table (the user's edit of 2026-11-01).
- The ZEUS `y_range`s in `eic/zeus.toml` are the user's own; checked against the ZEUS 2012 reference, nothing is cut.

**The machine root** `~/Himinbjorg`: Paint rebuilt from main (plot-only, safe). No job live, none paused.

**Tests** (run light: `taskset -c 0-5 nice -n 10 python3 -m pytest -q -p no:cacheprovider`, one session at a time):
- **Fast** (`-m "not slow"`): 1248 passed and 1 known failure, `test_stack_build::test_the_old_way_is_apt_and_a_venv`. About 7 minutes.
- **Slow** (`-m slow`, alone): 46 passed and 3 known failures, `test_gates_p1` ×2 (one YODA digit on the conda
  base, I-79: the user's decision) and `test_plot_stage::…pixel_for_pixel[yoda]` (the yoda backend, D4: to be
  deleted). About 13 minutes.

**Pitfalls met this cycle:**
- A reboot empties `/tmp`, and with it the session scratchpad and any worktree in it (branches survive).
- `bash -c '…'` is refused by a safety check: write a script file and run it.
- Python scratch scripts: `python3 -I` drops `PYTHONPATH`, so use `python3 -P` when the script needs `yoda` or `ROOT`.
- A file named like a stdlib module beside a script shadows it.
- Paint's tests run the Paint in `$HEIMDALL_APPS`: after changing `src/Apps/Paint/`, rebuild it (`heimdall make
  --framework src/Apps/Paint.exe`). That is safe. Rebuilding any other app is not (§2).

## 2. Rules that bind (from CLAUDE.md, memory and the user's word)

- **Plans first:** pending work is one issue in [ISSUES.md](ISSUES.md); a plan goes in `.plans/` before the code, written
  as it grows and linked from its issue; build only on an explicit order. Phased plans: an execution map, then each
  phase built, tested, committed with its V-row; pause only at the milestones the plan marks.
- **Git:**
  - Stage named paths, never `commit -a`.
  - Never push, never `git clean -x`.
  - A finished issue is deleted from ISSUES; its history is its V-row and commit.
- **Ask first:**
  - Downloads: name the file, source and size.
  - Rebuilding App_Pythia, App_yd2rt, a module or a Rivet plugin: it changes point identities.
  - Writing into a work dir (Brookhaven, High-Energy).
  - The machine root's `machine.toml`, `recipes.toml`, `toolkits/` and `tools/` are never rewritten.
- **Tests:**
  - Tests write only `forge/scratch`, and never name a real work dir.
  - The fixtures change only with the test that needs it, and `tests/reference/` is never regenerated.
  - On a failure, report it and restore nothing.
  - A fake has the real type.
- **Code:**
  - `framework/runner/` is one flat package by ranks (06 §2.1, enforced by `test_imports.py`).
  - The core never names a tool.
  - Every text read and write names `encoding="utf-8"`.
- **Docs:**
  - After a schema `doc`/`notes`, base.toml comment or CLI help change, run `heimdall make --framework docs schema`.
  - The user pages 00–05 cite no record ids (V/L/F…).
  - No real study's name in Heimdall's docs or history: say "a real study's work dir".
- **Audits:** the code decides, not the `.md` files (they lag). Be bold, and say plainly when a past V-row is reopened.

## 3. The scoring system (to be reworked)

**The pipeline today**, one Run's (or a runs-together `--across` set's) pages at a time:

1. **Paint measures** each page as drawn (after voiding, alignment and normalisation), over the x span before
   `x_range`/`y_range`: `src/Apps/Paint/main.cc` `statisticsJson` (~line 200) writes `<page>.toml.stats.json`. The
   curve arithmetic is in `src/Apps/Paint/Transform.hh` (area, χ², rebinning onto the reference's bins). The
   reference is the data when there are any, else the page's first curve.
2. **The table:**
   - `framework/runner/statstable.py` reads it (`statistics_of`) into rows of `STATISTIC_COLUMNS`: `page, cell, object,
     curve, point, reference, is_reference, bins, area, area_err, ref_area, cmp_area, abs_area, rel_abs_area,
     area_ratio, ratio_mean, ratio_dev, chi2, ndf, chi2_ndf`.
   - It writes `results/…/statistics/<set>/statistics.csv` (`write_statistics`, `write_set`) and reads it back (`read`).
   - The callers: `plot._tables` (plot.py ~1782), `plot.measure` (~1831, `heimdall stats`), `report.py`.
3. **Scoring and presentation:** `framework/plot/figures/bars.py` (875 lines) does both.
   - **Per page:** a bar image per page (`page`, `PANELS`).
   - **Per statistic:**
     - tables, a row per point and a column per object, shaded (`_tables`, `TABLES`, `RULES`);
     - rankings by mean (`_ranking`, `_means`), arithmetic, but **geometric** for the ratios;
     - cells against curves (`_crossed`).
   - **The standings (V176):**
     - `_page_rankings` places each page's curves in each of `SCORED = (chi2_ndf, rel_abs_area, area_ratio,
       ratio_mean, ratio_dev)`, by `_distance` (the number itself; the two ratios by |log10 r|);
     - `POINTS = (5, 4, 3, 2, 1)` per place, ties share the better place;
     - only pages against data are counted when any has data;
     - points of different page cells never meet.
   - **Head to head (V177):** `_head_to_head`, `_rates` (each pair of curves on a page is a match).
   - **Prose:** `DEFINITIONS`, `FORMULAS`, `NOTES`, `SCORE_TEXT` and `H2H_TEXT` are the prose that the summary *and* the
     report print (I-111 put the definitions first in reports).
   - **Composition:** `summary_model`/`summary_of` → `summary.pdf`/`.html` (via `paper.py`, `typeset.py`, `webpage.py`).
4. **Reports** (`framework/runner/report.py`, 2408 lines) re-render the chosen summary sections from
   `statistics.csv` (`stats = ["top5", "scoreboard", "scoreboard-cells", "head-to-head", "scoreboards", "chi2_ndf",
   …]`).

**Where it is documented:**
- 03 §3.2 "Statistics of the pages".
- 04's `[plot].statistics`, `[plot].legend_statistic` and `[stats]` keys (generated from `framework/schema/run.toml`).
- `.plans/statistics_a4_plan.md` (V196–V199, the summary's A4 layout).
- `.plans/report_context.md` (I-111).
- The rows: V160, V162, V164, V168, V175–V177, V196–V199, V205, V218, V219 (ranges only show), V233.

**Tests:** `tests/runner/test_statstable.py` (the table and much of bars.py's scoring), `test_summary_layout.py`,
`test_report.py`, `test_report_build.py`, and the slow `test_plot_stage.py`.

**What a rework will have to settle:**
- Scoring and drawing are in one 875-line module, and the rank table of 06 §2.1 puts it under `plot/figures/`. A
  scoring module of its own (pure: rows in, scores out), with bars.py only drawing, is the obvious seam.
- What a score is per page: competition places with fixed points, versus a continuous measure (a normalised
  distance, a likelihood, a p-value from χ²/ndf). Then how pages are pooled (sum, mean, weighting by bins or
  uncertainty), and how ties and missing statistics count.
- Whether the five statistics are independent enough to sum: `rel_abs_area` and `ratio_dev` move together; `area_ratio` and `ratio_mean` too.
- The reference rule (data, else the first curve, which then cannot be ranked; `[stats].reference` and the other
  `[stats]` keys, `framework/schema/run.toml` ~1018, measure with settings of their own) and pages without data.
- Scoring across Runs: `--across` sets get their own `statistics.csv`, but there is no score over several Runs' sets
  or Errands (X2 of the report audit dropped it then).
- `statistics.csv` is a public file (the report reads it, users read it). A column change wants a format version (I-28).

## 4. The docs overhaul and a documenting convention

**The manual today** (8,321 lines):

| Page | Lines | Role |
|---|---|---|
| 00_Quick | 106 | one page: commands, a whole errand file, where things go |
| 01_Overview | 265 | the model, vocabulary, principles, what is refused |
| 02_User_Guide | 1093 | setup, a first run, an errand file, pipelines as recipes, reruns, failures, pausing |
| 03_Plots | 1244 | the plot stage, `[plot]`, data and ratios, style, figure classes, backends, overlay, reports |
| 04_Config_Reference | 1684 | every key (generated from `framework/schema/*.toml`), precedence, placeholders, rules C1–C14 |
| 05_Commands_and_Tools | 1499 | every command (help generated from the CLI), the tools, the apps' command lines |
| 06_Internals | 1748 | layout, ranks, data model, identity and seeds, the plot stage inside, Paint, tests, conventions |
| 07_Record | 682 | the brief, decisions V1–V234, the ledger L, findings F, the glossary |

The index is [docs/README.md](../docs/README.md). Beside the manual:
- `docs/framework/`: the setup runbook;
- `docs/conda/`: the base's design;
- `docs/audit_2`–`audit_4` and `docs/reporter/`: history.

**What is enforced** (`tests/runner/test_docs.py`, the de facto convention today):
- the eight pages and the index exist;
- every relative link resolves;
- every TOML block parses, and complete errand files load;
- every key the loader accepts is documented;
- the generated sections and the editor schema are current;
- every style key, tool folder and tool option is documented;
- every cited section (`04 §9.4`) exists, and every cited id (`V22`, `L18`) is in the record;
- 02's rank table is the runner's;
- the user pages (00–05) need no record to be read.

**Generated:**
- 04's key tables come from the schema's `doc`/`notes` (`framework/runner/docs.py`, `schema.py`).
- 05's command help comes from argparse.
- The style tables come from `src/Apps/Paint/base.toml`.
- Regenerate them all with `heimdall make --framework docs schema`.

**What has drifted, or has no rule yet:**
- **07's V-rows** have grown into paragraphs. A row is one table cell of up to ~3,000 characters (V231, V233), so
  the record is hard to read and diff. The citations in code (`# V158`) point into it.
- **Prose style** is consistent (plain words, `·` separators, "the user, <date>: …" quotes) but written down nowhere.
- **Docstrings and comments cite V-rows freely**, and nothing checks that they are still true.
- **The `.plans/` files** are dated logs and plans with no common shape beyond `00_Plan.md` and execution maps.
- **History is spread**: 07, `docs/audit_*`, `docs/reporter/`, `.plans/commit_history.md`, and High-Energy's history before `split/base`.
- **Some sections lag the code**, which is the user's standing caution (audit from the code).

**For a convention, these questions are open:**
- What a V-row holds: a line plus a link to its plan, versus the full account.
- Where decisions live: 07, the plans, or an ADR per decision.
- Whether code comments may cite rows.
- How the user pages and the developer pages split.
- Which sections are generated.
- What `test_docs` should enforce next: a row length, links from code to the record, no dates in the user pages.

## 5. A points library (pooled points per Assignment)

**What a point is today:**
- **Planned** (`cli.build_plans` → `tools.PointPlan`): a configuration's sweep (`sweep.points`) gives `Point`s
  (index, name from the value tags, `choice`), each rendered into its tools' cards.
- **Identity** (`record.identity`, `identity_parts`, record.py:52–72): sha256 over threads, events, each tool's
  rendered identity parts (its cards, argv, binary hashes and versions), the groups, prelim, the **seed rule** (not
  the seed), and for a post stage its `upstream` (every point's identity).
  - **Not in it:** the Assignment, the Errand, the Run, the serial ("location, never identity", 04 §2), the point's name.
  - So two Errands that render the same cards already make the same identity.
- **Seeds** (`record.assign_seeds`, record.py:188):
  - `identity`: from the generators' identity, `seed_basis`, so the same point gets the same seed anywhere;
  - `random`: drawn, then kept from the point's `provenance.json`;
  - `manual`: given.
  - Blocks are kept disjoint **within one plan only**. A pooled library meets two Runs whose random-seed points
    share an identity but not a seed: which one is "the" point?
- **Where it lives**, per Run (`tools.RunFolders`, tools.py:604; `tools.run_dir` = `<A>/<E>/<NN_label>`):
  - `records/<A>/<E>/<R>/points/<name>/`: `.complete` (holds the identity: complete means "for this identity"),
    `identity.json` (for `--why`), `provenance.json` (seed, events, versions, revision), `attempts`;
  - `records/<A>/<E>/<R>/logs/<name>/`: the working folder (cards, `commands.sh`, `context.toml`, logs), deletable;
  - `records/<A>/<E>/<R>/points.json`: the manifest, and `config/`, the errand file's snapshot (V158);
  - `results/<A>/<E>/<R>/points/<name>/`: the products (YODA, ROOT);
  - `.cache/<A>/plots/<E>/<R>/`: the drawing's working files.
- **Skip-unchanged:** `record.is_complete` / `record.stale(plan, rerun)` (V232); a point is skipped when its own
  folder's `.complete` holds its identity.
- **Locks:** `record.PointLock`, so one session runs a point; `--wait` waits for another (U66).
- **Readers of a point's place:**
  - plot documents (`plotdoc`: a member's `yoda` path, relative to the Run's results);
  - `--across` (`plotdoc.load_across`, `[from].runs`/`@tag`);
  - compare figures over configurations and Errands (V83, V88);
  - `heimdall status`, `log`, `reproduce`, `report`, `migrate`;
  - the cluster's shards and finish jobs.

**Ideas already in ISSUES that meet it:**
- I-95: per-group identity and skip.
- I-96: shared generation for analysis-option sweeps.
- I-102: products that identify themselves, and an index of provenance (SQLite).
- I-11: an identity golden file, held, and the safety net any change to identity needs.
- I-28: record format versions, and `heimdall records upgrade`.

**What a library will have to settle:**
- **The key:** the identity as it is (generation + analysis), or a split. A generation key would let one generator
  run serve several Rivet analyses (I-96); a key per tool group would let a point reuse its generation and redo
  its analysis (I-95).
- **The layout:** a pool such as `records/<A>/points/<identity>/` and `results/<A>/points/<identity>/`, with a Run
  holding references (a manifest naming identities, or links), versus Runs keeping their folders and a pool index
  pointing into them. What `heimdall run` does on a pool hit: link, copy, or only record it in the Run.
- **Seeds and statistics:**
  - `identity` seeds make a pooled point the same events wherever it is asked for;
  - `random` seeds are not reproducible across Runs;
  - two points with one identity are one point, so they are not two samples: what a "more events" request means
    then (merging replicas is `combine`).
- **Invalidation:** a rebuilt app changes binary hashes, and with them every identity: is the old point
  stale, or kept and marked? Today a Run's `.complete` simply stops matching (V158 draws such points "as recorded").
- **Ownership and garbage:** a Run deleted while its points serve others; `heimdall` commands to list, verify and
  prune the pool. The pool spans Errands but stays within one Assignment (as asked).
- **Concurrency:** two jobs wanting one pooled point (`PointLock` is per folder today).
- **Migration** of existing Runs into the pool: Brookhaven's `eic/zeus` Runs share many points across serials and
  event counts. Identity is untouched by the move, so it is a reorganisation, not a rerun.
- **Records keep a format** (I-28) so the readers above can tell a pooled Run from today's.

## 6. Where to look

- The plans of this cycle, in `.plans/`:
  - [run_pause.md](run_pause.md), [errand_names.md](errand_names.md), [run_tags.md](run_tags.md), [copilot_review.md](copilot_review.md);
  - earlier: `report/` (heimdall report), `report_look.md`, `report_context.md`, `statistics_a4_plan.md`,
    `run_logging_*.md`, `restructure_plan.md`, `heimdall_names.md`.
- The pending work and its phases are in [ISSUES.md](ISSUES.md): the 2026-10-25 plan, phases 2–11. Phase 2 (the
  safety net: I-10, I-11, I-12) matters before any change to identity or records.
- The memory folder (`~/.claude/projects/-home-rajnoor-Github-Heimdall/memory/`) holds the running state
  (`heimdall-state.md`) and the working rules.
