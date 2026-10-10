# {{name}}

A Heimdall work dir (made by `hep setup` on {{date}}). Heimdall, the framework and its stack, is
elsewhere: `hep where` says which one this shell uses. Its manual is `$HEP/docs/README.md`.

| Folder | Holds | In git |
|---|---|---|
| `configs/<Project>/` | run TOMLs and their cards (`.cmnd`, `.in`, `.yaml`, …) | yes |
| `modules/<Project>/` | your programs (`X.cc` → `build/<Project>/X.exe`) and Rivet analyses (`Rivet/<x>.cc`) | yes |
| `datasets/` | input files a run reads (`data = "…"`) | no |
| `results/` | what runs produce: points, pages, provenance | no |
| `output/` | the runner's technical files: logs, the live view's state | no |
| `reports/` | decks of slides (`hep deck`) | no |
| `build/` | compiled modules and Rivet plugins (`hep build`) | no |

```bash
hep ls                          # every config and its configurations
hep build                       # compile modules/
hep run <Project>/<config>      # plan and run (add --plan to look first)
```

Git keeps no empty folders: after a fresh clone, `hep setup .` makes the missing ones again.
