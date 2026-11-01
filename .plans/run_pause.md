# Pausing a run; live runs by index (I-115)

Asked by the user on 2026-11-01: "Make it so that pressing "p" lets pausing the run. On single press, it begins
pause on finish protocol: running points are waited to finish and new points are not dispatched, once all done,
run is "quit" but logged as pause. Second press of p force pause, discards running points. heimdall runs lists
paused and running runs as "live". Let live runs be indexed (updated as runs start/finish/stop). And heimdall
watch -i <index>, heimdall runs --resume <index of paused run>". Built on branch `context`, after I-112 E1–E4.

## 1. What is there

- **Stopping** (V181, V183, V222): `q` in a watch (or the run's own terminal view) sends the worker SIGINT;
  `cli.catch_signals` sets `execute.Stopper.requested` (then `hard` on a second), and `execute.run_points`'s
  dispatcher stops dispatching, each running point ends through the stop ladder (its partial outputs kept, a rerun
  resumes), the later stages are skipped, the run exits 6 and its registry entry ends "stopped".
- **The registry** (V72, V202, V221): `runs.begin`/`finish` write `$HEIMDALL_MACHINE/runs/<id>.json`; `heimdall runs`
  lists running jobs (V221: by default), `--5 … --month` history; each entry keeps `argv`, `work`, `config`,
  `configurations`, `checkout`.
- **Resuming** is a rerun: a point already complete is skipped (its identity), so `heimdall run` of the same errand
  and configurations continues where it stopped.

## 2. Decided

- **P1 The key `p`** (in `heimdall watch` and in the run's own terminal view; the hint line names it): the first
  press sends the worker SIGUSR1, a **pause**: no point is dispatched any more, the running ones run to their end
  (done or failed as they would), then the run quits without its later stages (combine, post, plot), exit 6, its
  entry `paused`. A second `p` (SIGUSR1 again) is a **force pause**: the running points are stopped as a hard stop
  stops them (their tools killed at once, recorded stopped, partial outputs kept), then the same quit. A `q` after
  a `p` is a stop, as now. `heimdall stop` stays the stop. Each press says what it did ("pausing: N running points
  end first; p again discards them").
- **P2 Recorded as paused:** `Stopper.pausing`/`Stopper.paused`; the dispatcher's loop, the sequential sweep and the
  pipelined sweep's gates read `pausing` as they read `requested` for dispatch; the run's `run finished` event and
  verdict say paused ("paused: 12 done, 2 discarded, 42 left"), `runs.finish(…, state="paused")`, `run.jsonl` and
  `heimdall log` show it, and a sweep's later configurations are not begun.
- **P3 Live runs:** `heimdall runs` with no option lists the **live** runs: running and paused, under one heading
  "live", each with an index `[1]`, `[2]`, … in the order they began, recomputed whenever the listing is made
  (a run that ends drops out; a resumed run takes its paused entry's place). A paused entry stays live until it is
  resumed or `heimdall runs --forget N` drops it.
- **P4 `heimdall watch -i N`:** the Nth live run; refused for a paused one ("[2] is paused: heimdall runs --resume 2").
- **P5 `heimdall runs --resume N`:** the Nth live run, paused: its own command again (`argv` from its entry,
  without `--worker`), detached, in its work dir and with its checkout's runner, so it continues from its records
  (complete points skipped); the paused entry is marked `resumed` (pointing at the new id) and leaves the live list.
  A running one is refused.
- **P6 Docs:** 00 (the key hint), 02, 05 §1.5 (keys, `runs`, `watch -i`, `--resume`, `--forget`), 06 (the stopper,
  the registry's states); tests: a pause and a force pause of fake points (as test_detach's), the listing's
  indices, `watch -i`, `--resume` relaunching the argv.

## 3. Phases

| Phase | What | V-row | Then |
|---|---|---|---|
| R1 | P1–P2: the key, SIGUSR1, the stopper, the dispatcher, the verdict and the entry | V230 | straight on |
| R2 | P3–P6: live runs indexed, `watch -i`, `runs --resume`, `--forget`; docs, tests | V231 | straight on |

## 4. Execution map

| Phase | V-row | Commit | State |
|---|---|---|---|
| R0 this plan, I-115 | — | | written |
| R1 P1–P2: `p`, SIGUSR1, the stopper, the dispatcher, the verdict, the entry | V230 | COMMIT | done |

## 5. Log

- 2026-11-01 R1 (V230): SIGUSR1 `catch_pause`, `Stopper.pausing`/`paused`/`halted`, the dispatcher, sweeps and stages halt on it, verdict `paused: …`, `runs.finish(state="paused")`; `p` in `heimdall watch` and the run's own view (`pause_key`). Beyond the plan: `q` after a force pause does not kill the runner; `p` after a stop sends nothing; the lock wait and combine's groups halt too. Tests: test_pause.py (new), test_detach.py. Docs left to R2 (P6).
