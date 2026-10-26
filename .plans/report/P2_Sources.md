# P2: sources and recipes (V207)

[00_Plan.md](00_Plan.md) §2 P2, N1, N2, N6, Q2. The report's model, with no building yet.

## Tasks

- **`framework/runner/report.py`** (new, rank 4).
  - **`Source`:** a folder holding a `plot.toml`: a configuration's, or a run's runs-together folder.
    - **Its address:** `<P>/<run>/<cfg>`, `<P>/<run>` (every configuration folder with a `plot.toml`, then the
      run's own when it has one), a path, or a glob, under `results_root()`.
    - **Its facts (N2):**
      - its address, config and configuration;
      - Heimdall's revision, and when it was written (`[source]`);
      - its members: complete, failed (a record with an attempt and no `.complete`) or missing;
      - its event count (the members' `events`, `plotdoc.count_tag`);
      - what it is compared against: data, or the first curve (`[plot.data]`, `[stats].reference`).
    - **Its sets** (`plots/<set>/<backend>/` drawn) and the pages in each.
    - **Its statistics** (`statistics/<set>/statistics.csv`).
  - **The recipe:** `framework/schema/report.toml`, tables `report` and `section`, read by
    `schema.check` (`schema.REPORT_TABLES`).
    - `[report]`: `title`, `subtitle`, `from`.
    - `[[section]]`: `title`, `note`, `from`, and one item:
      - `pages` (with `set`, `backend`, `cells`, `layout`, `columns`, `label`);
      - `compare`;
      - `stats`;
      - `bars`;
      - `files`.

      Plus `plot` (N8; checked against `run.toml`'s `plot` keys).
  - **Recipe lookup:** `configs/<P>/<name>.toml` whose top table is `[report]` (with no `[run]`), or a
    `.toml` path. A recipe named like a run of its project (`results/<P>/<name>/`) is refused.
  - **The default recipe (N1):**
    - a front page;
    - `stats = ["top5", <each statistic's section>]`, rankings only;
    - each set in the document's `[plot].draw` (else every drawn set): its pages, a section per cell.
  - **`resolve(recipe, sources) -> Plan`:** the sections in order, each with its figures (source, set, cell,
    page, its files) and its statistics parts.
    - Each is marked *copied* (on disk in the formats needed: a PDF) or *drawn* (P4).
    - Until P4, a *drawn* entry is refused, naming the command that would draw it
      (`heimdall plot <address> --sets <set>`, `heimdall stats <address>`).
    - The sources on the command line replace `[report].from`; a section's own `from` stays.
  - **Labels:** `events` (`10M`, the source's count) or `folder` (its folder's name without the serial); two
    panels with one label in a side-by-side grid are refused.
  - **`listing(plan)`:** each section, its figures (copied or drawn) and the page count.
  - **`starter(source)`** for `--init`: a recipe listing the source's sets, cells and page names, commented.
- **`cli.py`:** `heimdall report [RECIPE] [SOURCE…] [--list] [--init SOURCE] [-o DIR]`.
  - Until P3, a build says it comes with the next phase.
  - `--init` writes `configs/<P>/<name>.toml` once.
- **`heimdall check`:** recipes (files with `[report]`) checked against the schema.
- **`heimdall ls`:** the recipes, under "reports".
- **`house` explain:** `report.<key>` and `section.<key>`, from the schema.
- **`heimdall make --framework docs schema`:** 04 §15 written from `schema/report.toml` (beside deck's until P5).

## Verification

- **New `tests/runner/test_report.py`** (synthetic trees as `test_deck.py` builds them, with a
  `statistics.csv`). It checks:
  - every address form;
  - a recipe's unknown key and its nearest;
  - a recipe named like a run;
  - the default recipe;
  - both layouts and their labels;
  - the override of `from`;
  - a *drawn* entry refused with its command;
  - `--list` writing nothing;
  - `--init` once and never again.
- `test_docs`, `test_imports` and the touched tests (`test_check`, `test_ls`, `test_explain`, if they exist).

## Log
