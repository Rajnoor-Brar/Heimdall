---
id: live-canonical-cards
summary: every tool with a card reads a final config with no comments, and the identity hashes it, so one physics is one identity whatever the writing
affects: tool-contract, tools-pythia, tools-herwig, tools-delphes, tools-sherpa, tools-whizard, tools-madgraph, errand-file, identity, caches, provenance, housekeeping
issue: I-149
---

**Now holds:**
- **What the tool reads.** An appended tool's card (`[card] style = "append"`: pythia, herwig, delphes) is a **final config**, made by `runner/cards.py`. The sources are its base cards, the point's settings, quantities and built-ins, the footer, and the seed lines.
  - Each source is parsed by the folder's grammar.
  - The comments go, after the directives they carry are read (`[card] directives`).
  - The sources merge in order, the last winning.
- **`[card] order` says how the final config is written.**
  - **`free`** (pythia): settings commute, and each is written once.
    - The `leading` keys come first, in that list's order (`Tune:ee`, `Tune:pp`), since a tune resets its parameters when read.
    - Then every other setting, sorted by key.
    - Then each `group`, in written order: a particle's commands (`^(\d+):`), base before point, since `onMode = off` must come before `onIfMatch`.
    - A setting set twice in one card is refused at `--plan`, naming both lines. A later source's value replaces an earlier one's, which `cards/<tag>.json` keeps under `overrode`. A `repeatable` command is kept every time.
  - **`sequential`** (herwig, delphes): a script. The base stays as written, with its comments gone. The point's lines follow, sorted, then the footer and the seed. Nothing replaces anything, since a later `set` is read later, and a key repeated in separate `module` blocks is no duplicate.
- **A free card's value has one spelling** (`cards.canonical`): a number as Python writes it (`6.` is `6.0`), a yes or no as the folder's `bools`. So a point value equal to the base's writes the same card.
- **The rendered tools** (`style = "render"`) get their overrides sorted by key, so the quantities' order is in no card.
  - **sherpa:** its final config is the merged YAML with sorted mappings, lists in order (`cards.dump_tree`). A key twice in one mapping of a base is refused (`cards.load_tree`).
  - **whizard:** the point's settings, sorted, then the base inlined without comments in place of `include(<path>)`, so the card holds the whole input. The `beam_structure` directive is read through `[card] directives`. No origin comments.
  - **madgraph:** the proc card in its prepare card is cleaned, in written order.
  - The card has no header naming the point.
- **The identity hashes each tool's final config before the seeds** (`identity_parts` → `tools[].card`). `base_sha256` is gone. A comment, a blank line, a re-spaced line, two commuting lines swapped, or `vary` reordered make no new point. A point's name is in no part, so the points library's key is the identity (`library.key`, `library.parts`), and the seed basis strips nothing.
- **Record format 2** (`record.FORMAT`): identities of final configs. An older Heimdall refuses a format-2 record rather than reading every point as stale. `heimdall records upgrade` gives a file its `format` key, format 1, and never 2: a record reaches 2 only when it is remade with the new identities.
- **The prepare key** (`tools._prepare_key`) is the final config before seeds, less the `ignore` keys. A `key = "base"` folder (madgraph) uses its base cards, cleaned. So a comment in a base card rebuilds no integration, and every prepare cache is rebuilt once, when next needed.
- **The card's grammar** (`[card] line`) reads `a=1` as `a = 1`: space beside punctuation is optional.
- **`heimdall run --plan --card <tag>`** shows an appended tool's final config. Each line says where it comes from, and which value it replaced (`← [quantities.pdf] = NNPDF23lo, over ep.cmnd:14`).
- **`[checks] card`** (Pythia's own reader) checks that final config before the seeds.
- **What does not change.** The point card `cards/<tag>.point.<ext>` (an appended tool's own lines, with a header, read by no tool).

**No longer holds:**
- `[card] merge = true`; `order = "free"` replaces it.
- The combined card's `<comment> from <base>` lines, its header, and its base comments.
- A Pythia base setting a key twice, with the last line winning silently.
- `tools.clean_base` and `tools.merged_card`.
- `base_sha256` in an identity, and the redundant-override rule (a point value equal to the base's left out of the identity): the final config holds it once.
- The library key as the identity without card comments, and the identity as distinct from it.
- `records upgrade` bringing a file to the current format.
- Whizard's `include(<base path>)` and `# <origin>` comments, the rendered cards' header.

**Decisions:**
- **V268** The card a tool reads keeps no scaffolding for human reading. What each value is and where it came from goes in `cards/<tag>.json` and in `--plan --card`, not in comments.
- **V269** A `free` folder refuses a setting twice in one card. Across sources, the last source wins: a later base over an earlier one, the point over the bases, and the runner last. A `sequential` folder refuses nothing, since its repeated keys are scoped by its commands.
- **V270** The order is the folder's, `[card] order`, and the code knows no tool. Where order is meaning it is kept: a sequential base, the leading keys, a group's commands.
- **V271** The identity hashes what the tool reads, its final config before seeds, and no file's raw bytes. One physics is one identity, and a point's name is in none, so the library key is the identity (developer, gate of 2026-11-09).
- **V272** Records are remade into format 2 once, never read in two forms. The runner keeps no old-identity code. `records upgrade` stops at format 1, so a file is never marked as holding identities it does not.
- **V273** A prepare cache keys on the final config, so it is rebuilt once after this change and never for a comment (developer, gate of 2026-11-09).

**Stable pages need:**
- [tool-contract](../stable/internals/tool-contract.md): the `[card]` keys `order`, `leading`, `group` and `directives` in place of `merge`, and the final config.
- [tools-pythia](../stable/tools/pythia.md): its card is the final config, sorted, tunes first and particles grouped.
- [tools-herwig](../stable/tools/herwig.md) and [tools-delphes](../stable/tools/delphes.md): their cards are the base without comments, then the point's lines, sorted.
- [errand-file](../stable/guide/errand-file.md): what `--plan --card` shows.
- [tools-sherpa](../stable/tools/sherpa.md), [tools-whizard](../stable/tools/whizard.md), [tools-madgraph](../stable/tools/madgraph.md): their final configs.
- [identity](../stable/internals/identity.md): what is hashed (the final config, no `base_sha256`), the library key as the identity, format 2.
- [caches](../stable/internals/caches.md): the prepare key.
- [provenance](../stable/internals/provenance.md) and [housekeeping](../stable/guide/housekeeping.md): record format 2, and that `records upgrade` gives format 1 only.
- V268–V270 into [errand-file decisions](../stable/design/decisions/errand-file.md), beside V59; V271–V273 into [identity decisions](../stable/design/decisions/identity.md).
