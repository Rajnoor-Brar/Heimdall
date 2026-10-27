# {{name}}

A Heimdall work dir (made by `heimdall setup` on {{date}}). Heimdall, the framework and its stack, is
elsewhere: `heimdall where` says which one this shell uses. Its manual is `$HEIMDALL/docs/README.md`.
`gjallarhorn {{name}}` loads Heimdall's environment and comes here, from anywhere (`heimdall recognise
--list` shows the titles this machine knows); `bifrost <pkg>` adds a package to the environment.

| Folder | Holds | In git |
|---|---|---|
| `configs/<Project>/` | run TOMLs and their cards (`.cmnd`, `.in`, `.yaml`, …) | yes |
| `modules/<Project>/` | your programs (`X.cc` → `build/<Project>/X.exe`) and Rivet analyses (`Rivet/<x>.cc`) | yes |
| `datasets/` | input files a run reads (`data = "…"`): small ones tracked; large ones listed in `datasets.toml` (url, sha256), which `heimdall setup .` fetches | yes |
| `results/<P>/<run>/<cfg>/` | what matters once a run is done: `points/<point>/` the products, `plots/<set>/` the pages (`totality` with no sets), `statistics/<set>/` their numbers against the data | no |
| `records/<P>/<run>/<cfg>/` | what a run needs while it runs or is launched, and what traces it back: `points/<point>/` each point's provenance, identity and completion (keep it with `results/`); `logs/<point>/` its cards, configs and a failed tool's last lines (safe to delete: `heimdall clean`); `config/` the run TOML and cards it ran with (`heimdall plot <P>/<run>/<cfg>` draws from it) | no |
| `.cache/` | what is rebuilt when needed: prepare caches, the drawings' page documents and working files (`plots/`), converted data; safe to delete | no |
| `reports/<P>/<run>/<cfg>/` | reports of runs' pages and numbers, as `heimdall report <P>/<run>/<cfg>` builds them where `results/` has their sources; their recipes are in `configs/` | no |
| `build/` | compiled modules and Rivet plugins (`heimdall build`) | no |

```bash
heimdall ls                          # every config and its configurations
heimdall build                       # compile modules/
heimdall run <Project>/<config>      # plan and run (add --plan to look first)
```

Git keeps no empty folders: after a fresh clone, `heimdall setup .` makes the missing ones again, and
fetches the files `datasets.toml` lists. `heimdall setup . --refresh` brings this file, `CLAUDE.md` and the
`Makefile` up to date with Heimdall's template.
