# `heimdall report`: audit of post-run presentation, and the plan (I-108)

Agreed with the user on 2026-10-26, after an audit of `heimdall deck` and a proposal to consolidate into
`heimdall report`. Phase files: [P1_Modular.md](P1_Modular.md), [P2_Sources.md](P2_Sources.md),
[P3_Build.md](P3_Build.md), [P4_Drawn.md](P4_Drawn.md), [P5_Deck_retired.md](P5_Deck_retired.md). The
execution map is §3; each phase file's Log says how its phase went.

**The user's constraints (2026-10-26):**
- **Plot and stats backends may be refactored and reorganised** for efficient, modular code that the report
  shares. **The commands and what they make stay intact:** `heimdall plot`, `heimdall stats`, a run's plot
  stage and `heimdall overlay`. A before-and-after gate proves it (gate P, §2).
- **The report need not depend on what plot and stats left on disk.** It may use their outputs, or generate
  its own through the shared modules.
- **The report is not a stage.** It runs only on `heimdall report`: nothing in run, plot or stats calls it,
  and nothing in a run TOML asks for it.
- **The scope is quick, informal reports,** the kind sent to colleagues or a supervisor. Formal
  presentations (talks for reviewers, graded or examined work, papers, theses) are not Heimdall's concern.
  At most, its outputs can be copied or edited into them easily.

---

## 1. Audit: what presents results beyond plots and stats

### 1.1 Inventory

| Feature | What it does | What it needs on disk | What the user writes | What it makes | Depends on |
|---|---|---|---|---|---|
| **`heimdall deck`** (V102–V104, U22) | slides from drawn pages | drawn pages `results/<P>/<run>/<cfg>/plots/<set>/<backend>/`; provenance in `records/` (or YODAs) for event-count labels; no run TOML is read (D-R12) | `decks/<deck>/deck.toml` (`[deck]` 8 keys, `[blocks.<name>]` 13 keys); `deck.md` (pandoc Markdown: sections, slides, columns, block references with `panels`/`size`/`columns`); `extras/` images | `reports/<deck>/`: `panels/`, `figures/`, `build/`, `deck.pdf` (Beamer), `deck.pptx`, `deck.html` (dzslides), `overleaf.zip`, `index.html` (viewer) | pandoc (the conda base's `decks` group), pdflatex + Beamer (the OS's TeX), poppler |
| **the viewer** `runner/viewer.py` | the deck's `index.html`: blocks of panels, S/M/L/Full, 2/3/4 columns, light/dark | a deck's panels | — | `index.html` | — |
| **layout** `framework/plot/figures/layout.py` | a grid of pages as one vector PDF (pdflatex) and its PNG (pdftoppm) | pages | — | composites (deck), tiles (the `sheet` figure) | pdflatex, poppler |

**Its weight.**
- **Code:**
  - `deck.py` 661 lines, `viewer.py` 162, `schema/deck.toml` 111;
  - the seams elsewhere: `schema.DECK_TABLES`, `house` explain, `migrate.deck_moves` (`cli.py:1890`),
    `paths.decks_root` / `HEP_DECKS`, `setup.FOLDERS` "decks", the template's README and `.gitignore`.
- **Tests:** `test_deck.py` and `test_deck_build.py`, 315 lines.
- **Docs:** `docs/reporter/` (5 files, 446 lines), 03 §11, 04 §15, 05 §1.8, and mentions in 00, 01 and 02.
- **Open debts:**
  - I-78: the build test fetches dzslides' Google font, so it fails offline;
  - I-105: a `template` key, decided but not built;
  - a dead name, `deck.deck_dir`.

**Its use.**
- **One deck ever:** Brookhaven's `decks/batch_1`, made on 2026-10-10 as the by-hand check.
- **Its `deck.md`** is the `--init` output, never edited, so the talk-writing half (D-R3) has never been used.
- **Its sources are gone:** `PhotoProduction/zeus` and `PhotoProduction/eic` are no longer in `results/`
  (now `eic/zeus`, `eic/zeus_validation`, `legacy/eic`). It cannot build today.
