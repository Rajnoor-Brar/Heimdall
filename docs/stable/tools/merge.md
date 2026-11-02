---
id: tools-merge
summary: the merge tool: rivet-merge, in post; also what shards, combine and merged figures use
code: framework/tools/merge/tool.toml
---

# `merge`

```toml
[tools.merge]
input      = "jets.yoda"         # that product of every point
output     = "merged.yoda"
equivalent = true                # -e: runs of one process; false merges different processes into their sum
```

Runs `rivet-merge [-e] -o <partial output> <every point's input>`. With `-e`, statistics add and σ is averaged. It reruns the analyses' `finalize()`, so they must be re-entrant. The runner also uses it for shards, each `combine` group, and `merged` figures. A post recipe: [scale](../guide/scale.md).
