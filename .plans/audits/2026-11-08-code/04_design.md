# Design patterns

Patterns that make the next change harder or let a defect hide. Each finding names the pattern, where it lives, and the shape it should have.

## Findings

### G-1 Run state is a sentence, and logic parses it back · Required · CONFIRMED
`runs.state()` returns display text: `"done, resumed"`, `"running (not reachable from here)"`. `house.state_word()` (`house.py:614`) cuts it at the first comma or parenthesis. The queue waiter decides whether to start with `word in ("done", "failed", …) or word.startswith("exit")` (`cli.wait_turn`, `cli.py:1184`). The `runs -i` action menu does the same (`cli.py:2287`), and so does the listing's `--state` filter (`house.py:675`). The states are also listed three times: `runs.VERDICTS` (`runs.py:45`), `house.RUN_STATES` (`house.py:580`, 13 states), and the colours.
So rewording a state on screen changes when a queued run starts.
**Move:** `runs.State`, an enum (running, queued, held, paused, done, failed, not run, stopped, lost, forgotten, submitted, …), plus qualifiers (`resumed`, `reachable`) as fields. `runs.state()` returns it, and `house` formats it. The waiter compares enums. **Closes when:** no logic calls `state_word`, and a test rewords a state's text without changing queue behaviour.

### G-2 An errand file's form is sniffed, not declared · Required · CONFIRMED
`v3.is_v3` (`v3.py:66`): a file is v3 if it has `[file]`, `[cfgs]` or `errand.chain`, otherwise v2. A v3 file that writes none of the three, say a minimal one with `[errand] run = …` and `[tools.*]`, is read as v2. Its errors then name v2 keys the user never wrote. Hasty in the sense that the heuristic was written for the files of the day.
**Move:** goes with D-1. Until then, make `[file]` mandatory in a v3 file, so the sniff is only the fallback for v2. **Closes when:** a v3 file without `[file]` is refused with "add [file]", or v2 is gone.

### G-3 Registry entries are bags of optional keys · Required · CONFIRMED
A run's entry is a dict read with `.get` in `runs.py`, `cli.py` and `house.py`. About 30 keys are read there, many optional and meaningful only together: `queued`, `held`, `queue`, `queued_to`, `began`, `left_queue`, `dispatched_from`, `resumed_by` and `forgotten`, beside `pid`, `pstart`, `boot` and `pidns`. Their valid combinations live only in `wait_turn`'s branches. `runs.VERSION = 1` and never moved, though the queue added nine keys.
**Move:** a `RunEntry` dataclass parsed once at `runs.entry()`, with the queue fields as one optional `Queue` value (`queue`, `after`, `held`, `dispatched_from`). `VERSION` goes up when the shape does. **Closes when:** `cli` and `house` read attributes, not `.get` on entries.

### G-4 `argparse.Namespace` as the planning API · Required · CONFIRMED
`build_plans(args, key)` takes the CLI's namespace, so internal callers forge one: `argparse.Namespace(**{**vars(args), "points": None, "rerun": False, **changed})` (`cli.py:548`, and 11 constructions in `cli.py`). A new option read inside planning breaks every forged namespace that lacks it, which is the `test_flags` failure class seen in this session. This is I-35 (`RunRequest`), blocked on I-25. The block is not needed: a `RunRequest` can be built from `args` today.
**Move:** a frozen `RunRequest` that `build_plans` takes. The CLI builds it once, and internal callers build their own. **Closes when:** no `argparse.Namespace(` outside the parser and the tests.

### G-5 Four control channels to a running worker · Consider · CONFIRMED
- **Stop:** SIGINT, SIGTERM or SIGHUP (`cli.catch_signals`).
- **Pause:** SIGUSR1 (`catch_pause`).
- **Jobs:** SIGUSR2 plus `runs/<id>.control.json` (`catch_control`).
- **Dispatch and forget:** `runs/<id>.queue.json`, polled every 5 s, with no signal.
- **The watch socket:** one way, never read (`events.Hub`).

Two of the four file and signal protocols differ in shape: control is signalled, the queue is polled. Each new action picks one.
**Move:** one `runs/<id>.ask.json` (`{ask, args, by, at}`) and one signal (SIGUSR2) for every non-destructive ask (jobs, dispatch, forget, later pause), with SIGINT kept for stop. A queued waiter sleeping on `signal.sigtimedwait` wakes at once instead of within 5 s. **Closes when:** one ask file and one handler.

### G-6 52 imports inside functions in `cli.py` · Consider · CONFIRMED
They are local to keep `heimdall --help` fast and the ranks clean. Some are needed (numpy, yoda, the `report` package). Most are runner modules already loaded by the time the function runs. The cost: an import error surfaces only on that command's path, and the import graph `test_imports` checks misses them, or it reads them through a special case.
**Move:** after S-1, each command module imports at the top, and only the heavy external libraries stay lazy. **Closes when:** local imports in the CLI are only of numpy, yoda, matplotlib and `stats`.

### G-7 Decisions are cited by ledger id, and the ids outlive their decisions · Consider · PLAUSIBLE
837 citations of 133 `V<n>` ids in framework. All resolve (sweep in [00_Index](00_Index.md#method-what-was-run-so-it-can-be-repeated)). But a superseded decision keeps its citations: `tests/integration/test_gates_run_sweep.py:127` still cites V75 ("has not started all its points (V75)") for the pipelining this session retired. A citation says "why", and when the why is retired the code it points at is suspect.
**Move:** `heimdall docs --drift` checks that every cited `V<n>` is not marked superseded, or names its successor. **Closes when:** that check exists and is clean.

### G-8 Free-text states in records, too · Consider · PLAUSIBLE
Point attempts carry `verdict` strings, the journal events carry `state` strings, and `status` maps both to words (`record.state_of`). The same pattern as G-1, one layer down. Not yet traced to a behaviour that depends on wording.
**Move:** check whether any branch reads a verdict's text past equality. If none does, record it as fine. **Closes when:** checked.

## Sweeps still to run

- **Keys read, then ignored.** A schema key the loader accepts but nothing downstream uses. F-2 (`[figure].weight`, in `Implementation_Issues.md`) is one. Trace each `run.toml` key to its effect, not only to a string match.
- **Silent fallbacks.** `or {}`, `or []` and `getattr(args, x, None)` on values that should always exist: each one hides a missing input. `getattr(args, …)` appears where `args` comes from several parsers.
- **Mutable defaults and module state.** Module-level caches (`lru_cache` on functions reading the environment or the disk) that a long-lived worker or a test would see stale.
- **Atomic writes.** Every write of a registry, record or library file through `write_atomic` or `runs._write`. List the ones that are not.
