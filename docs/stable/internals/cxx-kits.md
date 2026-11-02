---
id: cxx-kits
summary: writing C++ here: Module.hh, integrated programs, Status.hh and the status protocol, heimdallkit
code: src/Module.hh, src/Status.hh, src/Kit.hh, src/PythiaRun.hh, framework/heimdallkit.py
---

# The C++ kits

## Rules

- **A few headers only.** A helper a second program needs goes into `src/`; until then it lives in `modules/<A>/`.
- **An app speaks the status protocol** and uses `Kit::Exit`.
- **Outputs are written atomically:** a partial name, renamed on success. A stopped program writes what it has, marked partial, and exits 6.
- **Delphes declares a global `class Event`; X11 `#define`s `Status`,** so check a namespace against the toolchain.

## `Module.hh`

A module is a plain program in `modules/<A>/<Name>.cc`, built to `build/<A>/<Name>.exe`.

```cpp
// modules/Decay/Decay.cc          requires: root   (Module.hh adds hepmc3 toml)
#include "Module.hh"
#include "TH1D.h"

int main(int argc, char** argv) {
    Module::Job job(argc, argv);                        // CONFIG.toml --input= --output= --events= --sidecar=
    const double massTol = job.config().get("mass_tolerance", 0.15);
    Module::RootOut out(job.output());                  // written when the job finishes
    auto* mass = out.book<TH1D>("mass", ";m_{p#pi} [GeV];dN", 100, 1.08, 1.16);

    for (const Module::Event& event : job.events())     // file or FIFO, plain/gz/zst
        for (const auto& candidate : reconstruct(event.hepmc(), massTol))
            mass->Fill(candidate.mass, event.weight());

    out.scale(job.crossSectionPb() / job.sumW(), "width");   // once; "width" for a density
    return job.finish();
}
```

| Call | Does |
|---|---|
| `job.config()` | a `Values` view: `get`, `has`, `list`, `table`, `raw`. A top-level key the program never read is refused |
| `job.setting(key, fallback, doc)` | `config().get` with a doc, shown by `--describe` and `heimdall explain <Name>.exe`. Read settings first |
| `job.events()` | iterates `Module::Event`s; counts events and ΣW, reports progress, stops on a signal |
| `event.hepmc()`, `event.weight()` | the event; its first weight (1 if none) |
| `job.count()`, `job.sumW()` | so far |
| `job.crossSectionPb()`, `…ErrPb()` | from `--sidecar` when given, else the last event's `GenCrossSection` |
| `job.tool(name)`, `job.card(name)` | a tool of the point's context file |
| `job.hasInput()`, `job.countEvent(w)`, `job.setCrossSection(pb, err)` | for an integrated program |
| `job.progress(done, total)`, `job.status()`, `job.fail(code)`, `job.stopping()` | status and early exit |
| `job.finish()` | writes every output, then `<output>.json`; returns the exit code |
| `RootOut::book<H>("Dir/name", …)`, `out.scale(factor, option)` | once, after the loop: fill raw, scale once |

A module runs single-threaded.

- **L21** Rivet writes densities (dσ/dx). A module writing per-bin integrals differs by the bin width, so one plotted beside Rivet must divide by the width.
- **L3** `PythiaParallel` runs the callback on worker threads in both modes. An exception must be caught at the thread boundary, or it reaches `std::terminate`.

## Integrated programs

`modules/Demo/InprocJets.cc` runs with `generate_cards = ["pythia", "rivet"]` and reads both from the context file, so it gets the chain's card, seeds and analyses. It runs Pythia through `PythiaRun.hh`, and `rivet_threads` handlers on their own threads. Headers in `modules/Demo/Inproc/`: `Stamp.hh` (numbering, run info, the combined σ), `Feed.hh` (a bounded queue; whichever Rivet is free takes the next event), `Analysis.hh` (handlers initialised on the first event; `merge` into the first before any `finalize`), `Engines.hh` (`serial`, `parallel`).

Several Rivets in one process need SISCone's state per thread: `recipes/patches/fastjet-3.5.0-siscone-thread-local-ranlux.patch`, applied by `build_stack.py`. A single-threaded Rivet gives byte-identical YODAs with it.

| 200k events of `single`, ~5 s start-up included | photo_eic | ZEUS |
|---|---|---|
| chain, 12 threads + 10 shards | 29.0 s | 27.1 s |
| in one process, 12 + 1 Rivet | 112 s | — |
| in one process, 12 + 12 Rivets | 20.7 s | — |
| in one process, 10 + 14 Rivets | 19.3 s | 17.3 s |

- **L16** FastJet SISCone keeps process-wide statics: threads change the jets rather than crashing. A threaded module that clusters must not share them.
- **L29** Those are two pieces of state: the `ranlux` generator drawing each particle's reference, and one η range. Two threads clustering at once is a data race.

## The status protocol

A tool with `status = "standard"` writes JSON lines to the fd in `$HEIMDALL_STATUS_FD`, each `{"t": <unix time>, "k": <kind>, …}`. Unknown kinds reach the event stream and are otherwise ignored, so the set can grow.

| Kind | Fields | Shown as |
|---|---|---|
| `phase` | `phase`, `detail` | the tool's phase |
| `progress` | `done`, `total`, `rate` | bar, rate, ETA |
| `xsec` | `value_pb`, `err_pb`, `final` | σ |
| `log` | `level`, `msg` | the last warning or error |
| `summary` | tool-defined | the event stream only |
| `heartbeat` | | keeps it from counting as stalled |

**C++:** `#include "Status.hh"` before any X11 header, then `Status::Reporter status;`. `phase`, `progress` (at most every 0.25 s unless forced), `xsec`, `log`, `summary`, `dropped`. Writes are non-blocking and drop on a full pipe, so a slow reader never slows a generator. With the variable unset, plain stderr lines.

**Python:** `framework/heimdallkit.py`: `Status()`, `report(output, **fields)`, `Exit`, `stopping()`, `usage()`. Any other language writes the same lines.

```python
import heimdallkit                 # on the path through heimdall.pth
status = heimdallkit.Status()
status.progress(500, 10_000, 120.0)
heimdallkit.report(output, events=500)
```
