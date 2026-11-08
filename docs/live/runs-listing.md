---
id: live-runs-listing
summary: heimdall runs lists a run as a six-line block, coloured on a terminal with a log link; --state filters; stop -i N
affects: live-runs
issue: I-127
---

**Now holds:** `house.runs_listing` writes a block a run:

```
[2] <host> | <work dir's title> | <config>
    MM-DD HH:MM · <span>
    <A>/<E> · 03_nlo, …      (once it ended: X done (W with warnings), F failed, S stopped)
    running · 2 ongoing · 12/40 (1 failed)
    pid P : heimdall watch --pid P · heimdall stop --pid P
    log <path>
```

`[N]` is the run's place in the live list (oldest first, as `watch -i`, `stop -i` and `--resume`/`--forget` take it); a history list (`--5`…`--50`, `--week`, `--month`) names each run by its id first, with its `[N]` too when it is live. `<config>` is the config as `heimdall run` names it (`<A>/<E>` under the work dir's `configs/`), else its path relative to the current folder when under it, cut from its start to `house.CONFIG_WIDTH` (40) characters with a `…`; the configurations are not repeated after it. The third line is the run's records: each `<A>/<E>` folder under `records/` and its Runs' folders (`Demo/jets_more · 01_a, 02_b`), so an errand whose `name` is not its file's is named as its records are; a library entry is counted (`<A>/library · N entries`). The entry keeps `records` as the run goes (the recorder writes them with its progress). An entry with none (an older one) takes the record its config snapshot sits in (`records/<A>/<E>/<R>/config/…`, as `--resume` and `--again` run), else the config and `NN_<key>` with its `[tag]`. The state line has the entry's state, the points running now (`2 ongoing`, while it runs), and the points ended of those planned (`NULL` where an entry did not record it). A running run's failures so far are `(1 failed)`; an ended one's are in the counts. The line under a paused run is its `--resume N · --forget N`, under a failed, stopped or lost one `heimdall runs --again <id>`, under a cluster submission its `--status`. The first line is cut to the terminal's width with a `…`, never at its index.

The entry records `parallelism` (the cap the run began with, `run started`'s `parallelism`) and `points_failed` as it goes.

**Colour** only on a terminal, without `--plain` and without a non-empty `NO_COLOR` and with `TERM` not `dumb` (`house.wants_colour`), by plain SGR codes (`house.paint`): the index bold, the state green (running), yellow (paused), red (failed), magenta (stopped), dim (done), grey (lost), the commands cyan, the log dim. The log path is an OSC 8 link `file://<host><path>` (the entry's host, so a terminal over ssh opens no wrong file), its shown text unchanged (`house.link`). Without colour the words are the same and carry no escapes.

`heimdall runs --state running,failed` keeps the runs in those states (`house.RUN_STATES`: running, paused, failed, stopped, done, lost, not run, submitted, on Slurm, ended, cancelled) in any list; an unknown one is refused with the list; a live run keeps its live `[N]`. `heimdall stop -i N` stops the running live run [N] as `stop --pid` does; a paused, cluster or ended one is refused, saying what to do (`running_at`, which `watch -i N` shares).

**Actions.** `heimdall runs -i N|ID` shows that run's block and, on a terminal, the keys that fit it (`watch -i`, `stop -i` and `--resume` take the live number; an id also names a run that ended): `w` watch and `s` stop and `j` set jobs ([live-parallelism](live-parallelism.md)) for a running one, `r` resume and `f` forget for a paused one, `a` run again for a failed, stopped or lost one, `q` leave. `s`, `r`, `a` and `f` ask for their word typed (`stop`, `resume`, `again`, `forget`): anything else cancels and says so. Off a terminal the block alone is printed. Each action is also a flag: `heimdall stop -i N`, `runs --resume N`, `runs --forget N`, `runs --again ID|N`, `runs -i N --jobs M`; a flag acts without the prompt. `--again` is `--resume`'s relaunch (`cli.relaunch_entry`): the run's own command (`runs.again`), detached, from its checkout and work dir, over its latest record's config snapshot (`resume_snapshot`), its complete points skipped and its failed ones run; it leaves the old entry as it is, and is refused (with the state) for a running, paused or cluster run.

**No longer holds:** `[<configurations>]` after the config; `N of M at once` on the state line; `watch -i N · stop -i N` in the block; the old block (`[N] <id> | <title>`, then the counts, the times, pid and log); `heimdall runs` without colour; `stop` taking `--pid` only; `--resume N` and `--forget N` as the only actions.

**Decisions:** the developer's layout (2026-11-08): the block names the records' `<A>/<E>`, not the config's path; the config is shortened and has no `[configurations]` after it; the jobs are those ongoing, not the cap; the commands name `--pid`, which means one job whatever the live list holds (`-i N` still works). The plain block is the new layout too: the same words without escapes, not the old layout. Colour is plain SGR codes, not rich, because `[N]` is rich markup and a path may hold brackets. `stop -i N` came with the listing, since the block prints it. `runs -i` takes a live number or an id, because `a` applies to an ended run, which the live list never holds; an id tail of digits falls back to the id when no live run has that number. `--again` shares `relaunch_entry` with `--resume` and marks nothing on the old entry.

**Stable pages need:** `internals/live-runs.md` (the block, the entry's `parallelism` and `points_failed`, `--again`, `--state`), `guide/watching.md` (its table of what to type: `runs -i`, `--state`, `stop -i`, `--again`).
