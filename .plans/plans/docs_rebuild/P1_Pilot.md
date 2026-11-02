# Phase 1: the pilot (done, awaiting the developer's read)

**Built:** `docs/rules/` (invariants, code, writing, work), `docs/MAP.md`, `docs/reference/settings/plot.md`, `docs/stable/guide/plots.md`,
`docs/stable/internals/{identity,docs-system}.md`, `docs/stable/design/decisions/identity.md`, `docs/live/`, `docs/stable/CRYSTAL.toml`,
`runner/knowledge.py`, `runner/knowledge_site.html`, `heimdall docs [--drift] [--no-open]`, `tests/runner/test_knowledge.py`.

**Layout change from the plan:** `docs/rules/code.md` added: code conventions are neither invariants nor about writing.

**Found while building, for later phases:**
- Phase 2: the site lists the schema's v2 table names (`config`, `configuration`, `tool`, `quantity`): show v3's. Notes still say "a v2 file's…".
- Phase 2: `plot.style`'s note now names `heimdall explain style`, which phase 2 must make work.
- Phase 2: bare `0N §n` cites in schema notes (a test holds the plot page; extend to every settings page).
- Phase 7: `docs.plain` and `knowledge.plain` both exist until the old 04 goes.

**Checks:** dry crystallise in a throwaway worktree: drift named `identity` after a change to `record.py`; live doc merged and deleted; overlay gone;
drift empty; `test_knowledge.py` green there. Site checked in a browser at desktop and phone width, light and dark: no console errors, no overflow.
