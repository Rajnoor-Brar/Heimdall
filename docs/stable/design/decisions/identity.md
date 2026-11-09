---
id: decisions-identity
summary: why identity, seeds and skipping work as they do
---

# Decisions: identity and seeds

- **V9** Identity is per point: no shared generation, no Rivet multiplexing. Gave up: cheap analysis-option sweeps.
- **V12** `serial` is a folder prefix only; identity alone decides skipping.
- **V22** Seeds follow the generator's identity, not the point's, so one set-up gives the same events in any configuration.
- **V36** `parallelism` is in no identity or seed, so a point's result equals its one-at-a-time result.
- **V39** Seeds may be `identity`, `manual` or `random`; `identity` keeps its old identity text, so nothing reruns. Overlapping manual blocks on one set-up are refused.
- **V57** A completed point writes `identity.json`; `--why` diffs it against the plan. The hash itself did not change.
- **V137** Fingerprints name no folder: paths are portable in the identity, so moving a root reruns nothing.
- **V244** The golden file masks the Herwig, MadGraph and Sherpa fixtures' cache path, which makes their identities depend on where the cache is; fixing that would be an identity change.
- **V245** The points library's key drops every card comment line, so the identity is unchanged and nothing reruns. `record.FORMAT` stays 1: an older Heimdall takes a library point as stale.
- **V246** The library is a flat `library` key, not a `[points]` table. `"only"` keeps the Run's logs and `run.jsonl`. `prune` and `adopt` are dry runs unless `--yes`; `adopt` judges a point by its recorded parts.