- **Nothing is built:** `reports/` is empty in Brookhaven and High-Energy, and High-Energy's `decks/` is empty.

**Its model.** A block is one page name across result folders, a panel per folder, labelled by its event count:
the batch_1 study (statistics convergence), made general. It cannot show:
- a run's statistics;
- compare pages (`<run>/compare/`);
- the runs-together sets (`results/<P>/<run>/plots/<set>/`);
- several pages of one folder in a grid, except in folder mode.

**Not audited, by the user's word:**
- the plot side: the plot indexes, `sheet`, `compare`, `[plot.across]`, `statistic` figures and `overlay`;
- the stats side: `statistics/<set>/{statistics.csv, bars/, summary.pdf, summary.html}`.

They stay as they are. The report reads their outputs, or calls their code to make its own.

### 1.2 What is Heimdall's to do, and what isn't

- **Heimdall's: a quick, informal account of its own results.** The goal is something you can send to a
  colleague or a supervisor minutes after a run: these pages, these numbers, from these runs, at this revision,
  complete or not. Only Heimdall knows the results layout, the plot documents, the provenance and the
  statistics, so only it can pick and assemble them correctly, and rebuild them after new runs. Legible and
  honest is enough; polish isn't the aim.
- **Not Heimdall's: formal presentation.** Talks for reviewers, graded or examined work, papers and theses
  are made in Beamer, Overleaf, PowerPoint, Keynote, Google Slides or Quarto. That covers slide text, themes,
  institutional styles, slide formats, prose captions and citations. deck's wrapper over those tools carried
  four toolchains, pandoc's version quirks, a web font (I-78) and a theme key (I-105), and was never used for
  a talk.
- **The bridge is plain files.** The report's outputs are made to be lifted:
  - every figure it shows, copied as drawn (its PDF and PNG) into the report's folder;
  - the report's LaTeX source, which compiles alone in that folder (upload it to Overleaf as it is);
  - the statistics' own `statistics.csv`, untouched.

  Turning those into a formal document is the user's work in the user's tools.

### 1.3 The user's proposal, scrutinised

| Idea | Verdict | Why, and what changes |
|---|---|---|
| One command, `heimdall report`, for post-run presentation | **keep** | deck's name and its talk-writing ambition are the wrong shape, and its only use can't build. Retire it, keeping its two good ideas: one page across folders in a grid, labelled by events; copy-and-stamp rebuilds. |
| `[report]` inside the run TOML | **discard** | A run TOML says what to compute, and its `[plot]` is already copied into each result folder. A report reads result folders, which drift from run TOMLs (D-R12). It spans runs and projects, and it isn't a stage. The quick path it would have given comes from needing no recipe at all (N1). |
| A separate report config | **keep** | `configs/<P>/<name>.toml` with a top `[report]` table (§1.5). |
| `heimdall report <config> <results dir>`, the dir overriding the config's | **keep, made more general** | Sources on the command line replace `[report].from`: several, globs, and `<P>/<run>` (every configuration folder of the run, plus its runs-together folder when that is drawn). A section's own `from` stays. One recipe then works as a template for many runs: `heimdall report eic/weekly eic/zeus_validation/*_generator_pdf`. |
| `reports/` for output | **keep** | `reports/<P>/<name>/` (untracked, as now), or `-o DIR`. |
| Goal: a quick, presentable report of plots and stats | **keep, narrowed** | "A quick, informal report for colleagues or a supervisor: the chosen pages and numbers of one or more runs, and where they came from, with nothing to write." |
| Pick plots and sets from one result folder | **keep** | Sections pick by set, backend, page cells and page globs (the names in `plots/<set>/<backend>/`), and statistics by section. |
| Several runs | **keep, two layouts** | *Source by source* (each source's pages in turn), or *side by side* (a grid per page name, a panel per source: deck's block). Panels are pages, copied or drawn for the report, one source each; putting several runs' curves on one page stays `compare`'s and `[plot.across]`'s job. |
| Across projects | **keep** | Free, since every source is a full address. |

