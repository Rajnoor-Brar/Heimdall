# Process debt: plans, issues, live docs

Not code, but it decides what the next session trusts. `docs/rules/work.md`: `.plans/` holds only what is open, and a live doc wins over stable pages until a crystallise.

## Findings

### P-1 Decided, not built, while new work deepens the cost · Required · CONFIRMED · closed 8.1
Decided on 2026-10-25 and still open: I-20 and I-21 (one dialect, P1), I-36 (`heimdall plan`), I-41 (retire `plot_points`, still 46 references in `runner/`), I-50 (subpackages), I-57, I-59 and I-86. Since then, three subsystems landed on the old shapes: stats, the library and the queue. Each adds v2-named code to translate later, plus more modules to place when I-50 runs. The order in `ISSUES.md` ("2 safety net → 3 one dialect → …") was overtaken by the 2026-11-07 plans.
**Move:** the developer re-orders the phases. Recommendation: D-1 next, before any new feature, since every feature until then is written twice. **Closes when:** `ISSUES.md`'s order line matches what is done next.

### P-2 23 live docs since the last crystallise · Consider · CONFIRMED · closed 7.1
`docs/stable/CRYSTAL.toml`: 2026-11-02, `4f25f50`. `docs/live/` holds 23 docs, among them `scoring`, `score-engine`, `score-settings`, `stats-core`, `stats-catalogue`, `stats-measured-bins`, `stats-rms` and `statistics-format`: eight on one subject. Two docs tests fail on stable pages that lag the code ([T-1](07_tests.md#t-1)). A reader now merges 23 overlays in their head.
**Move:** a crystallise, on the developer's order (work.md). **Closes when:** `docs/live/` holds only what changed after it.

### P-3 A second issue list outside the rules · Consider · CONFIRMED · closed 0.3-0.4
`.plans/Implementation_Issues.md` (7 `F-` findings) and `.plans/Implementation_Notes.md` (134 lines of implementer decisions) are not in work.md's table of what `.plans/` holds. F-2, F-4, F-6, F-7 and F-9 are real open findings ([O-9](05_oversights.md#o-9), [T-1](07_tests.md#t-1)), and none has an `I-` id. The notes hold decisions the implementer made alone ([O-10](05_oversights.md#o-10)).
**Move:** triage: each `F-` becomes an `I-` or is closed, and each note is accepted into a decision note or reopened. Then delete both files, or add them to work.md if they are meant to stay. **Closes when:** `.plans/` holds only what work.md lists.

### P-4 Issues that disagree with the code · Consider · CONFIRMED · closed 0.5
- I-25 deletes `framework/tools/plotmerge/`, a live and tested tool ([R-6](01_dead-and-retired.md#r-6)).
- I-25 deletes `migrate.py`, which now holds `library adopt` ([S-3](03_structure.md#s-3)).
- `ISSUES.md`'s order line still lists the 2026-11-07 plans by name, and stats-backend and points-library as waiting. I-125–I-128 are gone from the file (closed), which agrees.

**Closes when:** each issue is re-read against the code, as the 2026-11-02 rebuild did.

### P-5 Plan folders held at a milestone · FYI · CONFIRMED · closed 8.2
`plans/stats-backend/` (every phase done, stopped for the developer's read of one summary) and `plans/points-library/` (done, `adopt` on a real work dir deferred, as this session agreed) are open by design. They leave `.plans/` when the developer signs them off, and their decisions then move to `docs/stable/design/decisions/`.

### P-6 `prompt.md` untracked · FYI · CONFIRMED · closed 8.2
`.plans/plans/prompt.md` is untracked (git status). The 2026-11-07 plan said to delete it once every line maps to a plan, so either the mapping is done and it goes, or it is the developer's working file. It is not this session's to touch.

## Sweeps still to run

- **Every open `I-` against the code**, as the 2026-11-02 rebuild did: done-when checks that already pass, and issues whose premise is gone.
- **`heimdall docs --drift`**: each stable page whose code changed since `4f25f50` with no live doc.
- **Memory against the repo.** Memory files hold preferences only (AGENTS.md). Check that none holds a repo fact that has since moved.
