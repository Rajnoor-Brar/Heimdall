---
id: commands
summary: every heimdall command and its arguments
code: framework/runner/cli.py
generated: true
---

# Commands

Generated from the CLI's help; change it there.

## `heimdall run`

plan and run a configuration

| Argument | Meaning |
|---|---|
| `config` | configs/<A>/<E>[.toml], ./path from the work dir, or a record <A>/<E>/<R> (what it ran with: its snapshot) |
| `[configuration]` | overrides [errand].configuration; under [errand].sweep_runs, runs only it |
| `--plan, --dry-run` | print the plan; run nothing |
| `--why` | for each point that would run, what changed since it last completed; run nothing |
| `--show-config` | print each configuration's resolved values and where each came from; run nothing |
| `--card TAG` | with --plan: that tool's card for the first point, each line with where its value comes from |
| `--points SEL` | run a subset: tags, indices or quantity=tag |
| `--detach` | start the job in the background and return: heimdall watch follows it, heimdall stop stops it (on a terminal, a job started without it leaves on d too) |
| `--set KEY=VALUE` | override one value for this invocation (repeatable), in the file's own names: errand.events=100 (v3), errand.event_count=100 (v2) |
| `--tag NAME` | tag each Run this job makes or resumes (over the one it has and its configuration's tag): a letter or digit, then letters, digits, . _ + -, at most 40 |
| `--rerun` | ignore skip-unchanged; under a serial the file sets, overwrite points made from other inputs |
| `--only pre\|post\|plot` | rerun only the pre tools, the post tools or the plots |
| `--no-plot` | draw nothing after the points (its plot.toml is written all the same), whatever [errand].plot says |
| `--no-stats` | measure nothing after the points, whatever [errand].stats says |
| `--stages LIST` | run only these stages, skip-unchanged: pre, points, combine, post, plot (comma-separated; heimdall cluster's jobs) |
| `--plain` | plain lines instead of the live view |
| `--wait` | a point another session is running: wait for it (default: skip it, naming who runs it) |
| `--journal` | also write every status event to records/…/status.jsonl (for heimdall watch --file and replay) |
| `--logs` | keep every tool's whole output in records/…/logs/<point>/<tag>.full.log (its digest, <tag>.log, is always kept) |
| `--keep WHAT` | also keep (comma-separated): logs, journal, work (a finished point's whole working folder), cache (card checks); also heimdall.toml's and machine.toml's [run] keep |

## `heimdall plot`

draw a configuration's pages from its complete points

| Argument | Meaning |
|---|---|
| `config` | the errand file, or a record <A>/<E>/<R>: its points as they were recorded, with the config they ran with (its snapshot, which you may edit) |
| `--plot FILE` | a file whose [plot] draws instead of the run's: configs/<A>/<E>, ./… or /… |
| `--sets NAMES` | draw these sets only (comma-separated; default: the document's [plot].draw, else every set) |
| `--points SEL` | pages of these points only, in this order, in the folder points/: indices, names, globs, tags or quantity=tag, comma-separated ([plot].sets for one set) |
| `--plan` | say each set's page cells and their curves, from the complete points; draw nothing; with --style-sync: what would change, written nowhere |
| `--style-sync CONFIG` | take this config's [plot] and [stats] into the plot documents named (<A>/<E>/<R>, or <A>/<E>: each of its Runs), what each Run knows left as it is; nothing is drawn unless --replot |
| `--replot` | with --style-sync: then draw what was synced |
| `--across` | the Runs of this errand together, results/<A>/<E>/plot.toml: its [plot.across] sets |
| `--keep WHAT` | cache: keep the card checks (as heimdall run --keep); the drawing's working files are .cache/'s anyway |
| `[configuration]` | overrides [errand].configuration; under sweep_runs, only it |
| `--set KEY=VALUE` | as for heimdall run |

## `heimdall stats`

a Run's statistics alone: its pages' numbers against the data, drawing no page

| Argument | Meaning |
|---|---|
| `config` | a Run <A>/<E>/<R>, a folder with a plot.toml, <A>/<E> (each of its Runs), or an errand file (its configurations' newest Runs) |
| `[configuration]` | with an errand file: only this configuration |
| `--sets NAMES` | measure these sets only (default: [stats].sets, else [plot].draw, else every set) |
| `--set KEY=VALUE` | as for heimdall run |
| `--across` | the Runs of this errand together (as heimdall plot --across) |

## `heimdall overlay`

overlay any YODA/ROOT files through Paint, with no errand file

| Argument | Meaning |
|---|---|
| `FILE…` | YODA (.yoda, .yoda.gz) or ROOT files |
| `-o, --output OUTPUT` | where the pages go (default results/plots/<first file>) |
| `--labels LABELS` | legend labels, comma-separated, one per file |
| `--objects GLOB…` | only these YODA paths |
| `--formats FORMATS` | pdf, png, svg, eps (default pdf,png) |
| `--ratio` | a ratio panel against the first curve |
| `--style FILE` | a style file over src/Apps/Paint/base.toml |

## `heimdall deck`

retired: heimdall report makes a report of Runs' pages and numbers

## `heimdall report`

a quick report of Runs' pages and numbers, built only when asked into reports/, where results/ has its sources (a folder's: its report.toml)

| Argument | Meaning |
|---|---|
| `RECIPE.toml\|SOURCE…` | sources alone: one folder's report.toml (else the default report), or the default over several: <A>/<E>/<R>, <A>/<E>, a path or a glob; or a recipe first, always named .toml (<A>/<E>.toml under configs/, ./… or /…: a recipe of its own, an errand file's [report], a report.toml), then its sources, which replace its [report].from |
| `--list, --dry-run` | its sources, sections and figures, each copied or drawn for the report; nothing written |
| `--init SOURCE` | write the recipe RECIPE.toml (<A>/<E>.toml) once: SOURCE's sets and pages, listed |
| `-o, --output DIR` | build into DIR (default: its recipe's [report].output, else reports/<A>/<E>/<R>/ as results/ has its sources) |

## `heimdall ls`

every config and its configurations

| Argument | Meaning |
|---|---|
| `[assignment]` | only this assignment's errand files |

## `heimdall explain`

a key of an errand file: its type, default and meaning (the schema's)

| Argument | Meaning |
|---|---|
| `key` | e.g. plot.y_gutter, errand.events, cfgs.pdf.threads, quantities.<q>.points, rivet.analyses |

## `heimdall context`

what an AI working in a work dir needs first: the model, a whole errand file, commands, where to read more

## `heimdall docs`

the docs as one searchable page: settings, pages by reader, their graph

| Argument | Meaning |
|---|---|
| `--drift` | instead: pages whose code changed since the docs were last crystallised, with no live doc naming them |
| `--no-open` | build it and print where, without opening a browser |

## `heimdall status`

each configuration's points: complete, stale, running, failed or stopped (when, and why), incomplete or to run; its events, seeds and tools

| Argument | Meaning |
|---|---|
| `[config]` | one config, or a record <A>/<E>/<R> (default: every config) |
| `[configuration]` | one configuration of it |
| `--set KEY=VALUE` | as heimdall run's, for the view |
| `--stack` | the loaded stack instead: each package installed, its release and state; the libraries' versions |

## `heimdall records`

the record files: `records upgrade` brings them to today's format (a backup of each beside it)

| Argument | Meaning |
|---|---|
| `action` | upgrade: add `format` to points.json, provenance.json, identity.json and plot.toml that lack it |
| `[A[/E[/R]]]` | only this Assignment, Errand or Run (default: every record) |
| `--dry-run` | list what it would do, change nothing |

## `heimdall migrate`

rewrite errand files and their cards in today's forms (a diff, or --apply)

| Argument | Meaning |
|---|---|
| `CONFIG…` | configs to migrate (default: every config) |
| `--v3` | into the errand file's third form (docs/stable/guide/errand-file.md, runner/v3.py) |
| `--layout` | move the work dir's older layouts into today's: logs/ into records/<A>/<E>/<R>/logs/, points into points/ (and output/ first, if any); no configs are read |
| `--list` | with --layout: every move, one a line |
| `--names` | a work dir from before Heimdall's names moved: hep → heimdall (its marker hep.toml → heimdall.toml, the old names in its own files: configs, modules, Makefile, editor settings) and [run] → [errand], [run].project → [errand].assignment (its configs, its records' snapshots, its plot documents' [source]) |
| `--snapshot RECORD` | give a record that ran before snapshots one: copy a config's files into <record>/config/ (--from, default the config its points.json names) and say which points it gives the same identity |
| `--plot-docs RECORD…` | write the plot document (results/<A>/<E>/<R>/plot.toml) of every record without one, or of these (<A>/<E>/<R>), from its snapshot (else the config its points.json names) |
| `--from CONFIG` | with --snapshot: the config to copy |
| `--set KEY=VALUE` | with --snapshot: the overrides it ran with (default: those its points' provenance records) |
| `--apply` | write the changes (default: print the diff) |
| `--dry-run` | print the diff, write nothing (the default) |

## `heimdall reproduce`

run a finished point again, from its provenance, beside it

| Argument | Meaning |
|---|---|
| `provenance` | records/…/<point>/provenance.json |
| `--anyway` | run it even though the setup changed since |
| `--plain` | plain lines instead of the live view |

## `heimdall clean`

remove what the runner made and no plan uses: working folders (records/…/logs/) and .cache/ (a point's records with --records)

| Argument | Meaning |
|---|---|
| `[config]` | one config (default: every config, and the unused caches) |
| `--dry-run` | list only |
| `--set KEY=VALUE` | as heimdall run's: what the plans use |
| `--yes` | delete without asking |
| `--records` | also the records no plan has (provenance, identities, completion): asked for even with --yes |

## `heimdall check`

check errand files: every configuration loaded, validated and planned

| Argument | Meaning |
|---|---|
| `CONFIG…` | configs to check (default: every configs/<A>/*.toml with an [errand]) |
| `--set KEY=VALUE` | as heimdall run's: check what that job would |

## `heimdall watch`

attach the live view to a running job

| Argument | Meaning |
|---|---|
| `[config]` | the errand file whose job to watch (default: the latest job) |
| `[configuration]` | overrides [errand].configuration (or the sweep's latest) |
| `--plain` | plain lines instead of the live view |
| `--file EVENTS.JSONL` | follow a Run's run.jsonl, or a --journal job's status.jsonl, instead |
| `--pid N` | the job of this process (heimdall runs lists them) |
| `-i, --index N` | the live job [N] of heimdall runs (not a paused one) |

## `heimdall runs`

live jobs (running and paused), each with its index [N]; with --5, --10, --20 or --50 the latest jobs, with --week or --month jobs of the last 7 or 28 days

| Argument | Meaning |
|---|---|
| `--5` | show the latest 5 jobs, including ended ones |
| `--10` | show the latest 10 jobs, including ended ones |
| `--20` | show the latest 20 jobs, including ended ones |
| `--50` | show the latest 50 jobs, including ended ones |
| `--week` | show all jobs from the last 7 days |
| `--month` | show all jobs from the last 28 days |
| `--resume N` | resume the paused job [N]: its own command again, detached, in its work dir and checkout (its complete points skipped) |
| `--forget N` | drop the paused job [N] from the live list (its entry is kept) |

## `heimdall tag`

a Run's tag: show it, set it, or --clear it

| Argument | Meaning |
|---|---|
| `RECORD` | a Run, <A>/<E>/<R>, or a path under records/ or results/ |
| `[NAME]` | the tag to give it (a letter or digit, then letters, digits, . _ + -, at most 40) |
| `--clear` | remove its tag |

## `heimdall log`

a record's own account, a point's attempts and logs, or a tool's log

| Argument | Meaning |
|---|---|
| `RECORD[/POINT[/TAG]]` | a record, <A>/<E>/<R>, then a point and a tool, or a path under records/ |
| `--full` | the whole logs (a job with --logs) instead of the digests |
| `--attempt N` | an earlier attempt's logs, from the point's history/ |

## `heimdall stop`

stop a running job as Ctrl-C would: its points end cleanly, a rerun resumes (a second stop kills its tools at once)

| Argument | Meaning |
|---|---|
| `[config]` | the errand file whose job to stop (default: your only running job) |
| `[configuration]` | the configuration it runs |
| `--pid N` | the job of this process (heimdall runs lists them) |
| `--no-wait` | ask it to stop and return, without waiting for it to end |

## `heimdall cluster`

run a configuration as Slurm jobs (sbatch): a pre job, a point per array task, a finish job

| Argument | Meaning |
|---|---|
| `config` | the errand file, as heimdall run names it |
| `[configuration]` | overrides [errand].configuration; under [errand].sweep_runs, submits only it |
| `--points SEL` | submit a subset: tags, indices or quantity=tag |
| `--set KEY=VALUE` | override one value for this submission (repeatable; cluster.time=… too); the jobs get it |
| `--keep WHAT` | what each job also keeps (as heimdall run --keep) |
| `--rerun` | submit complete points too, and rerun them |
| `--dry-run` | write the job scripts and print the sbatch lines; submit nothing |
| `--status` | the latest submission: each point's state (sacct, squeue) |
| `--cancel` | scancel the latest submission's jobs |

## `heimdall setup`

make a work dir: the key folders, heimdall.toml and the template's files (never overwrites)

| Argument | Meaning |
|---|---|
| `dir` | the work dir's folder: new, empty, or a work dir to complete |
| `--assignment A` | also configs/<A>/ with a starter errand file and card, and modules/<A>/ |
| `--git yes\|new` | commit what was added (only that), in the git repository the folder is in, or a new one when it is in none; --git=new: a repository of its own even inside another |
| `--adopt` | make a work dir of a folder that has files but no heimdall.toml |
| `--name NAME` | the work dir's name in heimdall.toml (default: the folder's) |
| `--example NAME` | also a working example assignment to run first: jets (the guide's Demo assignment: Pythia → Rivet → pages against ZEUS data) |
| `--refresh` | bring the framework's own files (Makefile, README/HEIMDALL.md, CLAUDE.md, .vscode, the .gitignore block) up to today's template, as a diff; never the user's files |
| `--yes` | with --refresh: write without asking |

## `heimdall doctor`

what this machine's stack and Heimdall can do, checked

| Argument | Meaning |
|---|---|
| `--quick` | skip the slow runs (Herwig's LHC.in): under a minute |
| `--record` | write this machine's summary to recipes/support/<platform>-<host>.toml (the support matrix) |
| `--matrix` | the support matrix: every machine's recorded summary |

## `heimdall tools`

every tool folder: the work dir's tools/, the machine root's, Heimdall's

| Argument | Meaning |
|---|---|
| `NAME \| new NAME…` | a folder to show, or new and a folder to make |
| `--package RECIPE` | heimdall tools new: a recipe the tool runs ([tool] packages; again for more) |
| `--runs COMMAND` | heimdall tools new: its program ([tool] executable) |
| `--from SOURCE` | heimdall tools new: the folder it starts from (exec, module: a copy; any other: extends it) |

## `heimdall build`

compile the work dir's module programs and Rivet plugins (make all)

| Argument | Meaning |
|---|---|
| `targets…` | make targets (default: all) |
| `--framework` | Heimdall's apps instead (framework/Apps/) |
| `--tests` | with --framework: the C++ tests too |
| `--clean` | empty the build first |
| `--configure` | probe the toolchain again (rewrite flags.mk) |
| `-j, --jobs N` | parallel jobs (default: every core) |
| `--dry-run` | what make would do (make -n); nothing built |

## `heimdall make`

make one source of the work dir (or --framework, Heimdall's): <path>/<X>.exe, <path>/<x>.so

## `heimdall stack`

this machine's stack: heimdall stack build|list|status|doctor [options]

## `heimdall help`

a command's help: heimdall help <command>

| Argument | Meaning |
|---|---|
| `[command]` |  |

## `heimdall refresh`

reload this shell's environment (gjallarhorn.sh's shell function)

## `heimdall quit`

leave this shell's environment (gjallarhorn.sh's shell function)

## `heimdall cd`

cd to a work dir's folder: heimdall cd ASSIGNMENT [configs|modules|results|records|logs] (gjallarhorn.sh's shell function)

## `heimdall recognise`

record work dirs by title, in the machine root's workdirs.toml (gjallarhorn <title> goes to one)

| Argument | Meaning |
|---|---|
| `[path]` | a work dir, or a folder to search below (default: here) |
| `--as TITLE` | record the work dir under this title instead |
| `--list` | every title, its path, and whether it is still a work dir |
| `--forget TITLE` | take a title out of the record |
| `--path TITLE` | print the work dir of TITLE (gjallarhorn asks this) |

## `heimdall bifrost`

the environment's packages (conda-forge; -python: PyPI), added, dropped or shown; --shell: gjallarhorn's block in ~/.bashrc and ~/.zshrc

| Argument | Meaning |
|---|---|
| `PACKAGE…` | conda-forge packages ("gsl=2.8", "gsl 2.8.*"), or PyPI ones with -python |
| `-python, --python` | PyPI packages, by their pip names |
| `--drop` | take the packages out |
| `--shell install\|remove` | write (or take out) gjallarhorn and bifrost in ~/.bashrc and ~/.zshrc |
| `--conda` | -c, -conda: the tools (recipes) ready-made from conda-forge, what they need too |
| `--build` | -b, -build: the tools built here from their recipes; -b@<toolkit>: with its changes |
| `--yes` | switch without asking (it reruns points and rebuilds) |

## `heimdall image`

Apptainer images of Heimdall and a machine root: list them, or build one

| Argument | Meaning |
|---|---|
| `[action]` |  |
| `KEY=VALUE…` | build: packages=@kit (default @primary), cores=N, root_cores=N |
| `--name NAME` | build: the image's name (default: the toolkit's) |
| `--dirty` | build: take uncommitted changes as they are |

## `heimdall where`

which Heimdall and which work dir this shell sees

| Argument | Meaning |
|---|---|
| `--heimdall` | only Heimdall's folder |
| `--work` | only the work dir (exit 2 outside one) |
