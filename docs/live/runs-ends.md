---
id: live-runs-ends
summary: heimdall runs shows when and how each run ended in its state's colour, orders a history list by its runs' ends, and gives every state a colour
affects: live-runs
---

**Now holds:** a block's time line is `MM-DD HH:MM · <span> · <state> HH:MM`. It holds the start, how long the run ran, then how it ended and when (`done 18:05`, `failed 10:00`, `stopped`, `paused`), in its state's colour. The end shows `MM-DD HH:MM` when it fell on another day than the start. A running or queued run has no end part. The end is the entry's `finished`, which `runs.finish` writes at every end. A lost run never wrote one, so its end is the last sign of it, marked `~` (`lost ~12:00`, `house.ended_at`): its log's last write, else its entry file's (the run wrote progress there while it went), else its start. It is never now, so a lost run never sorts as the latest. The span runs to that end.

A history list (`--5` … `--50`, `--week`, `--month`) is ordered by its runs' ends, the latest last. A run still going counts as ending now. `--5` keeps the five that ended last, and `--week` keeps the runs that ended within it. The live list keeps the order its runs began, so its `[N]` stays put.

**Colours** (`house.STATE_STYLE`, one for each of `runs.STATES`):
- running: bright cyan;
- done: green;
- failed: red;
- stopped: magenta;
- paused: yellow;
- held: bright yellow;
- queued: blue;
- submitted and on Slurm: bright blue;
- lost, not run, cancelled and forgotten: grey;
- ended and unknown: dim;
- exit: red.

On the state line, `N done` is green, `N failed` red, `N stopped` magenta, `with warnings` yellow and `N ongoing` bright cyan (`house.COUNT_STYLE`). A zero stays plain.

**No longer holds:** done dim and running green; a history list ordered by when its runs began.

**Decisions:**
- **V265** A history list orders runs by their ends, since the question it answers is what finished last. The live list orders by start, since its `[N]` must not move while runs end.
- **V266** A lost run's end is its last sign of life (its log's last write, its entry's, its start), marked `~`. It is never written into the entry, which would make it read as ended rather than lost.

**Stable pages need:** [live-runs](../stable/internals/live-runs.md): the block's time line, the history order and the colours.
