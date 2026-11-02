---
id: tools-pythia
summary: the pythia tool and App_Pythia: its card, what the runner owns, dealing events, the sidecar, what running it taught us
code: framework/tools/pythia/tool.toml, framework/tools/pythia/diagnose.py, src/App_Pythia.cc, src/PythiaRun.hh, src/App_PythiaCheck.cc
---

# `pythia`

```toml
[tools.pythia]
card   = "ep.cmnd"              # beside this file
output = "events.hepmc"         # a FIFO, a file or a product, by its reader; an array fans out
```

- **Runs** `App_Pythia.exe <outputs> <base cards…> <point card>`, the point card last, so its settings win.
- **Card:** `cards/pythia.point.cmnd` has a line per consumed value, then seeds. `cards/pythia.cmnd` holds each key once (`[card] merge`), and `cards/pythia.json` gives each key's value and origin. Particle-data commands that add up (`id:onIfMatch`) are kept every time.
- **Keys the runner sets:** `Main:numberOfEvents`, `Parallelism:numThreads`, the `Random:` seeds, `Parallelism:seeds`, `Beams:LHEF`. A base card's line for one is never used, and `--plan` says so.
- **Checked at plan time:** `App_PythiaCheck.exe` gives every card line to Pythia's own reader; a rejected line refuses the plan, with its source. No key list is kept.
- **Consumes** `energies`, `sqrts`, `beam_a`, `beam_b`, `beams`, `pdf` (checked installed), `events`, `threads`; anything else with `to`.
- **Shower of an LHE file:** the tool's input becomes `Beams:LHEF`; the base card sets `Beams:frameType = 4`.
- **When init fails** (exit 3), the runner reads the same cards into one plain Pythia and quotes why: *"pythia exited with exit code 3; asked again: PYTHIA Error in ProcessLevel::init: …"*. Its output is `<tag>.diagnose.log`.

## App_Pythia

```
App_Pythia.exe [--threads N] [--events N] [--seeds S1,S2,…] [--sidecar FILE] OUTPUT[,OUTPUT…] CARD [CARD…]
```

Every comma-separated OUTPUT gets every event. An OUTPUT `A+B+C` is a **deal group**: each event goes to one member, the first free. So `events.s1.hepmc+events.s2.hepmc,to_module.hepmc` deals between two Rivet shards and copies every event to a module.

- `PythiaParallel` with `processAsync = on`: each instance converts with its own `Pythia8ToHepMC`, σ is combined under one small lock, and each output has its own writer.
- Outputs open only after `init()` succeeds, so a bad card leaves no half-open FIFO.
- Runs in chunks of a multiple of the thread count, so SIGINT takes effect within a chunk.
- A `.gz` or `.zst` suffix picks a compressed writer.

**The sidecar**, `<first output>.json`, is written after outputs close: `tool`, `pythia_version`, `requested`, `attempted`, `accepted`, **`written`** (what the count check compares; it can be below `requested`), `write_failures`, `sigma_pb`, `sigma_err_pb`, `sum_w`, `threads`, `seeds`, `outputs`, **`written_per_output`** (a shard's check), `cards`, `stopped`.

## What running it taught us

- **L1** σ over `PythiaParallel` instances is a ΣW-weighted mean, errors in quadrature. `PythiaParallel` exposes σ but no error.
- **L2** A CLI Rivet normalises to the σ in the last event it reads, and `Pythia8ToHepMC` stamps each event with its own thread's running σ. So threads > 1 means a wrong normalisation unless handled: App_Pythia re-stamps every event with the combination.
- **L4** `Parallelism:seeds` is applied once in `init()`. Its length must equal the thread count, and each seed must be in 1…9·10⁸. Pythia does not check, so App_Pythia does.
- **L5** `Main:numberOfEvents` counts `next()` attempts, and failed events never reach the callback: ~2% at 5×41 GeV, 1e-4 at 27×920. So written ≠ requested.
- **L6** Repeated `run()` after one `init()` is σ-consistent, and a chunk size that is a multiple of the thread count reproduces the unchunked event set.
- **L23** Photoproduction card facts: with this card, `Photon:ProcessType` 0 and 1 give identical events, and direct needs its own card; `pTHatMin` 6 sits above jet `ETMIN` 5 and biases the lowest bins.
- **L25** Kept event files: zstd beats gz on every axis measured (2.1× faster to write, 1.26× to read, smaller).
- **L27** What sets a Pythia → Rivet point's pace (ZEUS_2012, i7-13700K): one Rivet reads ~1,500 events/s, whatever Pythia's threads. So split Rivet.

More on threads and on σ across outputs: [cxx-kits](../internals/cxx-kits.md), [connections](../internals/connections.md).
