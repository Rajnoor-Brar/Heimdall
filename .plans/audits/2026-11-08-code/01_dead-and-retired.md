# Dead and retired code

Code nothing reaches, and code kept only to refuse, translate or rewrite an old form. The first is deleted on proof. The second is a policy question: how long a retired form keeps a guard. Heimdall has no releases (no version, and the only tags are snapshots), so every "for a release" guard has no end date.

Severity: **Required** (a hard-rule break or a trap for the next change) · **Consider** (worth doing) · **Nit**. Verdict: **CONFIRMED** (read in the code, the check run) · **PLAUSIBLE** (reasoned, not yet proven).

## Findings

### R-1 `cli.others_of` is unreferenced · Consider · CONFIRMED · closed 2.1
`framework/runner/cli.py:543`: "another configuration's plans, for a compare figure (V83)". Nothing in framework or tests calls it (`grep -rn others_of framework tests`: the definition only). Compare figures now read another plot document (`plotdoc.py:85`, V165), so this is what the plan-based compare path left behind.
**Move:** delete it in its own commit. **Closes when:** gone, and the fast suite is green.

### R-2 Unused module constants · Nit · CONFIRMED · closed 2.2
Each is defined and never read: `plot.OUTSIDE` (`plot.py:55`), `plotdoc.CHOSEN` (`plotdoc.py:43`), `plotdoc.ATTRIBUTES` (`plotdoc.py:705`), `setup.REFRESHED` (`setup.py:373`), `typeset.BAR_TRACK` (`plot/figures/typeset.py:34`), `layout.TILED` (`plot/figures/layout.py:23`). Some may be documentation, a list a comment wants written down. Then that comment should cite the code that really holds the list.
**Move:** delete, or make the reader use it (if `plotdoc.ATTRIBUTES` is the list `load_across` adds, `load_across` should iterate it). **Closes when:** `sweeps/defs.py` lists none of them.

### R-3 `house.point_state` is read only by tests · Consider · CONFIRMED · closed 2.3
`house.py:1047`, used by `tests/runner/test_lifecycle.py:63,78` alone. `status` computes states its own way. Either the tests hold a second, unused definition of a point's state, or `status` should call it.
**Move:** make `house.status` use `point_state`, or move the test to what `status` prints. **Closes when:** one definition of a point's state, used by the command.

### R-4 Retired commands kept as stubs, with no end · Consider · CONFIRMED
`heimdall stats` (`cli.py:122`, `cmd_stats_retired` `:1950`, "retired for a release") and `heimdall deck` (`cli.py:147`, `cmd_deck` `:1780`, V212). Each is a parser entry, a function and a help line in `heimdall --help`, and each only raises. With no releases, "for a release" never ends.
**Move:** give each retirement a date and a removal rule (say 30 days or the next tag). Better, put them in I-26's one table, so the parser has no stub commands and an unknown command looks the table up. **Closes when:** `heimdall --help` lists no command whose only action is to refuse.

### R-5 Retired names refused in seven places · Required · CONFIRMED
One concern, seven mechanisms:

| Where | Refuses |
|---|---|
| `paths.RETIRED`, `check_retired()` (`paths.py:53–66`, called at `cli.py:3421`) | `HEKIT_*` and `HEP_*` environment variables |
| `config.RETIRED_BACKENDS` (`config.py:1571`) | `backend = "yoda"`, `"both"` |
| `tools.EXPORT` (`tools.py:60`), `tools.py:713` | `<tool>_<export> = true` keys |
| `tools.py:308` | the `{repo}` placeholder |
| `config.py:585` | `[run]` (now `[errand]`) |
| `v3.V2_TABLES`, `v3.refuse_old_names` (`v3.py`) | v2 tables in a v3 file |
| `cli.cmd_stats_retired`, `cli.cmd_deck` | two commands |

