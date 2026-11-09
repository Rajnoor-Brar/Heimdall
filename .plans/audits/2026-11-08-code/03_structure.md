# Structure: modules and boundaries

Hard rule: one reason to change per file. Size alone proves nothing, but past about 300 lines a module must say what its one responsibility is. Heimdall's runner is one flat package of 39 modules with declared ranks (`runner/__init__.py` `RANKS`, held by `test_imports.py`). The ranks work. The trouble is inside a few modules that have become a home for whatever had no other.

## Findings

### S-1 `cli.py`: 3553 lines, 117 definitions, about eight jobs · Required · CONFIRMED
It holds:
- the parser (`parser()`, a 400-line function);
- planning (`build_plans`, `Planned`, overwrites);
- run orchestration (`run_one`, 197 lines and 110 branches; `_cmd_run`; `_runs`; signals and control);
- the detached worker and the queue (`background`, `queue_run`, `queue_sweep`, `wait_turn`, `follow_worker`);
- the `runs` actions (`act_on`, `dispatch_run`, `forget_run`, `again_run`, `set_jobs`, `resume_snapshot`);
- the commands `plot`, `report`, `score`, `diff`, `log`, `show` and `tag`;
- the migrate commands (`migrate_names`, `migrate_plot_docs`, `migrate_snapshot`, `migrate_layout`);
- the `[heimdall]` flag merging (`heimdall_flags`, `config_flags`);
- the stack, image and shell verbs.

The stable rank table calls it "argparse … the order of events". 45 relative imports.
**Move:** I-50 (subpackages, decided). Concretely: `runner/cli/` with `parser.py`, `run.py` (planning and `run_one`), `worker.py` (detach, queue, follow), `runs_cmd.py`, `records_cmd.py` (log, show, tag, diff, library) and `migrate_cmd.py`. `main()` dispatches by a table. Tests patch `cli.<name>` in 14 places, so do the move by re-pointing the patches, not with re-exports ([R-9](01_dead-and-retired.md#r-9)).
**Closes when:** no module of the CLI is over about 800 lines, and each has a one-line "owns" that is true.

### S-2 `house.py`: "ls, explain, status, clean", plus eight more · Required · CONFIRMED
Its 58 definitions hold `ls`, `explain` (`_special`, 72 lines), the run listing (`runs_listing`, 129 lines; `live_line`, colours, OSC 8 links), `log_target`, `tag_lines`, `show_data` and `show_lines`, `status`, `clean_targets`, and `library_list`, `library_verify` and `library_prune`. Its rank-table row (`docs/stable/internals/runner.md`) names four of them.
**Move:** split by subject: `listing.py` (runs), `show.py` (log, show, tag), `library.py` ([S-3](#s-3)), and `house.py` keeps ls, explain, status and clean. **Closes when:** the rank table's row is true of each file.

### S-3 The points library is spread over three modules · Required · CONFIRMED · closed 3.1
- Key, entry, links and index in `record.py:101–296` (`library_parts`, `library_key`, `link_library`, `unlink_run`, `index_append`, `library_entries` and more).
- List, verify and prune in `house.py:1192–1313`.
- Adopt in `migrate.py:1474` (`adopt_points`, `DUPLICATE`).
- Seeds in `record._library_seed` (`:455`).

I-25 plans to delete `migrate.py` whole, which would take `adopt` with it.
**Move:** `runner/library.py` (rank 3, beside `record`) owns all of it. `record` keeps the identity and calls `library.key`. **Closes when:** `grep -n "def library_\|adopt_points" framework/runner` finds one file.

### S-4 `record.py`: nine subjects · Consider · CONFIRMED
75 definitions: identity, seeds, the library ([S-3](#s-3)), attempts, locks (`PointLock`), provenance and git state, the complete marker and staleness, the points manifest and constants, snapshots, and labels and tags. Identity and seeds are ask-first territory, and they share a file with label writing. So a change to `tag` touches the file whose every edit should make a reviewer careful.
**Move:** keep `identity.py` (identity, seeds, `why`) small and frozen. Move locks, attempts, the manifest and labels to their own modules. **Closes when:** a diff to labels or the manifest does not touch the file that hashes identities.

### S-5 `config.parse`: 261 lines, 112 branches · Required · CONFIRMED
`config.py:1053`. It builds tools, quantities and configurations, inheritance, the v3 private keys, and the checks. Much of its branching is the two dialects ([D-1](02_duplication.md#d-1)).
**Move:** after D-1, split it into `parse_tools`, `parse_quantities` and `parse_configurations`, each with a test seam. **Closes when:** no function in `config.py` is over about 80 lines.

### S-6 `report.py`: 2443 lines, sources to LaTeX · Consider · CONFIRMED
119 definitions in one file: sources and addresses, recipes (load, write, default), the plan of sections, layout (`_Build`, `Placed`), the drawings, tables and bars, prose, and two typesetters (`_tex`, `_highlight_html`). It changes for at least four reasons: a source form, a recipe key, a layout rule, a typesetting fix.
**Move:** `runner/report/` with `sources.py`, `recipe.py`, `plan.py`, `layout.py` and `tex.py`. **Closes when:** each part is under about 600 lines.

### S-7 The longest functions · Consider · CONFIRMED
By AST, as lines / branch nodes:

| Function | Lines | Branches |
|---|---|---|
| `cli.parser` | 400 | 2 (declarative: fine) |
| `plot._pages` (`plot.py:813`) | 272 | 150 |
| `config.parse` | 261 | 112 |
| `cli.run_one` (`cli.py:1537`) | 197 | 110 |
| `migrate.v3_text` | 145 | 89 |
| `plotdoc.load_across` (`plotdoc.py:799`) | 143 | 112 |
| `cli.main` | 141 | 68 |
| `tools._render` | 135 | 59 |
| `sweep.set_cells` | 131 | 80 |
| `execute.run_group` | 130 | 55 |
| `house.runs_listing` | 129 | 78 |

`plot._pages` and `plotdoc.load_across` are the riskiest: the most branches per line, and the code every drawing passes through. A junior engineer cannot follow either one without help (hard rule 2).
**Move:** for `_pages`, name its stages (cells, objects, overrides, looks, page documents) as functions, each with its own test. **Closes when:** none of the plot path's functions is over about 100 lines or 50 branches.

### S-8 `runner/` as one flat package of 39 modules · Consider · CONFIRMED
I-50 decided subpackages. With S-1, S-2, S-3 and S-6, the natural groups are already visible: `model/` (config, schema, sweep, quantities), `run/` (tools, execute, record, library, post, cluster), `live/` (runs, events, watch), `plot/` (plot, plotdoc, labels), `report/`, `cli/`, `machine/` (bifrost, setup, doctor, image, shellrc, workdirs). The ranks become package ranks.
**Closes when:** I-50's done-when holds.

## Sweeps still to run

- **The import graph.** Fan-in and fan-out per module. Which modules import half the package (`cli`, `house`), and which lower-rank modules import from a sibling only for one constant.
- **Cohesion of `tools.py` (1767 lines) and `plot.py` (2163 lines).** The same reading as S-1: list each one's responsibilities.
- **`plot/figures/`.** `bars.py` (830 lines) after the stats move: is it only drawing now (I-120's done-when)?
- **The stable rank table against the code.** S-1, S-2 and S-3 already show `docs/stable/internals/runner.md` lagging. Run `heimdall docs --drift` and record each row that is false.
