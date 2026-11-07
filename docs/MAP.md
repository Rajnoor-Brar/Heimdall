# Map

Generated: `heimdall make --framework docs`. One line a page: what it holds, its size.
`⟵ live:` a live doc changes that page, and wins until crystallised (see `work`).

## rules

- [code](rules/code.md): how code here is written; rules that hold across modules and are not visible from one file (2 KB)
- [invariants](rules/invariants.md): what must never happen in this repo and on this machine, and why; read before acting (3 KB)
- [work](rules/work.md): where work in progress lives; the live-doc format; the crystallise protocol (2 KB)
- [writing](rules/writing.md): how a page is written, where a fact belongs, how anything cites anything (3 KB)

## client

- [context](client/CONTEXT.md): what an AI working in a work dir needs first; heimdall context prints it (12 KB)

## reference

- [commands](reference/commands.md): every heimdall command and its arguments (21 KB)
- [keys](reference/keys.md): every setting in one line each, for grep: key, type, default (10 KB)
- [legacy](reference/legacy.md): the errand file's older (v2) names and today's (2 KB)

## reference/settings

- [settings-cluster](reference/settings/cluster.md): every key of [cluster], for running a job on Slurm (4 KB)
- [settings-errand](reference/settings/errand.md): every key of an errand file's [file], [errand], [cfgs.*] and [quantities.*]: type, default, values, effect (20 KB)
- [settings-plot](reference/settings/plot.md): every key of [plot], its figures, data and runs together, and [stats] and [score]: type, default, values, effect (32 KB)
- [settings-report](reference/settings/report.md): every key of a report's recipe: [report] and [[report.section]] (9 KB)
- [settings-stack](reference/settings/stack.md): every setting of the stack's build: what is built, with what, how many cores, nested as the file nests them (6 KB)
- [settings-style](reference/settings/style.md): every style key a page may set in [plot.style] or a style file, nested as the file nests them (6 KB)
- [settings-tools](reference/settings/tools.md): every key of a [tools.<name>] table, and each standard tool's own options (5 KB)

## stable/start

- [everyday](stable/start/everyday.md): the everyday commands and what to write for the common needs, on one page (2 KB)
- [first-run](stable/start/first-run.md): a first run from a new work dir to drawn pages, what to look at, and how a job behaves on a terminal (3 KB)
- [model](stable/start/model.md): what Heimdall is, how a run works, the core vocabulary, and the three places files live (4 KB)

## stable/guide

- [chains](stable/guide/chains.md): chains of tools: file chains, other generators, comparing generators and setups, stages made once (5 KB)
- [errand-file](stable/guide/errand-file.md): an errand file's anatomy, a complete example, which value wins, imports and starting a new assignment (6 KB)
- [guide-failures](stable/guide/failures.md): what to do when a point fails, and what each common refusal means (3 KB) ⟵ live: live-show
- [housekeeping](stable/guide/housekeeping.md): check, status, clean, migrate, reproduce, and pinning which stack a study was made with (1 KB)
- [outputs](stable/guide/outputs.md): what a run writes and where: records, results, reports, cache; what is kept; what may be deleted (3 KB) ⟵ live: live-points-library
- [overlay](stable/guide/overlay.md): heimdall overlay: any YODA or ROOT files on one page, with no errand file (1 KB)
- [paths](stable/guide/paths.md): how a path in an errand file resolves, how a Run's folder is named, and every placeholder (5 KB)
- [plots-across](stable/guide/plots-across.md): the Runs of an errand on one page: [plot.across], @events, @tag, [from], prefer and ignore (2 KB)
- [plots-curves](stable/guide/plots-curves.md): curves' labels and looks, per quantity value, per tag across Runs, and bands (1 KB)
- [plots-data](stable/guide/plots-data.md): reference data on pages, why the map is explicit, and ratio pads (1 KB)
- [plots-figures](stable/guide/plots-figures.md): figure classes and what each builds, types, and how a figure inherits [plot] (5 KB)
- [plots-sets](stable/guide/plots-sets.md): pages of chosen points: the totality set, named sets with page axes and curve groups, looks, short forms, split (5 KB)
- [plots-statistics](stable/guide/plots-statistics.md): the numbers behind each page: statistics.csv's columns, [stats], bar graphs, the summary and how points are scored (4 KB)
- [plots-style](stable/guide/plots-style.md): how a page's look is layered, a style file, legends outside the frame, and seeing the merged style (2 KB)
- [plots](stable/guide/plots.md): how a run's pages get made, and how to get the ones you want; objects, figures, pages and sets (7 KB) ⟵ live: live-across-axes, live-no-yoda-backend, live-record-formats, live-run-labels, live-score-engine, live-score-settings, live-scoring, live-set-merge, live-statistics-format, live-stats-catalogue, live-stats-core, live-stats-measured-bins, live-stats-rms
- [programs](stable/guide/programs.md): your own programs in a chain: a module, an integrated program, an exec tool, a tool folder of your own (4 KB)
- [reports](stable/guide/reports.md): heimdall report: an A4 report of Runs' pages and numbers; recipes, sections, what it draws for itself, where it is built (6 KB) ⟵ live: live-scoring
- [results-python](stable/guide/results-python.md): reading a run's results from Python, for notebooks and statistics tools (1 KB)
- [scale](stable/guide/scale.md): making a study bigger: more Rivets, several points at once, replicas and combine, seeds, several event counts, Slurm (6 KB)
- [sweeps](stable/guide/sweeps.md): recipes for varying things: grids, zips, fixed values, native keys, analysis options, several configurations, listed points (4 KB)
- [validation](stable/guide/validation.md): every rule checked at plan time, C1–C14, with an example message (3 KB)
- [watching](stable/guide/watching.md): looking before running, subsets, reruns, following a job, and a Run's record as a config (4 KB)

