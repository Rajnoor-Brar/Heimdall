# P6 Docs

**Verified when:** `pytest -q runner/test_docs.py` passes, and `docs/live/canonical-cards.md` holds Now holds / No longer holds / Decisions (new V ids) / Stable pages need: identity (what is hashed), tool-contract (the `[card]` rules), outputs (the sidecar).

### 6.1 The live doc (S)
- Acceptance: as above, in the same commit as P4 (the identity change), extended by P5's.
- Files: `docs/live/canonical-cards.md`, `docs/MAP.md` (generated).
- Blocked by: P4.

## Log
- 2026-11-10: the live doc carries V268–V275 (V274 Pythia reads its final config alone, V275 the remake's rule), and its Stable pages need names identity, tool-contract, the tools' pages, caches, provenance, housekeeping and outputs (the `cards/` files). `test_docs` green. The stable pages change only at a crystallise, on order.
