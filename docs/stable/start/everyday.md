---
id: everyday
summary: the everyday commands and what to write for the common needs, on one page
code: framework/runner/cli.py
---

# Every day

```bash
gjallarhorn Study                       # the environment, and cd to the work dir titled Study, from anywhere
heimdall build                          # the work dir's Rivet analyses and module programs
heimdall check                          # every config: validated, every point planned; nothing run
heimdall run Demo/jets pdf --plan       # the plan: cards, argv, connections
heimdall run Demo/jets pdf              # run what is not complete, then draw
heimdall run Demo/jets pdf --set errand.events=50000 --points 2   # for this job only
heimdall status Demo/jets               # each point: complete, stale, running, incomplete, to run
heimdall plot Demo/jets pdf             # redraw from what is on disk
heimdall watch                          # follow a job (d detaches, p pauses, q stops)
heimdall runs                           # live jobs on this machine, as [1], [2], …
heimdall explain errand.events          # any key, table, tool option, style key, stack setting
heimdall help run                       # any command
```

Every command: [commands](../../reference/commands.md).

## What to write

| To | Write | See |
|---|---|---|
| vary two things as a grid; zip two | `vary = ["energies", "pdf"]`; `vary = [["pdf", "alphas"]]` | [sweeps](../guide/sweeps.md) |
| a page per value of one | `plot_points = ["energies"]` | [plots](../guide/plots.md) |
| a value no tool knows by name | `to = { pythia = "MultipartonInteractions:pT0Ref" }` | [sweeps](../guide/sweeps.md) |
| a Rivet option | `to = { "rivet/photo_eic" = "R" }` | [sweeps](../guide/sweeps.md) |
| seed replicas, merged into one curve | `to = { "pythia/seed" = true }`, `combine = ["replica"]` | [scale](../guide/scale.md) |
| several event counts | `events = [100_000, 1_000_000]` in a configuration | [scale](../guide/scale.md) |
| your own program | `uses = "module"` or `uses = "exec"` | [programs](../guide/programs.md) |
| start from another file | `[file] import = ["validation"]` | [errand-file](../guide/errand-file.md) |
| a fixed folder number | `serial = 3` | [paths](../guide/paths.md) |

A whole file: [errand-file](../guide/errand-file.md). When something fails: [failures](../guide/failures.md).
