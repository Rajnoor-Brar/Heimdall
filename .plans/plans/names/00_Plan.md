# Names and commands: Himinbjorg, `heimdall show`

Issue: I-128 (and I-72, folded in). Status: planned 2026-11-07, not started. Blocked by: none. `tag`'s rethink (labels) is across-axes phase 4.

## Context

Verified at `cd6ceac`:

- **`machine_root()`** is defined at `framework/runner/paths.py:320`, with `MACHINE_VAR = "HEIMDALL_MACHINE"` and `DEFAULT_MACHINE = "~/Himinbjorg"` (:315-317, the last duplicated in `shellrc.py:21`). It is called in `image.py`, `cluster.py`, `paths.py`, `plot.py`, `bifrost.py`, `workdirs.py`, `runs.py`, `setup.py` and `cli.py`: 30 hits in framework/ and 10 in tests/.
- **The phrase "machine root"** appears about 73 times in framework/ (comments, docstrings, messages), 24 in tests/, 53 in docs/ (26 files, the generated `reference/commands.md` and `reference/settings/stack.md` among them), 42 in recipes/, and in `gjallarhorn.sh`, `launch.sh`, README and the Makefile. The glossary entry is `docs/stable/design/glossary.md:13`.
- **`HEIMDALL_MACHINE`** appears about 90 times: shell, recipes, tests, conftest. Every root variable is `HEIMDALL_*`.
- **`heimdall log`** (`cli.cmd_log`, `cli.py:1894`; `house.log_target`, :583) replays `run.jsonl`, a point's attempts and logs, and one tool's log. I-72 plans `heimdall show RECORD[/POINT]` (provenance, identity parts, products, σ, counts, logs' tail). They overlap.

## Design

- **The name.** Code says `himinbjorg()` and prose says "Himinbjorg" (the place where a machine's builds live), with the glossary line "Himinbjorg (once: machine root)". `MACHINE_VAR`, `HEIMDALL_MACHINE` and `DEFAULT_MACHINE`'s value stay. `machine_file` and `machine_settings` keep their names: they name `machine.toml`, which stays.
- **Docs.** Generated reference pages are regenerated from their sources (schema, argparse). Rules pages (`docs/rules/invariants.md` says "machine root" five times) change on the developer's word, given in this plan's approval. Stable pages change through `docs/live/himinbjorg.md` until a crystallise is ordered.
- **`heimdall show RECORD[/POINT[/TAG]]`** is one inspector.
  - For a Run: tag and labels, configuration, state counts, constants, and where its things are.
  - For a point: state, identity (short) and its parts (`--parts`), seed, events, σ from its products where a reader exists, products, provenance (tools, versions, host, stack), and the last 20 lines of its log.
  - For a tool tag: that tool's provenance and log tail.
  - `--log`, `--full` and `--attempt N` are today's `log` views. `heimdall log …` stays as the shorthand for `show --log …`, as `--logs` and `--journal` stayed (decided 2026-10-25).

## Phases

Test command, stack loaded: `taskset -c 0-5 nice -n 10 python -m pytest -q <files>`.

| # | Phase | Verified when | Blocked by | Size |
|---|---|---|---|---|
| 1 | [Himinbjorg](P1_himinbjorg.md) | `grep -rn "machine_root" framework tests` empty; `grep -rni "machine root"` only in the live doc's "no longer holds" and the glossary's "once"; fast suite green | none | M |
| 2 | [`heimdall show`](P2_show.md) | CLI tests for a Run, a point, a tool; `log` output unchanged as `show --log` | none | M |

## Decision log

| Decision | Chosen | Why |
|---|---|---|
| Rename | identifiers and prose; `HEIMDALL_MACHINE` kept | prompt.md: "just use himinbjorg"; every root variable is `HEIMDALL_*` and users' shells set it |
| `log` | folds into `show`, kept as its shorthand (developer) | One inspector; old habits keep working |

## Always / Never

- Always: regenerate generated docs, never hand-edit them; one commit for the identifier rename, one for the prose.
- Never: change `HEIMDALL_MACHINE`, the default path or `machine.toml`'s name; edit stable pages (live doc instead).

## Progress

| Phase | Status |
|---|---|
| Plan | approved 2026-11-07 |
| 1 | done 2026-11-08 (6743741, fed1a9b) |
| 2 | done 2026-11-08 |
