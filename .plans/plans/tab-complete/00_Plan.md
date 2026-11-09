# Tab completion for `heimdall`

Issue: I-73. Status: planned 2026-11-08; D1, D2, D4 and D6 decided by the developer 2026-11-09, D3 and D5 stand as proposed. Nothing built: implementation waits on the developer's order.

The ask: `heimdall run <TAB>` offers what is under `configs/`, a command that reads results offers what is under `results/`, and so on for every command.

## Feasible? Yes, cheaply

Checked on 2026-11-08 at `57b62ef`:

- **Bash only.** zsh is never the shell Heimdall runs in. There, `gjallarhorn` opens a bash through `launch.sh` (`stable/setup/environment.md`). Bash's `complete -F` is all that is needed.
- **There is a place for it.** `env/heimdall_env.sh` already defines the `heimdall` shell function (`:177`), and every shell that loads Heimdall sources that file.
  - The file returns early when the environment is loaded already (`:217`). A child shell sources it again for the functions alone. `complete` specs are not inherited either, so the `complete` line goes beside the functions, before that return.
  - `quit` takes the spec out again.
- **Python is fast enough to ask on every TAB:**
  - `heimdall --help` takes 73 ms in all (Python start, `import runner.cli`, building the parser).
  - Loading one errand file with `config.load` takes about 10 ms: all 11 fixture errands load in 97 ms.
  - Bash completion feels instant under about 150 ms, so the program itself can answer. No cache and no generated script are needed.
- **The parser already knows every command, option and `choices`** (`cli.parser()`, `:41`). A completer that walks it can never fall out of step with the commands.
- **Every path kind has a reader already:**
  - `house.config_names` gives `configs/<A>/<E>`.
  - `config.load(name).configurations` gives an errand's configuration names.
  - Runs are `records/<A>/<E>/<R>`. A point is `…/points/<point>`, and a tool is `logs/<point>/<tag>.log` (`house.log_target`).
  - `results/<A>/<E>[/<R>]` is read by `scorecmd` (`:54`) and `report`.
  - `schema.keys(table)` gives the keys `heimdall explain` takes. `paths.tool_chains()` gives the tool folders. `house.RUN_STATES` gives the states.
- **`argcomplete` is not in the base.** Both the pixi env and the venv lack it, and `shtab` too. Neither is needed (D1).

### What `plot` takes (corrected 2026-11-09)

