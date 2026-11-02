# A points library : pooled points per Assignment

Notes for planning, from 2026-11-01. A claim, not a plan: re-verify against the code. Pages: `identity`, `provenance`. Issue: I-121.

**What a point is today:**
- **Planned** (`cli.build_plans` → `tools.PointPlan`): a configuration's sweep (`sweep.points`) gives `Point`s
  (index, name from the value tags, `choice`), each rendered into its tools' cards.
- **Identity** (`record.identity`, `identity_parts`, record.py:52–72): sha256 over threads, events, each tool's
  rendered identity parts (its cards, argv, binary hashes and versions), the groups, prelim, the **seed rule** (not
  the seed), and for a post stage its `upstream` (every point's identity).
  - **Not in it:** the Assignment, the Errand, the Run, the serial ("location, never identity", 04 §2), the point's name.
  - So two Errands that render the same cards already make the same identity.
- **Seeds** (`record.assign_seeds`, record.py:188):
  - `identity`: from the generators' identity, `seed_basis`, so the same point gets the same seed anywhere;
  - `random`: drawn, then kept from the point's `provenance.json`;
  - `manual`: given.
  - Blocks are kept disjoint **within one plan only**. A pooled library meets two Runs whose random-seed points
    share an identity but not a seed: which one is "the" point?
- **Where it lives**, per Run (`tools.RunFolders`, tools.py:604; `tools.run_dir` = `<A>/<E>/<NN_label>`):
  - `records/<A>/<E>/<R>/points/<name>/`: `.complete` (holds the identity: complete means "for this identity"),
    `identity.json` (for `--why`), `provenance.json` (seed, events, versions, revision), `attempts`;
  - `records/<A>/<E>/<R>/logs/<name>/`: the working folder (cards, `commands.sh`, `context.toml`, logs), deletable;
  - `records/<A>/<E>/<R>/points.json`: the manifest, and `config/`, the errand file's snapshot (V158);
  - `results/<A>/<E>/<R>/points/<name>/`: the products (YODA, ROOT);
  - `.cache/<A>/plots/<E>/<R>/`: the drawing's working files.
- **Skip-unchanged:** `record.is_complete` / `record.stale(plan, rerun)` (V232); a point is skipped when its own
  folder's `.complete` holds its identity.
- **Locks:** `record.PointLock`, so one session runs a point; `--wait` waits for another (U66).
- **Readers of a point's place:**
  - plot documents (`plotdoc`: a member's `yoda` path, relative to the Run's results);
  - `--across` (`plotdoc.load_across`, `[from].runs`/`@tag`);
  - compare figures over configurations and Errands (V83, V88);
  - `heimdall status`, `log`, `reproduce`, `report`, `migrate`;
  - the cluster's shards and finish jobs.

**Ideas already in ISSUES that meet it:**
- I-95: per-group identity and skip.
- I-96: shared generation for analysis-option sweeps.
- I-102: products that identify themselves, and an index of provenance (SQLite).
- I-11: an identity golden file, held, and the safety net any change to identity needs.
- I-28: record format versions, and `heimdall records upgrade`.

**What a library will have to settle:**
- **The key:** the identity as it is (generation + analysis), or a split. A generation key would let one generator
  run serve several Rivet analyses (I-96); a key per tool group would let a point reuse its generation and redo
  its analysis (I-95).
- **The layout:** a pool such as `records/<A>/points/<identity>/` and `results/<A>/points/<identity>/`, with a Run
  holding references (a manifest naming identities, or links), versus Runs keeping their folders and a pool index
  pointing into them. What `heimdall run` does on a pool hit: link, copy, or only record it in the Run.
- **Seeds and statistics:**
  - `identity` seeds make a pooled point the same events wherever it is asked for;
  - `random` seeds are not reproducible across Runs;
  - two points with one identity are one point, so they are not two samples: what a "more events" request means
    then (merging replicas is `combine`).
- **Invalidation:** a rebuilt app changes binary hashes, and with them every identity: is the old point
  stale, or kept and marked? Today a Run's `.complete` simply stops matching (V158 draws such points "as recorded").
- **Ownership and garbage:** a Run deleted while its points serve others; `heimdall` commands to list, verify and
  prune the pool. The pool spans Errands but stays within one Assignment (as asked).
- **Concurrency:** two jobs wanting one pooled point (`PointLock` is per folder today).
- **Migration** of existing Runs into the pool: Brookhaven's `eic/zeus` Runs share many points across serials and
  event counts. Identity is untouched by the move, so it is a reorganisation, not a rerun.
- **Records keep a format** (I-28) so the readers above can tell a pooled Run from today's.
