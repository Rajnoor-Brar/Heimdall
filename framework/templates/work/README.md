# {{name}}

A Heimdall work dir (made by `heimdall setup` on {{date}}). Heimdall, the framework and its stack, is
elsewhere: `heimdall where` says which one this shell uses. Its manual is `$HEP/docs/README.md`.
`gjallarhorn {{name}}` loads Heimdall's environment and comes here, from anywhere (`heimdall recognise
--list` shows the titles this machine knows); `bifrost <pkg>` adds a package to the environment.

| Folder | Holds | In git |
|---|---|---|
| `configs/<Project>/` | run TOMLs and their cards (`.cmnd`, `.in`, `.yaml`, …) | yes |
| `modules/<Project>/` | your programs (`X.cc` → `build/<Project>/X.exe`) and Rivet analyses (`Rivet/<x>.cc`) | yes |
| `datasets/` | input files a run reads (`data = "…"`): small ones tracked; large ones listed in `datasets.toml` (url, sha256), which `heimdall setup .` fetches | yes |
| `decks/<deck>/` | your decks (`deck.md`, `deck.toml`), built into `reports/<deck>/` by `heimdall deck <deck>` | yes |
| `results/` | what runs produce: the points' products and the pages | no |
| `records/` | what runs recorded: each point's provenance, identity and completion; keep it with `results/` | no |
| `logs/` | each point's cards and configs, a failed tool's last lines, the page configs: safe to delete (`heimdall clean`) | no |
| `.cache/` | prepare caches (and card checks, converted data with `keep cache`): rebuilt when needed | no |
| `reports/` | the decks' slides, as `heimdall deck` builds them | no |
| `build/` | compiled modules and Rivet plugins (`heimdall build`) | no |

```bash
heimdall ls                          # every config and its configurations
heimdall build                       # compile modules/
heimdall run <Project>/<config>      # plan and run (add --plan to look first)
```

Git keeps no empty folders: after a fresh clone, `heimdall setup .` makes the missing ones again, and
fetches the files `datasets.toml` lists. `heimdall setup . --refresh` brings this file, `CLAUDE.md` and the
`Makefile` up to date with Heimdall's template.
