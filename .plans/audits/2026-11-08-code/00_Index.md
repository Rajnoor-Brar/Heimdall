# Audit 2026-11-08: code health

A code-first audit of Heimdall at `21d8523`: dead and retired code, duplicated mechanisms, structure, design patterns, oversights, room to grow, tests, and the debt in `.plans/` and `docs/live/`. Every finding is read from the code. Docs and issues are claims; where one disagrees with the code, the finding says so.

**State:** first pass done (2026-11-08). Each category file lists its findings, then **Sweeps still to run**. A finding closes when its **Closes when** check passes. It then leaves its file, and the decision it needed goes where `docs/rules/work.md` says.

## Categories

| File | Asks | Findings |
|---|---|---|
| [01_dead-and-retired](01_dead-and-retired.md) | What nothing reaches, and what is kept only to refuse or translate an old form | 9 |
| [02_duplication](02_duplication.md) | Two or more mechanisms for one job; copies that must move in lockstep | 8 |
| [03_structure](03_structure.md) | Modules with more than one reason to change; where a package boundary belongs | 8 |
| [04_design](04_design.md) | Patterns that make the next change harder: stringly state, sniffed forms, ledger ids in code | 8 |
| [05_oversights](05_oversights.md) | Use cases not handled; decisions that look made in haste | 8 open |
| [06_expansions](06_expansions.md) | Features the code is one step from, and the ones worth adding | 9 |
| [07_tests](07_tests.md) | Red tests left red, fixtures in the retired form, order and speed | 5 open |
| [08_process](08_process.md) | Debt in `.plans/` and `docs/live/`: finished plans not removed, decisions not built | 6 |

## Closed

- **O-1, O-2, T-5** (2026-11-08): a worker that has not begun within `runs.BEGIN_WAIT` is ended (`cli._begun`, used by `queue_run` and `queue_sweep`); `runs.prune` removes queue and control asks; tests for both and for a lost predecessor (`test_queue.py`, `test_runs.py`). Each test failed on the old code first.

## Leverage: where to start

1. **One dialect** ([D-1](02_duplication.md#d-1), [S-5](03_structure.md#s-5)). v3 is translated into v2, and all 11 fixtures are v2. Every key has two names, every error speaks v2, and `migrate.py` (1554 lines) exists for the old forms. Decided on 2026-10-25 (I-20, I-21), and not built since. It unblocks I-25, I-26, I-35 and I-70.
2. **State as a value, not a sentence** ([G-1](04_design.md#g-1)). `runs.state()` returns display text (`"done, resumed"`, `"running (not reachable from here)"`), and the queue waiter decides by parsing it back (`house.state_word`). Cheap to fix, and it guards the queue.
3. **The points library in one module** ([S-3](03_structure.md#s-3)). Its key and links are in `record.py`, list, verify and prune in `house.py`, and adopt in `migrate.py`. Yet I-25 plans to delete `migrate.py`.
4. **`cli.py` and `house.py` split by command** ([S-1](03_structure.md#s-1), [S-2](03_structure.md#s-2)). They are 3553 and 1313 lines, with 31 commands between them. I-50 decided the subpackages.
5. **Merging, five ways** ([D-2](02_duplication.md#d-2)). `combine`, the `merge` and `plotmerge` post tools, the `merged` figure, and a set's `merge` with `band`. Say which is the model, and make the others its front ends or retire them.
6. **The red tests** ([T-1](07_tests.md#t-1)). Six failures have stood across sessions, so a seventh would not be noticed.

## Method (what was run, so it can be repeated)

- **Unreferenced definitions.** An AST pass over every top-level def, class, constant and method in `framework/`, counting word-boundary hits across framework, tests, recipes, shell, the Makefiles and `src/`. It was calibrated on known-used names. The script is in this audit's [sweeps/defs.py](sweeps/defs.py).
- **CLI options against their readers.** Every `add_argument` dest against `args.<dest>`, `getattr(args, "<dest>")` and `"<dest>"` in framework. All 121 are read. The four the regex missed (`anyway`, `matrix`, `no_open`, `quick`) were checked by hand.
- **Schema keys against the code.** Every key of `framework/schema/run.toml` against a quoted or dotted use in framework Python and `src/` C++. None is unread at this coarse grain (a key may be read, then ignored: see [Sweeps still to run](04_design.md#sweeps-still-to-run)).
- **Markers.** `retired`, `legacy`, `for now`, `for a release`, `re-export`, `compat`, `TODO` in framework.
- **Size and branching.** Function length and branch count by AST. The worst 30 are in [03_structure](03_structure.md#s-7).
- **Ledger ids.** 837 citations of 133 distinct `V<n>` ids in framework. All 133 resolve to a note in `docs/`.
- **Against `.plans/ISSUES.md`.** Each finding names the issue it overlaps. A finding that only restates an issue is not repeated here. The issue stands.

## Not in scope

The C++ of `src/` beyond sizes, the stack recipes (`recipes/`), `editor/`, and the physics. Identity and seeds are named where a finding touches them, and never proposed changed without the developer's word (invariants).
