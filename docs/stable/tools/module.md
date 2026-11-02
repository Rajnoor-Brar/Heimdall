---
id: tools-module
summary: the module tool: running a Module.hh program; its config, counts and integrated programs
code: framework/tools/module/tool.toml, src/Module.hh
---

# `module`

- **argv:** `{exe} {config} --input={input} --output={partial:output} --events={events} --sidecar={input_sidecar} {arguments}`.
- **Status:** standard. **Count check:** `events` from its report, `<output>.json`, against the producer's sidecar.
- **An empty `--input=`** means an integrated program, reading cards from the context file, which `generate_cards` fills.
- **Settings:** every key of its config must be one the program reads; a misspelt one is refused before the first event, with the nearest name. `<Name>.exe --describe` and `heimdall explain <Name>.exe` list them.

Recipes: [programs](../guide/programs.md). The kit: [cxx-kits](../internals/cxx-kits.md).