## stable/tools

- [tools-delphes](stable/tools/delphes.md): the delphes tool: it reads a file, never a FIFO; its card and count check (1 KB)
- [tools-exec](stable/tools/exec.md): the exec tool: any executable; heimdallkit; turning a program into a tool folder of your own (1 KB)
- [tools-herwig](stable/tools/herwig.md): the herwig tool: read and run, beams in Herwig's slots, its four PDF objects, the repository (1 KB)
- [tools-madgraph](stable/tools/madgraph.md): the madgraph tool: proc card, launch script, the cached process directory, showering its LHE (1 KB)
- [tools-merge](stable/tools/merge.md): the merge tool: rivet-merge, in post; also what shards, combine and merged figures use (1 KB)
- [tools-module](stable/tools/module.md): the module tool: running a Module.hh program; its config, counts and integrated programs (1 KB)
- [tools-overview](stable/tools/overview.md): the standard tools at a glance; tools, packages and libraries; what is not a tool (3 KB)
- [tools-plotmerge](stable/tools/plotmerge.md): the plotmerge tool: the sweep in one file, as a copy elsewhere or a YODA version (0 KB)
- [tools-pythia](stable/tools/pythia.md): the pythia tool and App_Pythia: its card, what the runner owns, dealing events, the sidecar, what running it taught us (4 KB)
- [tools-rivet](stable/tools/rivet.md): the rivet tool: analyses and options, shards and how many, counts; what running it taught us (3 KB)
- [tools-sherpa](stable/tools/sherpa.md): the sherpa tool: YAML cards, what the plan owns, the cached integration, progress, several Sherpas for one curve (3 KB)
- [tools-whizard](stable/tools/whizard.md): the whizard tool: SINDARIN point cards, beams by name, what the plan owns, its limits (1 KB)
- [tools-yd2rt](stable/tools/yd2rt.md): the yd2rt tool and App_yd2rt: YODA to ROOT, merging a sweep into one file (1 KB)

## stable/setup

- [base](stable/setup/base.md): the conda base: what it holds, what stays the OS's, updating it, and base=system (2 KB)
- [build-fixes-generators](stable/setup/build-fixes-generators.md): why the generator recipes are written as they are: each problem a build hit and what is done about it (5 KB)
- [build-fixes](stable/setup/build-fixes.md): why the core recipes are written as they are: each problem a build hit and what is done about it (5 KB)
- [cluster](stable/setup/cluster.md): Heimdall on a cluster without sudo: an image or a user-space build, filesystems, what has been proven (2 KB)
- [environment](stable/setup/environment.md): gjallarhorn, the shell's environment, heimdall build, bifrost, recognised work dirs, every environment variable (5 KB)
- [fresh-machine](stable/setup/fresh-machine.md): from a clone to a working Heimdall on a new machine: what you need, the build, a first work dir, the checks (3 KB)
- [images](stable/setup/images.md): Heimdall and a machine root as one Apptainer image: building, using, what it can and cannot do (2 KB)
- [platforms](stable/setup/platforms.md): what differs on Ubuntu and on macOS; what is proven and what is not (2 KB)
- [stack](stable/setup/stack.md): how build_stack.py builds the stack: settings and their layers, cores, resuming, downloads, adding a package, what each package is (7 KB)
- [toolkits](stable/setup/toolkits.md): which set of packages to build: every toolkit, writing your own, isolated stacks, ready-made from conda-forge (4 KB)
- [verify](stable/setup/verify.md): how to check a new or changed machine: doctor, the support matrix, the tests, and comparing physics against a kept point (2 KB)

