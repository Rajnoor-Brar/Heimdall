# P4: the run's `report.toml` (V209)

[00_Plan.md](00_Plan.md) §1.6 and §1.7 (A1–A6), the plan amended after P3 by the user's word. The run says what its
folders' reports look like; `heimdall report <folder>` builds that.

## Tasks

- **`[report]` in a run TOML** (A3).
  - **`config.py`:** `report` joins the run TOML's tables (`[sections].order` in `schema/run.toml`,
    `RunConfig.report`). Imports merge it as any table (`_over`'s deep merge: a list of sections is replaced).
  - **`config.check_report(table, where, run_toml)`:** the recipe checks move here from report.py, so a run
    TOML's `[report]` is checked when it is read (rank 1). That is every key against `schema/report.toml`, each
    section one item kind, `stats` keys, a section's `plot` by `check_plot`, and `from` refused in a run TOML.
    `report.py` keeps the names (`ITEMS`, `SUMMARY`, …) by importing them.
  - **The template:** named as `[config].import` names a file (`_import_path`): read, checked and followed
    when it names its own (a circle refused). The merge: keys over the template's, sections after its.
  - **`schema/report.toml`:** `[report.template]`. A run TOML's `[report]` and a recipe's are one table
    (`schema.REPORT_TABLES`), so `heimdall explain report.template` and 04 §15 cover both.
  - **The editor's `run.schema.json`:** `[report]` added if `make schema` can take a second file's table
    simply; else noted here and left.
- **One recipe shape** (A4): `[report]` with `[[report.section]]` in a recipe file, in a run TOML and in
  `report.toml`. `load_recipe` reads `report.section`; P2's tests and 04 §15's example are moved to it.
- **`report.toml`** (A2).
  - **`report.recipe_for(run, configuration, plot)`:** the run TOML's `[report]` resolved: its template's and
    its own keys, `{project}`, `{run}`, `{configuration}` and `{title}` filled in, and the default sections
    when none are given. The default is A1's: a Standings section on the first set measured, then a pages
    section for each set in the document's `[plot].draw`.
  - **`report.write_recipe(...)`** writes it beside `plot.toml`, `report.toml`, under a header: written by the
    run from `<config>` (and `<template>`); rewritten each time; to change it, change those, or copy it into
    `configs/`.
  - **Called** where `plot.toml` is written (`cli.draw_run`, and the three places that write a missing one:
    `heimdall plot` from a record or a config, `heimdall migrate --plot-docs`), through one helper.
- **Entry modes and naming** (A5, A6) in `report.planned`.
  - The first argument is a recipe only when it ends `.toml`: `<P>/<name>.toml` under `configs/`, else a path.
    A run TOML there gives `recipe_for` for each source's configuration (by its document's
    `[source].configuration`).
  - One configuration folder and no `.toml`: its `report.toml`, else the default.
  - **Built where `results/` has its sources** (A6): the sources' common address under `reports/`, unless
    `-o` or the recipe's `[report].output` says otherwise; `output` refused in a run TOML; two projects with
    neither, refused. The run-name clash check goes.
  - P2's bare `<P>/<name>` recipe lookup goes.
- **The default** (A1): `default_recipe` takes `[plot].draw`'s sets; the 40-page hint goes.
- **`--init`:** `heimdall report <P>/<name>.toml --init SOURCE` (the `.toml` named, as everywhere).
- **`heimdall ls`:** recipes listed as `<P>/<name>.toml`.

## Verification

- **`tests/runner/test_report.py`:**
  - the modes: a folder's own `report.toml`, a folder without one, a recipe over a folder, a run TOML over a
    folder, a recipe alone;
  - a template's keys under the run TOML's, its sections first;
  - the placeholders filled;
  - `from` refused in a run TOML;
  - a template naming itself refused;
  - where each is built: a folder's, a run's, two runs', two projects' (refused), `-o`, `output`;
  - a bare `<P>/<name>` now taken as a source.
- **`tests/runner/test_report_build.py`:** a build from a folder's `report.toml`.
- **`tests/integration/test_plot_stage.py`:** the plot stage writes `report.toml` beside `plot.toml`, with
  the fixture's sets.
- **`heimdall check`:** on a run TOML with a bad `[report]` key, and on one whose template is missing.
- **On Brookhaven, read-only:** `heimdall report eic/zeus.toml
  eic/zeus_validation/02_generator_pdf` (mode 2, a run TOML, no `[report]`: the default), and a scratch copy
  of a run TOML naming a scratch template. `HEP_REPORTS` in the scratchpad; Brookhaven untouched.
- `test_docs`, `test_imports`, and the tests of `config`, `house` and the CLI.

## Log
