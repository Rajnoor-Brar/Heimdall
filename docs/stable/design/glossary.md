---
id: glossary
summary: Heimdall's words beyond the model's core vocabulary; the core ones are in the model page
---

# Glossary

The core words (assignment, errand, configuration, Run, job, quantity, point, tool, group, stage, object, figure, page) are in [model](../start/model.md).

| Term | Means |
|---|---|
| **Heimdall** | the framework's repository, `$HEIMDALL` |
| **Himinbjorg** | what a machine built, `$HEIMDALL_MACHINE`, by default `~/Himinbjorg` (once: machine root) |
| **work dir** | a folder whose `heimdall.toml` has `[work]`: a study |
| **package** | a recipe of the stack |
| **library** | what a `// requires:` line names, from `env/stack.toml` |
| **tool folder** | what the runner knows about a kind of tool |
| **toolkit** | a named set of packages (`@primary`, yours); an **isolated** one has its own `stacks/<toolkit>/` |
| **base** | the conda environment the stack builds with |
| **card** | a tool's native configuration file. A **base card** is yours; a **point card** is what the runner renders from it |
| **cell** | a group of points sharing a page |
| **set** | a named choice of cells and curves; `totality` when there are none |
| **integrated program** | one process running what a chain would, given the chain's cards |
| **sidecar** | a producer's small JSON beside its product: written, σ, seeds |
| **identity** | the hash of what decides a point's result |
| **plot document** | `results/<A>/<E>/<R>/plot.toml`, what every drawing reads |
| **record** | a Run's folder in `records/`; with its snapshot, itself a config |
| **live doc**, **crystallise** | see [work](../../rules/work.md) |
