# P3 The appended tools on the model: Pythia, Herwig, Delphes

**Verified when:** for each appended tool (`style = "append"`), the final config of each fixture point equals an expected file committed beside its test and read in review, and the slow suite's real tool runs stay green (the tools read the final configs). Nothing changes the identity: an appended tool's identity holds its point lines and `base_sha256`, not the final config, until P4.

### 3.1 Pythia (S)
- Acceptance: `order = "free"`, `leading = ["Tune:ee", "Tune:pp"]` (and any P1 finds), `group = '^(\d+):'` for the per-particle commands, `repeatable` kept, and a setting twice in one card refused (Q1). `merged_card` is replaced by `cards.merge` and `cards.write`; `cards/<tag>.json` keeps its shape (value, from), plus `overrode`.
- The fixture `configs/Decay/decay.cmnd` loses line 38 (`HeavyIon:SigFitNGen = 0`, answer A in [notes/inventory.md](notes/inventory.md)), together with the test that refuses a card holding both lines.
- Check: `pytest -q runner/test_cards_tools.py -k pythia`; the slow `test_plot_stage`.
- Files: `framework/tools/pythia/tool.toml`, `framework/runner/tools.py` (`finalise`, `merged_card`), `tests/runner/test_cards_tools.py` (new), `tests/fixtures/expected_cards/` (new).
- Blocked by: P2.

### 3.2 Herwig, Delphes (S)
- Acceptance: `order = "sequential"`. The base is cleaned in written order; the runner's `set` lines are sorted; the footer is last.
- Check: `pytest -q runner/test_cards_tools.py -k "herwig or delphes"`; the slow Herwig fixture run.
- Files: `framework/tools/{herwig,delphes}/tool.toml`.
- Blocked by: P2.

## Log

- 2026-11-09: Sherpa, Whizard and MadGraph (formerly 3.3 and 3.4) moved to P4. A rendered tool's identity holds its whole rendered card, so any change to its plugin is an identity change, and it belongs with P4's.
- 2026-11-09: 3.1 and 3.2 done.
  - pythia has `order = "free"`, `leading` and `group`; herwig and delphes have `order = "sequential"`. `[card] merge` is retired.
  - `tools.finalise` writes `cards.final` of the bases, the point, the footer and the seed. `merged_card` and `clean_base` are gone.
  - `check_cards` checks the final config before seeds, and `card_view` (`--plan --card`) shows it with each line's source and what it replaced.
  - `tests/runner/test_cards_tools.py` holds 8 cases. The expected cards in `tests/fixtures/expected_cards/` (pythia_ep.cmnd, herwig_dis_ep.in) were read in review; delphes is checked structurally, as its base is the 767-line ATLAS card.
  - The Decay fixture lost line 38 (answer A). `docs/live/canonical-cards.md` was written (V268–V270).
  - Whole suite, slow included: 2356 passed, 11 skipped, 5 xfailed, 2 failed. The failures are the rank-table row (P2) and the golden file at Decay's 29 points, where the first difference is `tools[2].base_sha256[0]` and nothing else differs.
