# P7: `heimdall deck` retired (V212)

[00_Plan.md](00_Plan.md) §2 P7, X3, X9. The report replaces the deck. **Pause after this phase: the plan is
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
  - `docs/reporter/00_Plan.md` headed "superseded by `heimdall report` (V206–V212)";
  - `heimdall make --framework docs schema`;
  - 07 V212.
- **`.plans/ISSUES.md`:**
  - I-78 deleted;
  - I-105's deck-template line dropped;
  - I-44: the viewer is the report's;
  - I-108 deleted, its history V206–V212.
- **CLAUDE.md:** the docs row (`reporter/` as history), the `.plans/` row.
- **Not touched:**
  - `recipes/base.toml`'s `decks` group (a base change marks the stack, I-62);
  - Brookhaven's `decks/batch_1`.

## Verification

- `grep -rn "deck" framework/ tests/` finds only the break message and its test.
- The fast suite (its baseline: everything but the old stack-build failure); `test_docs`.
- **The branch:** `report` fast-forwarded into main, the worktree removed.

## Log

- 2026-10-27: done (V212), in the worktree, branch `report`.
  - **Readings taken while doing it:**
    - `layout.grid` went with `composite`, its only user, and `viewer.Shown.composite` with them.
    - `heimdall deck` keeps its old options, hidden, so any old line parses and stops with the message
      (`cli.parse` is `parse_intermixed_args`, which takes no `REMAINDER`); the docs' commands block leaves out an
      argument table when every argument is hidden.
    - **Recipes:** the package lists stay (the base's `decks` group, I-62; `settings.toml`'s `apt_packages` keep
      pandoc beside it); their comments, the Brewfile's and the setup docs' now say pandoc is kept from the decks.
      A recipe's stamp hashes its parsed table, not its comments.
    - **History left as it is:** `docs/framework/01_Target.md`, `06_Workdirs.md`, `docs/conda/`, the audits;
      `docs/reporter/00_Plan.md` is headed "superseded"; 01's "Where it came from" keeps its decks row and gains
      the reports'.
  - **Verification:** `grep -rn deck framework/ tests/` finds the break, its test, and the stack test of the
    kept `decks` package group. The fast suite: 1075 passed, 10 skipped; 1 failed, the old
    `test_stack_build::test_the_old_way_is_apt_and_a_venv`.
    The slow suite (P6's and P4's checks with it): 44 passed (P1's 42 and `test_report_draw`'s 2); 5 failed,
    the same 5 as P1's baseline (`test_gates_combine`'s seeds merged, `test_gates_p1`'s legacy digit ×2, I-79;
    `test_listed_points`; the mpl-vs-mkhtml pixels).
  - **The branch:** `report` fast-forwarded into main; the worktree removed. Nothing pushed.
