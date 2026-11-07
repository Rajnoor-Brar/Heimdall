# A points library: pooled points per Assignment

Issue: I-121. Status: planned 2026-11-07, not started. Blocked by: safety-net (all four phases).

## Context

Verified at `cd6ceac` ([notes.md](notes.md) has the full survey, corrected 2026-11-07):

- **Identity** (`record.identity`, `record.py:52`) is the sha256 of `identity_parts`:
  - threads and events;
  - each step's rendered parts (`tools._render`, `tools.py:1115`): card, options, argv, `exe_sha256`, base cards, files;
  - groups, prelim, the seed rule, and `upstream` for stages.
  Versions are not hashed. A manual seed is.
- **The point's name is hashed.** The card header names the point (`tools.py:1206`), and `identity()` keeps it. Only `seed_basis` strips it (`record.py:178`). So the same physics under two names (`10M_nnpdf23` in an events sweep, `nnpdf23` in a pdf sweep) has two identities, and a library keyed by identity would never share them.
- **A point's place:**
  - records: `records/<A>/<E>/<R>/points/<name>/` (`.complete` holding the identity, `identity.json`, `provenance.json`, `attempts.jsonl`);
  - logs: `records/…/logs/<name>/`, which holds the point's `.lock` (`record.PointLock`);
  - products: `results/<A>/<E>/<R>/points/<name>/`;
  - `points.json` lists the points with absolute product paths.
  Readers (the blast radius): `plotdoc` (`_member`, `from_manifest`, `load`, `load_across`), `plot.recorded`, `house` (status, log), `cmd_reproduce`, `report.configured`, `migrate`, `cluster`, `results.load`, `bifrost`.
- **Skip:** `record.is_complete` compares `.complete` with `plan.identity`, and `record.stale(plan, rerun)` decides a rerun.
- **Precedent:** the prepare cache (`tools._prepare_key`, `.cache/<A>/<tool>/<sha16>/`) is a content-addressed pool per Assignment.
- **No reuse exists across Runs.** v3's `_numbered` (`cli.py:428`) reuses a whole serial folder, not a point.

## Design

- **Key.** `record.library_key(plan)`: the sha256 of the identity parts with the name-bearing parts stripped. The card header is one; phase 1's probe finds the rest. The identity itself is unchanged, so nothing reruns and recorded points can be adopted (developer: stripped content key). Seeds are not in the key, as prompt.md asks. A random-seed point pools as well: the first recorded serves every Run.
- **Layout per Assignment:**
  ```
  records/<A>/library/points.jsonl        index: key, full coordinates, events, threads, seed, created, first Run, Runs using it
  records/<A>/library/<key16>/            .complete (the key), identity.json, provenance.json, attempts.jsonl, .lock
  results/<A>/library/<key16>/            products
  ```
  A Run using a library point has relative symlinks: `records/…/<R>/points/<name>` → `../../../library/<key16>` (relative within `records/<A>/`), and the same under `results/`. So every reader in the blast radius keeps its paths, and `points.json` names `library = "<key16>"` (format 2, safety-net 4). Working logs stay per Run (`logs/<name>/`). The lock moves to the library entry.
- **Setting** (developer: one key plus `--rerun`): `[points] library = false | true | "only"`, per errand or configuration.
  - `true`: a hit is linked and skipped; a miss runs into the library and is linked.
  - `"only"`: points go to the library and the Run leaves no folder, manifest or plot stage, so the Run never happened except for its points.
  - `--rerun` on a library point reruns it into its entry under the entry's lock, replacing it for every Run that links it, and says so.
- **Scope:** generation points only. Combine groups and post stages stay per Run (their `upstream` is per Run), and a later plan may pool them.
- **Commands:** `heimdall library list | verify | prune | adopt`.
  - `verify` checks that each entry is complete for its key and that each link resolves.
  - `prune` removes entries no Run links. It runs as a dry run first, and deleting needs `--yes`.
  - `adopt <A>/<E>/<R>` moves a Run's complete generation points into the library and links them back. It is a reorganisation, not a rerun. On a real work dir it runs only on the developer's yes, dry run first.
- **Safety:** `clean` and `migrate` never follow a link into the library. Deleting a Run deletes its links, never the entries.

## Phases

Test command, stack loaded: `taskset -c 0-5 nice -n 10 python -m pytest -q <files>`.

| # | Phase | Verified when | Blocked by | Size |
|---|---|---|---|---|
| 1 | [⏸ Probe the name-bearing parts](P1_probe.md) | a written diff of one physics under two names; the strip list shown to the developer | safety-net | S |
| 2 | [The library key](P2_key.md) | the two names give one key; golden identities unchanged | 1 | S |
| 3 | [Layout, index, lock](P3_layout.md) | a library point links into a Run and every reader test passes through the link | 2 | M |
| 4 | [`library = true \| "only"`, `--rerun`](P4_settings.md) | two Errands share a point without rerunning it (the I-121 done-when) | 3 | M |
| 5 | [⏸ `heimdall library`](P5_commands.md) | list, verify, prune, adopt on the scratch work dir; `clean` leaves entries | 4 | M |

## Decision log

| Decision | Chosen | Why |
|---|---|---|
| Key | identity parts with name-bearing parts stripped (developer) | The same physics under two names is one point; identity untouched, nothing reruns |
| Not a random UUID | content key | A UUID still needs a content comparison to dedupe, and is a second name for one thing |
| Setting | `library = false \| true \| "only"`, overwrite by `--rerun` (developer) | Two flags make meaningless combinations |
| Layout | the library plus relative symlinks in Runs | Every reader keeps working; a Run stays browsable |
| Scope | generation points; stages per Run | Stages' upstream is a Run's |
| Seeds | not in the key; first recorded serves (prompt.md) | Two seeds of one physics are one point for the library; more statistics is `combine`'s job |

## Not yet specified

- Phase 1: the strip list, beyond the card header (argv paths, output names). The probe answers it.
- Phase 3: whether `results/` links are needed when `points.json` names the library (keep both until every reader is audited; contract later).
- Phase 4: what a cluster job does on a library hit (the job is skipped as complete; to be checked against `cluster.py:160` at the phase).

## Always / Never

- Always: the identity golden file green after every step; dry run before any move; links relative within `<A>`.
- Never: change `identity_parts` or `seed_basis`; write into a real work dir without the developer's yes; delete a library entry a Run links.

## Progress

| Phase | Status |
|---|---|
| Plan | approved 2026-11-07 |
| 1 | done 2026-11-08; strip list agreed: all comment lines |
| 2 | done 2026-11-08 |
| 3 | done 2026-11-08 |
| 4–5 | not started |
