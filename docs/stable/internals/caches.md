---
id: caches
summary: the prepare cache: what it keeps, its key, what counts as a hit
code: framework/runner/tools.py, framework/runner/execute.py
---

# The prepare cache

A tool folder may declare a **prepare step**: slow work that depends on the card but not the seed or event count, such as Sherpa's and Whizard's integrations, `Herwig read` or MadGraph's process directory.

- **Where:** before the point's groups, as its own supervised step (at least an hour before it counts as stalled), in `.cache/<A>/<tool>/<key>/`.
- **The key:** the tool, its binary's sha256, the base cards' sha256 and the card lines, without the lines the folder ignores (event count, seed). With `key = "base"`, the base cards alone (MadGraph builds from the proc card). So every point, replica, rerun and event count with the same physics shares one entry.
- **A hit:** the entry holds a `.prepared` stamp, written only after the step exited 0 and left its `marker` file. An interrupted integration is redone, never used.
- **The stamp** holds what ran, when, its `seconds`, `card_sha256`, and the `record` and `point` that filled it; the step's digest is copied in as `prepare.log`, and a hit names it. Its name stays `.prepared`: renaming it would integrate every Sherpa point again.
- **In use:** `{prepared}` names the entry in argv and cards; `--plan` shows each step and whether it is cached. A product asked for in `generate_cards` (`"herwig:run"`) runs the step on demand.
- **Shared safely:** see [run-flow](run-flow.md).