Each has its own message shape and none has a date. This is I-26, blocked on I-25 (which is blocked on I-21). The table is cheap even before the deletions it should eventually drive.
**Move:** `runner/retired.py`, `{old: (new, since, kind)}`, read by every site above. **Closes when:** each site is a lookup, and the table names a date for each row.

### R-6 `plotmerge` is live, yet I-25 lists it for deletion · Consider · CONFIRMED · closed 0.5
`framework/tools/plotmerge/tool.toml` (`App_yd2rt --merge`, every point's histograms in one ROOT or YODA file) is used and tested (`tests/integration/test_post.py:194–203`). I-25 says to delete `framework/tools/plotmerge/`. It is not a statistical merge, and it is the only way to get a sweep as one file. The issue is wrong, or out of date.
**Move:** correct I-25, keeping plotmerge, and fold it into [D-2](02_duplication.md#d-2)'s naming. **Closes when:** I-25 and the tool agree.

### R-7 The v2 → v3 translator is the live path, and v3 is the minority form · Required · CONFIRMED
See [D-1](02_duplication.md#d-1). Every fixture config in `tests/fixtures/work/configs/` is v2: none has `[file]`, `[cfgs]` or `errand.chain` (`grep -rL '^\[file\]'` lists all 11). `v3.py` is 421 lines, and `migrate.v3_text` (`migrate.py:627`, 145 lines, 89 branches) writes v3. `docs.legacy_page` (`docs.py:224`) generates `reference/legacy.md` for the names. So the "retired" dialect is the one the tests prove.

### R-8 `migrate.py` holds about ten one-shot migrations, with no record of whether any are still needed · Consider · PLAUSIBLE
`migrate.py` (1554 lines) holds rewrites for the `[run]` names (`cfgs_text`), placeholders (`placeholder_text`, `{repo}`), `[config]` keys (`config_text`), backends (`backend_text`), figures (`figure_text`), cards and exports (`card_text`, `exports_text`), `formerly`, v3 (`v3_text`), the layout, logs and sets moves, record formats (`upgrade_file`), the `hep.toml` marker and names (`names_changes`), plus `adopt_points` (not a migration: [S-3](03_structure.md#s-3)). Nothing records which work dir still needs which. I-25 says to delete them after dry runs.
**Move:** run every migration's dry run on both real work dirs (read only), and record per migration "needed by none" with the date. Delete those that no work dir needs, keeping `records upgrade` and `adopt`. **Closes when:** each surviving migration names a work dir or a form still in use.

### R-9 `statstable.py` and `plot.py` re-export for callers that could import the owner · Nit · CONFIRMED · closed 2.4 (statstable's re-export kept: the import rule's door)
`runner/statstable.py:1,13` re-exports `stats.table`. `plot.py:42,46` re-exports `labels` and `statstable` names ("noqa: F401 (re-exported)"). Re-exports hide a module's real owner, and they survive moves that should have updated their callers.
**Move:** point the callers at `stats.table` and `labels`, then delete `statstable.py`. **Closes when:** no `re-exported` noqa in framework.

## Sweeps still to run

- **Private helpers used once.** `_name` functions called from one site that only rename a call: inline the pass-throughs (the deletion test).
- **Branches no caller reaches.** Keyword arguments that no call site passes, and `if` arms on values no caller produces, starting with `run_one`, `_cmd_run` and `plot._pages`.
- **Tool folders.** Each of `framework/tools/*/tool.toml` against a fixture or test that runs it. `status = "standard"` against `"none"`.
- **Shell.** Functions in `gjallarhorn.sh` and `env/` against their callers. I-25 names `quit`, `heimdall_status`, `heimdall_stash`, `heimdall_forge`, `heimdall_stack`.
- **`src/`.** C++ functions and flags of Paint, `App_Pythia` and `App_yd2rt` against the Python that passes them.
- **Methods.** `sweeps/defs.py` counts methods by name, and names like `run` and `load` match anything. Re-run it per class, with receivers.
