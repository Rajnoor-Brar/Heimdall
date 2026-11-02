---
id: decisions-reports
summary: why heimdall report works as it does
---

# Decisions: reports

The full account of each is at tag `docs/pre-rebuild`, in `docs/07_Record.md`.

- **V103** `heimdall deck`: blocks collected. Retired by V212.
- **V133** Deck sources, datasets, the template; a work dir in a git repository.
- **V206** Plot and stats made modular for the report, their outputs unchanged.
- **V207** `heimdall report`: a source is a result folder holding a `plot.toml`.
- **V208** It builds under `reports/`, never under `results/` or a source.
- **V209** The run writes its folders' `report.toml`; reports mirror results.
- **V210** A report shows what each tool was given: baseline and varied options.
- **V211** A report draws for itself what a source has not drawn, since it shows vectors.
- **V212** `heimdall deck` retired: one deck was ever made.
- **V214** `reports/` is a run's output like the others.
- **V215** A report's look: one look, set once, in `report.tex`'s preamble.
- **V216** A report's statistics are typeset: a third renderer of one document.
- **V218** A report opens with context: what was run, how the numbers are made.
