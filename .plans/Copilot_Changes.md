# Copilot changes

## 2026-10-28 — plot axis ranges

- Audited `[plot]`: settings already cover backends/formats/objects, data, sets and across-run
  selections, drawing controls (gutters, logs, auto-range, normalisation, voiding, ratio), page labels
  and titles, styles, and statistics. Range-related settings covered gutters and automatic x clipping,
  but there was no explicit x/y axis-limit option.
- Added `plot.x_range` and `plot.y_range`, each a two-item pair of numbers or `"default"` endpoints.
  Figure-level overrides, schema validation, generated editor schemas, Paint, and the YODA/mpl range
  handoff now support them. Paint rejects non-increasing final limits and non-positive lower limits
  on logarithmic axes; heat maps receive the explicit bounds too.
- Updated the plot guide, page-document example, Paint internals, and generated config reference.
- Heimdall files edited, and where:
  - `framework/schema/run.toml`: documented schema metadata and `[plot.x_range]` / `[plot.y_range]`
    definitions, including pair length, `"default"` endpoints, and increasing numeric bounds.
  - `framework/runner/schema.py`: list item choices, exact list lengths, ordered numeric bounds, and
    corresponding editor JSON-schema generation.
  - `framework/runner/plot.py`: `page_settings`, carrying both ranges to generated page TOMLs with
    figure-over-`[plot]` precedence.
  - `src/Apps/Paint/Page.hh`: `Paint::Page` range endpoint fields and parsing/validation of
    `[page].x_range` and `[page].y_range`.
  - `src/Apps/Paint/main.cc`: apply explicit limits after calculated gutters; range JSON reports tool
    ownership only when neither endpoint is set.
  - `src/Apps/Paint/Draw.hh`: apply explicit axis bounds to regular plots and heat maps, with log-axis
    and increasing-range checks.
  - `framework/plot/yoda/backend.py`: clarified how explicit ranges participate in the backend's
    Paint range handoff; the handoff itself consumes the same range output.
  - `framework/schema/run.schema.json` and `framework/schema/run.v3.schema.json`: regenerated editor
    schemas for the two range keys and their endpoint/length constraints.
  - `docs/03_Plots.md`: `[plot]` example, drawing order, and the page-key list inherited by figures.
  - `docs/04_Config_Reference.md`: generated `[plot]` and figure key tables.
  - `docs/05_Commands_and_Tools.md`: Paint page TOML example.
  - `docs/06_Internals.md`: Paint's x/y range calculation order and heat-map bounds.
  - `tests/runner/test_plot.py`: schema acceptance/rejection, defaults, and figure inheritance.
  - `tests/integration/test_paint.py`: explicit and `"default"` endpoints in Paint's range output.
  - `.plans/Copilot_Changes.md`: this change record.
- Inspected the 12 ZEUS graphs under
  `/home/rajnoor/Github/Brookhaven/results/eic/zeus/03_generator_pdf/plots/pythia_all/mpl/py8`.
  Added per-object figure ranges in `configs/eic/zeus.toml` and all eight existing
  `results/eic/zeus/**/plot.toml` documents:

  | Objects | y range |
  |---|---:|
  | d01 | [0.001, 100000] |
  | d02 | [0, 1200] |
  | d03 | [0, 450] |
  | d04 | [0.01, 1000] |
  | d05–d07 | [0.001, 10000] |
  | d08 | [0.001, 1000] |
  | d09–d10 | [0.001, 100000] |
  | d11–d12 | [0, 1100] |

  The requested `results/zeus` directory was absent; the existing results are under `results/eic/zeus`.
  The TOML settings were updated; plot image files were not regenerated.
- Validation: generated docs/schema; 175 plot and docs tests passed; 26 Paint range integration tests
  passed. The combined integration run had one failure in the slow mpl/YODA pixel-equality
  test (`test_the_mpl_backend_draws_mkhtml_s_pages_pixel_for_pixel[yoda]`).
  `heimdall check eic/zeus` also reports an existing plot-set reference to `PDF4LHC21`, which is
  absent from that config's active PDF points. All nine edited Brookhaven TOML files parse, and
  their plot/figure tables pass schema validation.
- Follow-up range verification: strengthened Paint's integration test to set `y_range = [-2, 1]`
  while curve data exceeds 1, and assert the emitted range remains exactly `[-2, 1]`; added a YODA
  handoff test that checks those same explicit limits are emitted. Both tests pass in a combined
  171-test run with the plot runner tests.

## 2026-10-29 — visible overflow for explicit y ranges

- Numeric `y_range` endpoints remain fixed and clip curve values at the frame; they do not cap or
  replace data values. Paint and mpl now add thinner, color-matched line segments 2 px outside an
  explicit upper or lower frame edge for over-range bins. When several curves overflow the same
  bin and side, each gets an equal part of that bin's width, ordered from least to greatest overflow.
