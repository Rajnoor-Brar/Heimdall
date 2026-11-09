---
id: tools-overview
summary: the standard tools at a glance; tools, packages and libraries; what is not a tool
code: framework/tools
---

# The standard tools

A **tool** is a folder, `framework/tools/<tool>/`, and its name is its table's name, or `uses = "<tool>"`. A work dir's `tools/<tool>/` and Himinbjorg's come first, and may replace or extend one. `heimdall tools` lists them all. Keys: [tools settings](../../reference/settings/tools.md).

A folder says how a run drives a program. The program comes from a **package** (a recipe), built into `stack/` or taken ready-made into the base; a **library** is what a module links (`// requires:`). A config never sees how a package was installed: the program is found on `PATH`. `heimdall tools` shows how each is installed; a missing program says which package to get (`bifrost -b sherpa` builds it, `bifrost -c sherpa` takes it ready-made). Switching changes its bytes, so the points that ran it run again.

| Tool | Kind | Runs | Card | Reads a FIFO | Status | Count check | Prepare |
|---|---|---|---|---|---|---|---|
| [`pythia`](pythia.md) | event generator | `App_Pythia.exe` | `.cmnd`, append | — | standard | produces a sidecar | — |
| [`rivet`](rivet.md) | analysis | `rivet`, or K: `shards` | none | yes | filters | `/RAW/_EVTCOUNT` | — |
| [`yd2rt`](yd2rt.md) | conversion | `App_yd2rt.exe` | none | file | standard | — | — |
| [`merge`](merge.md) | post | `rivet-merge` | none | files | none | — | — |
| [`plotmerge`](plotmerge.md) | post | `App_yd2rt.exe --merge` | none | files | standard | — | — |
| [`exec`](exec.md) | any | your `executable` | none | per table | none, unless set | if you set it | — |
| [`module`](module.md) | analysis | your `Module.hh` program | none | yes | standard | its report's `events` | — |
| [`delphes`](delphes.md) | detector simulation | `DelphesHepMC3` | `.tcl`, append | **no** | filters | the `Delphes` tree | — |
| [`herwig`](herwig.md) | event generator | `Herwig run` | `.in`, append | — | filters | runner-written sidecar | `Herwig read` |
| [`sherpa`](sherpa.md) | event generator | `Sherpa` | `.yaml`, render | — | filters | runner-written sidecar | integration |
| [`whizard`](whizard.md) | process generator | `whizard` | `.sin`, render | — | filters | runner-written sidecar | integration |
| [`madgraph`](madgraph.md) | process generator | `mg5_aMC` | launch script, render | — | filters | runner-written sidecar | process directory |

`framework/tools/lhapdf/` is a provider, not a chain tool: a mapping with `check = "lhapdf:bare"`, `"lhapdf:set"` or `"lhapdf:pythia"` refuses an uninstalled PDF set and writes it in that tool's spelling. Paint is driven by the plot stage and never named in a chain.

**Not tools at all:** analysis algorithms (FastJet, ROOT libraries) are `// requires:` names. Geant4 is a module program with `// requires: geant4`. Statistics (RooFit, pyhf, uproot) are exec tools, usually in `post`.

## What matching generators takes

- **L24** Cross-generator photoproduction: match EPA Q²max, the photon PDF (CJKL vs CJKLLO), the proton PDF and the order. Measured at 18×275 LO MPI-off: 11,950 ± 34 pb (Pythia) vs 9,636 ± 782 pb (Sherpa).
