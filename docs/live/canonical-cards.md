---
id: live-canonical-cards
summary: an appended tool reads a final config, its sources merged by the folder's [card] order, with no comments and a key twice in one card refused
affects: tool-contract, tools-pythia, tools-herwig, tools-delphes, errand-file
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
- **The card's grammar** (`[card] line`) reads `a=1` as `a = 1`: space beside punctuation is optional.
- **`heimdall run --plan --card <tag>`** shows an appended tool's final config. Each line says where it comes from, and which value it replaced (`← [quantities.pdf] = NNPDF23lo, over ep.cmnd:14`).
- **`[checks] card`** (Pythia's own reader) checks that final config before the seeds.
- **What does not change.** An appended tool's identity: it still holds the point's lines and the bases' `base_sha256`, until the identity hashes the final config. The prepare key, and the point card `cards/<tag>.point.<ext>`.

**No longer holds:**
- `[card] merge = true`; `order = "free"` replaces it.
- The combined card's `<comment> from <base>` lines, its header, and its base comments.
- A Pythia base setting a key twice, with the last line winning silently.
- `tools.clean_base` and `tools.merged_card`.

**Decisions:**
- **V268** The card a tool reads keeps no scaffolding for human reading. What each value is and where it came from goes in `cards/<tag>.json` and in `--plan --card`, not in comments.
- **V269** A `free` folder refuses a setting twice in one card. Across sources, the last source wins: a later base over an earlier one, the point over the bases, and the runner last. A `sequential` folder refuses nothing, since its repeated keys are scoped by its commands.
- **V270** The order is the folder's, `[card] order`, and the code knows no tool. Where order is meaning it is kept: a sequential base, the leading keys, a group's commands.

**Stable pages need:**
- [tool-contract](../stable/internals/tool-contract.md): the `[card]` keys `order`, `leading`, `group` and `directives` in place of `merge`, and the final config.
- [tools-pythia](../stable/tools/pythia.md): its card is the final config, sorted, tunes first and particles grouped.
- [tools-herwig](../stable/tools/herwig.md) and [tools-delphes](../stable/tools/delphes.md): their cards are the base without comments, then the point's lines, sorted.
- [errand-file](../stable/guide/errand-file.md): what `--plan --card` shows.
- V268–V270 into [errand-file decisions](../stable/design/decisions/errand-file.md), beside V59.
