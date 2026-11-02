---
id: tools-yd2rt
summary: the yd2rt tool and App_yd2rt: YODA to ROOT, merging a sweep into one file
code: framework/tools/yd2rt/tool.toml, src/App_yd2rt.cc
---

# `yd2rt`

```toml
[tools.yd2rt]
input  = "rivet"
output = "jets.root"
select = ["/photo_eic/*"]     # optional: YODA path globs; default every object but /RAW and /TMP
```

```
App_yd2rt.exe IN.yoda OUT.root [GLOB …] [--keep-raw]
App_yd2rt.exe --merge OUT.root|OUT.yoda NAME=IN.yoda … [--keep-raw] [--select GLOB] [--points FILE]
```

| YODA | ROOT |
|---|---|
| `Histo1D`, `Estimate1D` | `TH1D` (an Estimate's error is the average of its down and up errors) |
| `Histo2D`, `Estimate2D` | `TH2D` |
| `Scatter2D` | `TGraphAsymmErrors` |
| `Counter`, `Estimate0D` | a one-bin `TH1D` |

- **Directories nest as the YODA path does.** A variant `/photo_eic:R=0.4/…` becomes `photo_eic__R-0.4/…`. Each object's title is its original path, and the `paths` TTree maps back.
- **`/RAW`, `/TMP`** are skipped unless `--keep-raw`, which also writes `<name>__entries` per-bin raw counts, which Paint's `min_entries` reads.
- **`--merge`:** each input's objects go under a directory named for it. Into `.yoda`, the name is a path prefix.