The first version of this plan said `plot` does not read `results/`. That was wrong, and the developer caught it. `plot`'s argument is any of:
- an errand file, `configs/<A>/<E>`;
- a Run, `<A>/<E>/<R>`. `record.record_of` (`record.py:1058`) takes it when `records/<A>/<E>/<R>` **or** `results/<A>/<E>/<R>` is a folder. Then `plotdoc.find` (`plotdoc.py:681`) draws from `results/<A>/<E>/<R>/plot.toml` when there is one (`cli.py:3512`), and otherwise from the record's snapshot;
- a path into `records/` or `results/`, or any folder holding a `plot.toml`, `results/<A>/<E>/` (an Errand's across page) included.

`run` and `status` call `record_of` with a snapshot required, so for them only a Run with a record in `records/` works. Of the other commands, `score`, `report` (its sources) and `tag` take names under `results/` too. The table below is the per-command map.

## What each command completes

The completer finds the command and the argument being typed, then answers by the argument's **kind**. Each kind is said once, in a table in `complete.py`. A test fails when a positional or a value-taking option of any command has no kind and is not listed as free text, so a new command cannot go uncompleted unnoticed.

| Command | Argument | Kind: what TAB offers |
|---|---|---|
| `run`, `status`, `watch`, `stop`, `cluster` | config | **errand**: `configs/<A>/<E>`, then after `<A>/<E>/` that Errand's Runs from `records/` (D2). `./` or `/` → the shell's own file completion, `.toml` only |
| `plot` | config | **errand or drawing**: `configs/<A>/<E>`, then after `<A>/<E>/` the Errand's Runs from `records/` **and** `results/` together (D7), one name each. `./` or `/` → the shell's own completion of folders and `.toml` files, so `./results/<A>/<E>/` (the across page) completes as a path |
| the same | configuration | **configuration**: the configurations of the errand already typed (`config.load`, ~10 ms) |
| `check`, `migrate`, `clean` | configs | **errand** (configs only) |
| `ls` | assignment | **assignment**: the folders of `configs/` |
| `show`, `log` | target | **record-deep**: `<A>/<E>/<R>`, then `/<point>` from `points/`, then `/<tag>` from `logs/<point>/*.log` |
| `tag`, `diff` | target, first | **record**: `records/<A>/<E>/<R>` |
| `diff` | second | **record**, or the bare `<R>` of the first Run's Errand |
| `score` | target | **result**: `results/<A>/<E>` and `results/<A>/<E>/<R>` |
| `report` | names | **recipe or result**: `.toml` recipes (`report.recipes`) and `results/` sources |
| `records`, `library` | scope | **record-scope**: `<A>`, `<A>/<E>`, `<A>/<E>/<R>` (`library` folders left out of an Errand's place) |
| `reproduce` | provenance | **file** named `provenance.json`, under `records/` |
| `overlay` | files | **file**: `.yoda`, `.yoda.gz`, `.root` |
| `explain` | key | **schema key**: tables, then `table.<key>` (`schema.keys`) |
| `tools` | what | **tool folder** names, and `new` |
| `help` | topic | **command** names |
| `stack` | (its own argv) | `build`, `list`, `status`, `doctor` |
| `setup`, `recognise` | dir, path | **directory** (the shell's) |
| `runs` | `--resume`, `--forget`, `--dispatch`, `--again`, `-i` | **run**: ids, and live indices (D4) |
| `run` | `--queued-to` | **run**: running and queued ids (D4) |
| `watch`, `stop` | `--pid`, `-i` | **run**: pids, and live indices (D4) |
| `runs` | `--state` | `house.RUN_STATES`, after the last comma too |
| `plot`, `watch` | `--plot`, `--file` | **file** |
| `heimdall cd` (shell) | `A [DIR]` | **assignment**, then `configs modules results records logs` |
| every command | `--…` | its options, from the parser. Any `choices` complete as given |
| free text | `tag` words, `build` targets, `bifrost` packages, `image` settings | nothing |

## Design

- **One hidden entry point.** `heimdall __complete CWORD WORD…` is handled first thing in `cli.main`, before `parse` and before the work-dir notes (`cli.py:3439`), so none of those run.
  - It never goes through argparse, so `reference/commands.md` (generated from the parser) does not list it.
- **`framework/runner/complete.py`** (rank 5 beside `cli` and `house`, standard library only):
  - It walks `cli.parser()` to find the command, the options already given and the argument at the cursor.
  - It answers from the kind table. Each kind is a small function over the readers named above.
- **What the shell gets back:**
  - The candidates, one per line.
  - Then one last line that is either `nospace`, when the candidates end in `/` and the user keeps going down, or `files:<glob>` / `dirs`, when bash's own `compgen` should answer.
  - The function `_heimdall` in `env/complete.bash` reads this and sets `COMPREPLY` and `compopt`. `heimdall_env.sh` sources it.
- **Read-only and silent, always:**
  - The completer writes nothing. That rules out `runs.entries()`, which prunes the registry (`runs.py:227`): runs are read by globbing the registry with `runs._own`. It also rules out notes, warnings and caches.
  - A `HeimdallError` or an `OSError` gives no candidates. A traceback never reaches the terminal.
  - Outside a work dir, the path kinds give nothing, and the commands and options still complete.
- **Fast.** A test holds each kind under 150 ms on the scratch work dir. The slowest is a configuration name, which loads one errand.

## Phases

Test command, stack loaded, from `tests/`: `taskset -c 0-5 nice -n 10 python -m pytest -q <files>`.

| # | Phase | Verified when | Blocked by | Size |
|---|---|---|---|---|
| 1 | [Commands and options](P1_core.md) | `__complete` answers commands, options and `choices` from the parser; nothing is written; under 150 ms | none | S |
| 2 | [Path and name kinds](P2_kinds.md) | every row of the table above has a test on the scratch work dir; the coverage test fails for an unkinded positional | 1 | M |
| 3 | [The bash function](P3_shell.md) | `bash -c` with `COMP_WORDS` set gets the expected `COMPREPLY` for each kind, `nospace` and `files:` included; `quit` removes it | 2 | S |
| 4 | [Live doc](P4_doc.md) | `docs/live/tab-complete.md` committed with phase 3; docs tests pass | 3 | XS |

## Decision log

| # | Decision | Chosen | Why |
|---|---|---|---|
| D1 | Mechanism | **Decided (developer, 2026-11-09):** our own stdlib completer over `cli.parser()` | `argcomplete` is not installed (a download and a base change), and it would still need a custom completer for every kind above. All it would add is the walk over argparse, which is about 60 lines. A generated static script would go stale, and it could not load an errand anyway |
| D2 | `run`/`plot` first argument | **Decided (developer, 2026-11-09):** errands, then the Errand's Runs after `<A>/<E>/` | Both forms are valid there (`cli.py:47`). Offering Runs only after the `/` keeps the first TAB short |
| D3 | Dynamic names | **Proposed:** configurations, points and tools, explain keys, tool folders | each is one cheap read |
| D4 | Run ids and indices | **Decided (developer, 2026-11-09):** yes, read-only from the registry | `--again ID` and `--queued-to ID` take an id like `20261023-104623-<host>-ff05`, which nobody types by hand |
| D5 | `gjallarhorn <title>` | **Proposed:** not in this plan | the function lives in the `~/.bashrc` block (`shellrc.py`), which is ask-first; a later issue |
| D6 | How bash gets it | **Decided (developer, 2026-11-09):** `heimdall_env.sh` sources `env/complete.bash`, so every Heimdall shell has it with nothing to install. I-73's `heimdall completion bash` is dropped | every shell that runs `heimdall` interactively has loaded that file. A command printing the script would only matter to a shell that never loads Heimdall, and there `heimdall` itself is not on `PATH`. I-73's done-when is reworded to match |
| D7 | `plot`'s Runs | **Decided (developer, 2026-11-09):** the Runs under `records/` and under `results/`, as one list | `plot <A>/<E>/<R>` draws a Run found in either (`record_of`, `plotdoc.find`), and its address is the same in both trees, so a name is offered once. A Run with only a `results/` folder (its record cleaned) can still be drawn from its `plot.toml` |

## Not yet specified

- Phase 2: how a live index `[N]` is numbered without the sockets that `house.live_runs` asks (`greeting`). Phase 2's pickup reads `house.live_entries` and decides whether the registry alone gives the same numbering. If it does not, the indices are left out and only ids complete.
- Phase 3: whether bash on the cluster's login node has `compopt` (bash ≥ 4). The phase checks, and falls back to no `nospace`.

## Always / Never

- **Always:** read-only, silent on error, under 150 ms, every candidate derived from the parser or from a reader that exists already.
- **Never:** a new package, a generated completion file, anything written to `~/.bashrc` or to Himinbjorg, a completer that names a tool.

## Progress

| Phase | Status |
|---|---|
| 1 | not started |
| 2 | not started |
| 3 | not started |
| 4 | not started |
