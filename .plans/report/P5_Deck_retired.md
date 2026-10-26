# P5: `heimdall deck` retired (V210)

[00_Plan.md](00_Plan.md) §2 P5, X3, X9. The report replaces the deck. **Pause after this phase: the plan is
done.**

## Tasks

- **Removed:**
  - `framework/runner/deck.py`, `framework/schema/deck.toml`, `schema.DECK_TABLES` and their uses;
  - `layout.composite` and `SIZES`, deck's alone (with their cases in `tests/runner/test_layout.py`);
  - `migrate.deck_moves` and its call in `migrate --layout` (`cli.py`);
  - `paths.decks_root`, `DECKS_VAR` / `HEP_DECKS`;
  - "decks" from `setup.FOLDERS`, `framework/templates/work/README.md` and `.gitignore`;
  - `RANKS["deck"]`.
- **`heimdall deck …`:** stops with "heimdall deck is now heimdall report", with a hint (as V74 did for
  `plot FILE`).
- **Tests:** `tests/runner/test_deck.py` and `test_deck_build.py` deleted.
- **Docs:**
  - 00, 01, 02, 03 §11, 04 §15 (regenerated), 05 §1.8, 06;
  - `docs/reporter/00_Plan.md` headed "superseded by `heimdall report` (V206–V210)";
  - `heimdall make --framework docs schema`;
  - 07 V210.
- **`.plans/ISSUES.md`:**
  - I-78 deleted;
  - I-105's deck-template line dropped;
  - I-44: the viewer is the report's;
  - I-108 deleted, its history V206–V210.
- **CLAUDE.md:** the docs row (`reporter/` as history), the `.plans/` row.
- **Not touched:**
  - `recipes/base.toml`'s `decks` group (a base change marks the stack, I-62);
  - Brookhaven's `decks/batch_1`.

## Verification

- `grep -rn "deck" framework/ tests/` finds only the break message and its test.
- The fast suite (its baseline: everything but the old stack-build failure); `test_docs`.
- **The branch:** `report` fast-forwarded into main, the worktree removed.

## Log
