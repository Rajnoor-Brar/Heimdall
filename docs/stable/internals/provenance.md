---
id: provenance
summary: what a run records and where: provenance.json, attempts.jsonl, points.json, tag, identity.json
code: framework/runner/record.py
---

# Provenance and manifests

- **`records/…/<point>/provenance.json`:** the point's values; identity, seed, threads, events; per tool its binary's path, sha256 and version, argv, card and sha256, config, and result (exit, seconds, warnings and errors each once with count and first line, its `summary` and last σ); the `--set`s; host, platform, user, times; `git = {heimdall, work}` revisions and dirty flags; `heimdall`, `work`, `stack`. `heimdall reproduce` runs a point again from it, warning when a revision moved or was dirty.
- **`records/…/<point>/attempts.jsonl`:** a line per attempt however it ended, under the point's lock: `n`, times, identity, card hashes, `verdict`, `cause` (failed, stalled, timeout, count, missing, stopped, prelim), tool `blamed`, message, and per tool its exit, seconds, stall details, warnings, and any prepare cache hit.
- **`records/…/<R>/points.json`:** every point's values, page, products, folders, identity, seed, whether complete, and `state` (complete, stale, running, failed, stopped, incomplete, to run). `constants` are what every point shares: events, threads, parallelism, seed rule, chain, stages, fixed quantities, each tool's folder, version, packages and analyses, base-card hashes, data, revisions, host, stack, image. Post tools, the plot stage and `runner.results` read it, so none must know the layout.
- **`records/…/<R>/tag`:** the folder's tag, one line, the source of truth (`record.run_tag`). `cli.give_tag` writes it from `--tag`, the file, or the configuration's `tag`; `heimdall tag` rewrites it. Nothing reads it into an identity.
- **`identity.json`** beside `.complete`: [identity](identity.md).
- **A snapshot** (`record.write_snapshot`): the errand file and what it imports, in `records/…/<R>/config/`, so a record is itself a config.
