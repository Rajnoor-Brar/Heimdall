---
id: tools-rivet
summary: the rivet tool: analyses and options, shards and how many, counts; what running it taught us
code: framework/tools/rivet/tool.toml, framework/tools/rivet/render.py
---

# `rivet`

```toml
[tools.rivet]
input    = "pythia"                      # what the pythia table writes
analyses = ["photo_eic", "MC_JETS"]      # "NAME" or "NAME:OPT=V:OPT=V"
options  = { R = 0.4 }                   # given to every analysis (optional)
output   = "jets.yoda"
```

- **Runs** `rivet -o <partial output> -a <analysis[:options]>… <input>`, with `RIVET_ANALYSIS_PATH = build/Rivet`.
- **Options**, in increasing precedence: `options`; the analysis's inline `NAME:OPT=V`; quantities targeting `"<tag>/<analysis>"`. Each analysis needs a `.info` (`build/Rivet/`, then `rivet-config --datadir`), and every option given must be declared there.
- **Consumes** nothing through the vocabulary: beams and energies come from the events.
- **σ** is the last event's `GenCrossSection`.
- **Count check:** `/RAW/_EVTCOUNT` against the producer's `written`.
- **Identity** includes each plugin's `.so`.
- **Page texts:** `{opt:NAME}`, each option at the point.

## `shards = K`

Details of the rewrite: [connections](../internals/connections.md). What you need to know:

- The chain does not change, and neither do the events. The merged YODA is the same up to rounding. The identity does change, so changing `shards` reruns the point.
- **Refused at plan time unless:** the tool reads one input and writes one output; the input has one producer whose folder can deal (`pythia`); every analysis is re-entrant (`Reentrant: true`), because `rivet-merge -e` runs `finalize()` again.
- Other outputs of the producer still get every event. Quantities aimed at the table reach every shard.
- **Choosing K:** `threads + shards` should not exceed the machine.

| `threads` + `shards` (i7-13700K, 24 hardware threads, 200k ZEUS_2012) | events/s |
|---|---|
| 20 + unsharded | ~1,570 |
| 8 + 8 | ~8,100 |
| 12 + 10 | ~9,200 |
| 14 + 10, 10 + 12 | the same: the CPU is full |

## What running it taught us

- **L7** `/RAW/_EVTCOUNT` is the analysed-event count, so it is the check against the generator.
- **L9** Rivet initialises from the first event (beams from the event); `setCheckBeams` decides whether a beam change is fatal.
- **L10** Rivet 4.1.3 skips `finalize` in a periodic dump for a non-reentrant analysis, so a dump is unscaled. Do not rely on dumps.
- **L18** Reference data is matched by an explicit map, never by name: ZEUS `d08` is not the same observable as `photo_eic`'s `d08`.
- **L19** A Rivet option not declared in the `.info` is silently ignored, giving identical curves. Check options against the `.info`.
- **L20** `rivet-build` needs include paths for shared headers, and the ONNX path when the `.info` says `Requires: ONNX`.
