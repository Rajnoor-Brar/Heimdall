# Oversights and hasty decisions

Use cases the code does not handle, and choices that look made for the case at hand rather than thought through. O-3 is in the run queue added on 2026-11-08 (`8315e8b`). O-1 (a stray worker when one was slow to begin) and O-2 (`queue.json` never pruned) are closed: see the index.

## Findings

### O-3 A reboot loses a whole queue, and nothing brings it back · Consider · CONFIRMED · closed 4.1
Each queued run is a sleeping process. After a reboot, `runs.alive` sees a new boot id and every waiter is `lost` (`runs.py:271`). A lost predecessor lets the next run start (tested since O-1's fix), but the next run's process is dead too, so a queue of ten 12-hour runs (the case in this session's work dir) is ten `lost` entries. `--resume` takes one entry and ignores `--queued-to` (`runs.again`), so rebuilding the queue is ten commands, typed in the right order.
**Move:** `heimdall runs --resume-queue ID|N` restarts the queue's unfinished runs in order, each queued to the one before. The entries already hold `queue` and `queued_to`. **Closes when:** a test kills every worker of a three-run queue, and one command requeues the two not done.

### O-4 A sweep is a queue with a terminal, and one process without · Consider · CONFIRMED
`live/run-queue.md`: with `--detach` or a terminal, a sweep is N workers with N entries. With `--plain`, a pipe or a worker, it is one process and one entry that runs the configurations in turn. So `heimdall runs`, `--resume`, `--dispatch` and the logs all behave differently for the same command, depending on whether stdout is a tty. A cron job or a `| tee` gets the other model.
**Move:** decide whether `--plain` should also queue (one entry per configuration, followed in turn in this process), so a sweep is one model. Ask the developer: it is a behaviour change. **Closes when:** one model, or the difference stated in `heimdall run --help`.

### O-5 Locks assume a local filesystem · Consider · PLAUSIBLE
`PointLock`, the library index and the prepare cache use `fcntl.flock` (`record.py:628`, `:227`; `execute.py:235`). The docstring says a lock is never stale "on this host". On a cluster, array tasks on different nodes share the work dir over NFS or Lustre, where `flock` may be node-local (Lustre's `localflock`, old NFS). Two nodes could then both hold a library entry's lock and write one point. The library makes this newly likely, since its entries are shared across Runs.
**Move:** verify on the cluster's filesystem (I-87). If `flock` is node-local, use `fcntl.lockf` (POSIX locks, which NFS forwards), or a lock file created with `O_EXCL` that carries host and pid, with a stale check. **Closes when:** two nodes contend for one entry in a test on the real site.

### O-6 Live-state files are read by every checkout, with one format number that never moves · Consider · PLAUSIBLE · closed 1.4
`runs/` is in Himinbjorg and read by every checkout (invariants). `runs.VERSION = 1` (`runs.py:40`), though the queue added nine fields. An older checkout reading a queued entry has no idea of `queued`: it sees a live pid and calls it "running". Its `--resume` or `stop` would act on a waiter. This is I-68's subject, from the other side: old readers of new files.
**Move:** bump `VERSION` when an entry's meaning changes, and have a reader refuse to act on an entry of a newer version than it knows ("this entry is from a newer Heimdall"). **Closes when:** both hold, with a test.

### O-7 Pid reuse is guarded only on Linux · Nit · CONFIRMED · closed 2.7 (on Linux unchanged; proven on macOS only when I-82 runs there)
`runs.started_at` reads `/proc/<pid>/stat` and returns `""` elsewhere (`runs.py:78–84`). `alive` then trusts the bare pid (`runs.py:285`). On macOS (I-82, unproven) a reused pid makes a dead run look alive, so `heimdall stop` could signal a stranger's process of the same user.
**Move:** `ps -o lstart= -p PID` as the fallback start time. **Closes when:** `started_at` is non-empty on macOS.

### O-8 "For one release" with no releases · Consider · CONFIRMED
`v3.py:25` and `cli.py:1951`. Heimdall has no version number, and the tags are snapshots (`pre-restructure`, `archive/…`). A "for a release" deprecation has no trigger, so it never ends. See [R-4](01_dead-and-retired.md#r-4) and [R-5](01_dead-and-retired.md#r-5).
**Move:** a date per retirement, in I-26's table, and `heimdall doctor` lists the ones past due. **Closes when:** no "release" wording without a date.

### O-9 Identities that hash an absolute cache path · Required · CONFIRMED (from `Implementation_Issues.md` F-4, re-read)
The Herwig, MadGraph and Sherpa fixtures' identities include a `.cache/…` absolute path, so a moved work dir or another checkout reruns every such point. The library key strips names but not paths ([S-3](03_structure.md#s-3)), so library entries made in two clones of a work dir would not pool. This is ask-first territory (identity). It is listed for the developer's decision, not for a fix.
**Closes when:** the developer decides.

### O-10 Scoring rules the implementer chose, not yet reviewed · Required · CONFIRMED
`.plans/Implementation_Notes.md` (2026-11-07, stats-backend) records choices made alone, several in its own words ("a pure rule of my own", "None of these thresholds were in the notes as numbers; they are mine"):
- **Weights precedence:** figure `weight` > first matching glob > 1 (`score.page_weight`). The figure weight is never read by the summary (F-2).
- **`mad`:** a floor of 10 % of the good-to-bad span.
- **`median`:** floored at `|good|`.
- **`promethee`:** q = 0.1, p = 1.0, fixed.
- **`topsis`:** 1 − closeness.
- **`fisher`:** p capped at 1e-300.
- **Mixed references:** data pages beat curve-measured pages when a table mixes them.
- **No renormalisation** of a merged set's file.
- **Marginals:** over (cell, point) scores.
- **An Errand's row:** only the pages every Run has (a page one Run lacks drops from all).

These decide which point a study calls best. They are physics-facing defaults chosen at implementation time.
**Move:** the developer reviews the list. Each rule accepted becomes a decision note, and each rejected one a fix. The opt-in ones (`mad`, `promethee`, `topsis`, `fisher`) can wait. The precedence, mixed references and the Errand's page intersection cannot, since they apply by default. **Closes when:** each rule has a decision note or an issue.

## Sweeps still to run

- **Disk.** A 12-hour run and the library write gigabytes, and nothing checks free space before starting, or says how much a run will take (`--plan` could, from earlier points' product sizes).
- **Interrupted writes.** Kill -9 during each write path (entry, record, library link, snapshot), then read back. `write_atomic` covers most of them: list the rest.
- **Two users on one Himinbjorg.** `_own(mine=True)` filters entries, but the library and `forge/` are shared: what a second user's run can overwrite or prune.
- **Clock and time zone.** Entries store `time.time()` and listings print local `HH:MM`. A run across a DST change, or a listing read over ssh from another time zone.
- **Huge sweeps.** Planning time and `points.json` size at 10⁴ points. `queue_sweep` spawns one sleeping process per configuration: what 50 configurations cost.