- The deprecated YODA/mkhtml backend does not draw overflow marks.
- Heimdall files edited, and where:
  - `src/Apps/Paint/Draw.hh`: added ROOT/NDC overflow segments for explicit numeric endpoints,
    including band envelopes, clipped to the visible x span and split equally by bin; the axis
    bounds and underlying values are unchanged.
  - `framework/plot/mpl/backend.py`: collected curve and band values and draws equivalent mpl
    segments outside the axes, including a 2 px offset and equal per-bin width allocation.
  - `tests/runner/test_plot.py`: verifies mpl curve-bin collection and marks beyond both upper and
    lower bounds, with the expected gap, thinner widths, color mapping, and equal width distribution.
  - `tests/integration/test_paint.py`: verifies ROOT renders upper and lower overflow marks outside
    the frame with the configured 2 px gap and thinner line widths.
  - `framework/schema/run.toml`: documents fixed limits/overflow indicators and labels YODA deprecated.
  - `framework/plot/yoda/backend.py`: identifies the already-frozen YODA backend as deprecated.
  - `framework/plot/mpl/backend.py`: documents its explicit-range overflow-marking exception to
    mkhtml matching.
  - `framework/schema/run.schema.json` and `framework/schema/run.v3.schema.json`: regenerated the
    editor-schema descriptions for `[plot].y_range` and the deprecated YODA backend.
  - `docs/03_Plots.md`: documents the rendering behavior and YODA limitation; marks YODA deprecated.
  - `docs/04_Config_Reference.md`: regenerated the `[plot].y_range` and backend reference descriptions.
  - `docs/06_Internals.md`: documents Paint's clipped values and overflow marks in its drawing order.
- Validation: rebuilt only Paint, regenerated docs/schema, and passed the plot, docs, and Paint
  integration suites (207 tests).

## 2026-10-30 — `heimdall runs` filtering and recent history

- Changed `heimdall runs` with no options to list only active runs. Added mutually exclusive
  `--5`, `--10`, `--20`, and `--50` options to show that many of the latest runs regardless of
  state, oldest first and newest last. Each run's block is separated by an empty line.
- Heimdall files edited, and where:
  - `framework/runner/cli.py`: added and dispatched the four count options; updated command help.
  - `framework/runner/house.py`: filters to active runs by default or selects recent entries by count
    or age, orders entries chronologically for display, and separates each run block.
  - `framework/runner/runs.py`: updated the registry module description to reflect the listing modes.
  - `tests/runner/test_runs.py`: covers running-only default, all four limits, chronological ordering,
    and blank-line separation.
  - `docs/05_Commands_and_Tools.md`: documents the new command forms and output ordering.
  - `docs/02_User_Guide.md`: updates the command lookup table, the terminal-run overview, and the
    cluster-submission listing description.
- Validation: regenerated CLI help docs and schemas; the runs, docs, cluster, and detached-run tests
  passed (82 tests).
- Added mutually exclusive `--week` and `--month` filters for all runs started in the last 7 and 28
  days, respectively.
- Updated files:
  - `framework/runner/cli.py`: adds both period options, passes their day limits to the listing, and
    updates the synopsis.
  - `framework/runner/house.py`: filters all recorded and unrecorded runs by start time; preserves
    chronological ordering and empty-line separators.
  - `tests/runner/test_runs.py`: verifies each period includes completed runs through its boundary,
    excludes older runs, and cannot be combined with a count option.
  - `docs/05_Commands_and_Tools.md` and `docs/02_User_Guide.md`: documents `--week` and `--month`.
  - `.plans/Copilot_Changes.md`: records these implementation and verification details.
- Validation: the runs, docs, cluster, and detached-run test suites passed (85 tests);
  `heimdall runs --help` lists all six mutually exclusive options, and `git diff --check` passed.

## 2026-10-30 — quit key for `heimdall watch`

- Changed `heimdall watch` so `d` and Ctrl-C detach, leaving the run running, while `q` asks the run
  to stop cleanly. The `s` key no longer triggers a stop prompt.
- Files edited, and where:
  - `framework/runner/cli.py`: maps `d`/`D` and Ctrl-C to detach, and `q`/`Q` to a clean stop;
    updates the on-screen hint and removes the `s` stop confirmation.
  - `tests/runner/test_detach.py`: verifies `d` and Ctrl-C leave the job running, while `q` stops it.
  - `docs/00_Quick.md`: documents the quick-start watch-key hint.
  - `docs/02_User_Guide.md`: documents `d`/Ctrl-C detach and `q` stop behavior.
  - `docs/05_Commands_and_Tools.md`: documents watch keys and the explicit stop command.
  - `.plans/Copilot_Changes.md`: records this change.
- Validation: `tests/runner/test_detach.py` passed (15 tests), including `d`/Ctrl-C detach, `q` clean
  stop, and the PID-namespace guard; `git diff --check` passed, and no docs or code references to the
  old `s` stop key remain.
- Corrected in review (I-114): references to `s`, `y` did remain, in docs/06_Internals.md §10 and I-07's checklist.

## 2026-10-30 — point progress in `heimdall runs`

- Added a progress line with completed/total point counts and active parallel points for running
  jobs. The active-point count is omitted for non-running entries; unavailable counts render as
  `NULL`. Progress is refreshed on point-start and point-terminal events, so no periodic polling
  interval is needed.
- Files edited, and where:
  - `framework/runner/runs.py`: `Recorder` aggregates run totals, terminal points, and active points
    across configurations and updates those values in the run registry as events arrive; it also
    captures runner-assigned serials from the actual output record directory.
  - `framework/runner/cli.py`: initializes progress fields on new registry entries and passes the
    entry ID, configuration serials, and labels to the recorder.
  - `framework/runner/house.py`: formats point progress and active parallelism on a separate line;
    omits active parallelism for non-running runs and shows `NULL` for unavailable counts.
  - `tests/runner/test_runs.py`: checks live progress persistence, runner-assigned serial capture,
    the requested output layout, and historical `NULL` values.
  - `tests/runner/test_runlog.py`: updates the completed-run counts assertion for the new row.
  - `.plans/Copilot_Changes.md`: records this change.
- Validation: the run registry, run listing, run log, and cluster tests passed (58 tests);
  `git diff --check` passed.
