# {{name}}

A Heimdall work dir (made by `hep setup` on {{date}}). Heimdall, the framework and its stack, is
elsewhere: `hep where` says which one this shell uses. Its manual is `$HEP/docs/README.md`.

| Folder | Holds | In git |
|---|---|---|
| `configs/<Project>/` | run TOMLs and their cards (`.cmnd`, `.in`, `.yaml`, …) | yes |
| `modules/<Project>/` | your programs (`X.cc` → `build/<Project>/X.exe`) and Rivet analyses (`Rivet/<x>.cc`) | yes |
| `datasets/` | input files a run reads (`data = "…"`) | no |
| `results/` | what runs produce: the points' products and the pages | no |
| `records/` | what runs recorded: each point's provenance, identity and completion; keep it with `results/` | no |
| `logs/` | each point's cards, logs and FIFOs; journals: safe to delete (`hep clean`) | no |
| `.cache/` | prepare caches, card checks, converted data: rebuilt when needed | no |
| `reports/` | decks of slides (`hep deck`) | no |
| `build/` | compiled modules and Rivet plugins (`hep build`) | no |

```bash
hep ls                          # every config and its configurations
hep build                       # compile modules/
hep run <Project>/<config>      # plan and run (add --plan to look first)
```

Git keeps no empty folders: after a fresh clone, `hep setup .` makes the missing ones again.
