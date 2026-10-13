# 00 — Quick reference

One page: the commands, a whole run TOML, where things go. Each line points to the page that says
it in full.

## Every day

```bash
hep setup ~/Study --example jets      # a work dir, with the demo project (--project P: a starter; --git: commit)
hep build                             # the work dir's Rivet analyses and module programs
hep check                             # every config: loaded, validated, every point planned; nothing run
hep run Demo/jets pdf --dry-run       # the plan: cards, argv, connections (also --why, --show-config)
hep run Demo/jets pdf                 # run what is not complete, then draw the pages
hep run Demo/jets pdf --set run.events=50000 --points 2   # one value changed, one point, for this run
hep status Demo/jets                  # each point: complete, stale, running, incomplete, to run
hep plot Demo/jets pdf                # redraw from what is on disk
hep watch                             # follow a run from another terminal
hep explain run.events                # any key, table, tool option or style key
hep help run                          # any command
```

Housekeeping: `hep clean` (logs and caches nothing uses), `hep migrate --v3` (a v2 file in v3),
`hep migrate --layout` (a work dir from before `records/`), `hep reproduce records/…/provenance.json`,
`hep cluster CONFIG CFG` (Slurm), `hep deck <deck>` (slides), `hep stack build|list|status|doctor`
(the machine's stack). [05 §1](05_Commands_and_Tools.md#1-commands).

## A run TOML

```toml
# configs/Demo/mini.toml
[run]
project = "Demo"
name    = "mini"
run     = "pdf"                           # what `hep run Demo/mini` runs
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
| `configs/<P>/`, `modules/<P>/`, `decks/<deck>/` | yours: run TOMLs and cards; programs and Rivet analyses; decks | tracked |
| `datasets/` | reference data (large ones listed in `datasets.toml`, fetched by `hep setup .`) | tracked |
| `results/<P>/<run>/<NN_cfg>/<point>/` | the products, and `plots/` (the pages) | no |
| `records/…` | each point's provenance, identity and `.complete`: delete it and everything reruns | no |
| `logs/…`, `.cache/` | cards, logs, FIFOs; prepare caches: safe to delete (`hep clean`) | no |
| `build/`, `reports/<deck>/` | compiled modules; built decks | no |

When something fails: read `logs/…/<point>/logs/<tool>.log`, fix, run again (complete points are
skipped). [02 §9](02_User_Guide.md#9-when-something-fails).
