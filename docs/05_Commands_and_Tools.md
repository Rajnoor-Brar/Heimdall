# 05 — Commands and tools

Every `heimdall` command and its options, the build and the environment; then every standard tool: what
it runs, how its card is written, which quantities it consumes, what it writes, how its events are
counted, what it puts in the context file, and the quirks that shaped it (the ledger rows,
[07 §3](07_Record.md#3-the-knowledge-ledger)). Then the apps as you run them by hand.
- **Generated:** the commands' options come from `heimdall`'s own parser (`make docs`).
- **Written by hand:** the tools' sections come from `framework/tools/<tool>/`.
- **Writing a new tool folder:** [06 §16](06_Internals.md#16-the-tool-folder-contract).

---

## 1. Commands

Every command is one program's (`framework/bin/heimdall` runs `framework/runner/cli.py`): `heimdall help`
lists them, `heimdall help <command>` (or `heimdall <command> --help`) says one, and a misspelt command gets
the nearest. Throughout:
- **`--dry-run`** shows what a command would do and does nothing: `run` (also `--plan`), `deck` (also
  `--list`), `clean`, `cluster`, `migrate` (its default: `--apply` writes), `build` (`make -n`) and
  `stack build`.
- **`--set KEY=VALUE`** works on every command that plans: `run`, `check`, `status`, `clean`, `cluster`.
- **`--plain`** may come anywhere, for any command.
- **Errors** are one shape: `heimdall: what`, then `where:` and `hint:`. A record id, when one helps, comes
  last, as `(see V93)`.
- **`heimdall stack build|list|status|doctor`** is the machine's stack: its builder
  (`recipes/build_stack.py`, on macOS `recipes/platforms/mac/build.sh`), its recipes, its packages,
  its checks.

Every subcommand and its arguments (options and positionals may come in any order):

<!-- generated: commands -->
**`heimdall run`**: plan and run a configuration

| Argument | Meaning |
|---|---|
| `config` | configs/<Project>/<name>[.toml], ./path from the work dir, or a record <Project>/<run>/<NN_cfg> (what it ran with: its snapshot) |
| `[configuration]` | overrides [run].configuration; under [run].sweep_runs, runs only it |
| `--plan, --dry-run` | print the plan; run nothing |
| `--why` | for each point that would run, what changed since it last completed; run nothing |
| `--show-config` | print each configuration's resolved values and where each came from; run nothing |
| `--card TAG` | with --plan: that tool's card for the first point, each line with where its value comes from |
| `--points SEL` | run a subset: tags, indices or quantity=tag |
| `--detach` | start the run in the background and return: heimdall watch follows it, heimdall stop stops it (on a terminal, a run started without it leaves on d too) |
| `--set KEY=VALUE` | override one value for this invocation (repeatable), in the file's own names: run.events=100 (v3), run.event_count=100 (v2) |
| `--rerun` | ignore skip-unchanged; under a serial the file sets, overwrite points made from other inputs |
| `--only pre\|post\|plot` | rerun only the pre tools, the post tools or the plots |
| `--no-plot` | draw nothing after the points (its plot.toml is written all the same), whatever [run].plot says |
| `--no-stats` | measure nothing after the points, whatever [run].stats says |
| `--stages LIST` | run only these stages, skip-unchanged: pre, points, combine, post, plot (comma-separated; heimdall cluster's jobs) |
| `--plain` | plain lines instead of the live view |
| `--wait` | a point another session is running: wait for it (default: skip it, naming who runs it) |
| `--journal` | also write every status event to records/…/status.jsonl (for heimdall watch --file and replay) |
| `--logs` | keep every tool's whole output in records/…/logs/<point>/<tag>.log (default: only a failed tool's last lines) |
| `--keep WHAT` | also keep (comma-separated): logs, journal, work (a finished point's whole working folder), cache (card checks); also hep.toml's and machine.toml's [run] keep |

**`heimdall plot`**: draw a configuration's pages from its complete points

| Argument | Meaning |
|---|---|
| `config` | the run config, or a record <Project>/<run>/<NN_cfg>: its points as they were recorded, with the config they ran with (its snapshot, which you may edit) |
| `--plot FILE` | a file whose [plot] draws instead of the run's: configs/<P>/<name>, ./… or /… |
| `--sets NAMES` | draw these sets only (comma-separated; default: the document's [plot].draw, else every set) |
| `--points SEL` | pages of these points only, in this order, in the folder points/: indices, names, globs, tags or quantity=tag, comma-separated ([plot].sets for one set) |
| `--plan` | say each set's page cells and their curves, from the complete points; draw nothing; with --style-sync: what would change, written nowhere |
| `--style-sync CONFIG` | take this config's [plot] and [stats] into the plot documents named (<P>/<name>/<cfg>, or <P>/<name>: each of its runs), what each run knows left as it is; nothing is drawn unless --replot |
| `--replot` | with --style-sync: then draw what was synced |
| `--across` | the runs of this run TOML together, results/<P>/<name>/plot.toml: its [plot.across] sets |
| `--keep WHAT` | cache: keep the card checks (as heimdall run --keep); the drawing's working files are .cache/'s anyway |
| `[configuration]` | overrides [run].configuration; under sweep_runs, only it |
| `--set KEY=VALUE` | as for heimdall run |

**`heimdall stats`**: a run's statistics alone: its pages' numbers against the data, drawing no page

| Argument | Meaning |
|---|---|
| `config` | a run <P>/<name>/<cfg>, a folder with a plot.toml, <P>/<name> (each of its runs), or a run TOML (its configurations' newest runs) |
| `[configuration]` | with a run TOML: only this configuration |
| `--sets NAMES` | measure these sets only (default: [stats].sets, else [plot].draw, else every set) |
| `--set KEY=VALUE` | as for heimdall run |
| `--across` | the runs of this run TOML together (as heimdall plot --across) |

**`heimdall overlay`**: overlay any YODA/ROOT files through Paint, with no run TOML

| Argument | Meaning |
|---|---|
| `FILE…` | YODA (.yoda, .yoda.gz) or ROOT files |
| `-o, --output OUTPUT` | where the pages go (default results/plots/<first file>) |
| `--labels LABELS` | legend labels, comma-separated, one per file |
| `--objects GLOB…` | only these YODA paths |
| `--formats FORMATS` | pdf, png, svg, eps (default pdf,png) |
| `--ratio` | a ratio panel against the first curve |
| `--style FILE` | a style file over src/Apps/Paint/base.toml |

**`heimdall deck`**: a deck of slides from drawn pages, in reports/<deck>/ (deck.toml, deck.md)

| Argument | Meaning |
|---|---|
| `deck` | decks/<deck> (built into reports/<deck>), or a path starting ./, ../ or / |
| `--list, --dry-run` | each block, its panels and where they came from; nothing written |
| `--only TARGETS` | some of pdf, pptx, html, overleaf, viewer (comma-separated) |
| `--init` | write deck.md once: a title slide and a slide per block |

**`heimdall ls`**: every config and its configurations

| Argument | Meaning |
|---|---|
| `[project]` | only this project's configs |

**`heimdall explain`**: a run TOML key: its type, default and meaning (the schema's)

| Argument | Meaning |
|---|---|
| `key` | e.g. plot.y_gutter, run.events, cfgs.pdf.threads, quantities.<q>.points, rivet.analyses |

**`heimdall status`**: each configuration's points: complete, stale, running, failed or stopped (when, and why), incomplete or to run; its events, seeds and tools

| Argument | Meaning |
|---|---|
| `[config]` | one config, or a record <P>/<run>/<NN_cfg> (default: every config) |
| `[configuration]` | one configuration of it |
| `--set KEY=VALUE` | as heimdall run's, for the view |
| `--stack` | the loaded stack instead: each package installed, its release and state; the libraries' versions |

**`heimdall migrate`**: rewrite run TOMLs and their cards in today's forms (a diff, or --apply)

| Argument | Meaning |
|---|---|
| `CONFIG…` | configs to migrate (default: every config) |
| `--v3` | into the run TOML's third form (03 §6, runner/v3.py) |
| `--layout` | move the work dir's older layouts into today's: logs/ into records/<run>/logs/, points into points/ (and output/ first, if any); no configs are read |
| `--list` | with --layout: every move, one a line |
| `--snapshot RECORD` | give a record that ran before snapshots one: copy a config's files into <record>/config/ (--from, default the config its points.json names) and say which points it gives the same identity |
| `--plot-docs RECORD…` | write the plot document (results/<run>/plot.toml) of every record without one, or of these (<P>/<name>/<cfg>), from its snapshot (else the config its points.json names) |
| `--from CONFIG` | with --snapshot: the config to copy |
| `--set KEY=VALUE` | with --snapshot: the overrides it ran with (default: those its points' provenance records) |
| `--apply` | write the changes (default: print the diff) |
| `--dry-run` | print the diff, write nothing (the default) |

**`heimdall reproduce`**: run a finished point again, from its provenance, beside it

| Argument | Meaning |
|---|---|
| `provenance` | records/…/<point>/provenance.json |
| `--anyway` | run it even though the setup changed since |
| `--plain` | plain lines instead of the live view |

**`heimdall clean`**: remove what the runner made and no plan uses: working folders (records/…/logs/) and .cache/ (a point's records with --records)

| Argument | Meaning |
|---|---|
| `[config]` | one config (default: every config, and the unused caches) |
| `--dry-run` | list only |
| `--set KEY=VALUE` | as heimdall run's: what the plans use |
| `--yes` | delete without asking |
| `--records` | also the records no plan has (provenance, identities, completion): asked for even with --yes |

**`heimdall check`**: check run TOMLs: every configuration loaded, validated and planned

| Argument | Meaning |
|---|---|
| `CONFIG…` | configs to check (default: every configs/<Project>/*.toml with a [run]) |
| `--set KEY=VALUE` | as heimdall run's: check what that run would |

**`heimdall watch`**: attach the live view to a running job

| Argument | Meaning |
|---|---|
| `[config]` | the run config whose job to watch (default: the latest job) |
| `[configuration]` | overrides [run].configuration (or the sweep's latest) |
| `--plain` | plain lines instead of the live view |
| `--file STATUS.JSONL` | follow a --journal run's status file instead |
| `--pid N` | the run of this process (heimdall runs lists them) |

**`heimdall runs`**: what runs on this machine now, and what ran in the last 30 days

| Argument | Meaning |
|---|---|

**`heimdall stop`**: stop a running job as Ctrl-C would: its points end cleanly, a rerun resumes

| Argument | Meaning |
|---|---|
| `[config]` | the run config whose job to stop (default: your only running job) |
| `[configuration]` | the configuration it runs |
| `--pid N` | the job of this process (heimdall runs lists them) |
| `--no-wait` | ask it to stop and return, without waiting for it to end |

**`heimdall cluster`**: run a configuration as Slurm jobs (sbatch): a pre job, a point per array task, a finish job

| Argument | Meaning |
|---|---|
| `config` | the run config, as heimdall run names it |
| `[configuration]` | overrides [run].configuration; under [run].sweep_runs, submits only it |
| `--points SEL` | submit a subset: tags, indices or quantity=tag |
| `--set KEY=VALUE` | override one value for this submission (repeatable; cluster.time=… too); the jobs get it |
| `--keep WHAT` | what each job's run also keeps (as heimdall run --keep) |
| `--rerun` | submit complete points too, and rerun them |
| `--dry-run` | write the job scripts and print the sbatch lines; submit nothing |
| `--status` | the latest submission: each point's state (sacct, squeue) |
| `--cancel` | scancel the latest submission's jobs |

**`heimdall setup`**: make a work dir: the key folders, hep.toml and the template's files (never overwrites)

| Argument | Meaning |
|---|---|
| `dir` | the work dir's folder: new, empty, or a work dir to complete |
| `--project P` | also configs/<P>/ with a starter run TOML and card, and modules/<P>/ |
| `--git yes\|new` | commit what was added (only that), in the git repository the folder is in, or a new one when it is in none; --git=new: a repository of its own even inside another |
| `--adopt` | make a work dir of a folder that has files but no hep.toml |
| `--name NAME` | the work dir's name in hep.toml (default: the folder's) |
| `--example NAME` | also a working example project to run first: jets (the guide's Demo project: Pythia → Rivet → pages against ZEUS data) |
| `--refresh` | bring the framework's own files (Makefile, README/HEIMDALL.md, CLAUDE.md, .vscode, the .gitignore block) up to today's template, as a diff; never the user's files |
| `--yes` | with --refresh: write without asking |

**`heimdall doctor`**: what this machine's stack and Heimdall can do, checked

| Argument | Meaning |
|---|---|
| `--quick` | skip the slow runs (Herwig's LHC.in): under a minute |
| `--record` | write this machine's summary to recipes/support/<platform>-<host>.toml (the support matrix) |
| `--matrix` | the support matrix: every machine's recorded summary |

**`heimdall tools`**: every tool folder: the work dir's tools/, the machine root's, Heimdall's

| Argument | Meaning |
|---|---|
| `NAME \| new NAME…` | a folder to show, or new and a folder to make |
| `--package RECIPE` | heimdall tools new: a recipe the tool runs ([tool] packages; again for more) |
| `--runs COMMAND` | heimdall tools new: its program ([tool] executable) |
| `--from SOURCE` | heimdall tools new: the folder it starts from (exec, module: a copy; any other: extends it) |

**`heimdall build`**: compile the work dir's module programs and Rivet plugins (make all)

| Argument | Meaning |
|---|---|
| `targets…` | make targets (default: all) |
| `--framework` | Heimdall's apps instead (framework/Apps/) |
| `--tests` | with --framework: the C++ tests too |
| `--clean` | empty the build first |
| `--configure` | probe the toolchain again (rewrite flags.mk) |
| `-j, --jobs N` | parallel jobs (default: every core) |
| `--dry-run` | what make would do (make -n); nothing built |

**`heimdall make`**: make one source of the work dir (or --framework, Heimdall's): <path>/<X>.exe, <path>/<x>.so

| Argument | Meaning |
|---|---|

**`heimdall stack`**: this machine's stack: heimdall stack build|list|status|doctor [options]

| Argument | Meaning |
|---|---|

**`heimdall help`**: a command's help: heimdall help <command>

| Argument | Meaning |
|---|---|
| `[command]` |  |

**`heimdall refresh`**: reload this shell's environment (gjallarhorn.sh's shell function)

| Argument | Meaning |
|---|---|

**`heimdall quit`**: leave this shell's environment (gjallarhorn.sh's shell function)

| Argument | Meaning |
|---|---|

**`heimdall cd`**: cd to a work dir's folder: heimdall cd PROJECT [configs|modules|results|records|logs] (gjallarhorn.sh's shell function)

| Argument | Meaning |
|---|---|

**`heimdall recognise`**: record work dirs by title, in the machine root's workdirs.toml (gjallarhorn <title> goes to one)

| Argument | Meaning |
|---|---|
| `[path]` | a work dir, or a folder to search below (default: here) |
| `--as TITLE` | record the work dir under this title instead |
| `--list` | every title, its path, and whether it is still a work dir |
| `--forget TITLE` | take a title out of the record |
| `--path TITLE` | print the work dir of TITLE (gjallarhorn asks this) |

**`heimdall bifrost`**: the environment's packages (conda-forge; -python: PyPI), added, dropped or shown; --shell: gjallarhorn's block in ~/.bashrc and ~/.zshrc

| Argument | Meaning |
|---|---|
| `PACKAGE…` | conda-forge packages ("gsl=2.8", "gsl 2.8.*"), or PyPI ones with -python |
| `-python, --python` | PyPI packages, by their pip names |
| `--drop` | take the packages out |
| `--shell install\|remove` | write (or take out) gjallarhorn and bifrost in ~/.bashrc and ~/.zshrc |
| `--conda` | -c, -conda: the tools (recipes) ready-made from conda-forge, what they need too |
| `--build` | -b, -build: the tools built here from their recipes; -b@<toolkit>: with its changes |
| `--yes` | switch without asking (it reruns points and rebuilds) |

**`heimdall image`**: Apptainer images of Heimdall and a machine root: list them, or build one

| Argument | Meaning |
|---|---|
| `[action]` |  |
| `KEY=VALUE…` | build: packages=@kit (default @primary), cores=N, root_cores=N |
| `--name NAME` | build: the image's name (default: the toolkit's) |
| `--dirty` | build: take uncommitted changes as they are |

**`heimdall where`**: which Heimdall and which work dir this shell sees

| Argument | Meaning |
|---|---|
| `--hep` | only Heimdall's folder |
| `--work` | only the work dir (exit 2 outside one) |
<!-- /generated -->

### 1.1 `heimdall run`

A run TOML may give the commands that read it their preference switches (`rerun`, `wait`, `detach`, `plain`,
`journal`, `logs`, `replot`, `keep`), in `[heimdall]` (04 §3); the command line wins over it.

The order is: the pre stage → every point not complete (in point order, `parallelism` at a time) →
`points.json` → the combined groups → the post stage → the plot stage. A failed point does not stop
the others.

- **`--plan`** prints everything and runs nothing:
  - per point: the values and their consumers, the groups and each tool's argv, what each reads and
    writes, the prepare steps and whether they are cached, the output and results directories, and
    whether the point is complete;
  - the pre, combined and post stages;
  - the page count;
  - each point's seed.
- **`--why`** gives, for each point and stage that would run, what changed since it last completed,
  from its `identity.json`: `events: 10 → 20`, `tools.pythia.card: + PDF:pSet = …`.
- **`--show-config`** prints each configuration's resolved values and the layer each came from (its
  own, `extends`, `[run]`, default), what `[file].import` gave, and the interfaces the chain
  makes.
- **`--points SEL`** takes comma-separated point names, single tags, 1-based indices, or
  `quantity=tag`. The other points keep their state, and `points.json` lists them all. It is
  refused under a sweep of several runs: name the configuration.
- **`--set KEY=VALUE`** overrides one value of the TOML, by dotted key, before anything is checked.
  The keys are the file's own names. The value is read as TOML, else as a string: `--set
  run.events=50000`, `--set cfgs.pdf.threads=8`, `--set quantities.energies.fixed=18x275`, `--set
  'plot.formats=["png"]'`, `--set plot.min_entries=default` (a v2 file: `run.event_count`,
  `run.cfgs.pdf.threads`, `static.energies`).
- **`--rerun`** runs complete points (and the stages) again.
- **`--only`:** `--only plot` draws the pages and runs nothing; `--only pre` and `--only post` run
  that stage whether or not it is complete.
- **`--stages LIST`** runs only the named stages of `pre, points, combine, post, plot`, each skipping
  what is unchanged (`--rerun` as usual): what `heimdall cluster`'s jobs run (§1.9). A run of the points
  alone writes no `points.json` and draws nothing; the points refuse to start without their pre
  stage complete.
- **`--journal`** also writes the run's events to `records/…/<cfg>/status.jsonl`. Without it,
  nothing of the run's state is on disk.
- **`--logs`** keeps every tool's whole output; without it, only a failed tool's last 200 lines are
  kept.
- **`--keep WORD,…`** keeps more than the default, which is the records, the results, each finished
  point's cards and configs, a failed tool's last lines and the prepare caches. The words: `logs` (as
  `--logs`), `journal` (as `--journal`), `work` (a finished point's whole working folder), `cache` (card
  checks, converted reference data, the plot stage's working files and skip markers). The work dir's
  `hep.toml` and the machine's `machine.toml` may say the same as `[run] keep = ["…"]`; the three
  add up (04 §14).

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | everything done or skipped |
| 1 | a point, a stage or a page failed |
| 2 | a config error, before anything ran |
| 6 | stopped by the user (Ctrl-C, SIGTERM or a closed terminal: SIGINT, then SIGTERM, then SIGKILL to the running tools; a second is a hard stop, the tools killed at once; a third kills the process) |

Under `[run].sweep_runs` (04 §4.1), the command exits 6 if a run was stopped, else 1 if any failed,
else 0. With `[run] notify = "desktop"`, the end is also a desktop notification.

### 1.2 `heimdall plot` and `heimdall overlay`

- **`heimdall plot CONFIG [CFG]`** draws a config's pages, as after a run (`--only plot`), from each point
  whose record is complete: a point that ran with other inputs than the config gives now (a card edited,
  a binary rebuilt) is drawn as recorded and named. Under `[run].sweep_runs` it draws every swept
  configuration's, each under its `run NN - <title> -` line, and the compare figures whose configurations
  are all complete.
- **`heimdall plot <P>/<run>/<NN_cfg>`** (a record: a configuration's folder of `records/`, or a path to it
  or to its `results/` twin) draws the points that run recorded, with the config they ran with: its
  snapshot, `records/…/config/` (02 §8.1). Nothing is planned. `heimdall run` and `heimdall status` take a
  record too: they read the snapshot as `configs/` (its imports and cards), with its configuration and
  `--set` overrides (yours after them).
- **`--plot FILE`** draws with another file's `[plot]` (a TOML holding `[plot]`, named as a config is)
  instead of the run's.
- **`heimdall overlay FILE…`** (`heimdall plot FILE…` is refused with the hint) takes files ending
  `.yoda`, `.yoda.gz` or `.root`:
  - one page per object any of them holds;
  - one curve per file, or one per point of a merged sweep file (labelled from the `points.json`
    inside it).

  `-o` defaults to `results/plots/<first file's stem>/`; `--labels` gives one label per file; and
  `--style` is a style file over base.toml.

### 1.3 `heimdall ls`, `heimdall explain`, `heimdall status`, `heimdall clean`

This is housekeeping.

- **`ls`** lists every config and its configurations, with descriptions; a `*` marks what `heimdall run
  CONFIG` runs.
- **`explain`** gives a key's type, default, choices, bounds, inheritance, doc and notes, from the
  schema (`framework/schema/run.toml`): `plot.y_gutter`, `run.events`, `cfgs.pdf.threads`,
  `quantities.<q>.points`, `plot.figures.<f>.logy`, or a bare key looked up in every table. It also
  answers for a table (`heimdall explain cfgs`), a v2 name (`run.event_count`), a tool folder's option
  (`rivet.analyses`), a style key (`style.page.dpi`), a quantity of the vocabulary, `deck.toml` and
  `machine.toml`.
- **`status`** gives every configuration's points and stages, each **complete**, **stale** (complete
  for an earlier identity: it reruns), **running** (a session holds its lock: `(pid N on <host>,
  since …)`), **incomplete** (begun, not done: failed or stopped) or **to run**. It reads the
  records and the locks, so deleting a configuration's `logs/` or `.cache/` changes no state. Each comes with when it
  finished and its results' size, and `[running]` marks a configuration a job is running now. `status --stack` gives each package of
  `env/stack.toml`, its version and where it is.
- **`clean`** removes, by lifecycle, what the runner made and no plan uses:
  - within each configuration's folder, the working folders no plan has (in `records/…/logs/`) and
    the `.partial` leftovers (there and in `results/…/`);
  - with no config named, every config is planned (all must plan), and the `logs/` of configuration
    folders no configuration has and the prepare cache entries of `.cache/` no plan references go too;
  - with `--records`, also the point records no plan has (`records/…/points/`: provenance, identity,
    completion), never a configuration's `cluster/` submissions. Removing records is asked for by
    name on a terminal (type `records`), even with `--yes`.

  It never removes a result: an unused point's `results/` folder is listed as kept. It lists first,
  then asks on a terminal (`--yes` elsewhere); `--dry-run` only lists, and it refuses while a job is
  running.
- **Two sessions, one point**: a point another session is running is skipped, its block naming
  who runs it (`running in another session (pid N on <host>, since …): skipped`); `heimdall run --wait`
  waits for it instead, and skips it if that session completed it. The lock is an `flock` on the
  point's `records/…/logs/<point>/.lock`, which the kernel frees when the holder ends, however it ends.
- **`migrate --layout`** moves a work dir's older layouts into today's (a dry run that counts the moves
  first, `--list` each; `--apply` moves them, by rename, nothing copied or deleted): a top-level `logs/`
  into each configuration's `records/…/logs/` (a point's `logs/*.log` one level up), its page
  documents and journal beside them, and the points into `points/` of `records/…/` and `results/…/`,
  `points.json` pointed at them; before that, `output/` (5.1) by lifecycle. A work dir still holding
  `logs/` says so on every command: its points would rerun until it is moved.
- **`migrate --snapshot <P>/<run>/<NN_cfg>`** gives a record from before snapshots one: the config its
  `points.json` names (or `--from CONFIG`, with `--set`; by default its points' recorded overrides) is
  planned and its files copied into `records/…/config/`; each recorded point is said to have the same
  identity under it, or what differs. `--apply` replaces a snapshot already there.

### 1.4 `heimdall check`

`heimdall check` loads each config (with none given, every `configs/<Project>/*.toml` that has a
`[run]`), validates its `[plot]` and its figures, and plans every configuration's points. That
covers every C-rule, path, consumer, connection and card, with nothing run or written. It
prints one line per config, and the error of each that fails. It exits 0, or 2 when any failed: for
a pre-commit hook, or before a long sweep.

### 1.5 `heimdall watch`, `heimdall runs`, `heimdall stop`

`heimdall watch` follows a running job from another terminal, through the watch socket its `heimdall
run` serves while it lives.
- **Which job:** with no config, the latest job started on this machine; with one, the job running
  that config (and that configuration).
- **What it shows:** the run so far, then what follows, as the same blocks as the run. It leaves when
  the job's process ends. Under `[run].sweep_runs` the job is one process, so the watch follows it
  from run to run.
- **`--file`** follows a `--journal` run's status file instead (a finished run's too). It leaves when
  the run finishes, or follows on to the next run's journal in a sweep.
- **Only your own runs** can be watched: a run's socket refuses another user.
- **`--pid N`** follows the run of that process (`heimdall runs` lists them). With no run to watch, it
  names the last one that ended and its log.
- **Keys**, on a terminal: `d` or Ctrl-C leaves (the run goes on); `s`, then `y`, stops the run as
  Ctrl-C at its own terminal would. They are written under the live view.

**A run on a terminal** (`heimdall run`, with a terminal for input and output, in its foreground) runs as
a worker process of its own, started in the background; the command shows it as `heimdall watch` does.
`d` leaves it running and gives the prompt back, printing the commands that watch and stop it. Ctrl-C
stops it: once cleanly, twice hard, a third time at once. Closing the terminal leaves it running. Its
exit code is the run's (0, 1, 2 or 6; a run killed by a signal N, 128 + N). A run that cannot be planned
says why and exits 2 before anything runs. `--plain`, a run not on a terminal, `… &`, a Slurm job and
`HEP_DETACH=never` keep the run in the command's own process, as before. A worker's output goes to
`<machine root>/runs/<id>.log` (a progress line a minute).

**`heimdall run … --detach`** starts the worker without showing it, and returns once its run has
started: its id, pid, log, and the watch and stop commands. Refused with `--plan`, `--why`,
`--show-config`, `--only plot` (they run nothing), and in a Slurm job (its processes end with the job).
A detached run still ends with the machine: logging out ends it where systemd kills a user's
processes at logout (`loginctl enable-linger` keeps them), and so does the end of an `salloc`
allocation, or an Apptainer image run with `--pid` or `--containall`.

**`heimdall stop [CONFIG [CFG]] [--pid N]`** asks a running job of yours to stop, as Ctrl-C would: its
points end cleanly, partial outputs are kept, a rerun resumes. It waits until the job has ended
(Ctrl-C stops the waiting, not the stopping; `--no-wait` returns at once) and says how it ended. With
neither a config nor a pid, it looks only at the jobs of the work dir it is in; several matching jobs
are listed and none stopped. A cluster job is stopped with `heimdall cluster … --cancel`.

**`heimdall runs`** lists what runs on this machine now, then what ran in the last 30 days, across every
work dir and Heimdall checkout: each run's id, its state (running, done, failed, stopped, not run, or
*lost* when its process ended without saying how), when it started and for how long, its work dir, its
config and configurations, and for a running one the pid to watch or stop it by. A run from inside an
Apptainer image is not recorded (its machine root is read-only) but is listed while it runs. The
registry is `<machine root>/runs/`.

### 1.6 `heimdall migrate`

`heimdall migrate` rewrites run TOMLs, and the base cards they name, in the forms the runner takes today
. By default it prints a diff of each file; with `--apply` it writes the files (with no
config, every config). It works by line, so comments and layout stay. It rewrites:

- **figures:** `[plot.overlay.<name>]` and `[plot.object."<glob>"]` → `[plot.figures.…]`, and in a
  figure, a style key written bare (`ratio.range`) → `style.ratio.range`. This runs first, on the
  text, so that a file that was not TOML only because of it reads once migrated;
- **labels** (`labels`, `title`, `title_left`, `title_right`, `legend_header`, `x_label`, `y_label`,
  `legend`): from TLatex to LaTeX, as a physicist writes it. `E_{T} > 4 GeV` becomes `$E_{T}$ > 4
  GeV`, and `p_{T0}^{ref}` becomes `$p_{T0}^{\mathrm{ref}}$`;
- **`swept = false`** → `sweep_runs = ["a", "b", …]`, the configurations the sweep ran, in its
  order;
- **an exec tool's bare `executable`** that is not built but is a command on PATH → `"path:<name>"`
;
- **a base card's lines for keys the runner sets** (its folder's `[card] owned`). This changes the
  card, so the points' identities: they rerun.

It reads each config leniently (the old forms included) before writing anything, and strictly after.

### 1.7 `heimdall reproduce`

`heimdall reproduce` runs a finished point again, exactly as it ran: its config, its configuration,
its `--set` overrides (the provenance records them) and its seed.
- **Where it runs:** into `.cache/<P>/reproduce/<identity>/`, with its own `records/` and `results/`,
  never over the original.
- **The comparison:** each product against the original's, giving `identical`, `the same values` or
  `differs`, with exit 1 if any differs:
  - a YODA file object by object;
  - a ROOT file histogram by histogram;
  - anything else byte for byte.
- **A changed setup:** if the identity is not the one the provenance records, it prints what changed,
  as `--why` does, and stops. `--anyway` runs today's setup with the recorded seed.

### 1.8 `heimdall deck`

`heimdall deck <deck>` makes slides from pages already drawn, in `reports/<deck>/` (a path
starting `./`, `../` or `/` is taken as it is). How to make a talk with it is
[03 §11](03_Plots.md#11-decks-talks-and-reports-heimdall-deck); its `deck.toml` keys are
[04 §15](04_Config_Reference.md#15-a-decks-recipe-decktoml).
- **What a run does, in order:**
  1. reads `deck.toml`'s blocks, or the folder's own files;
  2. copies the panels into `panels/`, again only when one changed;
  3. draws each composite into `figures/`, again only when its panels or settings changed;
  4. makes each target.
- **The targets:** `deck.pdf` (Beamer), `overleaf.zip`, `deck.pptx`, `deck.html` (dzslides) and
  `index.html` (the viewer). `[deck].targets`, or `--only pdf,pptx`, picks some. The slides need
  pandoc; the viewer does not.
- **`--list`:** the blocks, their panels and labels, and where each came from. Nothing is written.
- **`--init`:** writes `deck.md` once (a title slide, then a section per table and a slide per
  block), and a starter `deck.toml` where there is none. It refuses when `deck.md` is there.
- **What it needs:** pdflatex and poppler (`pdftoppm`, `pdfinfo`) for the composites, pandoc and
  the Beamer class for the slides (recipes/README.md §4).

---

### 1.9 `heimdall cluster`

`heimdall cluster <config> [<configuration>]` runs a configuration as Slurm jobs, from the cluster's login
node (how to, [02 §7.5](02_User_Guide.md#75-on-a-slurm-cluster); the keys,
[04 §16](04_Config_Reference.md#16-cluster-running-on-slurm)). It plans as `heimdall run --plan` does, with
every check, then writes three scripts into `records/<P>/<run>/<cfg>/cluster/<stamp>/` and submits
them with `sbatch --parsable`:

| Job | Runs | Waits for |
|---|---|---|
| pre (when there are pre tools to run) | `heimdall run C cfg --stages pre` | — |
| points: an array, a task per point to run | `heimdall run C cfg --points <name> --stages points` | the pre job's success (`afterok`) |
| finish | `heimdall run C cfg --stages combine,post,plot` | every point's end (`afterany`) |

- Each job sources Heimdall's `gjallarhorn.sh` (or the loaded isolated stack's) after `[cluster] setup`,
  exports `HEP_WORK` (and the output roots set at submission), and runs in the work dir.
- `points.txt` lists the points, `jobs.toml` the job ids and each `sbatch` line, `logs/` the jobs'
  output (`points-<job>_<task>.log`).
- **`--dry-run`** writes the scripts and prints the `sbatch` lines; nothing is submitted.
- **`--status`**: the latest submission's points, complete from their markers, else what `sacct` and
  `squeue` say of their tasks (a failed one with its log).
- **`--cancel`**: `scancel` the latest submission's jobs.
- **Refused:** no `sbatch` on `PATH`; no `time` in any layer; the latest submission still has jobs
  pending or running.

---

## 2. The environment, `heimdall build` and `make`

`heimdall build [TARGET…] [--framework] [--tests] [--clean] [--configure] [-j N]` is `make all`, on every
core by default:
- in the **work dir** (found as every command finds it), by its `Makefile`, which includes
  `$HEP/framework/work.mk`: every module program and Rivet plugin, into `build/`;
- with **`--framework`**, in **Heimdall**, by its own `Makefile`: the apps (`App_*.exe`, `Paint.exe`)
  into the machine root's `apps/` (`$HEP_APPS`), and Herwig's repository;
- `--tests` adds the C++ tests (Heimdall's, into `forge/tests/`);
- `--clean` empties the build first;
- `--configure` probes the toolchain again.

`heimdall make …` is `make …` in the work dir, wherever in it it is typed; `heimdall make --framework …`
is `make …` in Heimdall. The targets:
- `<path>/<X>.exe`, `<path>/<x>.so`;
- `all`, `configure`, `list`, `clean`;
- Heimdall's only: `tests`, `test`, `test-slow`, `schema`, `docs`.

The make rules are in [06 §15](06_Internals.md#15-the-build). Run them with the environment loaded
(`gjallarhorn`, the shell function the build writes into `~/.bashrc`; `source <Heimdall>/gjallarhorn.sh`
in bash; or `launch.sh` from any shell).

`heimdall refresh`, `heimdall quit` and `heimdall cd PROJECT [DIR]` change the shell they are typed in. `gjallarhorn.sh`
defines `heimdall` as a shell function that does them there, and runs `framework/bin/heimdall` for everything
else. `refresh` is `quit`, then the same stack again (`$HEP_STACK`: an isolated toolkit's included);
`quit` takes out everything the environment added, `machine.sh`'s lines too. In a shell without that
function (a script, or a shell started from one), `framework/bin/heimdall refresh` (or `quit`, `cd`) exits
2 and says to source `gjallarhorn.sh`. Everything else works without the environment: `framework/bin/heimdall`
runs the machine's Python by path, the base's (or the venv's), for cron, scripts and Slurm.

**The base.** A machine root built on a conda base (`base/`, the default; [recipes/README.md
§4](../recipes/README.md#4-the-base-or-the-systems-packages)) is activated first: `gjallarhorn.sh` sources its
`activate.sh` (recorded, so `quit` takes it out), which puts its `bin/` first on `PATH` and sets `CC`,
`CXX` and `FC` to its compilers. Its `lib/` never joins `LD_LIBRARY_PATH`: what is built on it (the stack,
Heimdall's apps, a work dir's modules and plugins) finds the base's libraries by rpath, which
`framework/rules.mk` adds for `$HEP_BASE`, and the OS's own programs (git, ssh) keep the OS's libraries.
A package taken ready-made from conda-forge lives in the base, so `LHAPDF_DATA_PATH`, `ONNXRUNTIME_DIR`
and `DELPHES_DIR` point there when the stack has none of its own.

`heimdall setup <dir>` makes a work dir and `heimdall where` says which Heimdall and which work dir a shell
sees ([02 §1](02_User_Guide.md#1-set-up-and-build); their options are in §1). In a git repository,
`heimdall setup` keeps the repository's own `README.md`, `CLAUDE.md` and `LICENSE` (Heimdall's guide goes
in `HEIMDALL.md`), merges a marked block into its `.gitignore`, and `--git` commits only the files it
added, in the repository the folder is in (`--git=new`: a repository of its own). It fetches what
`datasets.toml` lists (url, sha256) into `datasets/`; `--refresh` shows and writes (asked, or `--yes`)
the framework's own files as today's template has them. `HEP_DECKS` replaces the work dir's `decks/`.

**`gjallarhorn [title]`.** At the end of a build (setting `shell_rc`, default true), `recipes/build_stack.py`
writes a block into `~/.bashrc` (when the login shell is bash or the file is there) and `~/.zshrc`
(likewise), between `# >>> Heimdall >>>` and `# <<< Heimdall <<<`: `gjallarhorn`, which sources
`gjallarhorn.sh` (in zsh: opens `launch.sh --gjallarhorn`'s bash), and `bifrost` (§2's packages). It names
`HEP_MACHINE` only for a machine root not at `~/Himinbjorg`. A block another checkout's or machine root's
is left (the build says so); `bifrost --shell install` writes this one over it, `bifrost --shell remove`
takes it out, the rest of the file as it was. `gjallarhorn <title>` loads the environment, then goes to
the work dir `heimdall recognise --path <title>` names; an unknown title is said with the nearest, and the
environment stays loaded.

**`bifrost`: the environment's packages** (also `heimdall bifrost`; `framework/bin/bifrost`, and the shell
function of the block above, so it works before the environment is loaded).
- `bifrost <pkg>…` adds conda-forge packages to the base (`scipy`, `gsl=2.8` for 2.8.*, `"gsl >=2.8"`);
  `bifrost -python <pkg>…` (or `--python`) adds PyPI packages by their pip names, which pixi installs with
  the conda ones (no second numpy). They are recorded in the machine root's `machine.toml`,
  `[settings] base_packages` and `base_pypi` (its comments kept), then the base is made again
  (`build_stack.py --base`), so a later build keeps them and another machine can be given the same list.
- `bifrost --drop [-python] <pkg>…` takes them out; `bifrost` alone shows the base, each package added with
  the version installed, the tools (each recipe installed, its version, built or ready-made) and the block in
  each rc file; `bifrost --shell install|remove` writes or removes that block.
- **Tools, by recipe.** `bifrost -c <tool>…` (`-conda`) takes a recipe ready-made from conda-forge, and what
  it needs too (`-c rivet`: HepMC3, YODA, FastJet, fjcontrib), said; `bifrost -b <tool>…` (`-build`) builds
  it from its recipe (what it needs is added); `bifrost -b@<toolkit> <tool>…` builds it with that toolkit's
  changes laid, not the toolkit's set. The machine's choice goes into machine.toml (`[packages.<tool>] from =
  "conda-forge"` or `"source"`), so every later build and toolkit keeps it; then `build_stack.py` runs for
  those tools. A bare `bifrost <name>` that is a recipe's asks which (`-c` or `-b`).
- **A switch** (a built tool taken ready-made, or a ready-made one built) changes the programs: `bifrost`
  says which tool folders run them, how many recorded points of the recognised work dirs ran them (they run
  again, with new identities and seeds), and that Heimdall's apps and the modules that require them
  rebuild; it asks (y/N), or takes `--yes`, and is refused unasked when not in a terminal. The built copy
  is set aside in `forge/retired/` (never deleted; it may be emptied), and what was built on it is built
  again in the same run. A ready-made tool that needs one being built is refused (two copies): build it
  too. A failure puts machine.toml and the stack back.
- Refused: a package whose recipe the stack built (two copies would clash: `<recipe>.from=conda-forge`
  takes it ready-made); one the base cannot take leaves `machine.toml` as it was, with pixi's reason. A
  package the base holds as a ready-made recipe is said, not recorded twice.
- On a machine root made before the base (`base = "system"`), `-python` packages go into the venv by pip,
  recorded in `python_packages`; others are refused (apt or Homebrew's).
- It downloads: an agent asks first.

**Apptainer images.** An image holds a clean copy of this Heimdall and a machine root built inside it
(`/opt/heimdall`, `/opt/himinbjorg`), read-only; it lives in the machine root's `images/`, and work dirs
stay outside, bound at their own paths. The runtime is the system's: `apptainer`, else `singularity`.
- `heimdall image build [packages=@kit cores=N root_cores=N] [--name NAME]` builds
  `images/<name>.sif` from `recipes/platforms/container/heimdall.def` (a stock Ubuntu; `--fakeroot`, so no
  sudo where the user has subordinate ids); a checkout with uncommitted changes is refused (`--dirty`).
  `heimdall image` lists the images and their labels (Heimdall's revision, the toolkit, the date).
- `gjallarhorn --image <name> [title]` opens a shell in the image, in that work dir; `launch.sh --image
  <name> <command…>` runs one command in it; `--dev` binds this checkout over the image's `/opt/heimdall`.
  The host's environment never reaches it (`--cleanenv`).
- `heimdall cluster`: `[cluster] image = "<name>"` runs every job in the image (`setup` still runs first,
  on the node).
- A point run in an image records it in its provenance (the path and labels); the identity is the tools'
  binaries', as always.

**The work dirs this machine knows.** `heimdall recognise [PATH]` records a work dir by its title, its
`hep.toml`'s `[work] name` (else its folder's name), in the machine root's `workdirs.toml`, so that
`gjallarhorn <title>` loads the environment and goes there from anywhere. PATH (default: here) is a work
dir or a folder inside one: that one is recorded. Any other folder is searched, 4 folders deep, for work
dirs to record; hidden folders, a work dir's `results/`, `records/`, `logs/` and `build/`, Heimdall's
checkout and the machine root are not entered. `heimdall setup` records the work dir it makes.
- A path already recorded is "known"; a title whose work dir is gone is given to the new one ("moved
  from …"); a title another existing work dir holds is refused: `--as TITLE` records it under another.
- `--list` shows each title, its path, and whether it is "missing" or "no longer a work dir";
  `--forget TITLE` takes one out; `--path TITLE` prints its work dir (what `gjallarhorn` asks).
- `$HEP_WORKDIRS` replaces the file (the tests point it into `forge/scratch/`).

| Variable | Set by | Means |
|---|---|---|
| `HEP` | `gjallarhorn.sh` | Heimdall's folder. The runner always runs from its own Heimdall and refuses a `$HEP` that names another ("two Heimdalls") |
| `HEP_INSTALL`, `HEP_VENV` | `gjallarhorn.sh` | the loaded stack (`stack/`, or `stacks/<toolkit>/stack`) and its Python environment (the base, or `venv/`) |
| `HEP_BASE` | `gjallarhorn.sh` | the conda base's environment, `<machine root>/base/.pixi/envs/default`; unset with `base=system` |
| `HEP_STACK` | `stacks/<toolkit>/gjallarhorn.sh` | an isolated toolkit's stack is loaded: Heimdall's apps are `stacks/<toolkit>/Apps/` (built against it) |
| `HEP_WORK` | you, tests | the work dir, instead of the walk up from the working directory (it must have a `hep.toml` with `[work]`) |
| `HEP_WORKDIRS` | you, tests | replaces `<machine root>/workdirs.toml`, the work dirs `heimdall recognise` records |
| `HEP_RUNS` | you, tests | replaces `<machine root>/runs/`, the run registry `heimdall runs` lists |
| `HEP_DETACH` | you | `never`: a `heimdall run` on a terminal stays in the command's own process (a debugger, `pytest -s`) |
| `HEP_CLUSTER_JOB` | `heimdall cluster`'s job scripts | set in a cluster job: its `heimdall run` records nothing in the registry (its submission is recorded) and stays in-process |
| `HEP_RECORDS`, `HEP_CACHE`, `HEP_RESULTS`, `HEP_REPORTS` | you, tests | replace the work dir's `records/`, `.cache/`, `results/` and `reports/` (the tests point them into `forge/scratch/`) |
| `HEP_CONFIGS` | you | replaces the work dir's `configs/` as the root of run TOMLs and their cards |
| `HEP_STATUS_FD` | the runner, per tool | the status pipe of a `status = "standard"` tool |
| `RIVET_ANALYSIS_PATH` | the rivet and merge folders, per run | the work dir's `build/Rivet` (not set in the shell on purpose) |
| `LHAPDF_DATA_PATH`, `GEANT4_DATA_DIR`, `ONNXRUNTIME_DIR`, `DELPHES_DIR` | `env/hep_env.sh` | the toolchain's data; the base's, for a package taken ready-made |

High-Energy's variables (`HEKIT_ROOT`, `HEKIT_OUTPUT`, …) are retired: a shell that still sets one is
refused, naming its replacement, and `gjallarhorn.sh` unsets `HEKIT_ROOT` with a warning.

---

## 3. The standard tools at a glance

A **standard tool** is a folder `framework/tools/<tool>/`, and its name is the value of `tool = …`. The
runner discovers the folders and names none of them. A work dir's `tools/<tool>/` and the machine
root's come first, and may replace or extend (`extends = "<tool>"`) a shipped one
([06 §16](06_Internals.md#16-the-tool-folder-contract)); `heimdall tools` lists them all, with where each
comes from.

**Tools, packages and libraries.** A tool folder says how a run drives a program; the program comes from a
**package** (a recipe of `recipes/toolkits/standard.toml` or the machine root's `recipes.toml`), built into
`stack/` or taken ready-made into the base; and a **library** of `env/stack.toml` is what a module program
links (`// requires:`). A config never sees how a package was installed: the program is found on `PATH`,
which holds both `stack/<package>/bin` and the base's `bin/`. A folder names its packages (`[tool] packages
= ["sherpa"]`): `heimdall tools` shows how each is installed ("built 3.0.5", "ready-made 3.0.0" from
conda-forge, "installed" another way, "missing"); a program that is not there says which package to get
(`bifrost -b sherpa` builds it, `bifrost -c sherpa` takes it ready-made); and each point's provenance
records it. Switching a package between built and ready-made changes its programs' bytes, so the points
that ran them run again (their identities and seeds follow the binaries). A program of your own with no
folder runs through `exec` (§9), or a folder of yours: `heimdall tools new <name> --from exec`.

| `tool =` | Category | Runs | Card | Streamable | Status | Count check | Prepare | In the context file |
|---|---|---|---|---|---|---|---|---|
| `pythia` | event generator | `$HEP_APPS/App_Pythia.exe` | `.cmnd`, append | — (writes) | standard | produces: sidecar | — | `card` |
| `rivet` | analysis application | `rivet` (or K of them: `shards`) | none (flags) | yes | filters | `/RAW/_EVTCOUNT` | — | `analyses`, `plugin_path` |
| `yd2rt` | visualisation | `$HEP_APPS/App_yd2rt.exe` | none | file | standard | — | — | — |
| `merge` | analysis application (post) | `rivet-merge` | none | files | none | — | — | — |
| `plotmerge` | visualisation (post) | `App_yd2rt.exe --merge` | none | files | standard | — | — | — |
| `exec` | any | your `executable` | none | per table | none (set it) | only if you set it | — | `config` |
| `module` | analysis application | your `Module.hh` program | none | yes | standard | the report's `events` | — | `config` |
| `delphes` | detector simulation | `DelphesHepMC3` | `.tcl`, append (`set`) | **no** | filters | the `Delphes` tree | — | `card` |
| `herwig` | event generator | `Herwig run` | `.in`, append (`set`) | — (writes) | filters | produces: runner-written sidecar | `Herwig read` | `card`; product `run` |
| `sherpa` | event generator | `Sherpa` | `.yaml`, render (merge) | — (writes) | none | produces: runner-written sidecar | integration | `card`; product `results` |
| `whizard` | process generator | `whizard` | `.sin`, render | — (writes) | filters | produces: runner-written sidecar | integration | `card` |
| `madgraph` | process generator | `mg5_aMC` | launch script, render | — (writes a file) | filters | produces: runner-written sidecar | process directory | `card`; product `process` |

`framework/tools/lhapdf/` is not a tool in a chain: it is a provider. The plot backends (`yoda/`,
`mpl/`: `backend.py`, [03 §9](03_Plots.md#9-backends)) and the figures' plugins (`figures/`) are in
`framework/plot/`.

Paint (`src/Apps/Paint/`) is driven by the plot stage, and is never named in `tools` (§18).

**Not tools at all:**
- **Providers** (LHAPDF, FeynRules, SARAH) are plan-time checks. A mapping with `check =
  "lhapdf:bare"`, `"lhapdf:set"` or `"lhapdf:pythia"` refuses an uninstalled PDF set (C10,
  `framework/tools/lhapdf/provider.py`) and writes the set in that tool's spelling.
- **Analysis algorithms** (FastJet, ROOT libraries) are `// requires:` names in a source.
- **A detector simulation with no command line of its own** (Geant4) is a module program with
  `// requires: geant4`.
- **Statistics** (RooFit, pyhf, uproot, scikit-learn) are exec tools, usually in `post`.

---

## 4. `pythia` — App_Pythia

```toml
[tools.pythia]
card   = "ep.cmnd"              # configs/<P>/ep.cmnd
output = "events.hepmc"         # a FIFO, a file or a product, by its reader (04 §6); an array fans out
```

- **Runs** `$HEP_APPS/App_Pythia.exe <outputs> <base cards…> <point card>` (§16): the base cards in
  order, then the point card, so its settings win.
- **Card** (`cards/pythia.point.cmnd`, and `cards/pythia.cmnd` = base + point):
  - a header comment;
  - one `Key = value` line per consumed value and per `settings` entry (`on`/`off` for bools);
  - the footer;
  - then the seeds: `Random:setSeed = on`, `Random:seed = <seed>`, and at threads > 1
    `Parallelism:seeds = {…}`.
- **`cards/pythia.cmnd` holds each key once** (`[card] merge`): the base cards' settings without
  comments, less each key the point card sets, then the point card. The particle-data commands that
  add up (`id:onIfMatch` and the rest of `[card] repeatable`) are kept every time.
  - `cards/pythia.json` gives each key's value and where it came from (`ep.cmnd:34`,
    `[quantities.pdf] = NNPDF23lo`, `built-in events`, `[tools.pythia].settings`).
  - App_Pythia still reads the base cards and the point card, which gives the same settings.
- **Keys the runner sets** (`[card] owned`: `Main:numberOfEvents`, `Parallelism:numThreads`, the
  `Random:` seeds, `Parallelism:seeds`, `Beams:LHEF`): a base card's line for one of them is never
  used, and `--plan` and the run say so.
- **Checked** (`[checks] card`): at plan time, `$HEP_APPS/App_PythiaCheck.exe` gives every line of
  the card (base settings and point card, before seeds) to Pythia's own reader.
  - A line Pythia rejects (a key it does not know, a value of the wrong kind, a particle its table
    lacks) refuses the plan, with the line's source.
  - No list of keys is kept: a nucleus or an `id:new` particle earlier in the card is read as Pythia
    reads it.
  - Answers are kept by the card's text for the process, and in `.cache/<P>/checks/` with `keep cache`.
- **Footer** `Beams:LHEF = <input>`, only when the tool has an input: a shower of an LHE file from an
  earlier group (MadGraph). The base card sets `Beams:frameType = 4`.
- **Consumes** through the vocabulary: `energies`, `sqrts`, `beam_a`, `beam_b`, `beams`, `pdf`
  (checked installed), `events` and `threads` (04 §3); anything else with `key = { pythia = … }`.
- **Writes** HepMC3 to every output, and the **sidecar** `<first output>.json` (§16). It can
  **deal** its events among a sharded tool's inputs (`[outputs] deal = true`, §5.1).
- **In the context file** (04 §9.4): `card` (the combined card, seeds included) and `card_parts`.
- **Identity** includes the binary's sha256; the **version** is the stack's (`stack:pythia8`).

## 5. `rivet`

```toml
[tools.rivet]
input    = "pythia"                      # what the pythia table writes
analyses = ["photo_eic", "MC_JETS"]      # "NAME" or "NAME:OPT=V:OPT=V"
options  = { R = 0.4 }                   # applied to every analysis (optional)
output   = "jets.yoda"
```

| Option | Kind | Notes |
|---|---|---|
| `analyses` | array, **required** | Rivet analyses; inline options as `NAME:OPT=V` |
| `options` | table | options given to every analysis |

- **Runs** `rivet -o <partial output> -a <analysis[:options]>… <input>`, with
  `RIVET_ANALYSIS_PATH = build/Rivet`.
- **Options**, in increasing precedence (the parent→child rule):
  1. `options` (every analysis);
  2. the analysis's own inline `NAME:OPT=V`;
  3. quantities targeting `"<tag>/<analysis>"`.

  Each analysis must have a `.info` (`build/Rivet/`, then `rivet-config --datadir`), and every option
  it is given must be declared in the `.info`'s `Options:` (C9). A quantity's option aimed at an
  analysis the tool does not run is an error.
- **Consumes** nothing through the vocabulary: beams and energies come from the events.
- **σ** is the last event's `GenCrossSection`: App_Pythia re-stamps it with the combined value.
- **Count check**: `/RAW/_EVTCOUNT`'s entries against the producer's sidecar `written`.
- **Identity** includes each project plugin's `.so` (`build/Rivet/Rivet_<analysis>.so`); the
  version is the stack's.
- **In the context file** (04 §9.4): `analyses` (with this point's options applied, e.g.
  `photo_eic:R=0.4`) and `plugin_path` (`build/Rivet`): its folder's `[context] values`.
- **Its own code** is `framework/tools/rivet/render.py`'s `options` hook. It handles:
  - the analyses with their options;
  - the `.info` check;
  - `{analyses}` for the argv;
  - the page texts `{opt:NAME}` (each option at the point, the `.info`'s `(default X)` when
    unset).
- **Status** by filters: `Event N (` → progress, `ERROR`/`Exception` → error, `WARN` → warning (the
  "unvalidated" warning ignored).

### 5.1 Sharded Rivet: `shards = K`

One Rivet process is one core: with ZEUS_2012_I1116258 about 1,500 events/s, a third of it reading
the HepMC text and the rest clustering jets. It sets the pace of a Pythia → Rivet chain whatever
Pythia's threads (measured 2026-09-29: 20 threads left the machine at 4%). `shards = K` runs K Rivet
processes, each on a share of the events, and merges them:

```toml
[tools.rivet]
input    = "pythia"                      # a FIFO (or file) written by pythia
analyses = ["ZEUS_2012_I1116258"]
output   = "validation.yoda"
shards   = 10
```

- **The chain does not change** (`chain = [["pythia", "rivet"], "yd2rt"]`). For each point:
  - the runner makes the FIFOs `events.s1.hepmc` … `events.s10.hepmc` in place of `events.hepmc`;
  - App_Pythia deals the events among them (§16);
  - the steps `rivet.1` … `rivet.10` run in the group, each writing
    `records/…/logs/<point>/shards/validation.s<i>.yoda`, and each is count-checked against **its own share**
    (`written_per_output` in the sidecar);
  - then `rivet.merge`, a step of its own in the next group, runs `rivet-merge -e` (the `merge`
    folder) into the table's `output` (`validation.yoda`, in `results/`).

  The logs are `rivet.<i>.log` and `rivet.merge.log` in the point's working folder, and `--plan` shows every step.
- **The events do not change.** Seeds follow the generator's cards, not its argv, so a sharded
  point has the same events as the same point unsharded. The merged YODA is the same, up to the
  rounding of summing in another order. The point's identity does change (its argv), so changing
  `shards` reruns it.
- **Requirements**, refused at plan time otherwise:
  - the tool reads one input and writes one output;
  - the input is a FIFO or file of the point with exactly one producer in the chain, whose folder
    can deal (`pythia`);
  - every analysis is re-entrant (`Reentrant: true` in its `.info`), because `rivet-merge -e` runs
    `finalize()` again on the summed histograms.

  Other outputs of the producer (a module program's FIFO) still get every event.
- **Quantities aimed at the table reach every shard**: `to = { "rivet/photo_eic" = "R" }` (jets's
  `radius`) or `to = { rivet = … }` gives each `rivet.<i>` the same option, and `--plan` shows it as
  `rivet.1–10:R`.
- **Choosing K.** Each shard is one core, and so is each Pythia thread: `threads + shards` should not
  exceed the machine. Measured on the lab PC (i7-13700K, 24 hardware threads), 200k ZEUS_2012
  events, steady rate after the ~5 s start:

  | `threads` + `shards` | events/s |
  |---|---|
  | 20 + unsharded | ~1,570 |
  | 8 + 8 | ~8,100 |
  | 12 + 10 | ~9,200 |
  | 14 + 10, 10 + 12 | the same as 12 + 10: the CPU is full |

  `threads = 12`, `shards = 10` is what `jets.toml` and `validation.toml` use.

## 6. `yd2rt` — YODA → ROOT

```toml
[tools.yd2rt]
input  = "rivet"
output = "jets.root"
select = ["/photo_eic/*"]              # optional: YODA path globs
```

| Option | Kind | Notes |
|---|---|---|
| `select` | array | YODA path globs to convert; default every object except `/RAW` and `/TMP` |

It runs `App_yd2rt.exe <input> <partial output> <select…>` (§17). The ROOT file is a product, in
`results/`. Like every tool in the chain, it needs its `[tools.<name>]` table (C5), because the table
says what it reads and writes.

## 7. `merge` — rivet-merge, in `post`

```toml
[cfgs.replicas]
vary  = ["replica"]
chain = [["pythia", "rivet"]]
post  = ["merge"]

[tools.merge]
input      = "jets.yoda"         # that product of every point
output     = "merged.yoda"
equivalent = true                # default: -e, statistically equivalent runs
```

| Option | Kind | Default | Notes |
|---|---|---|---|
| `equivalent` | flag | true | `-e`: runs of one process (seed replicas); statistics add, σ is averaged. `false` merges different processes into their sum |

- **Runs** `rivet-merge [-e] -o <partial output> <every point's input>`, with `RIVET_ANALYSIS_PATH`
  set. It re-runs the analyses' `finalize()`, so they must be re-entrant.
- **Also used by the runner itself:**
  - to merge a sharded Rivet's shards inside a point (§5.1);
  - for each group of a `combine` (04 §5.5);
  - for a `merged` figure's members (03 §7.4).

## 8. `plotmerge` — the sweep in one file, in `post`

```toml
[tools.bundle]
uses   = "plotmerge"
input  = "jets.yoda"
output = "sweep.root"            # or sweep.yoda
```

It runs `App_yd2rt.exe --merge <partial output> <point>=<yoda>… --keep-raw --points points.json`
(§17).
- **Into ROOT:** a directory per point, the `paths` tree with a `point` column, and `points.json` as
  a `TNamed`.
- **Into `.yoda`:** one YODA file, with the point as a path prefix.

It is not a statistical merge (that is `merge`). The plot stage makes the same file itself, in
`.cache/<P>/plots/<name>/<cfg>/<cfg>.root`, so this tool is for a copy elsewhere, or a YODA version.

## 9. `exec`

Any executable (it was `custom`): its argv is `{exe} {config} {arguments}` (04 §9.2). Its status is
`none` unless the table sets it, and `HEP_STATUS_FD` is passed when `status = "standard"`. Like every
tool it finds the point's context file at `$HEP_CONTEXT`, or `{context}` in its arguments (04 §9.4).
`heimdall tools new <name> --from exec` copies the folder into the work dir's `tools/`, as a tool of its own.

```toml
[tools.jets_reco]
uses       = "exec"
executable = "path:python3"
arguments  = ["{work}/modules/Demo/delphes_jets.py", "{input}", "{partial:output}"]
input      = "delphes"
output     = "jets_reco.json"
```

**An exec tool in Python** gets the kit's half that applies through `framework/hepkit.py`:
- `Exit`: Kit::Exit's table;
- `Status`: the standard protocol, with a heartbeat, or plain lines on stderr when the fd is not
  given;
- `report(output, …)`: `<output>.json`, written whole;
- `stopping()`.

`delphes_jets.py` is its first user, so its table may say `status = "standard"`
([06 §22](06_Internals.md#22-statushh-and-the-status-protocol)).

**A command-line program as a tool of your own.** `exec` runs any program as it is. To give one a card, its
products and an identity, make it a folder: `heimdall tools new unfold --from exec --runs unfold-it --package
root` writes `tools/unfold/tool.toml` in the work dir (copy the folder to the machine root's `tools/` for
every work dir), with `[tool] executable` and `packages` filled. Then, in it ([06 §16](06_Internals.md#16-the-tool-folder-contract)):
- `[card] style`: `none` (values become arguments or the config file), `append` (base cards, then the
  point's lines, written with `line = "{key} = {value}"`), or `render` (a `render.py` writes the whole card);
- `[command] argv`: `{exe}`, `{card}`, `{config}`, `{input}`, `{output}` or `{partial:output}`, `{events}`,
  `{seed}` and the table's `[options]`;
- `[outputs]`: the kinds it writes, how its event count is read back (`event_count`), a producer's sidecar;
- `status`: `standard` (it speaks the status protocol, as hepkit.py and Module.hh do), `filters` (a
  `filters.toml` reads its stdout), or `none` (its log's last line is shown);
- `[identity] files = ["{exe}"]`: what of it makes a point's identity, beside its card and argv.
A library used from C++ is not a tool: a module program links it (`// requires:`, 06 §15).

## 10. `module` — a Module.hh program

- **argv:** `{exe} {config} --input={input} --output={partial:output} --events={events}
  --sidecar={input_sidecar} {arguments}` (04 §9.3).
- **Status:** standard.
- **Count check:** it reads `events` from the program's report, `<output>.json`, against the
  producer's sidecar.
- **Integrated programs:** an empty `--input=` means an integrated program, which makes its own
  events. It reads the cards of the tools it runs itself from the context file (`job.card("pythia")`),
  which `generate_cards` fills (04 §9.4).
- **Settings:** every key of its config must be one the program reads; a misspelt one is refused
  before the first event, with the nearest name. `<Name>.exe --describe` lists them (name, type,
  default, doc), and `heimdall explain <Name>.exe` shows them.

The kit is [06 §21](06_Internals.md#21-modulehh).

## 11. `delphes` — DelphesHepMC3

```toml
[tools.delphes]
card   = "delphes_card_ATLAS.tcl"
input  = "pythia_file"            # a file from an earlier group: never a FIFO
output = "delphes.root"
```

- **Runs** `DelphesHepMC3 <combined card> <partial output> <input>`.
- **Card**: Tcl, append style, `set {key} {value}` lines; the seed as `set RandomSeed <seed>`.
- **Not streamable**: Delphes sizes its input first and skips a zero-length one, which a FIFO
  always is. A FIFO into it is refused at plan time (C6). It creates its ROOT file before reading the
  card, so it writes the partial name the runner gives.
- **Count check**: the `Delphes` tree's entries (read with uproot) against the sidecar.
- **Seeds**: Delphes is not an event producer, so it never moves the generator's seeds.
- **In the context file:** `card`.

## 12. `herwig` — Herwig 7

```toml
[tools.herwig]
card   = "dis_ep.herwig.in"
output = "events.hepmc"
```

- **Prepare** (cached per card): `Herwig read --repo={apps}/Herwig/HerwigDefaults.rpo <card>` →
  `point.run` in the cache entry. The repository is made by `heimdall build --framework`: Herwig's own
  install could not make it, since its defaults need CT14lo/CT14nlo. A plan without it is
  refused (C10), with `heimdall build --framework`.
- **Runs** `Herwig run <cache>/point.run -N <events> -s <seed> -d 0`. Events and seed are flags, so
  every point and replica with the same physics shares one read.
- **Card**: ThePEG `set {key} {value}` lines (a later `set` wins). The footer reads HepMC output
  (`read snippets/HepMC.in`, the file name, `saverun point EventGenerator`), and must come last.
- **Beams**: in Herwig's slots, `[beams] slots = ["lepton", "hadron"]`: the snippet puts the
  lepton on beam A, and the runner reorders the run's per-beam values for it.
- **Consumes** `energies` (`Luminosity:BeamEMaxA`, `…B`), `sqrts` (`Luminosity:Energy`) and `pdf`
  (`HardLOPDF`, `ShowerLOPDF`, `MPIPDF` and `RemnantPDF`'s `PDFName`, the four Herwig's defaults set;
  its NLO objects and a member stay the card's).
- **Sidecar** written by the runner after exit 0 (`written = "requested"`: Herwig makes exactly `-N`
  events or fails).
- **In the context file:** `card`; the product `run` (`generate_cards = ["herwig:run"]`), the
  `.run` file, **prepared on demand** for a tool that asks.

## 13. `sherpa` — Sherpa 3

```toml
[tools.sherpa]
card   = "ep.sherpa.yaml"
output = "events.hepmc"
```

- **Card** (`render.py`): the base YAML files deep-merged in order, then each value assigned at its
  **key path** (`EPA:Q2Max`, `PDF_SET[0]`: a list entry is replaced, never appended), written whole.
  - `sqrts` becomes `BEAM_ENERGIES = [√s/2, √s/2]`.
  - `MPI_PDF_SET` follows `PDF_SET` (it agreed before, or was absent): Sherpa's MPI reads its own key
    and falls back to a PDF that is not installed.
  - The footer is `EVENT_OUTPUT: HepMC3_GenEvent[<output name>]`, and the seed is `RANDOM_SEED:
    <seed>`.
- **The plan owns** `BEAMS`, `BEAM_ENERGIES`, `RANDOM_SEED`, `EVENTS`, `EVENT_OUTPUT` and
  `RESULT_DIRECTORY`: a base card that sets one is refused.
- **Prepare** (the integration, cached by the card without `EVENTS`): `Sherpa -f <card> -e 0
  "RESULT_DIRECTORY: <cache>/Results" "EVENT_OUTPUT: None"`. `EVENT_OUTPUT: None` matters: otherwise
  Sherpa opens the FIFO at initialisation and waits for a reader that only the generation starts.
  The marker is `Results.zip`.
- **Runs** `Sherpa -f <card> "RESULT_DIRECTORY: <cache>/Results"`, in the point's directory. Sherpa
  prepends `./` to the output name, so the name is relative.
- **Its progress**: the folder's display arguments, `BATCH_MODE: 23` and
  `EVENT_DISPLAY_INTERVAL: <events ÷ 1000, at least 100>`, make Sherpa print one line per thousandth of
  the run, its elapsed time in seconds and the cross section on it; `filters.toml` reads them into a bar,
  a rate, an ETA and σ, enters `initialising`, `integrating` and `generating`, and ignores the routine
  messages (an event rejected and redone, a hadron a hair off its shell). They are not in the identity:
  a point that ran without them is the same point. The command line wins over the card, so a card's own
  `BATCH_MODE` is not used. A run's `stall_after` (the default 300 s) no longer needs Sherpa's quiet
  stretches allowed for: without these, it printed every 100 000 events.
- **Consumes** `energies`, `beams`, `sqrts`, `pdf` (checked) and `events`.
- **Sidecar** written by the runner (`written = "requested"`).
- **In the context file:** `card`; the product `results` (`"sherpa:results"`), the integration
  directory, prepared on demand.
- **Notes:**
  - Sherpa writes a YODA variation per extra weight; the plot stage draws the nominal only.
  - With `MI_HANDLER: Amisic`, ep photoproduction made 0 events in 768 s (v1), so the committed card
    has MPI off.
- **Several Sherpas for one curve.** A point is one Sherpa process. To spread a long point over K
  cores, vary a seed replica and merge it back (02 §7.3): K points of `events ÷ K` each, run
  `parallelism` at a time, each with its own seed, merged into one curve by `rivet-merge -e`.

  ```toml
  [quantities.replica]
  to     = { "sherpa/seed" = true }        # only the seed (with @generator: "pythia/seed" too)
  points = [{ tag = "s1", value = 1 }, { tag = "s2", value = 2 }, { tag = "s3", value = 3 }, { tag = "s4", value = 4 }]

  [run]
  events      = 2_500_000                  # each: 10M in all
  parallelism = 4

  [cfgs.generator_pdf]
  vary    = ["generator", "pdf", "replica"]
  combine = ["replica"]                    # one curve per generator and PDF
  ```

  Every replica shares the cached integration. Sherpa's MPI (built with `-DSHERPA_ENABLE_MPI=ON`, run
  under `mpirun`) speeds that integration, which is cached already; it is not built here.

## 14. `whizard` — Whizard 3

```toml
[tools.whizard]
card   = "ep.sin"               # exactly one base card
output = "events.hepmc"
```

- **Card** (`render.py`): SINDARIN is a script, so the point card comes **first** and includes the
  base **last**. In order:
  - the plan's assignments;
  - `seed = <seed>`, `sample_format = hepmc`;
  - `$sample = "<output without .hepmc>"` (Whizard appends `.hepmc`);
  - then `include("<base>")`.
- **Beams are names**: PDG codes become the SM model's names (from
  `share/whizard/models/SM.mdl`). The base card states its structure-function chain in a comment,
  `# hep: beam_structure = pdf_builtin, epa`, which is appended as `=> pdf_builtin, epa`.
- **The plan owns** `seed`, `n_events`, `sqrts`, `beams`, `beams_momentum`, `$sample` and
  `sample_format`: a base that assigns one is refused (it would run after the plan's value).
- **Prepare** (integration: library, phase space, grids): `whizard <prepare card>`. The prepare card
  is the point card without `n_events`, `$sample` and `sample_format`, keyed without them and
  `seed`. Generation then runs **in the cache entry** (`[command] cwd`), where Whizard finds them.
- **Consumes** `energies` (`beams_momentum`, in GeV), `beams` and `events` (`n_events`).
- **σ**: Whizard writes none into its events, so Rivet has none; the integration log has it.
- **Limits:** Whizard has no photon structure function, so it does direct photoproduction only
. Its EPA record has no scattered lepton, so a Rivet analysis using `DISKinematics` cannot run
  on it.
- **In the context file:** `card`.

## 15. `madgraph` — MadGraph5_aMC@NLO

```toml
[cfgs.single]
chain = ["madgraph", ["shower", "rivet"], "yd2rt"]   # an LHE file, then a FIFO from the shower

[tools.madgraph]
card   = "dis_ep.proc_card.mg5"   # the proc card: processes only, no `output` or `launch`
output = "unweighted.lhe"
keep   = false                    # a scratch file of the point (leave it out to keep it in results/)

[tools.shower]
uses   = "pythia"
card   = "shower_lhe.cmnd"        # sets Beams:frameType = 4; the LHEF line is the footer
input  = "madgraph"
output = "events.hepmc"
```

- **Prepare** (keyed on the **proc card only**, `key = "base"`): the proc card plus
  `output <cache>/process -f` → the process directory, built once. The marker is
  `process/bin/generate_events`.
- **Card** (the launch script), in order:
  - `set automatic_html_opening False` (else it opens a browser);
  - `launch <cache>/process -n r<seed>`;
  - shower, detector and analysis off;
  - then `set iseed <seed>`, and one `set <key> <value>` per value.

  Beams become `set lpp1/lpp2` (2212 → 1, −2212 → −1, leptons → 0), from the folder's `[render.lpp]`.
- **Runs** the launch, then unpacks the run's `Events/r<seed>/unweighted_events.lhe.gz` to the
  output: a file, for a `pythia` table in a later group to shower.
- **Consumes** `energies` (`ebeam1`, `ebeam2`: beam 1 is the proc card's first incoming particle),
  `beams` and `events` (`nevents`).
- **Sidecar** written by the runner (`written = "requested"`).
- **In the context file:** `card`; the product `process` (`"madgraph:process"`), the process
  directory, prepared on demand.

---

## 16. App_Pythia — `src/App_Pythia.cc`

```
App_Pythia.exe [--threads N] [--events N] [--seeds S1,S2,…] [--sidecar FILE] OUTPUT[,OUTPUT…] CARD [CARD…]
```

**Its rules.** Its Pythia rules (the σ combination, the stamping, the seed check, the chunking) are `src/PythiaRun.hh`'s. The integrated programs (InprocJets) run them too
, so an integrated point's events and σ are the chain's by construction.

**Outputs.** Every comma-separated OUTPUT gets **every** event (fan-out). An OUTPUT written
**`A+B+C`** is a **deal group**: each event goes to **one** of its members, the first that is free,
starting from a rotating index (so a slow consumer gets fewer). That is how a sharded Rivet gets its
shares (§5.1). `events.s1.hepmc+events.s2.hepmc,to_module.hepmc` deals the events between two Rivet
shards, and still copies every one to a module program.

**How the runner calls it.** `// requires: pythia8 hepmc3 zstd zlib`. The runner calls it as `{exe}
{outputs} {cards}`: the threads, events and seeds are in the point card.

| Behaviour |
|---|
| Reads the cards in order (the point card last: last wins) |
| `PythiaParallel` with `processAsync = on`: callbacks run concurrently, each instance converts with its **own** `Pythia8ToHepMC`, σ is combined under one small lock, and **each output has its own writer and lock**, so formatting the HepMC text is shared among the outputs. (With `processAsync = off` and one writer, the app was capped at ~2,200 events/s whatever its threads: 4 threads took 17.7 s and 20 threads 20.5 s for 40k events.) |
| Checks the seed list before `init()`: one per thread, each in 1…9·10⁸ (Pythia does not) |
| Opens the outputs only after `init()` succeeds: a bad card leaves no half-open FIFO |
| Runs in chunks of a multiple of the thread count, so SIGINT takes effect within a chunk |
| Catches in the callback and re-raises on the main thread |
| σ combined over instances: the ΣW-weighted mean, errors in quadrature |
| Once more than one instance has contributed, **re-stamps every event's `GenCrossSection` with the combination**, so the last event Rivet reads carries the final σ; at one thread the converter's numbers are untouched (bit for bit the legacy pipeline's) |
| **Every output ends on the latest σ**: each writes its events one late, and at the end its held event takes the σ of the last event stamped, so every shard of a deal group (and every copy) normalises to the σ an unsharded Rivet would |
| Several outputs: the same events to each (fan-out), or one of a deal group's members each; a `.gz` or `.zst` suffix picks HepMC3's compressed writer |
| Events are numbered once, from 0, across the threads; every event carries one shared run info |
| Status on `$HEP_STATUS_FD` (06 §22) |

**The sidecar**, `<first output>.json` (or `--sidecar`), is written after the outputs are closed. It
holds:
- `tool`, `pythia_version`;
- `requested`, `attempted`, `accepted`;
- **`written`**: what the count check compares; it can be below `requested`;
- `write_failures`;
- `sigma_pb`, `sigma_err_pb`, `sum_w`;
- `threads`, `seeds`, `random_seed`;
- `outputs` (every path, in order);
- **`written_per_output`** (`{"<path>": events, …}`): what a shard's count check compares;
- `cards`, `stopped`.

**Exit codes** (06 §11):

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | card or config |
| 2 | usage |
| 3 | init |
| 5 | output |
| 6 | stopped (outputs and sidecar written, `stopped: true`) |
| 70 | internal |

`App_PythiaCheck.exe CARD` is its card check (§4).

## 17. App_yd2rt — `src/App_yd2rt.cc`

```
App_yd2rt.exe IN.yoda OUT.root [GLOB …] [--keep-raw]
App_yd2rt.exe --merge OUT.root|OUT.yoda NAME=IN.yoda … [--keep-raw] [--select GLOB] [--points FILE]
```

`// requires: yoda root`.

| YODA | ROOT |
|---|---|
| `Histo1D`, `Estimate1D` | `TH1D` (an Estimate's error is the average of its total down and up errors) |
| `Histo2D`, `Estimate2D` | `TH2D` |
| `Scatter2D` | `TGraphAsymmErrors` |
| `Counter`, `Estimate0D` | a one-bin `TH1D` |

- **Directories nest as the YODA path does**: `/photo_eic/d01-x01-y01` → `photo_eic/d01-x01-y01`.
  A variant path `/photo_eic:R=0.4/…` becomes `photo_eic__R-0.4/…` (`:` → `__`, `=` → `-`). Every
  object's title is its original YODA path, and the `paths` TTree maps each ROOT path back.
- **`/RAW` and `/TMP`** are skipped unless `--keep-raw`, which also writes `<name>__entries` (per-bin
  raw entry counts) beside each `/RAW` histogram: Paint's `min_entries` reads them.
- **`--merge`**: each input's objects go under a directory named for it (its point). The `paths`
  tree gets a `point` column, and `--points` stores `points.json` in the file as the TNamed
  `points.json`. Into a `.yoda` file, the name is a path prefix instead.
- **Exit codes**: 0 ok, 2 usage, 4 input, 5 output.

## 18. Paint's command line

```
Paint.exe PAGE.toml [PAGE.toml …] [--ranges | --ranges-only]
Paint.exe PAGE.toml --dump-ranges
Paint.exe [PAGE.toml] --dump-style
```

Paint draws many pages in one ROOT process (the plot stage sends up to 200 at a time).
- **Several pages:** each page's outcome is a JSON line on stdout, `{"page", "ok", "error"}`, so one
  bad page does not stop the rest.
- **`--ranges`** also writes each page's final ranges and voided bins beside its config
  (`<page>.toml.ranges.json`), for the other backends; **`--ranges-only`** writes them and draws
  nothing.
- **Every page read** (drawn or not) also gets `<page>.toml.stats.json`: each curve's area and its
  area and χ² against the page's reference (03 §3.2), which the plot stage turns into each set's
  `statistics/<set>/statistics.csv` and legend entries.
- **`--dump-ranges`** prints one page's ranges as JSON; **`--dump-style`** prints the merged style
  (base.toml's alone, without a page).
- **Exit codes**: 0 ok, 1 page config or style (with several pages: any failed), 2 usage, 4 input,
  5 output.

**The page document**, written by the runner to `.cache/<P>/plots/<name>/<cfg>/<set>/[<cell>/]<object>.toml`. Its labels
are LaTeX converted to TLatex, which Paint draws:

```toml
[page]
name        = "totality/d06-x01-y01"
output      = "/…/results/…/plots/totality/root/d06-x01-y01"    # without extension
formats     = ["pdf", "png"]
title       = "1 > #eta > 1.5, #it{k}_{#it{T}} alg"
x_label     = "#it{E}_{#it{T}} [GeV]"
y_label     = "d#sigma / d#it{E}_{#it{T}} [pb/GeV]"
logx        = false
logy        = true
y_gutter    = 0.5                  # or "default"
x_gutter    = "default"
ratio       = true
ratio_label = "MC/Data"
normalise   = false
void_empty  = true
min_entries = 10
auto_range  = true
range_pad   = 0
# markers = true                   (a Scatter2D figure)
# heatmap = true, logz, z_label    (a HeatMap page: one [[curve]])
# x_labels = ["…", …]              (a statistic figure: a label under each bin centre 1, 2, …; no ratio)

[style]                            # only what the style layers changed (04 §12)
page.dpi = 300

[[curve]]
file   = "/…/.cache/…/default/default.root"
object = "MSTW08lo/ZEUS_2012_I1116258/d06-x01-y01"
raw    = "MSTW08lo/RAW/ZEUS_2012_I1116258/d06-x01-y01"   # optional: for min_entries
label  = "MSTW 2008 LO"
style  = { colour = "#EE3311" }                         # optional: the value's look
band   = [{ file = "/…/default.root", object = "…" }]   # optional: the envelope's members

[data]                             # optional
file   = "/…/plots/datasets/ZEUS_2012_I1116258.yoda.root"   # .cache/<P>/datasets/ with keep cache
object = "REF/ZEUS_2012_I1116258/d06-x01-y01"
label  = "ZEUS 2012"
```

A curve object is a `TH1`, a `TGraphAsymmErrors`, or for a heat map a `TH2`. What Paint does with a
page, in order, is [06 §20](06_Internals.md#20-paint-inside).
