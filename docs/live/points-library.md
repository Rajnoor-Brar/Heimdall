---
id: live-points-library
summary: a points library per Assignment pools generation points by a key that ignores the point's name; library = true | "only"
affects: identity, provenance, outputs
issue: I-121
---

**Now holds:** `[errand] library` (and `[cfgs.<k>] library`, inherited) is `false` (default), `true` or `"only"`. It is never part of an identity or a seed.

**The key.** `record.library_key(plan)` is the sha256 of `record.library_parts(plan)`: `identity_parts` with every card line that starts with the tool folder's `[card] comment` dropped (where the point's name sits: the card header), the seed rule kept. One physics under two point names or two Errands is one key; the identity is unchanged, so nothing reruns and the identity golden file is as it was. A random seed is not in the key (the first recorded point serves every Run); a manual seed is.

**Layout** (per Assignment):

```
records/<A>/library/points.jsonl        the index, one JSON line per change (created, used, rerun), appended under an flock
records/<A>/library/<key16>/            .complete (the key), identity.json, provenance.json, attempts.jsonl, .lock
results/<A>/library/<key16>/            the products
```

A Run that uses an entry has relative links `records/<A>/<E>/<R>/points/<name>` and `results/<A>/<E>/<R>/points/<name>` → `../../../library/<key16>`, so every reader of those paths works as before. Its working folder `logs/<name>/` stays its own. The entry's `identity.json` and `provenance.json` are the first Run's, with that Run's names. For a library point `points.json` names `library = "<key16>"` and its `identity` is the key, the text of `.complete` (`record.marker_text`; `record.recorded_identity` returns the plan's own identity when the marker is the plan's key, so `is_complete`, `overwritten` and the plot readers compare as before). `record.FORMAT` stays 1.

**The setting.**
- `true`: planning (`cli._planned_points`) sets `plan.library` for every generation point. A point complete in its entry is skipped (its seed is the entry's, whatever the plan's seed rule gives); a missing one runs into the entry, under the entry's lock (`record.lock_file`), and is linked. A run links at its start (`cli.pool_points`, and again in `execute.run_point` for a cluster job) and says how many points came from the library and which Run first made them. `--plan` and `--why` show a library hit (`library <key16>, first by <R>`).
- `--rerun` reruns a library point in its entry, replacing it for every Run that links it, and says which Runs those are.
- `"only"`: as `true`, but the run's stages are `pre` and `points` alone: no manifest, snapshot, combine, post or plot, and at its end its links are removed (`record.unlink_run`) with the empty `points/` folders. The Run's `logs/` and `run.jsonl` stay in `records/<A>/<E>/<R>/` (the library keeps no per-Run logs), and the registry entry lists the library entries as its records.

Stages (pre, combined groups, post) are not pooled. `heimdall clean` takes a Run's link away and never an entry (`house.remove` unlinks a link). A cluster submission skips a library hit (`cluster` asks `is_complete`), and its points jobs link as a Run does.

**Not yet:** `heimdall library list | verify | prune | adopt` (phase 5).
