# P2 The card model, `runner/cards.py`

**Verified when:** `tests/runner/test_cards.py` passes: per rule, a hand-made card in, the final config and the sidecar out. `test_imports` holds the rank: `cards.py` imports only `errors` and the stdlib, plus `yaml` lazily for the tree writer.

### 2.1 Entries and the grammar (S)
- Acceptance: `cards.parse(text, grammar, origin)` gives `Entry(key, normal, value, origin, line)` for each setting line, using the folder's `line` template (today's `card_parser`, moved), `comment`, `drop`, `trailing` and `drop_inside_braces` (today's `_cleaned`, moved). Directives are read first and returned beside the entries.
- Check: `pytest -q runner/test_cards.py -k parse`
- Files: `framework/runner/cards.py` (new), `framework/runner/tools.py` (`card_parser`, `_cleaned` and `clean_base` re-exported from cards).
- Seam: `cards.parse`.
- Blocked by: P1.

### 2.2 Merge and duplicates (M)
- Acceptance: `cards.merge(sources, rules)` applies the priority (runner > point > a later base > an earlier base), the duplicate rule within one source (gate Q1), across bases (Q2) and base against point (Q3), and the `repeatable` and `leading` classes. It returns the winning entries and a record of every loser (origin, value, why).
- Check: `pytest -q runner/test_cards.py -k merge`. One case per rule, plus a refusal naming both lines.
- Files: `cards.py`, `test_cards.py`.
- Seam: `cards.merge`.
- Blocked by: 2.1.

### 2.3 The writers and the sidecar (M)
- Acceptance: `cards.write(entries, rules)` for `free` (leading, sorted, then each particle's `<id>:` commands, repeatable or not, in written order, base before point), `sequential` (base order, the runner's lines sorted at their slot, the footer last) and `tree` (sorted mappings, lists in order). No comments, headers or blank lines. `cards.sidecar(...)` writes each key's value, origin and what it beat.
- Check: `pytest -q runner/test_cards.py -k "write or sidecar"`. A shuffled `free` card writes byte-identically; a shuffled `sequential` card does not, and that is asserted.
- Files: `cards.py`, `test_cards.py`, `framework/runner/schema` (tool.toml `[card]` keys: `order`, `leading`, `group`, `directives`; `tools.py:45`'s key list).
- Seam: `cards.write`.
- Blocked by: 2.2.

## Log

- 2026-11-09: 2.1–2.3 written. `framework/runner/cards.py` (rank 0, and in `PLUGINS_MAY_IMPORT` for the Sherpa plugin's tree): `parse`, `directives`, `setting`, `merge`, `write`, `sidecar`, `load_tree` and `dump_tree`. `tools.card_parser` and `tools._cleaned` now read through it. `tests/runner/test_cards.py` has 19 cases. The `[card]` keys `order`, `leading`, `group` and `directives` are in `tools.FOLDER_SECTIONS`.
  - **No `duplicates` key.** A `free` card always refuses a setting twice in one source (Q1). A `sequential` card never refuses one, since its repeated keys are block-scoped (P1 finding 5). With one value each, a key would be speculative.
  - **`group`** (a regex on the key: Pythia's `^(\d+):`) names the commands kept together in written order (P1 finding 3).
  - **The grammar now reads `a=1` as `a = 1`.** Space beside punctuation is optional, but stays required between words (`set a 1`). Before, `PDF:pSet=13` in a base was not read as a setting.
  - **The rank table:** `tests/runner/test_docs.py::test_the_rank_table_is_the_runners` wants a `cards.py` row in the stable page `internals/runner.md`. Stable pages are edited only on order, so this is the developer's call (see the round's report).
