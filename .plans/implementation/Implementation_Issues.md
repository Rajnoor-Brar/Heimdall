# Implementation issues, round 2

Written by the implementing agent. Findings left open, appended as found. Each is a claim with where it was seen: what failed or is wrong, the output or the line, and what it blocks (a step id, or nothing). At the close each one gets an `I-` id in `.plans/Issues.md`, or is marked closed here with why.

## Open

- **2026-11-10 · 1.5(a) · two docs tests red: a stable page names a renamed module.** R1 moves `framework/runner/scorecmd.py` to `rankcmd.py`. Two stable pages name the old file, and stable pages are on this round's Never list:
  - `docs/stable/internals/runner.md:41`, the rank table, read by `test_the_rank_table_is_the_runners` (`{'scorecmd': 4}` against `RANKS`' `{'rankcmd': 4}`);
  - `docs/stable/guide/plots-statistics.md`, its `code:` frontmatter, read by `test_the_code_a_page_names_exists[stable/guide/plots-statistics.md]` (`['framework/runner/scorecmd.py']`).
  
  No live doc can answer either test: both read the stable page alone. They are carried as named reds from 1.5(a) on, and no step is blocked. The fix is two lines on those two pages, the row and the frontmatter, which is the developer's call: allow the edit, or crystallise after phase 6. Until then the fast suite is "the baseline but for these two".
- **2026-11-10 · 1.5(c) · "tag" for a quantity's value is gone from `rank`'s messages only.** 00_Plan's ledger sends "tag → value in messages" (01's rename table) to 1.5. Step 1.5's acceptance names the `rank` command's words, and those say value (`--baseline q=value`, "not quantity=value"). Other user-facing messages that call a quantity's value a tag (sweeps, `[plot].sets`, `--points`) were not searched, since no file list of 1.5 holds them. The row in 01 is left unmarked. It blocks nothing; it is a sweep of message strings, best done with 6.1's live doc or as a step of its own.