## stable/internals

- [build](stable/internals/build.md): make, heimdall build, the rules, // requires:, the flag cache, and what rebuilds what (4 KB)
- [caches](stable/internals/caches.md): the prepare cache: what it keeps, its key, what counts as a hit (2 KB)
- [connections](stable/internals/connections.md): how tools connect: FIFOs, files, products, the rules checked at plan time, the context file, sharding (3 KB)
- [cxx-kits](stable/internals/cxx-kits.md): writing C++ here: Module.hh, integrated programs, Status.hh and the status protocol, heimdallkit (6 KB)
- [data-model](stable/internals/data-model.md): the runner's types, which module owns each, and what each holds (3 KB)
- [docs-system](stable/internals/docs-system.md): how the docs are generated and checked; the page model, the map, the drift report, the site (2 KB)
- [events](stable/internals/events.md): how a tool's status reaches the views: pipes, filter rules, digests, the event stream and its listeners, the views (6 KB)
- [extending](stable/internals/extending.md): how to add a standard tool, a plot backend or a figure class, and what each must touch (3 KB)
- [failures](stable/internals/failures.md): how a chain of processes fails and how each way is handled; attribution; exit codes (2 KB)
- [identity](stable/internals/identity.md): what a point's identity hashes, how seeds follow from it, what skips a point and what reruns it (4 KB) ⟵ live: live-identity-golden, live-points-library
- [layout](stable/internals/layout.md): Heimdall's folders, the machine root's and a work dir's; what is in git; how the roots are found; where a run's files go (5 KB)
- [live-runs](stable/internals/live-runs.md): a run as a worker and a client; the run registry; signals, pausing, resuming, heimdall watch and stop (4 KB) ⟵ live: live-live-parallelism, live-resume-record-config, live-runs-listing
- [paint](stable/internals/paint.md): Paint inside: the order of a page's arithmetic, drawing, heat maps, dumps; what is load-bearing (4 KB)
- [plot-backends](stable/internals/plot-backends.md): how the backends beside Paint draw the same pages, what they honour and refuse (2 KB)
- [plot-stage](stable/internals/plot-stage.md): the plot stage inside: members and stand-in plans, the merged sweep, page documents, drawing, what a record gives a drawing (5 KB)
- [provenance](stable/internals/provenance.md): what a run records and where: provenance.json, attempts.jsonl, points.json, tag, identity.json (2 KB) ⟵ live: live-points-library, live-record-formats
- [run-flow](stable/internals/run-flow.md): a run from command to pages: planning, one point, scopes, points at once, several runs, combine, and where each check lives (5 KB)
- [runner](stable/internals/runner.md): the runner's modules and ranks, what each owns, what plugins may import; the C++ files and what each links (8 KB)
- [testing](stable/internals/testing.md): the test suites, how they isolate themselves, the gates, and what holds the docs (3 KB) ⟵ live: live-identity-golden, live-shadow-root
- [tool-contract](stable/internals/tool-contract.md): what a tool folder holds, the search path, every tool.toml section and key, render.py, providers, and what the runner does per point (10 KB)

## stable/design/decisions

