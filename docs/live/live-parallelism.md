---
id: live-live-parallelism
summary: heimdall runs -i N --jobs M changes a running job's points at once while it runs: a request file and SIGUSR2; raising starts more, lowering stops none
affects: live-runs
issue: I-127
---

**Now holds:** `heimdall runs -i N --jobs M` (or `j` at the `runs -i N` prompt) changes the running job [N]'s points at once while it runs. It writes `runs/<id>.control.json` (`{"parallelism": M, "by": pid, "at": time}`, whole and atomically: `runs.write_control`) and sends the worker SIGUSR2. The registry keeps its one writer, the run; the file is the request, and the signal, like `p` and `q`, is sent only to a job of this user in this PID namespace (a run of another namespace or user is refused, a paused, ended or cluster one too). M is a whole number from 1 to `execute.Stopper.CEILING` (256); a note says so when M × the costliest point's cores (`point_cores` in the entry) exceed the machine's cores. The identity is untouched (parallelism is in no identity).

**The worker** catches SIGUSR2 beside SIGUSR1 (`cli.catch_control`; a spawned worker ignores it until then, `runs._pause_ignored`). The handler only sets `Stopper.control`; a daemon thread (`cli.control_thread`) reads the file and applies it (`cli.apply_control`): `Stopper.set_parallelism(M)`, the entry's `parallelism`, and a `{"k": "parallelism", "from", "to", "by"}` event, which `run.jsonl` keeps and the views say (`3 points at once now (was 1)`). A missing or bad file, or an M over the ceiling, is ignored with a note in the log.

**The cap** is `Stopper.cap(configuration.parallelism)`: the live number if one was given (for every later configuration of a sweep too), else the configuration's. `execute.run_points` reads it at every dispatch (there is no serial branch any more: a run at 1 is a pool of one, and the pool is made for the ceiling, its threads made as points start). Raising starts more points at once within half a second; lowering starts none until fewer than M run, and no running point is stopped. In a pipelined sweep the shared cores `Budget` is resized with it (`Budget.resize`: `max(cpus, M × the costliest point's cores)`); points already running keep their cores.

**No longer holds:** a run's points at once being fixed when it starts; `run_points`'s serial branch at 1; the pipelined sweep's `Budget` sized once.

**Decisions:** the cap is an override on the Stopper (`None` until a `--jobs`), not a value set at start, so a sweep's later configurations take it too. The pool is sized to `CEILING` = 256, not the CPU count: threads are made as points start, so the ceiling costs nothing, and a cap above the cores is the user's choice (a note says so; above 256 is refused). The signal handler only sets an Event and a daemon thread does the work, because the bus and the recorder take locks the main thread may hold. There is no uid check: the registry lists this user's runs alone. Lowering never stops a running point, because that would lose its work.

**Stable pages need:** `internals/run-flow.md` (`run_points` reads the cap at each dispatch; no serial branch), `internals/live-runs.md` (the control file and SIGUSR2), `guide/scale.md` and `guide/watching.md` (`--jobs`).
