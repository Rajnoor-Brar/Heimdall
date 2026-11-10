# Phase 6: docs

Status: in progress (6.1 done). Blocked by: phase 5. Rules: `docs/rules/writing.md`, read first.

**Today:** `docs/live/` holds `adopted-runs.md`, `canonical-cards.md`, `runs-ends.md`. The stable pages this round overlays are `plots-statistics` (`docs/stable/guide/plots-statistics.md`), `reports` (`docs/stable/guide/reports.md`), `glossary` (`docs/stable/design/glossary.md`); the generated ones are `settings-plot`, `commands`, `keys` under `docs/reference/`. The reference is written by `docs.write_generated` (`framework/runner/docs.py:282`); `test_the_generated_pages_are_current` holds it, and its failure message names the command that regenerates.

### Step 6.1: the live doc and the regenerated reference (Size: S)
- Acceptance:
  - `docs/live/grand-ranking.md`, front matter `id: live-grand-ranking`, a `summary`, `affects: [plots-statistics, reports, glossary]` (a generated page is not overlaid: it is regenerated), `issue: I-151`. Sections **Now holds**, **No longer holds**, **Decisions**, **Stable pages need**.
  - **Now holds** is written from the phase logs' lists: the order of a ranking and its gates; costs and their compression; the categories and the default set (linking the generated reference for ids and defaults, never listing them); marginals and how to read a row; the sections of a summary; the method record and where it is shown; old names and `migrate`; that a record with old names still reads.
  - **Decisions** carries R1–R18 that a reader relies on, and the design's decision log rows, each in a sentence with its why.
  - **Stable pages need** lists, page by page, what a crystallise must change, with the glossary's missing terms (01's list).
  - The reference is regenerated, and `docs/MAP.md` with it. `make schema`'s editor schema is regenerated if `test_the_editor_schema_is_current` asks.
  - Nothing under `docs/stable/` is edited. The study is not named.
- Files: `docs/live/grand-ranking.md`, `docs/reference/` (generated), `docs/MAP.md` (generated), the editor schema (generated).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_docs.py`, then `heimdall docs --drift` (its output in the log: it names the three stable pages).
- Seam: `test_docs`.
- Blocked by: 5.4.

### Step 6.2: the milestone (Size: XS)
- Acceptance: the full fast suite and the two integration files (each alone) are run and compared with 0.1's baseline; Progress and this log say what holds; the report to the developer is written as this log's last entry: what now holds, each off-plan decision, each open issue, the narrowing of gate answer 1 (R9), and the request for the four benchmark Runs' addresses and the order to run phase 7.
- Files: the round's files only.
- Check: the three runs above.
- Blocked by: 6.1.

## Log

- **6.1 · done 2026-11-10.**
  - `docs/live/grand-ranking.md` (11 993 bytes of the 12 000 cap): Now holds, No longer holds, Decisions (V276–V285, then the plan's decisions a reader relies on, as sentences), Stable pages need, page by page, with the glossary's terms defined.
  - `affects` is `plots-statistics, reports, glossary, extending, runner, decisions-plots`: three more than the acceptance named, each found stale by the drift check (Notes).
  - `make -s schema` changed nothing; `make -s docs` regenerated `docs/MAP.md` (the five pages marked "⟵ live: live-grand-ranking", the page listed). The reference was current since 5.4.
  - Check: `test_docs.py` 565 passed, the two named reds. `heimdall docs --drift` names 26 pages: everyday, first-run, model, chains, guide-failures, overlay, paths, plots-across, plots-curves, plots-data, plots-figures, plots-sets, plots-style, plots, scale, sweeps, validation, watching, tools-overview, connections, data-model, docs-system, layout, plot-stage, run-flow, run-queue. None of the overlaid ones: drift leaves out a page a live doc affects. None of the 26 holds `score`, `[score]`, `scorecmd`, `standings` or a ranking purpose.
