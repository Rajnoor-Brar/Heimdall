---
id: runner
summary: the runner's modules and ranks, what each owns, what plugins may import; the C++ files and what each links
code: framework/runner/__init__.py, framework/runner, src
---

# The runner

One flat package, `framework/runner/`, with a declared rank per module. A module imports only from its own rank or a lower one, and the graph has no cycles. `RANKS` in `runner/__init__.py` is the one table: `tests/runner/test_imports.py` enforces it, and a test holds the table below to it. v1's lesson: the half whose layering was written down and checked held; the half that was not had nine cycles.

| Rank | Module | Owns |
|---|---|---|
| 0 | `errors.py` | `HeimdallError(message, where, hint)`, `did_you_mean` |
| 0 | `paths.py` | the two roots: Heimdall (`heimdall_root`, where the code is) and the work dir (`work_root`: `$HEIMDALL_WORK` or the walk up to a `heimdall.toml`), `heimdall.toml` read (`work_meta`) |
| 0 | `schema.py` | the errand file's schema, `framework/schema/run.toml`: every key's type, choices, bounds, default, inheritance, doc and notes |
| 0 | `hepfiles.py` | reading YODA text (1D and 2D objects, `/RAW` twins, counters; `.gz` too) and Rivet's data directories, once |
| 0 | `plugins.py` | loading a folder's Python by path, once: `render.py`, `backend.py`, `provider.py`, the figures' plugins |
| 0 | `v3.py` | the errand file's third form read as the second's: `[file]`, `[cfgs.<name>]`, tools typed by their table's name, quantities as points rows (`fixed`, `to`, compound `fields`, beams `a`/`b`), `events` lists |
| 0 | `viewer.py` | the viewer: a page of blocks of labelled panels, sizes and columns, ← →, with a front block (a report's sources, V208) and blocks of text (`body`: a report's tools' configurations, V210) |
| 0 | `image.py` | Apptainer images: the system's runtime (`apptainer`, else `singularity`), an image by name in the machine root's `images/` or by path, `heimdall image build` (heimdall.def filled, a clean copy of the checkout, `--fakeroot`) and the listing, the image a point runs in for provenance |
| 0 | `shellrc.py` | the block Heimdall keeps in ~/.bashrc and ~/.zshrc: `gjallarhorn [title]` and `bifrost`, between marker lines |
| 1 | `config.py` | load the TOML, `[config].import`, `--set`, the strict schema check and the figure rules |
| 1 | `quantities.py` | the master TOML, static values and selectors, who consumes what (C7), provider checks (C10) |
| 1 | `sweep.py` | points from `sweeps` (grid, zip and listed rows: `Listed`, V154), point names, pages (`split_axes`: a listed group's paged members), a group's key, tag and labels at a point (`group_key`, `group_tag`, `group_labels`), `--points` |
| 1 | `labels.py` | Rivet `.plot` keys, YODA's text macros, line breaks, LaTeX → TLatex for Paint, TLatex → LaTeX for `heimdall migrate` |
| 1 | `events.py` | the event stream: the bus, the watch socket (`Hub`), the `--journal` file, the run's own log (`RunLog`, V202) |
| 1 | `workdirs.py` | the work dirs this machine knows, by title: `<machine root>/workdirs.toml` (`$HEIMDALL_WORKDIRS`) |
| 1 | `runs.py` | the run registry, `<machine root>/runs/` (`$HEIMDALL_RUNS`): an entry per run and cluster submission, written whole by one writer |
| 1 | `knowledge.py` | the docs as data: pages and frontmatter, the map, the drift report, the site |
| 2 | `tools.py` | the tool folders |
| 3 | `execute.py` | `[prelim]`, prepare steps, groups as supervised process groups, the count checks, settling products |
| 3 | `status.py` | the status and output pipes, read on a thread per tool; the filter rules; each tool's digest |
| 3 | `record.py` | identity, seeds, skip, provenance, `points.json` |
| 3 | `results.py` | a run's results from Python, read from `points.json` |
| 4 | `watch.py` | the reducer of events (`State`), the live and plain views, `heimdall watch` |
| 4 | `plot.py` | the plot stage: figures, the merged sweep, page configs, the style layers, Paint and the other backends; `heimdall overlay` on files |
| 4 | `plotdoc.py` | a run's plot document, `results/<A>/<E>/<R>/plot.toml`: written by the run (what it knows rewritten, the user's `[plot]` and `[stats]` kept), read by every drawing as a `Doc`, a `DocConfiguration` and members |
| 4 | `statstable.py` | the statistics table: a page's numbers as rows, a set's `statistics.csv` written and read back (`read`), its bar graphs and summary (`write_set`, through `figures/bars.py`) |
| 4 | `post.py` | the pre, combined and post stages |
| 4 | `report.py` | `heimdall report`: sources (result folders holding a `plot.toml`, by address, run, path or glob) and their facts, a recipe (`[report]`, `schema/report.toml`: a file of its own, an errand file's, a folder's `report.toml`, which `write_recipe` writes beside `plot.toml`, V209) or the default one, resolved into a plan of sections, built where `results/` has its sources (`_out`), what each tool was given read from the records (`configured`: a card's baseline and what varied, `split`, `key_value`, V210), grids of figures and statistics parts |
| 4 | `cluster.py` | `heimdall cluster`: [cluster] in its layers, the Slurm scripts (a pre job, a points array, a finish job, each an ordinary `heimdall run --stages …`), `sbatch` and the dependencies, `jobs.toml`, `--status` from `sacct` and `squeue`, `--cancel` |
| 5 | `cli.py` | `argparse`: `run`, `plot`, `overlay`, `watch`, `check`, …; the order of events |
| 5 | `house.py` | `ls`, `explain`, `status`, `clean` |
| 5 | `migrate.py` | `heimdall migrate`: errand files and cards rewritten in today's forms |
| 5 | `docs.py` | `make docs`: the manual's generated blocks (keys, style, commands) from the schema, base.toml and the CLI |
| 5 | `doctor.py` | `heimdall doctor`: every installed package's checks (its recipe's `[[verify]]`, through `recipes/verify.py`), the scan for libraries that no longer resolve, Heimdall's own rows |
| 5 | `bifrost.py` | `bifrost` (also `heimdall bifrost`): the environment's packages, conda-forge's (`base_packages`) and PyPI's (`base_pypi` |
| 5 | `setup.py` | `heimdall setup` (a work dir from `framework/templates/work/`, never overwriting) and `heimdall where`; the `[framework] expects` warning |

## Plugins and dependencies

- A tool plugin (`render.py`, `provider.py`) and a backend's `backend.py` may import only `PLUGINS_MAY_IMPORT`, and never another plugin. The figures' plugins import nothing of the runner.
- The runner is standard library plus `tomli_w`. Lazily: `yaml` (Sherpa's plugin), `uproot` (the Delphes count, `heimdall overlay` on ROOT files), YODA's Python (figures, backends), PIL (sheets). `rich` is optional.

## The C++

No libraries and no namespace hierarchy: a few headers, and apps that each link what their `// requires:` line names ([cxx-kits](cxx-kits.md)).

| File | Is | Links |
|---|---|---|
| `Status.hh` | `Status::Reporter`: JSON lines to `$HEIMDALL_STATUS_FD`, or plain stderr; heartbeat; drop-on-full | nothing |
| `Kit.hh` | `Kit::Exit` (the exit-code table), `Kit::Args`, `Kit::Json` | nothing |
| `Module.hh` | the kit for module programs: argv, config, HepMC input, ΣW, σ, `RootOut`, the report | HepMC3, toml++, (ROOT) |
| `PythiaRun.hh` | App_Pythia's Pythia rules, shared with integrated programs: σ combination, stamping, seed check, chunking | Pythia 8, HepMC3 |
| `App_Pythia.cc` | Pythia → HepMC3, threaded, σ combined, sidecar | Pythia 8, HepMC3, zstd, zlib |
| `App_PythiaCheck.cc` | the card check: Pythia's own reader on every line | Pythia 8 |
| `App_yd2rt.cc` | YODA → ROOT; `--merge` | YODA, ROOT |
| `Apps/Paint/` | pages from page TOMLs and the style, many per process | ROOT, toml++ |
