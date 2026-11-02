---
id: tools-plotmerge
summary: the plotmerge tool: the sweep in one file, as a copy elsewhere or a YODA version
code: framework/tools/plotmerge/tool.toml
---

# `plotmerge`

```toml
[tools.bundle]
uses   = "plotmerge"
input  = "jets.yoda"
output = "sweep.root"            # or sweep.yoda
```

Runs `App_yd2rt.exe --merge`: not a statistical merge (that is [`merge`](merge.md)). The plot stage makes the same file itself in `.cache/`, so this tool is for a copy elsewhere, or a YODA version.
