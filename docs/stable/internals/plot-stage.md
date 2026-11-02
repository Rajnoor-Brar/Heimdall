---
id: plot-stage
summary: the plot stage inside: members and stand-in plans, the merged sweep, page documents, drawing, what a record gives a drawing
code: framework/runner/plot.py, framework/runner/plotdoc.py, framework/runner/record.py
---

# The plot stage inside

`plot.draw(run, configuration, plans, say, others)` runs after the stages, on `--only plot`, and in `heimdall plot`. Its input is the points whose record is complete (`plot.drawable`): a plan whose `.complete` is there (any identity: one other than the plan's is drawn as recorded, and named) and whose YODA is on disk. `heimdall plot RECORD` gives it `plot.Member`s instead (`plot.recorded`): points.json read with the snapshot's run; nothing is planned.

## A record is a config

`record.record_of` finds a configuration's folder with a snapshot (`record.write_snapshot`): the files the run read (`snapshot_files`: the errand file, its imports and report templates, base cards, filters, root style, master) and `snapshot.toml`. `cli.opened` turns it into a config for `run`, `plot` and `status`: `$HEIMDALL_CONFIGS` at its `config/`. An identity writes a path under another configs root as `{work}/configs/…` (`paths.identity_texts`), so a record's points plan to the identities they ran with.

## Steps

1. **Figures.** `plot.figures(run)` reads `[plot.figures.<key>]` into `Figure`s in file order; the implicit figure is `_pages`' own. A figure carries every `page = true` key it sets; `override_of` and `chosen` resolve a key, most specific first, `"default"` keeping the value below.
2. **Members.** A page builder works on plans keyed by `point.name`, each with a YODA. Some classes build stand-in plans (`dataclasses.replace`), each YODA made once per change of its inputs, stamped by a sha256:
   - **derived** (`point_yodas`, `derive.py`): each point's YODA with `/FIGURES/<name>` appended;
   - **merged** (`_merged`): per value of the kept axes, members merged by `tools.merge_files`;
   - **scan** (`_scanned`, `derive.scan_value`): a Scatter2D per value of the other curve axes;
   - **compare** (`compare_pages`): every compared configuration's members, gaining a `@configuration` axis. Another errand file's members carry their own run in `context["run"]`.
3. **The sweep in one file** (`merge`): every member's YODA merged by `App_yd2rt --merge`, a directory per member, raw entries and `points.json`, at `.cache/<A>/plots/<E>/<R>/<cfg>.root`. Rebuilt only when a member's YODA changed. Reference data are converted once into `.cache/<A>/datasets/`.
4. **Page documents** (`_pages`):
   - Objects come from `hepfiles.objects`, `objects_2d`, keyed by the option-free path, so a swept option's variants are curves on one page.
   - A declared defined figure claims its objects' pages; two claiming one object are refused.
   - A page per set, cell and object (a 2D object: per member, `_heatmap`), or per set and cell for an overlay. A compare figure's pages have no set.
   - `located` names each page, `page_settings` takes labels from the `.plot` under the figure's and `[plot]`'s values, with placeholders filled by `filler`, `_banded` folds bands, and labels pass through `for_root` (LaTeX → TLatex).
5. **Draw** (`_draw`):
   - One `Paint.exe` per `PAINT_BATCH` pages, each outcome a JSON line; `--ranges` writes ranges and voids beside the config for other backends.
   - `plots/<set>/<backend>/` and `statistics/<set>/` are cleared first (`_clear`, only under `results/`).
   - Other backends get the same `Page`s, with `output` moved (`for_backend`). Heat maps are Paint's alone.
   - An `index.html` per set and backend (`write_index`), and `plots/index.html` (`write_sets_index`).
   - Sheets tile what was drawn (`figures/layout.py`). A compare figure is drawn by each of its configurations' stages once all have complete points.
   - A failed page is counted, the run exits 1, the others are drawn. Failures leave a digest in the record's `logs/plot/` (`plot.failure_log`; the folder is a ContextVar, as a sweep's runs draw on threads). `heimdall clean` keeps it.

## Cells and statistics

**Cells** (`_pages.cells`): members by their `plot_points` tags, or by `[plot].sets` (`sweep.set_entries`, `sweep.chosen_points`, checked at plan time by `check_figures`), each cut by `split`. merged, scan and compare figures pass `grouped=False`.

**Statistics:** Paint writes `<page>.toml.stats.json` for every page it reads (`Paint::statistics`, `Transform.hh`). `_draw` runs Paint `--ranges-only` first on pages with a `legend_statistic` and adds numbers to labels, then writes each set's `statistics.csv`. `statistic_pages` builds a statistic figure's pages from those rows.

## The style

A stack of TOML layers over `src/Apps/Paint/base.toml`, checked against it at plan time (`check_style`). Keys a backend cannot honour are errors, never silently dropped: v1's `LegendXPos` was parsed and ignored.
