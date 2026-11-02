---
id: tools-exec
summary: the exec tool: any executable; heimdallkit; turning a program into a tool folder of your own
code: framework/tools/exec/tool.toml, framework/heimdallkit.py
---

# `exec`

Any executable: argv is `{exe} {config} {arguments}`. Status is `none` unless the table sets it. A recipe: [programs](../guide/programs.md).

**A program as a tool of your own.** `heimdall tools new unfold --from exec --runs unfold-it --package root` writes `tools/unfold/tool.toml`, with `executable` and `packages` filled. Then, in it:

- `[card] style`: `none` (values become arguments or config), `append` (base cards, then the point's lines, with `line = "{key} = {value}"`), or `render`.
- `[command] argv`: `{exe}`, `{card}`, `{config}`, `{input}`, `{partial:output}`, `{events}`, `{seed}`, and `[options]`.
- `[outputs]`: what it writes, how its event count is read back, a producer's sidecar.
- `status`: `standard`, `filters`, or `none` (its log's last line is shown).
- `[identity] files = ["{exe}"]`: what of it makes a point's identity.

Every key: [tool-contract](../internals/tool-contract.md). A library used from C++ is not a tool: a module links it.
