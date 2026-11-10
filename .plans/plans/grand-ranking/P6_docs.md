# P6 · Docs

Verified when: `docs/live/grand-ranking.md` (`affects: plots-statistics, reports, glossary, settings-plot`) states what now holds and what no longer does, with decision notes for the gate, compression, the defaults, matched marginals and the renames; the reference is regenerated; `heimdall docs --drift` names the stable pages it overlays; nothing under `docs/stable/` is edited.

### 6.1 The live doc and the regenerated reference (S)
- Files: `docs/live/grand-ranking.md`, `docs/reference/` (generated), `docs/MAP.md` (generated).
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest runner/test_docs.py -q`
- Seam: `test_docs`.
- Blocked by: P5.

## Log
