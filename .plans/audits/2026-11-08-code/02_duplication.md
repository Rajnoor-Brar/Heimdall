# Duplication: one job, several mechanisms

Two mechanisms for one job cost every later change twice, and they drift. This file lists the parallel paths, and for each it says which should be the model and what becomes of the rest.

## Findings

### D-1 Two errand-file dialects, the new one translated into the old · Required · CONFIRMED
- `v3.py:1–25`: "A v3 file is translated, table by table, into the v2 tables the loader has always read." The loader, `schema/run.toml` (1523 lines), every check and every message work in v2 names. A v3 file is renamed in (`v3.translate`), and its errors are renamed back out (`v3.v2_path`, `config.py:690`; `own_names`, `config.py:951,978`).
- The names are written four times: `schema/v3.toml`, `v3.py`'s tables, `migrate.v3_text` and `docs.legacy_page`. Plus two editor schemas, `run.schema.json` and `run.v3.schema.json`.
- The form is sniffed, not declared ([G-2](04_design.md#g-2)).
- Every fixture is v2 ([R-7](01_dead-and-retired.md#r-7)).

The developer decided on 2026-10-25 to drop v2 (I-20, then I-21, which makes v3 the model). Neither is built, and four more blocked issues wait on them (I-25, I-26, I-35, I-70).
**Move:** I-21's order, with one change: migrate the fixtures first (`heimdall migrate --v3`, the fixture changing together with the test, by the invariant), since a v3-only loader cannot be tested on v2 fixtures. Then the model in v3 names, with `identity_parts` mapping to the frozen v2 keys (the golden identity file, `tests/golden/`, proves nothing reruns). Then delete `v3.py`, the v2 branches and `run.schema.json`.
**Closes when:** one schema, one name for each key, the golden identities unchanged, and `v3.py` gone.

### D-2 Merging points, five ways · Required · CONFIRMED
| Mechanism | Where | Does | Recorded? |
|---|---|---|---|
| `combine` | `post.plan_combined`, `tools.combiner()` (`tools.py:344`), rivet-merge `-e` | statistical merge of replicas, as a configuration's group | yes, a point |
| `merge` post tool | `framework/tools/merge/tool.toml` | rivet-merge of every point's product | yes, a post product |
| `plotmerge` post tool | `framework/tools/plotmerge/tool.toml`, `App_yd2rt --merge` | every point in one file, each kept apart | yes, a post product |
| `merged` figure | `plot.merged_curves`, `plot._merged` (`plot.py:690,789`), `tools.merge_files` (`:353`) | a figure of merged curves at drawing time | no |
| set `merge` and `band` | `stats/merge.py`, `plot._banded` (`plot.py:1524`), `live/set-merge.md` | a bin-wise mean (`how`) or an envelope, per set | no |

`combine` and the `merge` tool both run rivet-merge, at two stages. The `merged` figure and a set's `merge` with `how = "combine"` both merge at drawing time. A user who wants "these seeds as one curve" has four routes and no guide to choose between them.
**Move:** decide the model. Proposal: a set's `merge` is the one drawing-time merge, and the `merged` figure becomes a set (I-41 already retires `plot_points` for sets). `combine` stays as the recorded merge. The `merge` post tool is kept only if a use exists that `combine` does not cover: ask. `plotmerge` stays, renamed for what it does (`bundle`), since it does not merge. **Closes when:** a decision note names one mechanism per job, and the rest are front ends or gone.

### D-3 `heimdall log` and `heimdall show --log` · Consider · CONFIRMED
`cli.py:280–295`: both take `RECORD[/POINT[/TAG]]`, `--full` and `--attempt N`, and `show --log` is "the logs, as heimdall log prints them". The plan (I-72, `live/show.md`) kept `log` as a shorthand. Two parsers with the same three options will drift: a fourth option added to one is missing from the other.
**Move:** make `log` an alias that the parser maps to `show --log` (one parser, one set of options). **Closes when:** `log`'s options are defined once.

### D-4 HTML pages written five ways · Consider · CONFIRMED
`plot.write_index` (`plot.py:1620`), `plot.write_sets_index` (`:1871`), `report._index` (`report.py:2227`), `figures/webpage.py:245`, `viewer.py:157`, plus `knowledge_site.html`. Each writes its own `<!DOCTYPE html>`, head and escaping. This is I-44 ("One HTML index writer").
**Move:** one `html` helper (page shell, escape, a table, an image grid), used by all of them. **Closes when:** one `<!DOCTYPE` in framework Python.

### D-5 A point's state, computed twice · Consider · CONFIRMED
See [R-3](01_dead-and-retired.md#r-3). `house.point_state` (tests only) and `house.status`. A third view is `record.state_of` (`record.py:551`). Three answers to "is this point done?".
**Move:** one function in `record`, which `status`, `show` and `--plan` call. **Closes when:** `grep "def .*state" framework/runner/{house,record}.py` finds one point-state function.

### D-6 Run state: the registry's and the listing's · Consider · CONFIRMED
`runs.state()` builds a sentence. `house.state_word()` (`house.py:614`) cuts it back to a word, and `house.RUN_STATES`, `runs.VERDICTS` and the colours each list states again. See [G-1](04_design.md#g-1).

### D-7 Waiting loops with their own sleeps · Nit · CONFIRMED
`cli.py:1067,1101,1124,1194,1336`, `execute.py:534`, `record.py:650`, `watch.py:249,696,772`: ten polling loops, each with its own interval, and some with their own deadline. Several wait for the same thing: an entry to appear, a process to end.
**Move:** `runs.wait_for(predicate, every, deadline)`, used where the loops wait on the registry. **Closes when:** the registry waits are one helper.

### D-8 Library code across three modules · Required · CONFIRMED
See [S-3](03_structure.md#s-3).

## Sweeps still to run

- **Near-identical functions.** An AST normalisation (names stripped) over framework to find bodies that are copies. Start with the `_*_lines` helpers of `house.py` and the `_*_section` builders of `report.py`.
- **Flags that mean the same.** `--plain`, `--journal`, `--logs`, `--keep`, `--stages` and `--only` across commands (I-70).
- **Option lists repeated in help text and in code.** A help string that lists choices the code also lists.
- **Paint and mpl.** Statistics computed in C++ (`Transform.hh`) and in `stats/`: which numbers both compute, and whether both are needed now that `stats/` reads the measured bins.