### 1.4 New ideas

**Worth doing (in the plan):**
- **N1 No recipe needed.** `heimdall report eic/zeus_validation/01_pdf` makes the default report:
  - a front page;
  - the statistics' headline (the top five and each statistic's ranking);
  - each drawn set's pages, a grid per page cell.
- **N2 Where it came from, up front.** It's the first thing a supervisor asks. For each source, from its
  `plot.toml` and records:
  - its address, config and configuration;
  - Heimdall's revision and when it was drawn;
  - its points: complete, failed or missing;
  - its event count;
  - whether it is compared against data or against a curve.

  Each grid is captioned with its source, set and page cell.
- **N3 Drawn for itself when needed, never into `results/`.**
  - **When:** a picked page that isn't drawn, or isn't drawn in the formats the report needs (a vector PDF), or
    a set's numbers that aren't measured.
  - **How:** the source's plot document is loaded with its outputs sent to
    `.cache/<P>/reports/<name>/<source>/` (P1's `plotdoc.load(path, folders=…)`), and is drawn or measured by
    `plot.draw` and `plot.measure`, the same code `heimdall plot` and `heimdall stats` run.
  - **The source untouched:** neither its `results/` folder nor its records is written.
  - **Stale:** a source whose points completed after its pages were drawn is flagged on the front page.
- **N4 Statistics generated by the report, only the sections chosen.** They come from the numbers: the
  source's `statistics.csv` (read by P1's `statstable.read`), else the report's own measurement (N3).
  - **The summary's sections:** through `bars.summary_model` and P1's `paper.write`, with their own notes.
    I-107's `summary_from_csv.py` already proved the path.
  - **A page's bar image:** through `bars.page`.
  - Nothing depends on `summary.pdf` or `bars/` being on disk.
