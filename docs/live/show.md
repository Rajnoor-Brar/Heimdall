---
id: live-show
summary: heimdall show prints what a Run, a point or a tool did, read from its record; heimdall log is show --log
affects: guide-failures
issue: I-72
---

**Now holds:** `heimdall show <A>/<E>/<R>[/<point>[/<tag>]]` (also a path under `records/`) reads a record and nothing else: `points.json`, each point's `identity.json`, `provenance.json` and `attempts.jsonl`, and the logs. It runs and checks nothing; what it prints is what the record claims (`house.show_data`, text by `house.show_lines`).

- **Run:** its tag and labels, errand and configuration, events, threads, seeds and parallelism, then a line per point (state as `points.json` last said, attempts recorded), and where its records and results are. A record with no `points.json` (before it was kept) lists its points from `logs/` and their last attempt's verdict.
- **Point:** state, the first 12 characters of its identity, seed, events, threads, its axes' tags, σ, each tool's exit and seconds, its products, its attempts, where and when it ran, and the end of each digest log. `--parts` adds the identity's own parts (`identity.json`, what the identity hashes).
- **Tool** (`…/<point>/<tag>`): its provenance entry (tool, version, executable and its hash, exit, argv) and the last 20 lines of its log.
- `--json` prints the same view as JSON (`sigma_pb`, `sigma_note`, `attempts`, `tools`, `products`, `parts`).

**σ** is what the latest attempt's tools reported (`reported.xsec_pb`, [σ, error] in pb, which a generator's reader sets); otherwise "–" and why. It is not read from the products: no reader of a product file for σ exists yet.

`--log`, `--full` and `--attempt N` give exactly `heimdall log`'s output (the point's attempts and digests, a tool's log, a run's `run.jsonl`), and `heimdall log` stays as the shorthand, unchanged.

**No longer holds:** `heimdall log` as the only inspector of a point (nothing printed its identity, σ and provenance together).

**Decisions:** `show` reads the record alone and recomputes nothing, so a changed setup does not change what it prints. σ is what the tools reported, because no reader of a product file for σ exists. `heimdall log` stays as the shorthand (developer).

**Stable pages need:** `docs/stable/guide/failures.md` names `heimdall log`; it may say `heimdall show` where it reads a point's state.
