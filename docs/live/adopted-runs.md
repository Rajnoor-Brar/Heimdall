---
id: live-adopted-runs
summary: an adopted Run's points plan as library points whatever its config says; migrate --layout leaves statistics/ and an Errand's folders; adopt still breaks plot
affects: outputs, identity
issue: I-130
---

**Now holds:** a point whose `records/<A>/<E>/<R>/points/<name>` is a link into `<A>/library/` (`library.linked`) is planned as a library point (`plan.library = library.key(plan)`, `cli._planned_points`), even when its config does not pool. So a Run that `heimdall library adopt` moved in still reads complete for `status`, keeps its number when a config without a serial is planned, and a rerun writes its own entry under the entry's lock, never through a link that another Run shares. `heimdall migrate --layout` leaves a Run's `results/…/statistics/` (V164) and an Errand's `compare/`, `plots/` and `statistics/` (its across pages) where they are (`migrate.RESULT_FOLDERS`, `ERRAND_FOLDERS`).

**No longer holds:** an adopted Run whose config does not pool reading `stale` (its `.complete` holds the key, its plan the identity), and its config planning a new Run to rerun every point. `migrate --layout` moving `statistics/` into `points/statistics`, and an Errand's `plots/<set>` into `plots/points/<set>`.

**Decisions:**
- **V263** A link into the library makes a point a library point; the link is the record of the adoption, so the config need not say `library = true`.
- **V264** An Errand's folder in `results/<A>/<E>/` is a Run only when it is none of `compare`, `plots`, `statistics`.

**Not yet holding (I-130):** `heimdall plot` of an adopted Run draws nothing (`plot: no complete point has a YODA product to draw`). Its plot document, `results/<A>/<E>/<R>/plot.toml`, still names each point's identity, while the marker holds the key. Adopt must rewrite the document's identities as it does `points.json`'s. An adopted point that was stale reads `incomplete`, where before it read `stale`.

**Stable pages need:** [outputs](../stable/guide/outputs.md): what adopt rewrites (`points.json`, the plot document), and that the Run's config need not pool. V263 and V264 into [identity](../stable/design/decisions/identity.md).
