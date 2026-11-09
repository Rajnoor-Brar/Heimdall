# P4 The identity hashes the final config

**Verified when:** `test_identity_order.py`'s three strict xfails pass, and their marks come off. The golden file `tests/golden/identity_parts.json` is rewritten by its own `write(path)`, by hand, and its diff is read by the developer ⏸ before the commit. The fast and slow suites are green.

### 4.0a Sherpa (S)
- Acceptance: `order = "tree"`. The loader refuses a duplicate key (or follows Q1), and the dump uses `sort_keys=True`. The `owned` refusal and the `MPI_PDF_SET` follow-up stay.
- Check: `pytest -q runner/test_cards_tools.py -k sherpa`; the slow Sherpa fixture run.
- Files: `framework/tools/sherpa/render.py`, `tool.toml`.
- Blocked by: P3.

### 4.0b Whizard, MadGraph (M)
- Acceptance: the overrides reach every plugin sorted by key (`tools._render`), so the quantities' order is not in a rendered card. Whizard's directive (`beam_structure`) is read through `[card] directives`. Its origin comments go to the sidecar. The base is inlined after the point lines, cleaned, in written order, in place of `include(path)`, so the final config holds the whole input. MadGraph's proc card is cleaned in written order (its prepare card), and the launch script's `set` lines are sorted between their fixed head and `done`.
- Check: `pytest -q runner/test_cards_tools.py -k "whizard or madgraph"`; the slow Whizard and MadGraph fixture runs.
- Files: `framework/tools/{whizard,madgraph}/render.py`, `tool.toml`.
- Blocked by: P3.

### 4.1 The parts (S)
- Acceptance: a tool's `card` part is its final config before the seed lines, and `base_sha256` leaves the identity. `record.FORMAT = 2` is written in `identity.json`. `record.seed_basis` and `library.parts` no longer strip comments (there are none). `library.key` becomes the identity, under its name.
- Check: `pytest -q runner/test_identity_order.py runner/test_library_key.py runner/test_identity_golden.py`, with the golden file rewritten once by hand.
- Files: `framework/runner/record.py`, `framework/runner/tools.py:1234-1243`, `framework/runner/library.py`, `tests/golden/identity_parts.json`.
- Blocked by: 4.0a, 4.0b.

### 4.2 The prepare key (S)
- Acceptance: `_prepare_key` hashes the final base and the keyed lines (gate Q5). A comment in a Sherpa base reuses its integration.
- Check: `pytest -q runner/test_prepare*.py`; a test where a base comment keeps the prepare dir.
- Files: `framework/runner/tools.py:1300`.
- Blocked by: 4.1.

## Log

- 2026-11-09: 4.0a, 4.0b, 4.1 and 4.2 written.
  - The rendered tools get their overrides sorted, and the plugins get `rules`, `directives` and `base_names`. sherpa uses `cards.load_tree` and `dump_tree`; whizard inlines its base and reads the directive from `[card] directives`; madgraph cleans its proc card. No header.
  - An identity's `card` is the final config before seeds, and `base_sha256` is gone, as is the redundant-override rule. A free value has one spelling (`cards.canonical`) instead.
  - `library.parts` is `identity_parts`, so the key is the identity. `seed_basis` strips nothing.
  - `record.FORMAT = 2`. `migrate.LAYOUT = 1`: `records upgrade` stops at 1.
  - `_prepare_key` keys on the final config, or a `key = "base"` folder's base cards, cleaned.
  - The tests that pinned the old rules changed with them: test_library_key, an adopt test, test_why, test_run_tags, the Whizard plugin test and test_cards. The three xfail marks are off and their tests pass.
  - Whole suite, slow included: 2357 passed and 5 failed, of which 4 were fixed after (tests of the old rules, the map). The golden test is left.
  - **The golden diff** (193 of 193 points): `card` and `base_sha256` in every tool; `prepare`, and the `argv` naming the prepare dir, for sherpa (4), herwig (3), madgraph (1) and whizard (1); one exec's argv (the Herwig prepare it reads). Nothing else differs. ⏸ The rewrite waits for the developer's yes.