- [decisions-architecture](stable/design/decisions/architecture.md): why Heimdall is shaped as it is: processes, one flat runner, no libraries, where things live (3 KB)
- [decisions-chain](stable/design/decisions/chain.md): why tools connect and run as they do: FIFOs, stages, shards, context files, tool folders (2 KB)
- [decisions-errand-file](stable/design/decisions/errand-file.md): why an errand file is read as it is: forms, imports, vars, defaults, paths (3 KB)
- [decisions-identity](stable/design/decisions/identity.md): why identity, seeds and skipping work as they do (1 KB)
- [decisions-plots](stable/design/decisions/plots.md): why plots and figures work as they do: backends, labels, sets, plot documents, statistics (5 KB)
- [decisions-quantities](stable/design/decisions/quantities.md): why sweeps, quantities and points work as they do (2 KB)
- [decisions-reports](stable/design/decisions/reports.md): why heimdall report works as it does (1 KB)
- [decisions-run](stable/design/decisions/run.md): why a run behaves and records as it does: views, records, logging, pausing, the registry (3 KB)
- [decisions-stack](stable/design/decisions/stack.md): why the stack is built as it is: recipes, toolkits, the conda base, the machine root, images, the cluster (3 KB)

## stable/design

- [glossary](stable/design/glossary.md): Heimdall's words beyond the model's core vocabulary; the core ones are in the model page (2 KB) ⟵ live: live-himinbjorg
- [history](stable/design/history.md): where Heimdall came from, in a dozen lines (1 KB)
- [principles](stable/design/principles.md): the principles behind Heimdall's shape, each with what it buys and what it costs (4 KB)
- [refused](stable/design/refused.md): what Heimdall deliberately does not do, and why (1 KB)

## live

- [live-across-axes](live/across-axes.md): Runs with different axes drawn together: every member has every quantity (a quantity a Run never names is unset there), Runs told apart by serial, heimdall diff, Run labels as axes (3 KB)
- [live-himinbjorg](live/himinbjorg.md): Himinbjorg is the name of what was called the machine root; paths.himinbjorg() is its function (2 KB)
- [live-identity-golden](live/identity-golden.md): every fixture point's identity parts are kept in a golden file, and a test compares them (2 KB)
- [live-live-parallelism](live/live-parallelism.md): heimdall runs -i N --jobs M changes a running job's points at once while it runs: a request file and SIGUSR2; raising starts more, lowering stops none (2 KB)
- [live-no-yoda-backend](live/no-yoda-backend.md): the yoda plot backend (rivet-mkhtml) is gone; mpl owns the transforms it borrowed (2 KB)
- [live-points-library](live/points-library.md): a points library per Assignment pools generation points by a key that ignores the point's name; library = true | "only" (3 KB)
- [live-record-formats](live/record-formats.md): record files carry a format version, and heimdall records upgrade brings old ones to it (2 KB)
- [live-resume-record-config](live/resume-record-config.md): a paused run resumes with the latest attempted Run's recorded config snapshot (2 KB)
- [live-run-labels](live/run-labels.md): a Run's tag is one of its labels: key=value words from heimdall tag, in the tag file's TOML, each an across axis @key (2 KB)
- [live-runs-listing](live/runs-listing.md): heimdall runs lists a run as a six-line block, coloured on a terminal with a log link; --state filters; stop -i N (4 KB)
- [live-score-engine](live/score-engine.md): framework/stats/score.py: how a table's rows become a point's score, worst page, veto and per-purpose shares, and the other aggregators (4 KB)
- [live-score-settings](live/score-settings.md): the [score] table, [stats].metrics and centres, a set's score, a figure's weight, and heimdall explain score (2 KB)
- [live-scoring](live/scoring.md): the statistics summary and the report's statistics by purpose: standings, a section a purpose, a metric's ranking and table, a head to head only when asked (5 KB)
- [live-set-merge](live/set-merge.md): a set's merge: a quantity's values become one curve per combination of the other axes, by pooling statistics or a mean, with an optional band (4 KB)
- [live-shadow-root](live/shadow-root.md): the tests run on a shadow Himinbjorg, and a guard watches the live one (1 KB)
- [live-show](live/show.md): heimdall show prints what a Run, a point or a tool did, read from its record; heimdall log is show --log (2 KB)
- [live-statistics-format](live/statistics-format.md): statistics.csv is format 2 with a statistics.json sidecar and the default metrics as columns (2 KB)
- [live-stats-catalogue](live/stats-catalogue.md): the opt-in metrics and means of framework/stats, off until named (2 KB)
- [live-stats-core](live/stats-core.md): framework/stats computes metrics and means from Paint's measured bins (2 KB)
- [live-stats-measured-bins](live/stats-measured-bins.md): Paint writes the bins it measured, in each curve's stats.json (1 KB)
- [live-stats-rms](live/stats-rms.md): a statistic over pages is a root mean square, not a mean (1 KB)
