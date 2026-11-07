---
id: first-run
summary: a first run from a new work dir to drawn pages, what to look at, and how a job behaves on a terminal
code: framework/runner/setup.py, framework/runner/cli.py
---

# A first run

With the stack built ([fresh-machine](../setup/fresh-machine.md)):

```bash
gjallarhorn                              # the environment
heimdall setup ~/Study --example jets    # a work dir with the demo assignment
cd ~/Study && heimdall build             # its Rivet analysis and module programs
heimdall check Demo/jets                 # every configuration planned; nothing run
heimdall run Demo/jets single --plan     # what would run
heimdall run Demo/jets single --set errand.events=50000
```

`--assignment A` instead of `--example` gives a starter of your own, and `--git` commits it. `heimdall recognise <dir>` records work dirs so `gjallarhorn <title>` finds them from anywhere.

`single` is one point: App_Pythia generates 27.5 × 920 GeV e⁺p photoproduction into a FIFO, Rivet's `photo_eic` reads it, the YODA is converted to ROOT, and 17 pages are drawn, those ZEUS measured against its data. The terminal shows the running tools, then one block:

```
── point 1/1: point ── ok after 42.3s at Tue 21 Oct 14:03

   done → results/Demo/jets/03_single/point
```

| Look in `…/Demo/jets/03_single/` | For |
|---|---|
| `results/…/points/point/` | `jets.yoda`, `jets.root`: the products |
| `results/…/plots/totality/root/` | the pages, and `index.html` |
| `results/…/statistics/totality/` | `statistics.csv`, the pages' numbers against the data, and bar graphs |
| `results/…/plot.toml` | its plot document; its `[plot]` is yours to edit |
| `records/…/points/point/` | `provenance.json`, `identity.json`, `.complete` |
| `records/…/logs/point/` | `cards/`, `context.toml`, `commands.sh`, a tool's `<tool>.log` |
| `records/…/config/` | the errand file and cards it ran with |

`Demo/jets/03_single` is the Run's address, and every command that takes or prints a folder names it so.

Run the same command again and nothing happens. Change a card, an event count or a binary and it runs again.

## A job on a terminal

```bash
heimdall run Demo/jets energy_pdf        # 16 points: 4 beam energies × 4 PDFs
heimdall watch                           # from another terminal
heimdall plot Demo/jets energy_pdf       # redraw from what is on disk
```

A job on a terminal runs in the background, shown here.

| Press | Does |
|---|---|
| `d` | the prompt comes back, and the job goes on. Closing the terminal leaves it running too |
| `p` | pause: no more points start, running ones finish, the job ends paused before its later stages. A second `p` discards the running points |
| Ctrl-C | stop. A second is a hard stop |

`heimdall runs` lists live jobs as `[1]`, `[2]`, …: `heimdall watch -i 2` follows one, `heimdall runs --resume 2` restarts a paused one (complete points are skipped), `--forget 2` drops a pause. `heimdall stop` stops one; `--detach` starts one without showing it. With `--plain`, or off a terminal, a job runs in the shell's own process, as in a script.

A detached job still ends when what holds its session ends: logging out where systemd ends a user's processes (`loginctl enable-linger` keeps them), an allocation's end on a cluster, an Apptainer shell started with `--pid` or `--containall`.
