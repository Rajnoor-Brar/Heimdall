# 00 — Quick reference

One page: the commands, a whole errand file, where things go. Each line points to the page that says
it in full.

## Every day

```bash
gjallarhorn Study                          # Heimdall's environment, and cd to the work dir titled Study (from anywhere)
heimdall recognise ~/Github                # record the work dirs found there, by title (--list: every one this machine knows)
bifrost scipy                              # a package into the environment (-python <pkg>: from PyPI; bifrost: what is there)
heimdall setup ~/Study --example jets      # a work dir, with the demo assignment (--assignment A: a starter; --git: commit)
heimdall build                             # the work dir's Rivet analyses and module programs
heimdall check                             # every config: loaded, validated, every point planned; nothing run
heimdall run Demo/jets pdf --dry-run       # the plan: cards, argv, connections (also --why, --show-config)
heimdall run Demo/jets pdf                 # run what is not complete, then draw the pages
heimdall run Demo/jets pdf --set errand.events=50000 --points 2   # one value changed, one point, for this job
heimdall status Demo/jets                  # each point: complete, stale, running, incomplete, to run
heimdall plot Demo/jets pdf                # redraw from what is on disk
heimdall watch                             # follow a job from another terminal (d/Ctrl-C detach; p pauses it; q stops it)
heimdall runs                              # live jobs on this machine, running and paused, as [1], [2], … (--5: recent ones)
heimdall watch -i 2                        # follow the live job [2]; heimdall runs --resume 2 resumes it once paused
heimdall stop --pid 12345                  # stop a job as Ctrl-C would (a job's own terminal: d leaves it running)
heimdall explain errand.events             # any key, table, tool option or style key
heimdall help run                          # any command
```

Housekeeping: `heimdall clean` (logs and caches nothing uses), `heimdall migrate --v3` (a v2 file in v3),
`heimdall migrate --layout` (a work dir from before `records/`), `heimdall reproduce records/…/provenance.json`,
`heimdall cluster CONFIG CFG` (Slurm), `heimdall report <A>/<E>/<R>` (an A4 report of a Run's pages and numbers),
`heimdall stack build|list|status|doctor`
(the machine's stack). [05 §1](05_Commands_and_Tools.md#1-commands).

## An errand file

```toml
# configs/Demo/mini.toml
[errand]
assignment = "Demo"
name    = "mini"
run     = "pdf"                           # what `heimdall run Demo/mini` runs
events  = 100_000
threads = 8
chain   = [["pythia", "rivet"], "yd2rt"]  # group 1 together (a FIFO between), then group 2 (a file)

[cfgs.single]                             # one point, at every quantity's fixed point

[cfgs.pdf]
vary = ["pdf"]                            # a point per PDF; a page per histogram, a curve per point

[tools.pythia]                            # the table's name is the tool (uses = "pythia" for a second one)
card   = "ep.cmnd"                        # configs/Demo/ep.cmnd: the physics
output = "events.hepmc"

[tools.rivet]
input    = "pythia"                       # what pythia writes
analyses = ["photo_eic"]
output   = "jets.yoda"

[tools.yd2rt]
input  = "rivet"
output = "jets.root"

[quantities.pdf]                          # the vocabulary maps it to Pythia's PDF:pSet
fixed  = "MSTW08lo"
points = [
  { tag = "MSTW08lo",  value = "LHAPDF6:MSTW2008lo68cl",         label = "MSTW 2008 LO" },
  { tag = "NNPDF23lo", value = "LHAPDF6:NNPDF23_lo_as_0130_qed", label = "NNPDF 2.3 LO" },
]

[plot]
formats = ["pdf", "png"]
ratio   = true
```

| To | Write | Page |
|---|---|---|
| vary two things as a grid; zip two | `vary = ["energies", "pdf"]`; `vary = [["pdf", "alphas"]]` | [04 §5.1](04_Config_Reference.md#51-vary) |
| a page per value of one | `plot_points = ["energies"]` | [04 §5.2](04_Config_Reference.md#52-plot_points) |
| a value no tool knows by name | `to = { pythia = "MultipartonInteractions:pT0Ref" }` | [04 §8.1](04_Config_Reference.md#81-who-consumes-a-quantity) |
| a Rivet option | `to = { "rivet/photo_eic" = "R" }` | 04 §8.1 |
| seed replicas, merged into one curve | `to = { "pythia/seed" = true }`, `combine = ["replica"]` | [04 §5.5](04_Config_Reference.md#55-combine) |
| several event counts | `events = [100_000, 1_000_000]` in a configuration | [04 §5.6](04_Config_Reference.md#56-events-as-a-list-one-configuration-per-count) |
| your own program | `uses = "module"` (Module.hh) or `uses = "exec"` (anything) | [04 §9.2](04_Config_Reference.md#92-exec-tools) |
| start from another file | `[file] import = ["validation"]` | [04 §3](04_Config_Reference.md#3-file) |
| a fixed folder number | `serial = 3` (else the runner numbers it, and never overwrites) | [04 §2](04_Config_Reference.md#2-paths) |
| the drawing tool's own range | `y_gutter = "native"`; `"default"` is always the layer below | [04 §1](04_Config_Reference.md#1-files-and-which-wins) |

## Where things go

| Folder of a work dir | Holds | git |
|---|---|---|
| `configs/<A>/`, `modules/<A>/` | yours: errand files, cards and report recipes; programs and Rivet analyses | tracked |
| `datasets/` | reference data (large ones listed in `datasets.toml`, fetched by `heimdall setup .`) | tracked |
| `results/<A>/<E>/<R>/` | `points/<point>/` the products, `plots/` the pages | no |
| `records/<A>/<E>/<R>/` | `points/<point>/` each point's provenance, identity and `.complete` (delete it and the point reruns); `logs/<point>/` its cards and configs, each tool's digest `<tag>.log`, earlier attempts in `history/` (deleting it reruns nothing: `heimdall clean`; more with `--keep`); `plots/` the page configs; `config/` the errand file and cards it ran with | no |
| `.cache/` | prepare caches: safe to delete | no |
| `build/`, `reports/<A>/<E>/<R>/` | compiled modules; reports, where `results/` has their sources | no |

`<A>/<E>/<R>` is an address: an **assignment** `<A>` (`configs/<A>/`), an **errand** `<E>` (its errand file
`configs/<A>/<E>.toml`, `[errand]`), a **Run** `<R>` (one configuration's folder, `NN_<label>`, with its record
and cache). One `heimdall run` is a job: it makes or resumes the Runs of the configurations it runs.
[02 §2](02_User_Guide.md#2-a-first-run).

When something fails: read `records/…/logs/<point>/<tool>.log`, fix, run again (complete points are
skipped). [02 §9](02_User_Guide.md#9-when-something-fails).
