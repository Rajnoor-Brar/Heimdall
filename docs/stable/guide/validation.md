---
id: validation
summary: every rule checked at plan time, C1–C14, with an example message
code: framework/runner/config.py, framework/runner/tools.py, framework/runner/quantities.py, framework/runner/sweep.py
---

# Validation rules

All are checked at plan time. Every error names the file and key and gives a hint; a misspelt name gets the nearest spelling. `heimdall run` exits 2 on any, before anything runs. `heimdall check` runs them over every config and runs nothing.

| # | Rule | Example |
|---|---|---|
| **C1** | An unknown section or key is an error; a tool-specific key is checked against its folder's `[options]`. | `unknown key 'min_entry'` · `did you mean 'min_entries'?` |
| **C2** | `[errand].run`, and a configuration named on the command line, must name a `[cfgs.<name>]`. | `no configuration 'energy-pdf'` |
| **C3** | Every `vary` entry names a declared quantity; entangled ones have equal point counts; none varied twice. | `entangled quantities need equal value counts` |
| **C4** | `plot_points` names only quantities varied here. | `plot_points names 'mpi', which is not swept here` |
| **C5** | Every `chain`, `pre`, `post` entry is a tool table; groups nest one level; an `@q` entry's values make a valid chain. | `'pythya' is not a [tools.<tag>] table` |
| **C6** | Connections: a FIFO within one group, one reader, a writer for every FIFO, none into a non-streamable tool; every input made or on disk; one writer per output. | `'delphes' cannot read a FIFO` |
| **C7** | Every active quantity has a consumer in the chain. | `[quantities.lepton] is set but no tool in this chain consumes it` |
| **C8** | One source per native key in one card. | `'PDF:pSet' is set by both …` |
| **C9** | A Rivet analysis has a `.info`, and every option given is declared there. | `'photo_eic' does not declare the option RADIUS` |
| **C10** | Providers: a named PDF set is installed; base configs exist; executables are built; files a folder needs exist. | `the PDF set 'CT14lo' is not installed` |
| **C11** | Point directory names are unique. | `these points would share a directory: …` |
| **C12** | Paths: no `../`; a missing file is reported under its root. | `'../cards/x.cmnd' climbs out of its root` |
| **C13** | `generate_cards` names tool tables, and `"<tag>:<product>"` a product that folder makes. | `pythia makes no product 'run'` |
| **C14** | `combine` names quantities varied here as their own axes, none in `plot_points`. | `'replica' is both combined and a page axis` |

The plot checks have the same shape: an unknown backend, format, gutter, data, figure or style key; a data file without a map; a style key a backend cannot honour; a band or `over` that is not a curve axis; a figure's class rules; a TLatex label; a page text citing what the points lack.
