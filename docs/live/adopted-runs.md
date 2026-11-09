---
id: live-adopted-runs
summary: an adopted Run reads, numbers and draws as before (its points library points by their links, its plot document re-keyed); migrate --layout leaves statistics/ alone
affects: outputs, identity
issue: I-130
---

**Now holds:** a point whose `records/<A>/<E>/<R>/points/<name>` is a link into `<A>/library/` (`library.linked`) is planned as a library point (`plan.library = library.key(plan)`, `cli._planned_points`), even when its config does not pool. So a Run that `heimdall library adopt` moved in still reads complete for `status`, keeps its number when a config without a serial is planned, and a rerun writes its own entry under the entry's lock, never through a link that another Run shares. `heimdall migrate --layout` leaves a Run's `results/…/statistics/` (V164) and an Errand's `compare/`, `plots/` and `statistics/` (its across pages) where they are (`migrate.RESULT_FOLDERS`, `ERRAND_FOLDERS`).

**No longer holds:** an adopted Run whose config does not pool reading `stale` (its `.complete` holds the key, its plan the identity), and its config planning a new Run to rerun every point. `migrate --layout` moving `statistics/` into `points/statistics`, and an Errand's `plots/<set>` into `plots/points/<set>`.

**Decisions:**
- **V263** A link into the library makes a point a library point; the link is the record of the adoption, so the config need not say `library = true`.
- **V267** Adopt rewrites the Run's plot document with the keys, and a library point whose link names another entry is judged by that entry.
- **V264** An Errand's folder in `results/<A>/<E>/` is a Run only when it is none of `compare`, `plots`, `statistics`.

**Adopt rewrites the plot document** too (`plotdoc.rekey`, handed to `library.adopt` by the command): each member that ran with an identity it adopted names the key instead, as a run writes a library point, and only those lines change. **A library point's folder is judged by its link** (`record.recorded_identity`): a link to another entry than its key's holds other physics in that Run, so the point is stale there and the folder made from other inputs, and a config without a serial numbers past it, as before adopting. A stale adopted point reads `stale`.

**`prune --duplicates` keeps a duplicate drawn with another seed** than its entry (`library._independent`): other events, not a copy, said with both seeds. A duplicate with the same seed is the same events, and goes.

**Checked on a real work dir** (2026-11-09, 42 Runs, 886 entries, 274 duplicates linked): `heimdall status` of every Run and the points each plot document draws were the same after adopting as before.

**Stable pages need:** [outputs](../stable/guide/outputs.md): what adopt rewrites (`points.json`, the plot document), and that the Run's config need not pool. V263, V264 and V267 into [identity](../stable/design/decisions/identity.md).
