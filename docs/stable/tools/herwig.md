---
id: tools-herwig
summary: the herwig tool: read and run, beams in Herwig's slots, its four PDF objects, the repository
code: framework/tools/herwig/tool.toml, framework/tools/herwig/quantities.toml
---

# `herwig`

```toml
[tools.herwig]
card   = "dis_ep.herwig.in"
output = "events.hepmc"
```

- **Prepare**, cached per card: `Herwig read --repo={apps}/Herwig/HerwigDefaults.rpo <card>`. `heimdall build --framework` makes the repository; a plan without it is refused.
- **Runs** `Herwig run <cache>/point.run -N <events> -s <seed> -d 0`. Events and seed are flags, so every point with the same physics shares one read.
- **Card:** ThePEG `set {key} {value}` lines, a later one wins. The footer reads HepMC output and must come last.
- **Beams** go in Herwig's slots, `[beams] slots = ["lepton", "hadron"]`: the runner reorders the run's values.
- **Consumes** `energies`, `sqrts`, `pdf`.
- **Sidecar** written by the runner: Herwig makes exactly `-N` events or fails.
- **Context file:** `card`; the product `"herwig:run"`, prepared on demand.

## What running it taught us

- **L15** Build ThePEG and Herwig `--with-hepmc --with-hepmcversion=3` (the default 2 fails). ThePEG's `RivetAnalysis` does not build against Rivet 4, and is not needed.
- **L30** Herwig's PDFs are four LO objects: `/Herwig/Partons/HardLOPDF`, `ShowerLOPDF`, `MPIPDF`, `RemnantPDF`, each set by `:PDFName`. `pdf` sets the four; NLO objects and a member stay the card's.
