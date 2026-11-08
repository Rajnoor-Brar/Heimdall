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

**Commands.** `heimdall library list [A]` (entries with their quantities' tags, events, seed, complete or not, the Run that first made each and the Runs linking it now, from the links on disk); `verify [A]` (each entry complete for its key: `.complete` begins with the folder's name and is the key `identity.json` gives, `record.library_key_of_recorded`; its products there; each link resolves; the index and the folders agree; it reports, fixes nothing, and exits 1 on a problem); `prune [A] [--duplicates] [--yes]` (the entries no Run links, unless a session holds them; the index gets a `pruned` line; `--duplicates` also the `<name>.adopted-duplicate` folders); `adopt <A>/<E>/<R> [--yes]`.

`prune` and `adopt` only say what they would do until `--yes` (`--dry-run` is the default spelled out); with `--yes` they wait while a job of the work dir goes. `adopt` files each point its `points.json` lists, whose `.complete` is the hash of its recorded `identity.json`, under the key of those recorded parts, and links it back; a point whose key is already complete in the library is linked to that entry and its own folders are kept beside the link as `<name>.adopted-duplicate`; an unfinished entry of that key stops that point; the Run's `points.json` gets `library` and the key as `identity`. A plot document of the Run still names the old identities until it is written again, and draws those points "as recorded". `adopt` is tested on the scratch work dir only.

**No longer holds:** a point's records always being its own Run's folder; `.complete` always holding the point's identity (a library point's holds its key); no point being reused across Runs.

**Decisions:** the key drops every card comment line, not only the header (developer, 2026-11-08); the identity is unchanged. `record.FORMAT` stays 1: `library` is an additive key and an older reader works through the links, while format 2 would mark every record file as below the format. Known cost: an older Heimdall reads a library point's `.complete` as the key, not its identity, and takes the point as stale. The library code is in `record.py` (a new module would need a rank row). The setting is a flat `library` key, not a `[points]` table. A library point's records are read and written in its entry directly; the links serve the readers that walk a Run's folders. A hit's seed is the entry's recorded one. `"only"` keeps the Run's `logs/` and `run.jsonl`, looser than the plan's "no folder": the developer is to confirm. `prune` and `adopt` are dry runs unless `--yes`. `adopt` judges a point by its recorded parts, so no config is loaded. `migrate` is unchanged, as no layout it moves holds a library.

**Stable pages need:** `internals/identity.md` (Skipping: the library key, a marker holding it), `internals/layout.md` (`records/<A>/library/`, `results/<A>/library/`, the links), `internals/provenance.md` (`points.json` `library` and `identity`), `guide/scale.md` (the setting), `guide/outputs.md` (`heimdall library`).
