# Canonical cards: the config a tool reads is a final, canonical text, and the identity hashes it

Issue: [I-149](../../Issues.md). Stage 2 (design plan), written 2026-11-09. **Status: approved 2026-11-09 ("Go on"); implementation round 1 under way.**

## Goal

The card a tool reads is a **final config**: every source merged (base cards, `settings`, quantities, the runner's own keys), duplicates resolved by the tool's rules, comments, blank lines and layout dropped, and its keys in a canonical order wherever the tool's semantics allow. It keeps no scaffolding for human reading. The identity hashes that final config, so **one physics is one identity**: a comment, a blank line, a re-indented card, swapped `[quantities.*]` tables, a reordered `vary`, or two commuting card lines reordered make no new point. Where order *is* physics (sequential formats, Pythia tunes, particle-data commands), it is kept.

## Context (read from the code at `9641cc2`)

**What the identity holds today** (`record.identity_parts`, `record.py:71`): per tool, `tag`, `tool`, `exe` and its sha256, `flags`, `options`, `config_values`, `card`, `argv`, `prepare`, and **`base_sha256`**, the raw hash of each base card file (`tools.py:1234`).

**How cards are made** (`tools._render`, `tools.py:1100-1245`). There are three styles in `tool.toml [card] style`:

| Style | Tools | The file the tool reads | What the identity's `card` holds |
|---|---|---|---|
| `append` | pythia (`.cmnd`, `merge = true`), herwig (`.in`), delphes (`.tcl`) | `cards/<tag>.<ext>`: the base cards' cleaned lines, then the point lines (`finalise`, `tools.py:1529-1535`); pythia leaves out a base key the point sets (`merged_card`, `tools.py:1567`) | **the point lines only**: a header comment naming the point, the quantity and setting lines, the footer. The base's content enters only through `base_sha256` |
| `render` | sherpa (`.yaml`), whizard (`.sin`), madgraph (`.mg5`) | the plugin's `card()` output (`render.py`) | the rendered card. Sherpa's is the parsed base YAML merged and dumped, with `sort_keys=False` (`sherpa/render.py:84`). Whizard's has `# origin` comments, and `include("<base path>")` instead of the base (`whizard/render.py:56`). MadGraph's is a launch script; its proc card goes to the prepare card |
| `none` | rivet, exec, merge, module, plotmerge, yd2rt, lhapdf | none: flags and options only | none |

**What breaks "one physics, one identity"**, shown by `tests/runner/test_identity_order.py` (three strict xfails):
1. `base_sha256`: any edit to a base card, even a comment, is a new point.
2. Quantity lines go into the card in `vary` order, then the static ones (`tools.py:932`, `values = dict(point.choice)`).
3. A card's lines are hashed in the order written.
4. The header comment names the point (`tools.py:1221`). So the identity depends on the point's name, which the library key (`library.parts`) and the seed basis (`record.seed_basis`, `record.py:197`) each strip again on their own.

**Rules that already exist and are kept:**
- One source per native key across `settings` and quantities (`claim`, `tools.py:1150`: refused).
- A point key beats a base key (Pythia `merged_card`).
- `repeatable` particle-data commands (Pythia) are kept every time.
- `owned` keys are refused in a base (Sherpa, Whizard) or noted (Pythia).
- Cleaning drops blank lines and comments, with per-folder `comment`, `drop`, `trailing` and `drop_inside_braces` (V54, `tools._cleaned`).

**Order semantics, per tool** (from the code and the tools' manuals; P1 confirms them on real cards):
- **Pythia `.cmnd`.** `Key = value` settings commute, and a repeated key's last line wins. But a `Tune:pp` / `Tune:ee` line resets the parameters of its tune when it is read, so a setting before it is lost. Particle-data commands (`23:onMode`, `23:onIfAny`) act in sequence within one particle, and commute across particles. Keys are case-insensitive.
- **Sherpa YAML.** A mapping has no order. A list's order is meaning (per-beam values, `PROCESSES`). `yaml.safe_load` takes a repeated key silently, the last one winning.
- **Herwig `.in`, Delphes `.tcl`, MadGraph proc cards, Whizard SINDARIN.** Scripts: commands run in order. Herwig's `cd` changes context, Delphes `module { … }` blocks and `ExecutionPath` are structure, MadGraph's `import model` comes before `generate`, and SINDARIN runs the point lines before the included base. Among the runner's own `set` lines (absolute keys, one each), order does not matter.
- **Comments that carry meaning.** Whizard reads `# heimdall: beam_structure = …` from the base (`whizard/render.py:24`). They must be read before stripping.

**Who reads the cards besides the tool:**
- `cards/<tag>.json` (Pythia's settings and their origins).
- The context file (`HEIMDALL_CONTEXT`, each tool's card path).
- The prepare key (`_prepare_key`, `tools.py:1300`: `base_sha256` plus the keyed lines).
- `heimdall show` / `log` (the cards folder).
- `--why` (`record.why`, which diffs `identity.json`).
- The golden file `tests/golden/identity_parts.json` (written by hand, never regenerated to pass).

**What a change costs:** every existing point's identity changes. A real work dir's 885 library entries all carry `base_sha256`. A re-keyed identity reruns everything unless the records are remade in the new form (P5).

## Design

**One model, `runner/cards.py`.** A card is a list of **entries**, each `(key, value, origin, line)`, parsed by the folder's grammar (the `[card] line` template, `cards.grammar`, plus the YAML tree for Sherpa). Origins are the base file and line, `[tools.<tag>].settings`, `[quantities.<q>] = <tag>`, or the runner. Then, in one place:
1. **Read the directives** a comment carries (`[card] directives`, a regex per folder), then drop the comments.
2. **Merge** in priority order: the runner's owned keys, over the point's (quantities and `settings`, already one source each), over the base cards, a later base over an earlier one.
3. **Resolve duplicates** by the key's class (`[card]` in `tool.toml`):
   - `free` (the default): one value. Two in one source are refused (Q1); across sources, the higher priority wins and the loser is recorded in the sidecar.
   - `repeatable` (today's key): every occurrence is kept, in written order.
   - `leading` (Pythia `Tune:*`): written first, in written order.
4. **Write the final config** by the folder's `order`:
   - `free`: `leading`, then the free keys sorted by normal key, then each particle's `<id>:` commands (repeatable or not), grouped by particle id, each group in written order with the base's before the point's (P1 finding 3).
   - `sequential`: the base's command lines in written order, with the runner's point lines sorted among themselves at their slot. The footer stays last.
   - `tree` (Sherpa): mappings dumped with sorted keys, lists in order.
   Whitespace is normalised to the folder's line template. There are no comments, no header and no blank lines.
5. **Keep the readable account in the sidecar**, `cards/<tag>.json`, for every tool with a card: each key's value, its origin, and what it overrode. `heimdall show` reads it.

**The identity hashes the final config**, before the seed lines. The changes:
- `card` becomes the final config's lines, and `base_sha256` leaves the identity.
- The point's name leaves with the header, so the library key and the identity become one hash; `library.key` stays as a name for it.
- `record.FORMAT` goes to 2 for `identity.json`.
- The prepare key hashes the final base (canonical) instead of `base_sha256`, so a comment no longer rebuilds an integration either.
- The quantity order (`tools.py:932`) stops mattering, since the writer sorts.

**Migration: the records are remade, once** (P5, gate Q4). The runner reads only the new form; it keeps no legacy identity code. A one-off script, kept in this plan folder and deleted at the close, remakes a work dir's records so its points are complete under the new system and nothing reruns. Per Run, it:
1. plans the Run's config snapshot with the old code (a scratch worktree at the commit before P4) and checks that each complete point's marker is that old identity. That proves the record came from that snapshot. A point that fails stays as it is, listed;
2. plans it with the new code and writes the new `.complete` and `identity.json` (each after a `.bak`);
3. re-keys the library: renames each entry to its new key, relinks the Runs, and rewrites the index, `points.json` and the plot documents (`plotdoc.rekey`).
It runs after a hard-link snapshot, as a dry run, then on the developer's yes, with `status` and the drawable points compared before and after. Work dir 1 first; work dir 2 if its records need it. Seeds are kept as recorded: a remade point keeps its provenance.

## Execution map

| Phase | What | Verified when | Blocked by | Size |
|---|---|---|---|---|
| [P1](P1_inventory.md) | Inventory: every base card in the fixtures and the real work dirs, parsed. Duplicates, order-sensitive keys and directives found | the report is read by the developer ⏸ | gate | S |
| [P2](P2_cards_model.md) | `runner/cards.py`: entries, the merge, the duplicate rules, the three writers, the sidecar | `test_cards.py`, per rule, on hand-made cards | P1 | M |
| [P3](P3_tool_rules.md) | The appended folders' `[card]` rules on the model: pythia, herwig, delphes (no identity change) | per tool: the final card of each fixture equals a reviewed expected file; the slow suite's tool runs green | P2 | M |
| [P4](P4_identity.md) | The rendered tools on the model (sherpa, whizard with its base inlined and directives, madgraph); the identity hashes the final config; `base_sha256` out; FORMAT 2; the prepare key; the library key the identity | the three xfails pass; the golden file rewritten by hand, its diff read ⏸ | P3 | M |
| [P5](P5_migration.md) | The one-off: a work dir's records remade in the new form, the library re-keyed | a fixture work dir recorded under the old form plans with nothing to run after the one-off, with `status` and drawing unchanged; then ⏸ work dir 1, dry run, a yes | P4 | M |
| [P6](P6_docs.md) | The live doc, the decision notes, tool-contract and identity stable-page needs | `test_docs`, and the live doc names each decision | P4 | S |

## Decision log

| Decision | Chosen | Why |
|---|---|---|
| Where the rules live | `tool.toml [card]`, read by one model in `runner/cards.py` | Each folder already owns its grammar (V59); one merge replaces Pythia's `merged_card` and each plugin's own merge |
| What the identity hashes | the final config before seeds | It is what the tool reads. A base's comment, or a key the point overrides, cannot change the physics |
| Readability | the sidecar `cards/<tag>.json`, not comments in the card | The card is for the tool. Origins belong to provenance |
| The point's name | out of the identity | Its only path in was the header comment |
| Order where order is physics | kept: `sequential` folders, `leading` and `repeatable` keys | Sorting there would change the events |
| Old records | remade once by a one-off script, not read in two forms (gate Q4) | the runner stays single-form; 885 entries of a real work dir would otherwise rerun |
| Pythia's argv | `{card}`, the final config, not `{cards}` (its raw bases, then the point card) (developer, 2026-11-10) | found in P5: Pythia read its bases as written, and their paths were in every Pythia identity, so a renamed base was new physics. App_Pythia takes any number of cards: no rebuild |
| Entries one physics after the remake | the most linked stays in the library (the earliest made on a tie); each other stays its Run's own as `<name>.adopted-duplicate` beside its link; entries no Run links are removed (developer, 2026-11-10) | the library holds one entry per key; a duplicate with another seed is other events, which `prune --duplicates` keeps. Not `library/.superseded/`: prune would take any unlinked folder there for an entry and delete it |

## Not yet specified

- P1: whether the real cards hold duplicates, a tune after settings it resets, or a directive other than Whizard's. The inventory decides each folder's rules. A conflict found there is a question for the developer, not a guess.
- P3: Delphes detector cards: whether any `set` outside `module { … }` blocks is order-free. Until shown, Delphes is `sequential`, and only the runner's lines are sorted.
- P3: Herwig `cd` contexts in base cards: point lines use absolute paths; a base that `cd`s is kept as written.
- P5: fog. A Run's plot document and the report's tool pages name identities and card paths; their re-keying is researched at P5's pickup. So is whether a Run whose snapshot no longer plans (a retired form) can be remade, or is listed and left.

## Always / Never

- **Always:** a key's winner and what it beat are recorded in the sidecar. Refusals name both sources with their file and line. Each phase is green alone. Each identity change comes with the golden file's diff, read by the developer.
- **Never:** reorder a `sequential` folder's base lines. Strip a comment before its directives are read. Regenerate `tests/reference/`. Rewrite the golden file without the developer's yes. Write into a work dir without a dry run and a yes. Merge independent-seed copies (out of scope, I-149).

## The gate (2026-11-09)

Asked at once, with recommendations; assumptions listed beside them.

1. **A key twice in one base card** (a `free` key): refuse, naming both lines *(recommended: today Pythia's last line wins silently)* · or the last wins, said in the sidecar.
2. **A key in two base cards** (`baseconfig = [a, b]`): the later base wins, and the sidecar says so *(recommended: a later file refines an earlier one)* · or refuse.
3. **A base key the point sets** (a quantity or `settings`): the point wins and the sidecar records the base value *(recommended, today's rule)* · or refuse unless the base key is marked as a default.
4. **Old records:** accept the old identities and upgrade on a yes, so nothing reruns *(recommended)* · or a clean break, with every point rerun.
5. **Prepare caches** (Sherpa integration, MadGraph process, Whizard grids): key them on the final base, so they rebuild once when a point next needs them *(recommended; only caches)* · or keep `base_sha256` for the prepare key.
6. **Pythia:** `Tune:*` leading and particle-data commands per particle in written order, everything else sorted *(recommended)* · or Pythia `sequential`, with only the runner's lines sorted.

**Assumptions** (they stand unless corrected):
- (a) The sidecar is enough for a human; no annotated copy of the card is written.
- (b) Sherpa: YAML mappings are order-free for Sherpa, and lists keep their order.
- (c) Herwig, Delphes, MadGraph and Whizard are `sequential`, so only the runner's lines are sorted.
- (d) Seeds: a new point draws its seed from the new basis; an old complete point keeps its recorded seed.
- (e) The library key equals the identity from P4.
- (f) `test_identity_order.py`'s xfails are the acceptance tests of P4.

**Answers (the developer, 2026-11-09),** by the gate's numbers:
- Q1–Q3: refuse a free key twice in one card; across sources the priority runner > point > later base > earlier base wins, each loser recorded in the sidecar.
- Q4: remake the records; a special one-off for the real study's work dir (work dir 1) updates them with the new keys and makes its points compatible with the new system. Read as: nothing reruns and the runner reads only the new form, so P5 is a one-off migration, not a legacy path.
- Q5: prepare caches key on the final base and rebuild once, when next needed.
- Q6: Pythia puts tunes first, sorts the rest, and keeps particle-data commands per particle in written order.
- The assumptions stand; (d) now reads: a remade point keeps its recorded seed, and a new point draws its seed from the new basis.

## Progress

| Phase | Status |
|---|---|
| P1 | done 2026-11-09: [notes/inventory.md](notes/inventory.md); question A answered ("Use 200") |
| P2 | done 2026-11-09; the rank-table row added on the developer's yes |
| P3 | done 2026-11-09; the golden file differs at Decay's 29 points (`base_sha256` of the edited fixture), rewritten once after P4 (the developer, 2026-11-09) |
| P4 | done 2026-11-10: the golden file rewritten on the developer's yes (193 points) |
| P5 | done 2026-11-10: checked on an old-form fixture work dir, then work dir 1 remade (states and drawing unchanged); Pythia's argv fixed on the way (74eb9ed) |
| P6 | not started |