- **N5 Everything it shows is in its folder** (the user's word, 2026-10-26).
  - **Copied or drawn:** every page, compare page and user file the report uses goes into `figures/` as its PDF
    and its PNG: copied when drawn, else drawn for the report (N3). A PNG is rendered by pdftoppm when a page
    has none.
  - **Created:** the statistics parts and bar images go into `stats/`.
  - **Composites:** none are made. A grid is only placement in `report.tex`, so each figure stays one file to
    take as it is.
  - **`report.tex`** names files in the folder only, by relative path, so it compiles alone.
- **N6 Quick to start.**
  - `--list`: what the report would include, with its page count; nothing is written.
  - `--init SOURCE`: a starter recipe, with that source's sets, page cells and pages listed and commented.
- **N7 A page to browse, for free.** `index.html` from the existing viewer, unchanged: the same grids, panel
  by panel, with links to each source's `summary.html`.
- **N8 Its own look, when wanted.** A section's `plot = { … }` takes any `[plot]` key, over the source's own
  (checked against the run schema's `plot` table). That includes a set of its own (`sets.<name>`, as in
  `[plot.sets]`), `normalise`, `formats` or a `legend_statistic`. That section's pages are then drawn for the
  report (N3), so a report can show a page cut a way no run drew it.

**Considered and dropped:**
- **X1** A report after every run or plot (the user's word: explicit only).
- **X2** Statistics across runs in the report: new numbers are stats' job, and `[plot.across]` already scores
  runs together.
- **X3** Slides, themes or templates of any kind (pptx, Beamer, dzslides, Overleaf bundles, a `template` key):
  formal presentation isn't Heimdall's.
- **X4** Free Markdown text. A title, a subtitle (the date, who it's for) and one plain `note` per section are
  enough.
- **X5** A self-contained `report.html` with the statistics' sortable tables inside: the PDF is what gets
  sent, `summary.html` already exists per set, and N7 links it.
- **X6** A manifest (`report.json`) and "what changed since the last build": stamps keep rebuilds fast, and
  the front page says where everything came from.
- **X7** Folder mode (a regex over loose files). It gives way to a section item, `files = ["extras/*.png"]`,
  relative to the recipe.
- **X8** Sheets as an item kind: a grid of pages already does a sheet's job.
- **X9** Migrating deck recipes: only one exists, and its sources are gone.

### 1.5 Decided (2026-10-26)

- **Q1 Output:** an A4 `report.pdf`, with every figure it shows in its folder (N5) and N7's page. No slides
  PDF, no composites and no pandoc target.
- **Q2 Where recipes live:** in `configs/<P>/<name>.toml`, beside the run TOMLs, told apart by a top
  `[report]` table.
  - **Addressed** like a config (`heimdall report eic/weekly`), or by a path.
  - **Built into** `reports/<P>/<name>/`. A report with no recipe goes to `reports/<P>/<run>/<cfg>/`.
  - **Walkers:** `heimdall ls` and `heimdall check` already take only files with `[run]`
    (`house.config_names`, `cli.py:1499`), and `house.importers` reads only `import` keys.
  - **A name clash** with a run of the same project is refused, so the two output trees can't collide.
- **Q3 Statistics:** re-rendered, only the sections chosen (N4), each source's as its own numbered part with
  its notes.
- **Q4 Execution** (the user's word): phased execution plan files are written in `.plans/` first. The compaction
  pauses come at the milestones that matter, not after every phase.
- **Q5 Refactoring** (the user's word): plot and stats backends may be reorganised where the report shares their
  code; the commands and their outputs stay as they are.

---

## 2. The plan

| Phase | What it gives | V-row | Then |
|---|---|---|---|
| **P0** Paperwork | `.plans/report/`: `00_Plan.md` (this audit, the decisions, the execution map), `P1_Modular.md`, `P2_Sources.md`, `P3_Build.md`, `P4_Drawn.md`, `P5_Deck_retired.md` (each: tasks, verification, a log); I-108 in `ISSUES.md`; CLAUDE.md's `.plans/` row; the milestone memory refined (Q4); gate P's baseline taken | none (a docs commit) | straight on |
| **P1** Plot and stats made modular | the shared pieces the report needs, every command's output unchanged (gate P) | V206 | **pause for compaction**: the refactor proven, before the new feature |
| **P2** Sources and recipes | sources, recipes, the schema, `--list`, `--init`, `check` / `ls` / `explain` | V207 | straight on |
| **P3** The build | `figures/` (copied), `stats/` (from `statistics.csv`), `report.tex`, `report.pdf`, `index.html`, on real results | V208 | **pause for compaction**: the report works end to end |
| **P4** Drawn for itself | N3 and N8: a source's document drawn or measured into the report's folders, a section's `plot = {…}`, bar images by `bars.page` | V209 | straight on |
| **P5** deck retired | deck's code, tests, folders and docs gone; the fast suite | V210 | **pause**: done, main fast-forwarded if built in a worktree |

### P1 Plot and stats made modular (V206)

Only what the report shares is reorganised. Each move keeps its callers' behaviour: the same files, the same
bytes, the same messages.

- **New `framework/runner/statstable.py`** (rank 4): the statistics table, moved out of `plot.py` (2081 lines).
  - **Moved:** `STATISTIC_COLUMNS`, `statistics_of`, `write_statistics`, `heading_of`, and the per-set
    tables, bar graphs and summary (`plot._tables` as `statstable.tables`). `plot.py` calls them from there.
  - **New:** `read(path) -> rows`, the inverse of `write_statistics` (the types as `statistics_of` gives them;
    the conversion `summary_from_csv.py` proved).
- **`framework/plot/figures/paper.py`: `write(document, target, formats, title)`.** This is the page loop
  (PdfPages, one PNG or SVG per page) moved out of `bars.summary_of`, which then calls it. The report writes
  its statistics parts with it.
- **`framework/plot/figures/layout.py`: one LaTeX placer.** `_draw`'s single page becomes a page writer that
  composites, sheets and P3's multi-page `report.tex` all use. That covers the panels in cells,
  `\includegraphics` keeping aspect, labels and `tex()` escaping. `composite` and `tile` keep their
  signatures.
- **`plotdoc.load(path, folders=None)`.** A document can be loaded with its outputs sent to other
  `RunFolders` (`plot.draw` takes every output path from its members' folders). `heimdall plot` and
  `heimdall stats` pass nothing, so nothing changes for them; P4 passes the report's.
- **Event counts in one place.** The report takes a member's events from its plot document (`plotdoc`'s
  `_member_events`, `count_tag`), so deck's `requested`, `analysed` and `count` aren't carried over; they go
  with deck in P5.
- **Not touched:**
  - the plot indexes (I-44), since their HTML is an output;
  - Paint, the backends, the page documents and the statistics' arithmetic.
- **Tests:**
  - `tests/runner/test_statstable.py`: a `statistics.csv` written then read gives back its rows;
  - `test_summary_layout`, `test_layout`, `test_plot_logs` and `test_deck_build` pass unchanged;
  - `tests/runner/test_imports.py` with `statstable`'s rank.
- **Gate P** (before at P0 on main, after at P1). In the scratchpad, with `HEP_CACHE` and `HEP_REPORTS` there,
  two of Brookhaven's result folders are drawn and measured from copies of their plot documents (the YODAs
  named by absolute path), as `heimdall plot <folder>` and `heimdall stats <folder>` draw a folder anywhere:
  `eic/zeus_validation/01_pythia_qed_lepton` and `02_generator_pdf`. For each, compare:
  - the list of files made;
  - `statistics.csv`, `summary.html` and `index.html`, byte for byte;
  - every PNG, byte for byte; where PNG bytes differ, pixel for pixel;
  - the PDFs' page counts and sizes (`pdfinfo`; their dates differ).

  The slow suite runs once, against its baseline (42 pass, 5 known failures). Brookhaven's `git status` and a
  tree hash of its `results/` and `records/` are unchanged.
- **Docs:** 06 (the modules, ranks), 07 V206.

### P2 Sources and recipes (V207)

- **New `framework/runner/report.py`**, at rank 4 (deck's).
  - **Sources.** A source is a folder holding a `plot.toml`: a configuration's, or a run's runs-together folder.
    - **Addressed by:** `<P>/<run>/<cfg>`, `<P>/<run>`, a path, or a glob.
    - **Its facts (N2):** from the document's `[source]`, `[axes]` and `[members]` (`plotdoc.load`).
    - **Its event count:** the members' own (P1).
  - **The recipe** (schema `framework/schema/report.toml`, tables `report` and `section`):
    - **`[report]`:** `title`, `subtitle`, `from`.
    - **`[[section]]`:** `title`, `note`, its own `from`, and one item:
      - `pages`, with `set`, `backend`, `cells`, `layout` (`"pages"` or `"sources"`), `columns` and
        `label` (`events` or `folder`);
      - `compare`: figure names;
      - `stats`: the summary's section keys (`top5`, `scoreboard`, `scoreboard-cells`, `head-to-head`,
        `scoreboards`, `chi2_ndf`, `rel_abs_area`, `area_ratio`, `ratio_mean`, `ratio_dev`, `area`);
      - `bars`: page globs, a bar image each (N4);
      - `files`.
    - **`plot = { … }` on a section (N8):** checked against the run schema's `plot` table.
    - **Checked** with `schema.check` and `did_you_mean`.
  - **The default recipe (N1):** used when no recipe is named.
  - **An example:**

    ```toml
    # configs/eic/weekly.toml
    [report]
    title    = "ZEUS photoproduction: generators and PDFs"
    subtitle = "for the group, 30 Oct 2026"
    from     = ["eic/zeus_validation/02_generator_pdf"]   # replaced by sources on the command line

    [[section]]
    title = "Standings"
    stats = ["top5", "ratio_dev"]

    [[section]]
    title = "Spectra"
    pages = ["d01-*", "d02-*"]                # set "totality"; backend: the first drawn of root, mpl, yoda
    note  = "Pythia 8.318 and Sherpa 3.0.5 against ZEUS 2012"

    [[section]]
    title  = "Run by run"
    from   = ["eic/zeus/0[1-3]_generator_pdf"]   # its own sources, kept on an override
    pages  = ["d01-x01-y01"]
    layout = "sources"                        # a grid per page, a panel per source
    label  = "folder"
    ```
  - **Resolving** a recipe against its sources gives a plan: each section's figures (source, set, cell, page)
    and its statistics parts, each marked *copied* (on disk) or *drawn* (for the report, N3). Until P4 a
    *drawn* entry is refused, with the command that would draw it.
- **`cli.py`:** `heimdall report [RECIPE] [SOURCE…] [--list] [--init SOURCE] [-o DIR]`.
  - The first argument is a recipe when it names a `configs/<P>/<name>.toml` with `[report]`, or a `.toml`
    path; otherwise every argument is a source.
  - A recipe named like a run of its project is refused.
  - **`--list`** prints the plan (each figure copied or drawn) and its page count.
  - **`--init SOURCE`** writes `configs/<P>/<name>.toml` once, never over a file.
  - **`heimdall check`** checks each recipe's keys against the schema.
  - **`heimdall ls`** lists the recipes under "reports".
  - **`heimdall explain report.<key>`** answers from the schema (house's deck entry becomes the report's).
  - The build is P3's; until then `heimdall report` without `--list` or `--init` says so.
- **Tests:** `tests/runner/test_report.py`, on synthetic result trees as `test_deck.py` builds them, plus a
  `statistics.csv`. It checks addressing, the recipe's checks and refusals, the default recipe, both layouts,
  the override of `from`, `--list` and `--init`.
- **Docs:**
  - 04 §15, generated from the schema (`heimdall make --framework docs schema`);
  - 05 §1.8 (the command);
  - 07 V207.

### P3 The build (V208)

- **Building, into `reports/<P>/<name>/`.** It copies and draws only what changed (deck's sha stamps).
  1. **`figures/`:** every page, compare page and user file is copied as drawn (N5), as
     `figures/<section>/<NN>_<source>_<page>.pdf` and `.png`. A page with no PNG gets one from `layout.png`.
     What no section uses any more is removed.
  2. **`stats/`:** `statstable.read` → rows → `bars.summary_model` → the chosen sections → `paper.write` →
     `stats/<source>.pdf` (P1).
  3. **`report.tex`** (A4, relative paths into the folder only):
     - a front page with the sources' facts (N2) and any flags;
     - the contents;
     - each section: its figures placed in a grid by layout's page writer (P1), each an `\includegraphics`
       of its PDF in `figures/` (vectors kept) and captioned;
     - the statistics pages included whole, with their own footers.
  4. **`report.pdf`:** pdflatex, with a second pass for the contents.
  5. **`index.html`:** `viewer.page` as it is (N7), with links to each source's `summary.html`.
- **Tests:** `tests/runner/test_report_build.py` (skipped where pdflatex is missing):
  - an A4 `report.pdf` (`pdfinfo`);
  - every file `report.tex` names is in the folder, and it compiles from a copy of the folder;
  - a rebuild copies and draws nothing;
  - a page whose source changed is copied again.
- **Docs:** 03 §11 becomes "Reports"; 06 (layout, ranks); 07 V208.
- **On real results, read-only,** before the pause (see Verification).

### P4 Drawn for itself (V209)

- **Loaded for the report.** The source's document is loaded with
  `plotdoc.load(path, folders=RunFolders(…))` (P1). Its pages, numbers, working files and failure logs go to
  `.cache/<P>/reports/<name>/<source>/`. Its `[plot]` gets the section's `plot` keys laid over it in memory,
  `formats` holding pdf and png, and `draw` only the sets the report needs. Nothing is written to the source.
- **Drawing:** `plot.draw` for missing pages and for sections with `plot`; `plot.measure` for numbers no
  `statistics.csv` holds. The results are then copied into `figures/` and `stats/` as in P3. A failure names
  its log (V204's `logs/plot/`, under that folder).
- **Bar images:** `bars.page(rows, stats/bars/<source>/<page>, ["pdf", "png"], title)`.
- **Tests:** `tests/integration/test_report_draw.py`, run on a fixture run's result folder:
  - a page drawn for the report with `plot = { normalise = "area" }`;
  - a set no run drew;
  - numbers measured when there is no `statistics.csv`;
  - the source's `results/` and `records/` byte for byte unchanged (a tree hash before and after).
- **Docs:** 03 §11 (what is drawn for a report, and where), 07 V209.

### P5 `heimdall deck` retired (V210)

- **Removed:**
  - `deck.py`, `schema/deck.toml`, `schema.DECK_TABLES`;
  - `layout.composite` and its `SIZES`, whose only user was deck (sheets use `tile`; the report places pages
    itself), with their cases in `test_layout.py`;
  - `migrate.deck_moves` and its call (`cli.py:1890`);
  - `paths.decks_root` and `HEP_DECKS`;
  - "decks" from `setup.FOLDERS`, and from the template's README and `.gitignore`.
- **`heimdall deck`** now stops with a message naming `heimdall report` (as V74 did for `plot FILE`).
- **Tests:** `test_deck.py` and `test_deck_build.py` deleted.
- **Issues:**
  - I-78 is deleted (it falls with deck);
  - I-105 loses its deck-template line;
  - I-44 notes that the viewer is now the report's.
- **Docs:**
  - 00, 01, 02, 03, 04, 05 and 06;
  - `docs/reporter/` gets a "superseded by `heimdall report`" line at its head (kept as history);
  - 07 V210.
- **Paperwork:** I-108 is deleted from `ISSUES.md` (its history is V206–V210), and `00_Plan.md`'s map is
  ticked.
- **Not touched:**
  - `recipes/base.toml`'s `decks = ["pandoc", "poppler"]` stays: a change to the base marks the stack
    (I-62), so the group is renamed when the base is next rebuilt;
  - Brookhaven's `decks/batch_1`, which is yours.

### Pace and verification

- **Pace:** each phase is built, then tested (light, one session), then committed by named paths with its
  V-row. Its phase file's log and `00_Plan.md`'s map are written at each commit, so a compaction loses
  nothing. Compaction pauses only where the table says: after P1, P3 and P5.
- **Before P1:** `heimdall runs`. If a live run uses main's checkout, the work is built in a worktree, since
  P1 changes code a running plot stage loads.
- **On real results, read-only (P3):** with `HEP_REPORTS` set to the scratchpad, build:
  - the default report of Brookhaven's `eic/zeus_validation/01_pythia_qed_lepton`;
  - a side-by-side report over `eic/zeus_validation/0[2-4]_generator_pdf`. Its recipe is a path in the
    scratchpad, never in Brookhaven's `configs/`.

  Check:
  - every page is A4 (`pdfinfo -l`);
  - the contents' pages are right;
  - every figure shown is in `figures/`, and `report.tex` compiles from a copy of the folder;
  - the time taken.

  At P4, again with `HEP_CACHE` in the scratchpad too: a section with `plot = { normalise = "area" }` drawn
  for the report. Brookhaven's `results/` and `records/` get a tree hash before and after, which must be
  equal.

  I view the pages and send the user the PDF. Brookhaven's `git status` must be unchanged.
- **Gates:**
  - `test_docs` at each phase;
  - gate P and the slow suite at P1;
  - the slow suite again at P4 (the new integration test);
  - the fast suite at P5.

---

## 3. Execution map

Built in the worktree `scratchpad/heimdall-report`, branch `report` (from main at `9028970`); main is
fast-forwarded at P5. Each row is ticked at its commit.

| Phase | V-row | Commit | State |
|---|---|---|---|
| P0 Paperwork | — | f9c2076 | done |
| P1 Plot and stats made modular | V206 | 1e9ffe6 | done: gate P same; paused for compaction |
| P2 Sources and recipes | V207 | 304d3f8 | done |
| P3 The build | V208 | (this commit) | done: on Brookhaven's results; paused for compaction |
| P4 Drawn for itself | V209 | | |
| P5 deck retired | V210 | | |
