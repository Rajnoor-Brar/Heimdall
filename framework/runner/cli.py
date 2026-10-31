"""`heimdall run`, `heimdall plot`, `heimdall overlay`, `heimdall watch`, `heimdall check` and the housekeeping commands (`ls`,
`explain`, `status`, `clean`: house.py) (rank 5): argument parsing and the order of events.

docs/05_Commands_and_Tools.md §1. `heimdall build` is handled by the shell dispatcher
(framework/bin/heimdall), which runs make.

Exit codes: 0 every point done (or skipped), 1 a point failed, 2 a config error before anything ran,
6 stopped by the user. Under [run].sweep_runs (V38), several runs one after another: 6 if one was
stopped, else 1 if any failed (or could not be planned at its turn), else 0.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import tomllib
import sys
from dataclasses import dataclass
from pathlib import Path

from . import cluster as clustermod
from . import config as configmod
from . import execute, house, paths, plot, plotdoc, post, record, runs, sweep, tools
from . import doctor as doctormod
from . import setup as setupmod
from .errors import HeimdallError, did_you_mean
from .paths import cache_root, check_retired, find_work, records_root, results_root
from .quantities import load_master
from .events import Bus, Hub, Journal, RunBus, RunLog, greeting, connect, hubs
from .watch import PlainView, follow_events, follow_file, view


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="heimdall", description="Heimdall: plan, run, draw and record studies (docs/README.md). "
                                                       "`heimdall help <command>` for one command.")
    top.add_argument("--plain", action="store_true", help="plain lines instead of the live view (any command, anywhere)")
    commands = top.add_subparsers(dest="command", required=True, metavar="<command>")

    run = commands.add_parser("run", help="plan and run a configuration")
    run.add_argument("config", help="configs/<Project>/<name>[.toml], ./path from the work dir, or a record "
                                    "<Project>/<run>/<NN_cfg> (what it ran with: its snapshot)")
    run.add_argument("configuration", nargs="?", help="overrides [run].configuration; under [run].sweep_runs, runs only it")
    run.add_argument("--plan", "--dry-run", dest="plan", action="store_true", help="print the plan; run nothing")
    run.add_argument("--why", action="store_true",
                     help="for each point that would run, what changed since it last completed; run nothing")
    run.add_argument("--show-config", action="store_true",
                     help="print each configuration's resolved values and where each came from; run nothing")
    run.add_argument("--card", metavar="TAG", help="with --plan: that tool's card for the first point, each line with "
                                                   "where its value comes from")
    run.add_argument("--points", metavar="SEL", help="run a subset: tags, indices or quantity=tag")
    run.add_argument("--detach", action="store_true",
                     help="start the run in the background and return: heimdall watch follows it, heimdall stop stops it "
                          "(on a terminal, a run started without it leaves on d too)")
    run.add_argument("--worker", metavar="ID", help=argparse.SUPPRESS)       # a detached run's own process (V183)
    run.add_argument("--set", metavar="KEY=VALUE", action="append", default=[],
                     help="override one value for this invocation (repeatable), in the file's own names: "
                          "run.events=100 (v3), run.event_count=100 (v2)")
    run.add_argument("--rerun", action="store_true", help="ignore skip-unchanged; under a serial the file sets, "
                                                          "overwrite points made from other inputs")
    run.add_argument("--only", choices=["pre", "post", "plot"], help="rerun only the pre tools, the post tools or the plots")
    run.add_argument("--no-plot", action="store_true", dest="no_plot",
                     help="draw nothing after the points (its plot.toml is written all the same), whatever [run].plot says")
    run.add_argument("--no-stats", action="store_true", dest="no_stats",
                     help="measure nothing after the points, whatever [run].stats says")
    run.add_argument("--stages", metavar="LIST",
                     help="run only these stages, skip-unchanged: pre, points, combine, post, plot (comma-separated; heimdall cluster's jobs)")
    run.add_argument("--plain", action="store_true", help="plain lines instead of the live view")
    run.add_argument("--wait", action="store_true",
                     help="a point another session is running: wait for it (default: skip it, naming who runs it)")
    run.add_argument("--journal", action="store_true",
                     help="also write every status event to records/…/status.jsonl (for heimdall watch --file and replay)")
    run.add_argument("--logs", action="store_true",
                     help="keep every tool's whole output in records/…/logs/<point>/<tag>.full.log (its digest, <tag>.log, is always kept)")
    run.add_argument("--keep", action="append", default=[], metavar="WHAT",
                     help="also keep (comma-separated): logs, journal, work (a finished point's whole working folder), "
                          "cache (card checks); also heimdall.toml's and "
                          "machine.toml's [run] keep")

    draw = commands.add_parser("plot", help="draw a configuration's pages from its complete points")
    draw.add_argument("config", help="the run config, or a record <Project>/<run>/<NN_cfg>: its points as they were "
                                     "recorded, with the config they ran with (its snapshot, which you may edit)")
    draw.add_argument("--plot", metavar="FILE", dest="plot_file",
                      help="a file whose [plot] draws instead of the run's: configs/<P>/<name>, ./… or /…")
    draw.add_argument("--sets", metavar="NAMES", dest="draw_sets",
                      help="draw these sets only (comma-separated; default: the document's [plot].draw, else every set)")
    draw.add_argument("--points", metavar="SEL", dest="page_points",
                      help="pages of these points only, in this order, in the folder points/: indices, names, globs, "
                           "tags or quantity=tag, comma-separated ([plot].sets for one set)")
    draw.add_argument("--plan", action="store_true",
                      help="say each set's page cells and their curves, from the complete points; draw nothing; "
                           "with --style-sync: what would change, written nowhere")
    draw.add_argument("--style-sync", metavar="CONFIG", dest="style_sync",
                      help="take this config's [plot] and [stats] into the plot documents named (<P>/<name>/<cfg>, or "
                           "<P>/<name>: each of its runs), what each run knows left as it is; nothing is drawn unless --replot")
    draw.add_argument("--replot", action="store_true", help="with --style-sync: then draw what was synced")
    draw.add_argument("--across", action="store_true",
                      help="the runs of this run TOML together, results/<P>/<name>/plot.toml: its [plot.across] sets (V169)")
    draw.add_argument("--keep", action="append", default=[], metavar="WHAT",
                      help="cache: keep the card checks (as heimdall run --keep); the drawing's working files are .cache/'s anyway")
    draw.add_argument("configuration", nargs="?", help="overrides [run].configuration; under sweep_runs, only it")
    draw.add_argument("--set", metavar="KEY=VALUE", action="append", default=[], help="as for heimdall run")

    numbers = commands.add_parser("stats", help="a run's statistics alone: its pages' numbers against the data, drawing no page")
    numbers.add_argument("config", help="a run <P>/<name>/<cfg>, a folder with a plot.toml, <P>/<name> (each of its runs), "
                                        "or a run TOML (its configurations' newest runs)")
    numbers.add_argument("configuration", nargs="?", help="with a run TOML: only this configuration")
    numbers.add_argument("--sets", metavar="NAMES", dest="draw_sets",
                         help="measure these sets only (default: [stats].sets, else [plot].draw, else every set)")
    numbers.add_argument("--set", metavar="KEY=VALUE", action="append", default=[], help="as for heimdall run")
    numbers.add_argument("--across", action="store_true", help="the runs of this run TOML together (as heimdall plot --across)")

    overlay = commands.add_parser("overlay", help="overlay any YODA/ROOT files through Paint, with no run TOML")
    overlay.add_argument("files", nargs="+", metavar="FILE", help="YODA (.yoda, .yoda.gz) or ROOT files")
    overlay.add_argument("-o", "--output", help="where the pages go (default results/plots/<first file>)")
    overlay.add_argument("--labels", help="legend labels, comma-separated, one per file")
    overlay.add_argument("--objects", nargs="+", default=[], metavar="GLOB", help="only these YODA paths")
    overlay.add_argument("--formats", default="pdf,png", help="pdf, png, svg, eps (default pdf,png)")
    overlay.add_argument("--ratio", action="store_true", help="a ratio panel against the first curve")
    overlay.add_argument("--style", metavar="FILE", help="a style file over src/Apps/Paint/base.toml")

    deck = commands.add_parser("deck", help="retired: heimdall report makes a report of runs' pages and numbers")
    deck.add_argument("rest", nargs="*", help=argparse.SUPPRESS)          # what it took, so any old line stops with the message
    deck.add_argument("--list", "--dry-run", dest="list", action="store_true", help=argparse.SUPPRESS)
    deck.add_argument("--only", help=argparse.SUPPRESS)
    deck.add_argument("--init", action="store_true", help=argparse.SUPPRESS)

    reported = commands.add_parser("report", help="a quick report of runs' pages and numbers, built only when asked into "
                                                  "reports/, where results/ has its sources (a folder's: its report.toml)")
    reported.add_argument("names", nargs="*", metavar="RECIPE.toml|SOURCE",
                          help="sources alone: one folder's report.toml (else the default report), or the default over several: "
                               "<P>/<run>/<cfg>, <P>/<run>, a path or a glob; or a recipe first, always named .toml (<P>/<name>.toml "
                               "under configs/, ./… or /…: a recipe of its own, a run TOML's [report], a report.toml), "
                               "then its sources, which replace its [report].from")
    reported.add_argument("--list", "--dry-run", dest="list", action="store_true",
                          help="its sources, sections and figures, each copied or drawn for the report; nothing written")
    reported.add_argument("--init", metavar="SOURCE", help="write the recipe RECIPE.toml (<P>/<name>.toml) once: SOURCE's sets and "
                                                           "pages, listed")
    reported.add_argument("-o", "--output", metavar="DIR", help="build into DIR (default: its recipe's [report].output, "
                                                                "else reports/<P>/<run>/<cfg>/ as results/ has its sources)")

    listing = commands.add_parser("ls", help="every config and its configurations")
    listing.add_argument("project", nargs="?", help="only this project's configs")

    explain = commands.add_parser("explain", help="a run TOML key: its type, default and meaning (the schema's)")
    explain.add_argument("key", help="e.g. plot.y_gutter, run.events, cfgs.pdf.threads, quantities.<q>.points, rivet.analyses")

    state = commands.add_parser("status", help="each configuration's points: complete, stale, running, failed or stopped "
                                                "(when, and why), incomplete or to run; its events, seeds and tools")
    state.add_argument("config", nargs="?", help="one config, or a record <P>/<run>/<NN_cfg> (default: every config)")
    state.add_argument("configuration", nargs="?", help="one configuration of it")
    state.add_argument("--set", metavar="KEY=VALUE", action="append", default=[], help="as heimdall run's, for the view")
    state.add_argument("--stack", action="store_true", help="the loaded stack instead: each package installed, its release and state; the libraries' versions")

    move = commands.add_parser("migrate", help="rewrite run TOMLs and their cards in today's forms (a diff, or --apply)")
    move.add_argument("configs", nargs="*", metavar="CONFIG", help="configs to migrate (default: every config)")
    move.add_argument("--v3", action="store_true", help="into the run TOML's third form (03 §6, runner/v3.py)")
    move.add_argument("--layout", action="store_true",
                      help="move the work dir's older layouts into today's: logs/ into records/<run>/logs/, points into "
                           "points/ (and output/ first, if any); no configs are read")
    move.add_argument("--list", action="store_true", help="with --layout: every move, one a line")
    move.add_argument("--names", action="store_true",
                      help="a work dir from before Heimdall's names moved (hep → heimdall): its marker hep.toml → "
                           "heimdall.toml, and the old names in its own files (configs, modules, Makefile, editor settings)")
    move.add_argument("--snapshot", metavar="RECORD",
                      help="give a record that ran before snapshots one: copy a config's files into <record>/config/ "
                           "(--from, default the config its points.json names) and say which points it gives the same identity")
    move.add_argument("--plot-docs", nargs="*", metavar="RECORD",
                      help="write the plot document (results/<run>/plot.toml) of every record without one, or of these "
                           "(<P>/<name>/<cfg>), from its snapshot (else the config its points.json names)")
    move.add_argument("--from", dest="source", metavar="CONFIG", help="with --snapshot: the config to copy")
    move.add_argument("--set", metavar="KEY=VALUE", action="append", default=[],
                      help="with --snapshot: the overrides it ran with (default: those its points' provenance records)")
    move.add_argument("--apply", action="store_true", help="write the changes (default: print the diff)")
    move.add_argument("--dry-run", action="store_true", help="print the diff, write nothing (the default)")

    again = commands.add_parser("reproduce", help="run a finished point again, from its provenance, beside it")
    again.add_argument("provenance", help="records/…/<point>/provenance.json")
    again.add_argument("--anyway", action="store_true", help="run it even though the setup changed since")
    again.add_argument("--plain", action="store_true", help="plain lines instead of the live view")

    clean = commands.add_parser("clean", help="remove what the runner made and no plan uses: working folders (records/…/logs/) and .cache/ (a point's records with --records)")
    clean.add_argument("config", nargs="?", help="one config (default: every config, and the unused caches)")
    clean.add_argument("--dry-run", action="store_true", help="list only")
    clean.add_argument("--set", metavar="KEY=VALUE", action="append", default=[], help="as heimdall run's: what the plans use")
    clean.add_argument("--yes", action="store_true", help="delete without asking")
    clean.add_argument("--records", action="store_true",
                       help="also the records no plan has (provenance, identities, completion): asked for even with --yes")

    check = commands.add_parser("check", help="check run TOMLs: every configuration loaded, validated and planned")
    check.add_argument("configs", nargs="*", metavar="CONFIG",
                       help="configs to check (default: every configs/<Project>/*.toml with a [run])")
    check.add_argument("--set", metavar="KEY=VALUE", action="append", default=[], help="as heimdall run's: check what that run would")

    watch = commands.add_parser("watch", help="attach the live view to a running job")
    watch.add_argument("config", nargs="?", help="the run config whose job to watch (default: the latest job)")
    watch.add_argument("configuration", nargs="?", help="overrides [run].configuration (or the sweep's latest)")
    watch.add_argument("--plain", action="store_true", help="plain lines instead of the live view")
    watch.add_argument("--file", metavar="EVENTS.JSONL",
                       help="follow a run's run.jsonl, or a --journal run's status.jsonl, instead")
    watch.add_argument("--pid", type=int, metavar="N", help="the run of this process (heimdall runs lists them)")

    listed = commands.add_parser("runs", allow_abbrev=False,       # --1 is no --10
                                 help="running jobs; with --5, --10, --20 or --50 the latest runs, with --week or --month "
                                      "those of the last 7 or 28 days")
    run_limits = listed.add_mutually_exclusive_group()
    for limit in (5, 10, 20, 50):
        run_limits.add_argument(f"--{limit}", dest="limit", action="store_const", const=limit,
                                help=f"show the latest {limit} runs, including non-running runs")
    run_limits.add_argument("--week", dest="days", action="store_const", const=7,
                            help="show all runs from the last 7 days")
    run_limits.add_argument("--month", dest="days", action="store_const", const=28,
                            help="show all runs from the last 28 days")

    logged = commands.add_parser("log", help="a record's own account, a point's attempts and logs, or a tool's log")
    logged.add_argument("target", metavar="RECORD[/POINT[/TAG]]",
                        help="a record, <P>/<run>/<NN_cfg>, then a point and a tool, or a path under records/")
    logged.add_argument("--full", action="store_true", help="the whole logs (a run with --logs) instead of the digests")
    logged.add_argument("--attempt", type=int, metavar="N", help="an earlier attempt's logs, from the point's history/")

    stop = commands.add_parser("stop", help="stop a running job as Ctrl-C would: its points end cleanly, a rerun resumes "
                                            "(a second stop kills its tools at once)")
    stop.add_argument("config", nargs="?", help="the run config whose job to stop (default: your only running job)")
    stop.add_argument("configuration", nargs="?", help="the configuration it runs")
    stop.add_argument("--pid", type=int, metavar="N", help="the job of this process (heimdall runs lists them)")
    stop.add_argument("--no-wait", action="store_true", help="ask it to stop and return, without waiting for it to end")

    batch = commands.add_parser("cluster", help="run a configuration as Slurm jobs (sbatch): a pre job, a point per array task, a finish job")
    batch.add_argument("config", help="the run config, as heimdall run names it")
    batch.add_argument("configuration", nargs="?", help="overrides [run].configuration; under [run].sweep_runs, submits only it")
    batch.add_argument("--points", metavar="SEL", help="submit a subset: tags, indices or quantity=tag")
    batch.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                       help="override one value for this submission (repeatable; cluster.time=… too); the jobs get it")
    batch.add_argument("--keep", action="append", default=[], metavar="WHAT",
                       help="what each job's run also keeps (as heimdall run --keep)")
    batch.add_argument("--rerun", action="store_true", help="submit complete points too, and rerun them")
    what = batch.add_mutually_exclusive_group()
    what.add_argument("--dry-run", action="store_true", help="write the job scripts and print the sbatch lines; submit nothing")
    what.add_argument("--status", action="store_true", help="the latest submission: each point's state (sacct, squeue)")
    what.add_argument("--cancel", action="store_true", help="scancel the latest submission's jobs")

    make = commands.add_parser("setup", help="make a work dir: the key folders, heimdall.toml and the template's files (never overwrites)")
    make.add_argument("dir", help="the work dir's folder: new, empty, or a work dir to complete")
    make.add_argument("--project", metavar="P", help="also configs/<P>/ with a starter run TOML and card, and modules/<P>/")
    make.add_argument("--git", nargs="?", const="yes", choices=["yes", "new"],
                      help="commit what was added (only that), in the git repository the folder is in, or a new one "
                           "when it is in none; --git=new: a repository of its own even inside another")
    make.add_argument("--adopt", action="store_true", help="make a work dir of a folder that has files but no heimdall.toml")
    make.add_argument("--name", help="the work dir's name in heimdall.toml (default: the folder's)")
    make.add_argument("--example", metavar="NAME", help="also a working example project to run first: jets "
                                                        "(the guide's Demo project: Pythia → Rivet → pages against ZEUS data)")
    make.add_argument("--refresh", action="store_true",
                      help="bring the framework's own files (Makefile, README/HEIMDALL.md, CLAUDE.md, .vscode, the "
                           ".gitignore block) up to today's template, as a diff; never the user's files")
    make.add_argument("--yes", action="store_true", help="with --refresh: write without asking")

    doctor = commands.add_parser("doctor", help="what this machine's stack and Heimdall can do, checked",
                                 description="Every installed package's checks (its recipe's [[verify]]), a scan for "
                                             "libraries that no longer resolve, and Heimdall's own: one row each, "
                                             "ok / MISSING / FAIL / n/a. Exit 1 on a FAIL.")
    doctor.add_argument("--quick", action="store_true", help="skip the slow runs (Herwig's LHC.in): under a minute")
    doctor.add_argument("--record", action="store_true",
                        help="write this machine's summary to recipes/support/<platform>-<host>.toml (the support matrix)")
    doctor.add_argument("--matrix", action="store_true", help="the support matrix: every machine's recorded summary")

    folders_ = commands.add_parser("tools", help="every tool folder: the work dir's tools/, the machine root's, Heimdall's",
                                   description="Each tool folder by name, nearest first: a work dir's tools/<name>/, the "
                                               "machine root's tools/<name>/, Heimdall's framework/tools/<name>/. A nearer "
                                               "folder replaces a farther one, or, with extends = \"<name>\" in its "
                                               "tool.toml, is laid over it. `heimdall tools <name>`: one folder in full; "
                                               "`heimdall tools new <name> --from <tool>`: a folder in this work dir's tools/.")
    folders_.add_argument("what", nargs="*", metavar="NAME | new NAME", help="a folder to show, or new and a folder to make")
    folders_.add_argument("--package", action="append", default=[], metavar="RECIPE",
                          help="heimdall tools new: a recipe the tool runs ([tool] packages; again for more)")
    folders_.add_argument("--runs", default="", metavar="COMMAND", help="heimdall tools new: its program ([tool] executable)")
    folders_.add_argument("--from", dest="source", help="heimdall tools new: the folder it starts from (exec, module: a copy; "
                                                        "any other: extends it)")

    build = commands.add_parser("build", help="compile the work dir's module programs and Rivet plugins (make all)")
    build.add_argument("targets", nargs="*", help="make targets (default: all)")
    build.add_argument("--framework", action="store_true", help="Heimdall's apps instead (framework/Apps/)")
    build.add_argument("--tests", action="store_true", help="with --framework: the C++ tests too")
    build.add_argument("--clean", action="store_true", help="empty the build first")
    build.add_argument("--configure", action="store_true", help="probe the toolchain again (rewrite flags.mk)")
    build.add_argument("-j", "--jobs", type=int, metavar="N", help="parallel jobs (default: every core)")
    build.add_argument("--dry-run", action="store_true", help="what make would do (make -n); nothing built")

    commands.add_parser("make", help="make one source of the work dir (or --framework, Heimdall's): <path>/<X>.exe, <path>/<x>.so",
                        add_help=False)
    commands.add_parser("stack", help="this machine's stack: heimdall stack build|list|status|doctor [options]", add_help=False)

    helping = commands.add_parser("help", help="a command's help: heimdall help <command>")
    helping.add_argument("topic", nargs="?", metavar="command")

    for verb, what in (("refresh", "reload this shell's environment"), ("quit", "leave this shell's environment"),
                       ("cd", "cd to a work dir's folder: heimdall cd PROJECT [configs|modules|results|records|logs]")):
        commands.add_parser(verb, help=f"{what} (gjallarhorn.sh's shell function)", add_help=False)

    known = commands.add_parser("recognise", help="record work dirs by title, in the machine root's workdirs.toml "
                                                  "(gjallarhorn <title> goes to one)",
                                description="A work dir (or a folder inside one) is recorded under its title, its "
                                            "heimdall.toml's [work] name or else its folder's name; any other folder is "
                                            "searched for work dirs, 4 folders deep, and each is recorded.")
    known.add_argument("path", nargs="?", help="a work dir, or a folder to search below (default: here)")
    known.add_argument("--as", dest="title", metavar="TITLE", help="record the work dir under this title instead")
    asked = known.add_mutually_exclusive_group()
    asked.add_argument("--list", action="store_true", help="every title, its path, and whether it is still a work dir")
    asked.add_argument("--forget", metavar="TITLE", help="take a title out of the record")
    asked.add_argument("--path", dest="path_of", metavar="TITLE", help="print the work dir of TITLE (gjallarhorn asks this)")

    bridge = commands.add_parser("bifrost", help="the environment's packages (conda-forge; -python: PyPI), added, "
                                                 "dropped or shown; --shell: gjallarhorn's block in ~/.bashrc and ~/.zshrc",
                                 description="Added packages are recorded in the machine root's machine.toml "
                                             "([settings] base_packages, base_pypi) and the base is made again (pixi). "
                                             "Also the program `bifrost`.")
    bridge.add_argument("packages", nargs="*", metavar="PACKAGE",
                        help='conda-forge packages ("gsl=2.8", "gsl 2.8.*"), or PyPI ones with -python')
    bridge.add_argument("-python", "--python", action="store_true", help="PyPI packages, by their pip names")
    bridge.add_argument("--drop", action="store_true", help="take the packages out")
    bridge.add_argument("--shell", choices=("install", "remove"),
                        help="write (or take out) gjallarhorn and bifrost in ~/.bashrc and ~/.zshrc")
    bridge.add_argument("--conda", action="store_true",
                        help="-c, -conda: the tools (recipes) ready-made from conda-forge, what they need too")
    bridge.add_argument("--build", action="store_true",
                        help="-b, -build: the tools built here from their recipes; -b@<toolkit>: with its changes")
    bridge.add_argument("--toolkit", metavar="KIT", help=argparse.SUPPRESS)
    bridge.add_argument("--yes", action="store_true", help="switch without asking (it reruns points and rebuilds)")

    images = commands.add_parser("image", help="Apptainer images of Heimdall and a machine root: list them, or build one",
                                 description="An image holds a clean copy of this Heimdall and a machine root built "
                                             "inside it; it lives in the machine root's images/. The runtime is the "
                                             "system's (apptainer, or singularity). gjallarhorn --image <name> [title] "
                                             "runs a shell in one; [cluster] image runs heimdall cluster's jobs in one.")
    images.add_argument("action", nargs="?", choices=("list", "build"), default="list")
    images.add_argument("settings", nargs="*", metavar="KEY=VALUE",
                        help="build: packages=@kit (default @primary), cores=N, root_cores=N")
    images.add_argument("--name", default="", help="build: the image's name (default: the toolkit's)")
    images.add_argument("--dirty", action="store_true", help="build: take uncommitted changes as they are")

    where = commands.add_parser("where", help="which Heimdall and which work dir this shell sees")
    which = where.add_mutually_exclusive_group()
    which.add_argument("--heimdall", action="store_const", const="heimdall", dest="which", help="only Heimdall's folder")
    which.add_argument("--work", action="store_const", const="work", dest="which", help="only the work dir (exit 2 outside one)")
    return top


@dataclass
class Planned:
    """One run, planned: what `heimdall run CONFIG CONFIGURATION` executes."""
    run: configmod.RunConfig
    configuration: configmod.Configuration
    every: list                                    # every point's plan
    plans: list                                    # the points to run (--points)
    post: object                                   # the post stage's plan, or None
    pre: object                                    # the pre stage's plan, or None
    combined: list                                 # the combined groups (V35)


def build_plans(args, key: str | None) -> Planned:
    run, configuration = configmod.for_configuration(configmod.load(args.config, sets=args.set), key)   # V179
    plot.validate(run)                       # before anything is planned (V54): a [plot] typo costs no planning
    master = load_master(run.project, run.master_toml)
    points = sweep.points(run, configuration)
    chosen = {p.index for p in sweep.select_points(run, configuration, points, args.points)}
    if configuration.serial_auto:
        pre_plan, plans = _numbered(run, configuration, master, points)
    else:
        pre_plan, plans = _planned_points(run, configuration, master, points)
    again = getattr(args, "rerun", False) and getattr(args, "only", None) is None   # the points run anew
    record.assign_seeds(plans, frozenset(p.point.name for p in plans if again and p.point.index in chosen))
    for plan in plans:
        tools.finalise(plan, plan.seed)
        tools.check_cards(plan)                  # the tools read their cards (V59), cached by text
    if configuration.parallelism_auto:           # "auto" (V75): from the plans' cores
        configuration.parallelism = execute.auto_parallelism(plans)
    plot.check_texts(run, plans)                 # a placeholder typo costs no point run (V66) …
    plot.check_figures(run, configuration)       # … nor a band's (V69), nor what a figure merges (V82)
    return Planned(run, configuration, plans, [p for p in plans if p.point.index in chosen],
                   post.plan(run, configuration, master, plans), pre_plan,
                   post.plan_combined(run, configuration, master, plans))


def _planned_points(run, configuration, master, points):
    """The pre stage and every point, planned in the configuration's folder, with their identities."""
    pre_plan = post.plan_pre(run, configuration, master, points)
    plans = []
    for point in points:
        plan = tools.plan_point(run, configuration, point, master, pre=pre_plan)
        plan.identity = record.identity(plan)
        plans.append(plan)
    return pre_plan, plans


def _numbered(run, configuration, master, points):
    """A v3 configuration without a serial (03 §6): the runner numbers its folder. The newest folder its
    points completed in as it stands now (an older one, when a change was undone); else the newest, when
    nothing in it was made from other inputs (a run under way, or one never begun); else a new number,
    so that a change never overwrites what was made."""
    taken = tools.serials_taken(run, configuration)
    newest = None
    for number in sorted(taken, reverse=True):
        configuration.serial = number
        pre_plan, plans = _planned_points(run, configuration, master, points)
        stages = [s for s in (pre_plan, *plans) if s is not None]
        clash = record.overwritten(stages)
        if newest is None:
            newest = (number, pre_plan, plans, clash)
        if not clash and any(record.is_complete(s) for s in stages):
            configuration.serial_note = f"folder {number:02d}: made from these inputs"
            return pre_plan, plans
    if newest is not None and not newest[3]:
        configuration.serial, configuration.serial_note = newest[0], f"folder {newest[0]:02d}: nothing in it made yet"
        return newest[1], newest[2]
    configuration.serial = max(taken, default=0) + 1
    held = ", ".join(f"{n:02d}" for n in sorted(taken))
    configuration.serial_note = (f"folder {configuration.serial:02d}: new ({held} {'holds' if len(taken) == 1 else 'hold'} "
                                 "other inputs)" if taken else f"folder {configuration.serial:02d}: the first")
    return _planned_points(run, configuration, master, points)


def overwrites(planned: Planned, stages=None) -> list:
    """What running would replace that was made from other inputs, under a serial the file sets (v3,
    03 §6): the pre stage and the chosen points, as the stages run them."""
    if planned.run.form != 3 or planned.configuration.serial_auto:
        return []
    stages = STAGES if stages is None else stages
    return record.overwritten([s for s in ([planned.pre] if "pre" in stages and planned.pre is not None else [])
                               + (planned.plans if "points" in stages else [])])


def refuse_overwrites(planned: Planned, args, stages=None) -> None:
    """A set serial's promise: a changed configuration never overwrites what it made, unless --rerun says to."""
    changed = [] if getattr(args, "rerun", False) else overwrites(planned, stages)
    if changed:
        c = planned.configuration
        names = ", ".join(s.point.name if hasattr(s, "point") else "pre" for s in changed[:4]) + (", …" if len(changed) > 4 else "")
        where = c.origins.get("serial", "[run]").replace("[run.cfgs.", "[cfgs.")   # a v3 file: its own names
        raise HeimdallError(f"configuration '{c.key}': {len(changed)} of its points in {tools.run_dir(planned.run, c)} were "
                       f"made from other inputs ({names}); running would overwrite them",
                       where=f"{planned.run.path}: {where}",
                       hint=f"serial = {c.serial + 1} gives a fresh folder; or leave serial out and the runner numbers it; "
                            f"--rerun replaces them; --why says what changed")


def others_of(args):
    """Another configuration's plans, for a compare figure (V83), of this run or of another run TOML
    (V88): its points, or its combined groups."""
    def plans_of(ref: str) -> list:                 # "cfg", or "<Project>/<config>:<cfg>" (V88)
        config, _, key = ref.rpartition(":")
        changed = {"config": config, "set": []} if config else {}
        planned = build_plans(argparse.Namespace(**{**vars(args), "points": None, "rerun": False, **changed}), key)
        return planned.combined or planned.every
    return plans_of


def write_documents(run, configuration, members: list, say=print) -> tuple[Path | None, list[str]]:
    """A folder's plot document (plotdoc.write, V165) and beside it its report's recipe, report.toml (V209): the run
    TOML's [report], else the default report, written again each time. Its failure is said, never the run's."""
    target, notes = plotdoc.write(run, configuration, members)
    if target is not None:
        _write_recipe(run, target, say)
    return target, notes


def _write_recipe(run, target: Path, say) -> None:
    from . import report as reportmod
    try:
        reportmod.write_recipe(run, target)
    except (HeimdallError, OSError) as error:
        say(f"report: {target.with_name(reportmod.RECIPE)} not written: {getattr(error, 'message', error)}")


def draw_run(run, configuration, members: list, say, draw: bool = True, stats=True) -> int:
    """A run's plot stage (V165): its plot document written, results/<run>/plot.toml (what the run knows
    rewritten, the user's [plot] and [stats] kept), then its pages drawn from that document alone, as
    `heimdall plot` draws them, and their statistics (V168: `stats` true, false or the sets measured); with
    `draw` false, the statistics alone. The pages that failed."""
    target, notes = write_documents(run, configuration, members, say)
    for note in notes:
        say(f"plot: note: {note}")
    if target is None:
        return 0
    doc, kept, drawn = plotdoc.load(target)
    if not doc.plot:
        return 0
    if not draw:
        return plot.measure(doc, kept, drawn, say, picked=stats if isinstance(stats, list) else None) if stats else 0
    return plot.draw(doc, kept, drawn, say, stats=stats)


def journal_path(run, configuration) -> Path:
    """records/<P>/<run>/<cfg>/status.jsonl: a --journal run's events, which heimdall watch --file follows."""
    return tools.run_folders(run, configuration).journal


def header(number: int, configuration) -> str:
    """'run 02 - Beam energies -': a run's place in a sweep of runs, and its title (V38)."""
    return f"run {number:02d} - {configuration.title} -"


def _print_stage(title: str, stage, run) -> None:
    print(f"{title}   identity {stage.identity[:12]}")
    for line in tools.describe(stage, run)[1:]:
        print(line)
    print(f"  results {stage.res}   ({'complete' if record.is_complete(stage) else 'to run'})")


def run_title(run, configuration, plans) -> str:
    """A run's title, two lines (the user's form, 2026-10-26):

        zeus_validation · 12  ·  generator_pdf
           - 16 point(s), 1000000 events, 1 threads, 19 at once (~38 of 24 cores)

    the run's name, its record's serial (none when the folder has none) and the configuration; then its size."""
    serial = re.match(r"(\d+)_", tools.run_dir(run, configuration).name)
    head = f"{run.name} · {serial.group(1)}  ·  {configuration.key}" if serial else f"{run.name}  ·  {configuration.key}"
    return (f"{head}\n   - {len(plans)} point(s), {configuration.event_count} events, {configuration.threads} threads"
            + parallel_note(configuration, plans))


def parallel_note(configuration, plans) -> str:
    """', 4 at once (~52 of 24 cores)' for the title and --plan; nothing when one at a time (V36)."""
    if configuration.parallelism <= 1 or not plans:
        return ""
    each = max(execute.cores(p) for p in plans)
    return f", {configuration.parallelism} at once (~{configuration.parallelism * each} of {os.cpu_count()} cores)"


def crowded(configuration, plans) -> str:
    """A warning when the points at once want more cores than the machine has."""
    if configuration.parallelism <= 1 or not plans:
        return ""
    each = max(execute.cores(p) for p in plans)
    if configuration.parallelism * each <= (os.cpu_count() or 1):
        return ""
    return (f"parallelism {configuration.parallelism} × ~{each} cores a point is more than the {os.cpu_count()} "
            f"here: lower threads, shards or parallelism, or accept the oversubscription")


def totality_pages(run, configuration, points: list) -> tuple[int, str]:
    """The pages per object the totality set draws (V195: its own axes, not plot_points'), and what other sets
    the configuration draws, for --plan's plot line."""
    try:
        spec = sweep.set_entries({sweep.TOTALITY: sweep.totality(configuration, points)}, sweep.TOTALITY)[0]
        count = len(sweep.set_cells(run, points, spec)[0])
    except Exception:                    # a count never stops a plan (listed points' KeyError): plot_points'
        count = len(sweep.pages(configuration, points))
    drawn = configuration.draw
    others = ([s for s in drawn if s != sweep.TOTALITY] if isinstance(drawn, list)
              else [s for s in (run.plot or {}).get("sets", {}) if s != sweep.TOTALITY] if drawn else [])
    return count, f", and {len(others)} more set(s) ({', '.join(others)})" if others else ""


def print_plan(run, configuration, plans, post_plan=None, pre_plan=None, combined=()) -> None:
    print(f"run {run.name} ({run.path}) · configuration {configuration.key}: {len(plans)} point(s), "
          f"{configuration.event_count} events, {configuration.threads} threads" + parallel_note(configuration, plans))
    if crowded(configuration, plans):
        print(f"note: {crowded(configuration, plans)}")
    for note in notes_of(plans):
        print(f"note: {note}")
    for warning in tools.meta_notes(run):                       # V97
        print(f"warning: {warning}")
    if configuration.serial_note:
        print(f"note: {configuration.serial_note} (no serial set: the runner numbers the folder)")
    if run.form == 3 and not configuration.serial_auto:
        changed = record.overwritten([s for s in (pre_plan, *plans) if s is not None])
        if changed:
            print(f"warning: {len(changed)} of these were made from other inputs: running refuses to overwrite them "
                  f"(serial = {configuration.serial + 1}, or --rerun)")
    if configuration.seed_type != "identity":
        print(f"seeds: {configuration.seed_type}")
    if configuration.manual_seed is not None and configuration.seed_type != "manual":
        print(f"note: manual_seed = {configuration.manual_seed} is unused: seed_type is '{configuration.seed_type}'")
    if pre_plan is not None:
        _print_stage("pre (before every point)", pre_plan, run)
    for plan in plans:
        state = "complete" if record.is_complete(plan) else "to run"
        for line in tools.describe(plan, run):
            print(line)
        print(f"  output  {plan.out}\n  results {plan.res}   ({state})")
    for group in combined:
        _print_stage(f"combined {group.point.name} (merges {len(group.upstream)} points: "
                     f"{', '.join(configuration.combine)})", group, run)
    if post_plan is not None:
        _print_stage("post (after every point)", post_plan, run)
    if run.plot and plans:
        count, more = totality_pages(run, configuration, [p.point for p in plans])
        print(f"plot ({', '.join(plot.backends(run.plot))}): {count} page(s) per object in totality{more}, "
              f"{', '.join(plot.formats_of(run.plot))} → {plans[0].folders.plots}")


def print_why(run, configuration, plans, post_plan=None, pre_plan=None, combined=()) -> None:
    """--why (V57): each point and stage that would run, and what changed since it last completed."""
    stages = [*([pre_plan] if pre_plan else []), *plans, *combined, *([post_plan] if post_plan else [])]
    todo = [p for p in stages if not record.is_complete(p)]
    print(f"run {run.name} · configuration {configuration.key}: {len(todo)} of {len(stages)} to run")
    for plan in todo:
        print(f"{plan.point.name}   identity {plan.identity[:12]}")
        for line in record.why(plan):
            print(f"  {line}")


def notes_of(plans) -> list[str]:
    """What the plans say once (V59): a base card's line the runner overrides, …; each note once."""
    return list(dict.fromkeys(note for plan in plans for note in plan.notes))


def catch_signals(stopper: execute.Stopper) -> dict:
    """Ctrl-C (SIGINT), SIGTERM and SIGHUP ask the run to stop (V181): the first cleanly (each point ends, its
    partial outputs kept, a rerun resumes); the second hard (the tools killed at once, the stop still
    recorded); the third is the default behaviour, at once. SIGHUP, the terminal gone, also points the
    output at /dev/null; a SIGHUP ignored when the run began (nohup) stays ignored. Returns the handlers
    it replaced."""
    def on_signal(signum, frame):
        if signum == signal.SIGHUP:
            _quiet()
        if stopper.hard:
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)
            return
        stopper.hard = stopper.requested
        stopper.requested = True

    previous = {}
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        if signum == signal.SIGHUP and signal.getsignal(signum) is signal.SIG_IGN:
            continue
        previous[signum] = signal.signal(signum, on_signal)
    return previous


def _quiet() -> None:
    """The terminal is gone (SIGHUP): what the run still prints goes nowhere, not to an error."""
    try:
        null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null, 1)
        os.dup2(null, 2)
        os.close(null)
    except OSError:
        pass


#: A run's stages, in order (V114). `--stages` runs some of them, skip-unchanged; `--only` runs one again.
STAGES = ("pre", "points", "combine", "post", "plot")


def stages_of(args) -> frozenset[str]:
    """The stages this `heimdall run` runs: `--only`'s one, `--stages`'s list, or all of them."""
    given = getattr(args, "stages", None)
    if given is None:
        return frozenset([args.only]) if getattr(args, "only", None) else frozenset(STAGES)
    if getattr(args, "only", None):
        raise HeimdallError("--only and --stages do not go together",
                       hint="--only reruns one stage; --stages runs several, skipping what is unchanged")
    named = [s.strip() for s in given.split(",") if s.strip()]
    for stage in named:
        if stage not in STAGES:
            raise HeimdallError(f"--stages: '{stage}' is not a stage", hint=did_you_mean(stage, STAGES) or ", ".join(STAGES))
    if not named:
        raise HeimdallError("--stages names no stage", hint=", ".join(STAGES))
    return frozenset(named)


def _ask_keep(args) -> None:
    """The command's keep words (--keep, --logs, --journal), for this process (paths.keep; V149)."""
    paths.ask_keep([w for item in getattr(args, "keep", None) or [] for w in item.split(",")]
                   + ["logs"] * bool(getattr(args, "logs", False)) + ["journal"] * bool(getattr(args, "journal", False)))


def opened(args) -> Path | None:
    """A record named where a config goes (V158): `heimdall run|plot|status <P>/<run>/<NN_cfg>`, or a path into
    records/ or results/. Its snapshot is read: its config, its configuration, its --set overrides (yours after
    them), with configs/ at records/<run>/config/ for the command, so its imports and cards are the ones it
    ran with. Returns the record, or None for a config."""
    found = record.record_of(args.config)
    if found is None:
        return None
    snap = record.read_snapshot(found)
    rel = found.relative_to(records_root())
    if getattr(args, "configuration", None) and args.configuration != snap["configuration"]:
        raise HeimdallError(f"the record {rel} is configuration '{snap['configuration']}', not '{args.configuration}'",
                       hint=f"leave the configuration out: heimdall {args.command} {rel}")
    os.environ[paths.CONFIGS_VAR] = str(found / "config")
    args.config, args.configuration = snap["config"], snap["configuration"]
    args.set = [*snap.get("sets", []), *getattr(args, "set", [])]
    args.record = found
    print(f"record {rel}: {snap['config']} · {snap['configuration']} as it ran ({found / 'config'})", file=sys.stderr)
    return found


def cmd_run(args) -> int:
    """One run; or, under [run].sweep_runs, every swept configuration as a run of its own, one after
    another (V38). Each is exactly `heimdall run CONFIG <cfg>`, after a `run NN - <title> -` line. All are
    planned before the first starts, so a config error anywhere exits 2 with nothing run; one is
    planned again at its turn only if the TOML was edited meanwhile, so edits still count. A failed run leaves the next to
    start; a stop starts no more. On a terminal, and with --detach, the run is a worker of its own, which this
    process follows (or leaves) (V183)."""
    worker = getattr(args, "worker", None)
    if worker:
        _worker_signals()
    _ask_keep(args)
    run = configmod.load(args.config, sets=args.set)
    keys = run.runs(args.configuration)
    nothing_runs = getattr(args, "why", False) or args.plan or stages_of(args) == {"plot"} \
        or getattr(args, "show_config", False)
    if getattr(args, "detach", False) and not worker:
        if nothing_runs:
            raise HeimdallError("--detach starts a run in the background, and --plan, --why, --show-config and --only plot run "
                           "nothing", hint="leave --detach out")
        if os.environ.get("SLURM_JOB_ID") or runs.cluster_job():
            raise HeimdallError("--detach in a Slurm job: its processes end with the job's allocation",
                           hint="heimdall cluster submits a run as jobs; or run it here without --detach")
        return background(args, run, keys, attach=False)
    if not worker and not nothing_runs and live(args):
        return background(args, run, keys, attach=True)
    if getattr(args, "show_config", False):
        for line in show_config(run, keys):
            print(line)
        return 0
    stopper = execute.Stopper()
    if getattr(args, "why", False) or args.plan or stages_of(args) == {"plot"}:
        bus, recorder = None, None           # nothing runs: nothing to watch
    else:                                    # one stream for the whole process, served while it lives (V72)
        bus = Bus()
        worker = getattr(args, "worker", None)
        opened = runs.log_of(worker) if worker else None    # the log its parent opened, wherever it is
        log = str(opened) if opened else None
        work = find_work()
        configuration_serials = {key: run.configurations[key].serial for key in keys}
        entry = runs.begin(worker or runs.new_id(), {       # the registry (V182): nothing on a read-only root
            "config": str(run.path), "run": run.name, "configurations": keys, "argv": getattr(args, "argv", []),
            "configuration_serials": configuration_serials,
            "points_completed": 0, "points_total": None, "active_parallel_points": 0,
            "work": str(work) if work else None, "checkout": str(paths.heimdall_root()), "detached": bool(worker), "log": log})
        hub = Hub({"config": str(run.path), "run": run.name, "configurations": keys, "id": entry, "log": log,
                   "configuration_serials": configuration_serials,
                   "work": str(work) if work else None, "detached": bool(worker)})
        recorder = runs.Recorder(
            entry,
            configuration_serials,
            {key: run.configurations[key].label for key in keys},
        )
        bus.subscribe(hub)
        bus.subscribe(recorder)
    code, crashed = 2, None
    try:
        try:
            code = _runs(args, run, keys, stopper, bus, recorder=recorder)
        except HeimdallError as error:            # what main() prints, for a watcher too (V181)
            if bus is not None:
                bus.say(error.render())
            raise
        except KeyboardInterrupt:
            code = 6
            raise
        except Exception as error:           # the runner itself failed: said, and recorded
            crashed = f"the runner failed: {type(error).__name__}: {error}"
            if bus is not None:
                bus.say(crashed + (f" (its log: {log})" if log else ""))
            raise
        return code
    finally:
        if bus is not None:
            runs.finish(entry, code, crashed, records=recorder.records, verdicts=recorder.verdicts,  # before the
                        counts=recorder.counts(), **recorder.close())
            hub.close()                                                                              # stream ends
            notify(run, code)


def live(args, stdin=None, stdout=None, environ=None) -> bool:
    """Whether this `heimdall run` is a live one (V183): a terminal in and out, in its foreground (not `… &`),
    not --plain, not a worker, not in a Slurm job, and HEIMDALL_DETACH not "never". Then the run is a worker of its
    own, followed here, and `d` leaves it running."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    environ = os.environ if environ is None else environ
    if getattr(args, "plain", False) or getattr(args, "worker", None) or environ.get("HEIMDALL_DETACH") == "never":
        return False
    if environ.get("SLURM_JOB_ID") or environ.get(runs.CLUSTER_VAR):
        return False
    try:
        import termios  # noqa: F401
        return stdin.isatty() and stdout.isatty() and os.tcgetpgrp(stdin.fileno()) == os.getpgrp()
    except (ImportError, OSError, ValueError, AttributeError):
        return False


def _worker_signals() -> None:
    """A worker until its run's own handler is in (V183): SIGINT, SIGTERM and SIGHUP are a KeyboardInterrupt
    (exit 6), whatever it inherited."""
    def interrupt(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, signal.default_int_handler)
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)


def background(args, run, keys: list[str], *, attach: bool) -> int:
    """The run as a worker of its own (V183): this command again with --worker <id>, in a session of its own,
    its output in the registry's <id>.log. `attach`: followed here as heimdall watch does (`d` leaves it
    running; Ctrl-C stops it, once cleanly, twice hard); else (--detach) left once its run has started."""
    from .watch import follow, socket_of, started, tail
    run_id = runs.new_id()
    log = runs.log_file(run_id)
    proc = runs.spawn(getattr(args, "argv", []), run_id, log)
    what = f"{run.name} · {', '.join(keys)}"

    def left() -> None:
        print(f"left running: {what} (pid {proc.pid})\n  heimdall watch --pid {proc.pid}   follow it again\n"
              f"  heimdall stop --pid {proc.pid}    stop it\n  log {log}")

    def ended() -> int:
        code = proc.wait()
        if code < 0:                                         # killed: the worker could not say so itself
            runs.finish(run_id, 128 - code, f"killed by signal {-code}")
            code = 128 - code
        return code

    if not attach:
        if started(proc.pid, proc) is None:
            print("\n".join(tail(log)), file=sys.stderr)
            return ended()
        print(f"running in the background: {what} (pid {proc.pid}, {run_id})")
        left()
        return 0
    asked = []

    def on_key(key: str, shown) -> str | None:
        return "detached" if key in ("d", "D") else None

    def on_interrupt(shown) -> None:
        asked.append(True)
        os.kill(proc.pid, signal.SIGINT)
        shown.keys({1: "stopping: each point ends cleanly (Ctrl-C again: a hard stop)",
                    2: "stopping hard: the tools are killed (Ctrl-C again: at once)"}.get(len(asked), "killing it"))
        return None

    from .watch import Keys
    with Keys(sys.stdin) as keys_in:
        outcome = follow(socket_of(proc.pid), plain=args.plain, keys=keys_in.fd, on_key=on_key, on_interrupt=on_interrupt,
                         proc=proc, hint="d: leave it running · Ctrl-C: stop it")
    if outcome == "detached":
        left()
        return 0
    if outcome == "dropped":
        print(f"this terminal fell behind the run: heimdall watch --pid {proc.pid} follows it again", file=sys.stderr)
        left()
        return 0
    if outcome == "gone":
        print("\n".join(tail(log)), file=sys.stderr)
    return ended()


def cmd_stop(args) -> int:
    """`heimdall stop [CONFIG [CFG]] [--pid N]` (V183): a running job of yours asked to stop, as Ctrl-C does (its
    points end cleanly, partial outputs kept, a rerun resumes), then waited for (Ctrl-C leaves the waiting)."""
    from .events import namespace
    wanted = configmod.load(args.config) if args.config else None
    found = house.live_runs(str(wanted.path) if wanted else None, args.configuration, args.pid)
    if wanted is None and args.pid is None:                 # named by neither: this work dir's alone
        work = find_work()
        if work is None:
            raise HeimdallError("stop which job? outside a work dir, name it", hint="heimdall stop --pid N (heimdall runs lists them)")
        found = [(n, h) for n, h in found if h in house.runs_here(work)]
    if not found:
        cluster = next((e for e in runs.entries() if e.get("kind") == "cluster" and runs.state(e) == "submitted"
                        and (wanted is None or e.get("config") == str(wanted.path))), None)
        raise HeimdallError("no running job to stop" + (f" for {wanted.path}" if wanted else "")
                       + (f" with pid {args.pid}" if args.pid else ""),
                       hint=(f"its cluster jobs: heimdall cluster {cluster.get('config')} {cluster.get('configuration', '')} --cancel"
                             if cluster else "heimdall runs lists what runs"))
    if len(found) > 1:
        raise HeimdallError(f"{len(found)} jobs match: " + "; ".join(
            f"pid {h.get('pid')} {Path(h.get('config', '')).stem} · {', '.join(h.get('configurations', []))}" for _, h in found),
            hint="name one: heimdall stop --pid N")
    _, hello = found[0]
    if hello.get("pidns") and namespace("pid") and hello["pidns"] != namespace("pid"):
        raise HeimdallError(f"pid {hello.get('pid')} is another PID namespace's (a container's): stopping it from here could "
                       "signal another process", hint="stop it from where it runs")
    pid = hello["pid"]
    os.kill(pid, signal.SIGINT)
    what = f"{Path(hello.get('config', '')).stem} · {', '.join(hello.get('configurations', []))}"
    print(f"stopping pid {pid}: {what} (a first stop lets its points end cleanly, a second kills its tools at once; "
          f"heimdall watch --pid {pid} shows it)")
    if args.no_wait:
        return 0
    try:
        while not runs.ended(pid):
            time.sleep(0.25)
    except KeyboardInterrupt:
        print(f"no longer waiting; it is still stopping (heimdall runs)")
        return 0
    entry = runs.entry(hello["id"]) if hello.get("id") else None
    print(f"stopped: {runs.state(entry)}" if entry else "it has ended")
    return 0


def notify(run, code: int) -> bool:
    """[run] notify = "desktop" (V76): a notify-send when the command ends, for runs of hours. Never
    fails the run: no notify-send, or no desktop, and it says nothing."""
    if run.raw.get("run", {}).get("notify", "none") != "desktop" or not shutil.which("notify-send"):
        return False
    verdict = {0: "done", 1: "a point failed", 2: "a config error", 6: "stopped"}.get(code, f"exit {code}")
    try:
        subprocess.Popen(["notify-send", "--app-name=heimdall", f"heimdall run {run.name}", f"{run.path.name}: {verdict}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    return True


def _points_planned(args, planned: Planned) -> int:
    """The configuration points a run will end (run, or skip as complete): none when its stages leave them out."""
    return len(planned.plans) if "points" in stages_of(args) else 0


def _runs(args, run, keys: list[str], stopper: execute.Stopper, bus, recorder: runs.Recorder | None = None) -> int:
    """The command's runs, each planned before the first starts; `recorder` is told how many points they plan
    (the registry's progress, `heimdall runs`)."""
    if len(keys) == 1:
        planned = build_plans(args, keys[0])
        if recorder is not None:
            recorder.plan({"": _points_planned(args, planned)})
        return run_one(args, keys[0], stopper, bus=bus, planned=planned)
    if args.points:
        raise HeimdallError("--points picks points of one configuration, and this sweep runs several",
                       where=f"{run.path}: [run].sweep_runs", hint=f"name it: heimdall run {args.config} <configuration> --points …")
    skipped, ahead = {}, {}
    stamp = run.path.stat().st_mtime_ns
    for key in keys:
        try:
            ahead[key] = planned = build_plans(args, key)
        except HeimdallError as error:
            error.message = f"configuration '{key}': {error.message}"
            raise
        if args.only in ("pre", "post") and getattr(planned, args.only) is None:
            skipped[key] = f"   no {args.only} tools: skipped"
    if len(skipped) == len(keys):
        raise HeimdallError(f"no configuration of this sweep has {args.only} tools", where=f"{run.path}: [run].sweep_runs")
    if recorder is not None:
        recorder.plan({key: 0 if key in skipped else _points_planned(args, ahead[key]) for key in keys})
    if bus is not None and args.only is None and getattr(args, "stages", None) is None:
        return _pipelined(args, run, keys, stopper, bus, ahead, stamp)
    failed = False
    for number, key in enumerate(keys, 1):
        if stopper.requested:
            return 6
        following = next((journal_path(run, run.configurations[k]) for k in keys[number:] if k not in skipped), None) \
            if paths.keeping("journal") else None
        if key in skipped:
            print(("\n" if number > 1 else "") + header(number, run.configurations[key]))
            print(skipped[key])
            if bus is not None:                  # a watcher hears it too (V181)
                bus.say(f"{header(number, run.configurations[key])}\n{skipped[key]}")
            continue
        voice = RunBus(bus, key, alone=True) if bus is not None else None      # each run's events say which run (V75)
        try:                                 # planned again only if the TOML was edited meanwhile (V38, V54)
            unchanged = run.path.stat().st_mtime_ns == stamp
            code = run_one(args, key, stopper, number=number, following=following,
                           planned=ahead[key] if unchanged else None, bus=voice)
        except HeimdallError as error:            # the TOML was edited since the check: this run fails alone
            print(("\n" if number > 1 else "") + header(number, run.configurations[key]))
            print(error.render(), file=sys.stderr)
            if voice is not None:
                voice.say(f"{header(number, run.configurations[key])}\n{error.render()}")
            not_run(journal_path(run, run.configurations[key]) if paths.keeping("journal") else None,
                    header(number, run.configurations[key]), error.message, following, voice)
            code = 2
        if code == 6:
            return 6
        failed = failed or code != 0
    return 1 if failed else 0


def _pipelined(args, run, keys: list[str], stopper: execute.Stopper, bus: Bus, ahead: dict, stamp: int) -> int:
    """A sweep of runs, pipelined (V75, the user's B8 decision): each run starts once the one before has
    started all its points, and its points take the free cores of a budget the runs share (never more
    than the largest run alone would use), so a run's last points and the next run's first overlap. Each
    run's own order (pre, points, combined, post, plots) is kept. One view for the sweep; each run's
    events carry its key. A stop starts no more runs; a failed run leaves the next to start."""
    each = {key: max((execute.cores(p) for p in ahead[key].plans), default=1) for key in keys}
    budget = execute.Budget(max(os.cpu_count() or 1,
                                *(max(1, ahead[key].configuration.parallelism) * each[key] for key in keys)))
    shown = view(args.plain, every=paths.log_settings()["worker_every"] if getattr(args, "worker", None) else 5.0)
    bus.subscribe(shown)
    catch_signals(stopper)
    codes: dict[str, int] = {}
    errors: list[BaseException] = []
    threads: list[threading.Thread] = []
    gate: threading.Event | None = None
    try:
        for number, key in enumerate(keys, 1):
            while gate is not None and not gate.wait(0.25) and not stopper.requested:
                pass
            if stopper.requested:
                break
            following = next((journal_path(run, run.configurations[k]) for k in keys[number:]), None) \
                if paths.keeping("journal") else None
            gate = threading.Event()

            def job(key=key, number=number, following=following, gate=gate) -> None:
                voice = RunBus(bus, key)
                try:                         # planned again only if the TOML was edited meanwhile (V38, V54)
                    unchanged = run.path.stat().st_mtime_ns == stamp
                    codes[key] = run_one(args, key, stopper, number=number, following=following,
                                         planned=ahead[key] if unchanged else None, bus=voice, shown=shown,
                                         budget=budget, gate=gate)
                except HeimdallError as error:    # the TOML was edited since the check: this run fails alone
                    voice.say(header(number, run.configurations[key]))
                    voice.say(error.render())
                    not_run(journal_path(run, run.configurations[key]) if paths.keeping("journal") else None,
                            header(number, run.configurations[key]), error.message, following, voice)
                    codes[key] = 2
                except BaseException as error:           # the runner's own error: raised once all have ended
                    errors.append(error)
                    codes[key] = 1
                finally:
                    gate.set()

            thread = threading.Thread(target=job, name=f"heimdall-run-{key}")
            thread.start()
            threads.append(thread)
        while any(t.is_alive() for t in threads):        # the main thread takes the signals
            time.sleep(0.25)
    finally:
        for thread in threads:
            thread.join()
        bus.unsubscribe(shown)
        shown.end()
    if errors:
        raise errors[0]
    if stopper.requested or 6 in codes.values():
        return 6
    return 1 if any(codes.values()) else 0


def show_config(run, keys: list[str]) -> list[str]:
    """--show-config (V56): every resolved value of each configuration with the layer it came from (its
    own table, one it extends, [run], the schema's default), each fixed quantity with where it was
    fixed, the interfaces (inferred from the chain in a v3 file), then every quantity and tool table
    with the file it came from. A v3 file is shown in v3's names."""
    from . import schema
    v3 = run.form == 3
    names = {"event_count": "events", "tools": "chain", "sweeps": "vary", "label": "folder", "prelim": "interfaces"} if v3 else {}
    order = [k for k in schema.keys("configuration") if k not in ("extends", "static", "manual_seed")]
    lines = []

    def place(origin: str) -> str:
        return origin.replace("[run.cfgs.", "[cfgs.") if v3 else origin

    for key in keys:
        configuration = run.configurations[key]
        lines.append(f"run {run.name} ({run.path}) · configuration {key}")
        seed = configuration.manual_seed if configuration.seed_type == "manual" else configuration.seed_type
        fields = {"serial": configuration.serial, "name": configuration.run_folder, "label": configuration.label,
                  "title": configuration.title, "description": configuration.description,
                  "event_count": configuration.event_count, "threads": configuration.threads,
                  "parallelism": "auto" if configuration.parallelism_auto else configuration.parallelism,
                  "swept": configuration.swept, "seed_type": seed,
                  "sweeps": configuration.sweeps, "plot_points": configuration.plot_points,
                  "combine": configuration.combine, "tools": configuration.tools, "pre": configuration.pre,
                  "post": configuration.post, "generate_cards": configuration.generate_cards,
                  "prelim": configuration.prelim, "cluster": configuration.cluster}
        width = max(len(names.get(n, "seed" if n == "seed_type" and v3 else n)) for n in order) + 2
        own = run.raw.get("run", {}).get("cfgs", {}).get(key, {})
        for name in order:
            value = fields.get(name)
            if value in (None, [], {}, "") and name not in configuration.origins:
                continue
            shown = names.get(name, "seed" if name == "seed_type" and v3 else name)
            if name == "prelim" and v3:
                origin = "inferred from the chain"
            else:
                origin = place(configuration.origins.get(name, f"[run.cfgs.{key}]" if name in own else "default"))
            lines.append(f"  {shown:{width}s} = {json.dumps(value, default=str):40s} {origin}")
        mine = own.get("static", {}) if isinstance(own.get("static"), dict) else {}
        for quantity, tag in configuration.static.items():
            if quantity in mine:
                origin = f"[cfgs.{key}].fixed" if v3 else f"[run.cfgs.{key}].static"
            elif f"quantities.{quantity}" in run.included and quantity not in run.raw.get("static", {}):
                origin = f"included from {run.included[f'quantities.{quantity}']}"
            else:
                origin = f"[quantities.{quantity}].fixed" if v3 else "[static]"
            label = f"fixed {quantity}" if v3 else f"static.{quantity}"
            lines.append(f"  {label:{width}s} = {json.dumps(tag, default=str):40s} {origin}")
    for quantity, q in run.quantities.items():
        source = f"included from {run.included[f'quantities.{quantity}']}" if f"quantities.{quantity}" in run.included else "this file"
        lines.append(f"  quantity {quantity}: {len(q.values)} point(s){' (a compound field)' if q.silent else ''}   {source}")
    for tag, tool in run.tools.items():
        source = f"included from {run.included[f'tools.{tag}']}" if f"tools.{tag}" in run.included else "this file"
        lines.append(f"  tool {tag} ({tool.tool})   {source}")
    return lines




def not_run(path: Path | None, title: str, message: str, following: Path | None, bus=None) -> None:
    """A run that could not be planned at its turn still says so: to the watchers, and in its journal
    (--journal), so heimdall watch --file moves on."""
    journal = Journal(path) if path is not None else None
    for event in ({"k": "run", "state": "started", "points": 0, "title": title, "header": title},
                  {"k": "run", "state": "finished", "verdict": f"not run: {message}",
                   **({"next": str(following)} if following else {})}):
        if bus is not None:
            bus.emit("", "", event)
        if journal is not None:
            journal.event({"v": 1, "point": "", "tool": "", **event})
    if journal is not None:
        journal.close()


def dropped_points(every: list) -> list[str]:
    """The complete points a configuration's last points.json listed that its plan no longer has (V158)."""
    path = record.manifest_file(every)
    try:
        before = json.loads(path.read_text(encoding="utf-8")).get("points", []) if path.is_file() else []
    except (OSError, ValueError):
        return []
    planned = {p.point.name for p in every}
    return [e["name"] for e in before if e.get("complete") and e.get("name") not in planned]


def run_one(args, key: str, stopper: execute.Stopper, *, number: int = 0, following: Path | None = None,
            planned: Planned | None = None, bus: Bus | None = None, shown=None, budget=None,
            gate: threading.Event | None = None) -> int:
    """One run: the pre stage, every point not complete, the combined groups, the post stage and the
    plots, said on `bus` (V72). In a sweep of runs, `number` is its place (a `run NN - <title> -` line
    first), and `following` is the next run's journal (--journal), named in this one's `run finished`
    event so that heimdall watch --file follows on."""
    planned = planned or build_plans(args, key)
    run, configuration, every, plans = planned.run, planned.configuration, planned.every, planned.plans
    post_plan, pre_plan, combined = planned.post, planned.pre, planned.combined
    stages, again = stages_of(args), getattr(args, "only", None)       # again: the stage --only reruns
    title_line = header(number, configuration) if number else ""
    if getattr(args, "why", False):
        if title_line:
            print(("\n" if number > 1 else "") + title_line)
        print_why(run, configuration, plans, post_plan, pre_plan, combined)
        return 0
    if args.plan or stages == {"plot"}:
        if title_line:
            print(("\n" if number > 1 else "") + title_line)
        if args.plan:
            if getattr(args, "card", None):
                if not plans:
                    raise HeimdallError("--card: no point to show", hint="--points picks one")
                for line in tools.card_view(plans[0], args.card):
                    print(line)
                return 0
            print_plan(run, configuration, plans, post_plan, pre_plan, combined)
            return 0
        return 1 if draw_run(run, configuration, combined or every, print) else 0
    if args.only == "post" and post_plan is None:
        raise HeimdallError(f"configuration '{configuration.key}' has no post tools", where=f"{run.path}: [run.cfgs.{configuration.key}].post")
    if args.only == "pre" and pre_plan is None:
        raise HeimdallError(f"configuration '{configuration.key}' has no pre tools", where=f"{run.path}: [run.cfgs.{configuration.key}].pre")
    if "points" in stages and "pre" not in stages and pre_plan is not None and not record.is_complete(pre_plan):
        raise HeimdallError(f"configuration '{configuration.key}': the pre stage is not complete, and the points need it",
                       hint="run --stages pre first (heimdall cluster's pre job does), or leave --stages out")
    refuse_overwrites(planned, args, stages)
    if stopper.requested:                    # Ctrl-C while this run was being planned
        return 6

    bus = bus if bus is not None else Bus()
    own_view = shown is None                 # a pipelined sweep's runs share the sweep's view (V75)
    if own_view:
        shown = view(args.plain, every=paths.log_settings()["worker_every"] if getattr(args, "worker", None) else 5.0)
        # a worker's log: a progress line each [run] log worker_every seconds (V202), 10 minutes by default
        bus.subscribe(shown)
    if threading.current_thread() is threading.main_thread():
        catch_signals(stopper)
    logs = paths.keeping("logs")

    journal = Journal(plans[0].folders.journal, run=getattr(bus, "run", None)) \
        if plans and paths.keeping("journal") else None
    if journal:
        bus.subscribe(journal)
    run_log = RunLog(tools.run_folders(run, configuration).run_log, run=getattr(bus, "run", None))   # always (V202)
    bus.subscribe(run_log)
    title = run_title(run, configuration, plans)
    tally = runs.Tally()                     # the verdict's counts and failures (V200)
    bus.subscribe(tally)
    known = record.constants(every, run, configuration) if every else {}       # what every point shares (V200)
    if number > 1:
        bus.say("")
    bus.emit("", "", {"k": "run", "state": "started", "points": len(plans), "title": title,
                      "record": str(records_root() / tools.run_dir(run, configuration)),       # the registry's (V182)
                      **({"header": title_line} if title_line else {}), **({"constants": known} if known else {})})
    if crowded(configuration, plans):
        bus.say(f"   note: {crowded(configuration, plans)}")
    for note in notes_of(plans):
        bus.say(f"   note: {note}")
    for warning in tools.meta_notes(run):                       # V97
        bus.say(f"   warning: {warning}")
    def manifest() -> None:                  # a points-only run (a cluster job) leaves it to the finish job
        if plans and stages != {"points"}:
            record.write_atomic(record.manifest_file(every), json.dumps(
                record.points_manifest(every, run, configuration, known), indent=1, default=str) + "\n")
    dropped = dropped_points(every) if every and stages != {"points"} else []     # read before it is rewritten
    manifest()
    if every and stages != {"points"}:              # V158: the config it ran with, beside points.json
        if record.write_snapshot(run, configuration, every) is not None and dropped:
            bus.say(f"   note: {len(dropped)} point(s) recorded in {tools.run_dir(run, configuration)} are not in the config now "
                    f"({', '.join(dropped[:4])}{', …' if len(dropped) > 4 else ''}): its snapshot and points.json describe "
                    "the config as it is; give the configuration a serial of its own to keep a run whole")
    failed = done = 0
    verdict = "stopped"
    try:
        if "pre" in stages:
            if not post.run_pre(pre_plan, run, configuration, bus=bus, stopper=stopper, logs=logs,
                                rerun=args.rerun or again == "pre"):
                verdict = "pre failed: no point ran"
                return 6 if stopper.requested else 1
            if stages == {"pre"}:
                verdict = "pre done"
                return 0
        if "points" in stages:
            done, failed, stopped = execute.run_points(plans, run, configuration, bus=bus, stopper=stopper,
                                                       rerun=args.rerun, logs=logs, budget=budget,
                                                       started_all=gate.set if gate is not None else None,
                                                       wait_held=getattr(args, "wait", False))
            if stopped:
                return 6
        warned = tally.warned(getattr(bus, "run", "") or "")
        verdict = (f"{done} done{f' ({warned} with warnings)' if warned else ''}, {failed} failed, "
                   f"{len(plans) - done - failed} skipped") if "points" in stages else ""
        manifest()                           # post tools read it: it must say which points are complete
        if combined and "combine" in stages:
            bad = post.run_combined(combined, every, run, configuration, bus=bus, stopper=stopper, logs=logs,
                                    rerun=args.rerun, say=bus.say)
            if stopper.requested:
                return 6
            if bad:
                failed += bad
                verdict = f"{verdict}, {bad} combined group(s) failed"
        if "post" in stages and not post.run(post_plan, every, run, configuration, bus=bus, stopper=stopper, logs=logs,
                                             rerun=args.rerun or again == "post", say=bus.say):
            if stopper.requested:
                return 6
            failed += 1
            verdict = ", ".join(v for v in (verdict, "post failed") if v)
        elif post_plan is not None and again == "post":
            verdict = "post done"
        if "plot" in stages:
            drawing = not (getattr(args, "no_plot", False) or configuration.draw is False)     # V167, V168: the gates
            measuring = False if getattr(args, "no_stats", False) else configuration.measure
            if not drawing:
                bus.say(f"plot: not drawn ({'--no-plot' if getattr(args, 'no_plot', False) else '[run].plot = false'}): "
                        f"heimdall plot {tools.run_dir(run, configuration)} draws it")
            failed += draw_run(run, configuration, combined or every, bus.say, draw=drawing, stats=measuring) > 0
            across, written = plotdoc.write_across(run)                    # V169: the runs together
            if across is not None:
                bus.say(f"plot: {'wrote ' + str(across) + ': ' if written else ''}heimdall plot "
                        f"{record.config_name(run)} --across draws this run with the others of {run.name}")
        verdict = verdict or ", ".join(s for s in STAGES if s in stages) + " done"         # a run without its points
        bus.say(verdict)                     # before end(): the view's thread prints it (V32)
        if failures := tally.failures(getattr(bus, "run", "") or ""):          # V200: which failed, and why
            bus.say("failed:\n" + "\n".join(failures))
    finally:
        onward = {"next": str(following)} if following and not stopper.requested else {}
        bus.emit("", "", {"k": "run", "state": "finished", "verdict": verdict, **onward})
        if own_view:
            bus.unsubscribe(shown)
            shown.end()
        manifest()
        bus.unsubscribe(tally)
        bus.unsubscribe(run_log)
        run_log.close()
        if journal:
            bus.unsubscribe(journal)
            journal.close()
    return 1 if failed else 0


def cmd_cluster(args) -> int:
    """`heimdall cluster` (V114): each configuration (every swept one under [run].sweep_runs) planned as heimdall run
    plans it, then submitted, or its latest submission's state shown, or cancelled (runner/cluster.py)."""
    run = configmod.load(args.config, sets=args.set)
    keys = run.runs(args.configuration)
    if len(keys) > 1 and args.points:
        raise HeimdallError("--points picks points of one configuration, and this sweep runs several",
                       where=f"{run.path}: [run].sweep_runs", hint=f"name it: heimdall cluster {args.config} <configuration> --points …")
    planned = {key: build_plans(argparse.Namespace(**{**vars(args), "only": None, "stages": None}), key) for key in keys}
    if not (args.status or args.cancel):
        for key in keys:
            refuse_overwrites(planned[key], args)
    code = 0
    for number, key in enumerate(keys, 1):
        if number > 1:
            print()
        if args.status:
            code = max(code, clustermod.status(planned[key]))
        elif args.cancel:
            code = max(code, clustermod.cancel(planned[key]))
        else:
            for note in notes_of(planned[key].plans):
                print(f"note: {note}")
            for warning in tools.meta_notes(run):
                print(f"warning: {warning}")
            code = max(code, clustermod.submit(planned[key], args))
    return code


def cmd_overlay(args) -> int:
    """`heimdall overlay FILE…` (V74, was `heimdall plot FILE…`): any YODA/ROOT files overlaid through Paint."""
    bad = [f for f in args.files if not plot._is_plot_file(f)]
    if bad:
        raise HeimdallError(f"{bad[0]} is not a YODA or ROOT file", hint="heimdall overlay takes files ending .yoda, .yoda.gz "
                                                                   "or .root; a configuration's pages: heimdall plot CONFIG")
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    wrong = [f for f in formats if f not in plot.FORMATS]
    if wrong:
        raise HeimdallError(f"format '{wrong[0]}' is not one of {', '.join(plot.FORMATS)}")
    labels = [x.strip() for x in args.labels.split(",")] if args.labels else None
    return 1 if plot.files(args.files, Path(args.output) if args.output else None, labels=labels,
                           objects=args.objects, formats=formats, ratio=args.ratio, style=args.style) else 0


def cmd_deck(args) -> int:
    """`heimdall deck …`, retired (V212, as V74 retired `heimdall plot FILE`): it stops, naming heimdall report."""
    raise HeimdallError("heimdall deck is now heimdall report: an A4 report of runs' pages and numbers, its figures and "
                   "LaTeX in its folder to lift into a talk",
                   hint="heimdall report <P>/<run>/<cfg> (docs/03_Plots.md §11); a deck's decks/<deck>/ is yours, left as it is")


def cmd_report(args) -> int:
    """`heimdall report [RECIPE.toml] [SOURCE…]` (I-108, V207, V209): a recipe and its sources, or sources alone (one
    folder's report.toml, else the default), resolved into sections of figures and statistics and built where
    results/ has them; --list says them, --init writes a recipe once."""
    from . import report as reportmod
    from .paths import configs_root
    if args.init:
        name = args.names[0] if len(args.names) == 1 else ""
        if not name.endswith(".toml") or name.count("/") != 1 or name.startswith(("./", "/")):
            raise HeimdallError("--init writes a recipe under configs/: name it, <P>/<name>.toml",
                           hint=f"heimdall report eic/weekly.toml --init {args.init}")
        target = configs_root() / name
        if target.exists():
            raise HeimdallError(f"{target} is there already", hint="--init writes a recipe once: edit it, or name another")
        (source, *_) = reportmod.sources([args.init], "--init")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(reportmod.starter(name, source), encoding="utf-8")
        print(f"report: wrote {target}")
        return 0
    first, rest = (args.names[0], args.names[1:]) if args.names else (None, [])
    plan = reportmod.planned(first, rest, Path(args.output).resolve() if args.output else None)
    if args.list:
        for line in reportmod.listing(plan):
            print(line)
        return 0
    reportmod.build(plan)
    return 0


def cmd_plot(args) -> int:
    """`heimdall plot CONFIG [CONFIGURATION] | RECORD | <folder>` (V165): the pages of a run's plot document,
    results/<run>/plot.toml, from records alone (no tool planned, no stack beyond Paint). CONFIG names its
    configurations' latest records (the newest folder); RECORD (`<P>/<name>/<cfg>`) or a folder with a
    plot.toml names one. A record without a document gets one written first, from the config (or its
    snapshot). `--plot FILE`: another file's [plot] for this drawing; `--points`: one set; `--plan`: the sets'
    cells, nothing drawn."""
    if plot._is_plot_file(args.config):                     # break and migrate (V74)
        raise HeimdallError("heimdall plot draws a configuration's pages; files are overlaid by heimdall overlay",
                       hint=f"heimdall overlay {args.config} …")
    args.points = None
    if getattr(args, "across", False) and getattr(args, "style_sync", None):
        return style_sync_across(args)
    if getattr(args, "style_sync", None):
        return style_sync(args)
    styled = configmod.plot_of(args.plot_file) if getattr(args, "plot_file", None) else None
    failed = False
    targets = [across_of(args)] if getattr(args, "across", False) else documents_of(args)
    for number, target in enumerate(targets, 1):
        doc, configuration, members = plotdoc.load(target)
        for shadowed, by in list(doc.source.get("shadowed", {}).items())[:1]:   # V169: a point two runs have
            print(f"plot: {len(doc.source['shadowed'])} point(s) two runs have are drawn from the later "
                  f"({shadowed} as {by}, …): [from].prefer = \"all\" keeps both")
        if len(targets) > 1:
            print(("\n" if number > 1 else "") + f"run {number:02d} - {configuration.title or configuration.label} -")
        if styled is not None:
            doc.plot = dict(styled)
        if getattr(args, "page_points", None) and doc.plot:          # V159: one set, from the command line
            picked = [int(x) if x.strip().isdigit() else x.strip() for x in args.page_points.split(",") if x.strip()]
            doc.plot = {**{k: v for k, v in doc.plot.items() if k != "draw"}, "sets": {"points": {"points": picked}}}
        if getattr(args, "draw_sets", None) and doc.plot:            # V167: these sets of the document's
            doc.plot = {**doc.plot, "draw": [s.strip() for s in args.draw_sets.split(",") if s.strip()]}
        if not doc.plot:
            raise HeimdallError(f"{target} has no [plot] table", hint="its config had none when it ran: add [plot] there and "
                                                                 "take it with --style-sync, or edit [plot] here")
        plot.validate(doc)
        plot.check_figures(doc, configuration)
        if getattr(args, "plan", False):                    # V163: the sets' cells, nothing drawn
            print("\n".join(plot.plan_lines(doc, configuration, members)))
            continue
        plot.check_texts(doc, members)
        failed = plot.draw(doc, configuration, members, print) or failed
    return 1 if failed else 0


def style_sync(args) -> int:
    """`heimdall plot <P>/<name>/<cfg> | <P>/<name> --style-sync CONFIG [--plan] [--replot]` (V166): each named plot
    document's [plot] and [stats] replaced by the config's (its configuration's, resolved as a run writes them),
    what the run knows left as it is. A document whose configuration the config lacks, or whose points the
    config's [plot] cannot page (a set naming a quantity or tag it has not), is left, and said; the others are
    synced. --plan says what would change and writes nothing; --replot then draws the synced ones."""
    name = args.config.strip("/")
    found = plotdoc.find(name)
    if found is not None:
        targets = [found]
    elif name.count("/") == 1 and (results_root() / name).is_dir():
        targets = sorted(p for p in (results_root() / name).glob(f"*/{plotdoc.FILE}"))
    else:
        raise HeimdallError(f"'{args.config}' names no plot document", hint="a run, <P>/<name>/<cfg>, or a run TOML's runs, "
                                                                      "<P>/<name> (results/<P>/<name>/*/plot.toml)")
    if not targets:
        raise HeimdallError(f"results/{name}/ holds no plot document", hint="heimdall migrate --plot-docs writes them")
    run = configmod.load(args.style_sync, sets=args.set)
    plot.validate(run)
    synced, left = [], 0
    for target in targets:
        doc, configuration, members = plotdoc.load(target)
        rel = target.parent.relative_to(results_root()) if target.parent.is_relative_to(results_root()) else target.parent
        if configuration.key not in run.configurations:
            print(f"left    {rel}: {args.style_sync} has no configuration '{configuration.key}'")
            left += 1
            continue
        live, picks = configmod.for_configuration(run, configuration.key)   # V179: its own data
        new_plot, new_stats = plotdoc.chosen_of(live, configuration, members, picks=picks)
        changed = sorted(k for k in {*doc.plot, *new_plot} if doc.plot.get(k) != new_plot.get(k))
        changed += ["[stats]"] if doc.stats != new_stats else []
        if not changed:
            print(f"same    {rel}")
            continue
        try:
            from dataclasses import replace as with_
            plot.check_figures(with_(doc, plot=new_plot, stats=new_stats), configuration)
        except HeimdallError as error:
            print(f"left    {rel}: the config's [plot] cannot draw its points: {error.message}")
            left += 1
            continue
        print(f"{'would sync' if args.plan else 'synced '} {rel}: " + ", ".join(k if k.startswith("[") else f"[plot].{k}" for k in changed))
        if not args.plan:
            plotdoc.write_chosen(target, new_plot, new_stats)
            synced.append(target)
    print(f"{len(synced) if not args.plan else 'nothing'} synced" + (f", {left} left" if left else "")
          + ("" if args.plan else "" if args.replot or not synced else ": heimdall plot … draws them (or --replot)"))
    failed = False
    for target in synced if args.replot else ():
        doc, configuration, members = plotdoc.load(target)
        if doc.plot:
            failed = plot.draw(doc, configuration, members, print) or failed
    return 1 if failed or left else 0


def cmd_stats(args) -> int:
    """`heimdall stats RUN | <folder> | <P>/<name> | CONFIG [CFG]` (V168): each run's statistics alone, from its plot
    document: the pages [plot] defines, as [stats] measures them, read by Paint (no image drawn), into
    statistics/<set>/. `--sets`: these sets only."""
    name = args.config.strip("/")
    if getattr(args, "across", False):
        targets = [across_of(args)]
    elif plotdoc.find(name) is None and name.count("/") == 1 and (results_root() / name).is_dir() \
            and not (paths.configs_root() / f"{name}.toml").is_file():
        targets = sorted((results_root() / name).glob(f"*/{plotdoc.FILE}"))      # <P>/<name>: each of its runs
    else:
        targets = documents_of(args)
    picked = [s.strip() for s in args.draw_sets.split(",") if s.strip()] if getattr(args, "draw_sets", None) else None
    failed = 0
    for target in targets:
        doc, configuration, members = plotdoc.load(target)
        if len(targets) > 1:
            print(f"{target.parent.relative_to(results_root()) if target.parent.is_relative_to(results_root()) else target.parent}:")
        if not doc.plot:
            print(f"stats: {target} has no [plot]: no pages to measure")
            continue
        plot.validate(doc)
        plot.check_figures(plot.measured(doc, picked), configuration)
        failed += plot.measure(doc, configuration, members, print, picked=picked)
    return 1 if failed else 0


def across_of(args) -> Path:
    """The runs of a run TOML together (V169): results/<P>/<name>/plot.toml, its argument a run TOML (written from
    its [plot.across] when there is none) or that folder."""
    found = plotdoc.find(args.config)
    if found is not None:
        return found
    run = configmod.load(args.config, sets=args.set)
    target, written = plotdoc.write_across(run)
    if target is None:
        raise HeimdallError(f"{run.path} has no [plot.across] sets: nothing to draw its runs together",
                       hint="[plot.across.<set>] pages = { … }, curves = { \"@events\" = \"all\", … }: 03 §3.3")
    if written:
        print(f"plot: wrote {target}, from {args.config}'s [plot.across]")
    return target


def style_sync_across(args) -> int:
    """`heimdall plot CONFIG --across --style-sync CONFIG`: the Name level's [plot] and [stats] become the config's
    (its [plot] with its [plot.across] sets); --plan says what would change; --replot draws."""
    run = configmod.load(args.style_sync, sets=args.set)
    plot.validate(run)
    target = plotdoc.across_path(run.project, run.name)
    if not target.is_file():                                # none yet: written, as a run writes it
        if plotdoc.write_across(run)[0] is None:
            raise HeimdallError(f"{run.path} has no [plot.across] sets", hint="[plot.across.<set>]: 03 §3.3")
        print(f"plot: wrote {target}")
        return 1 if args.replot and plot.draw(*plotdoc.load(target), print) else 0
    new_plot, new_stats = plotdoc.across_chosen(run)
    doc = plotdoc.load(target)[0]
    changed = sorted(k for k in {*doc.plot, *new_plot} if doc.plot.get(k) != new_plot.get(k))
    print(f"{'would sync' if args.plan else 'synced '} {target}: " + (", ".join(f"[plot].{k}" for k in changed) or "the same"))
    if args.plan or not changed:
        return 0
    plotdoc.write_chosen(target, new_plot, new_stats)
    return 1 if args.replot and plot.draw(*plotdoc.load(target), print) else 0


def documents_of(args) -> list[Path]:
    """The plot documents `heimdall plot` draws (V165): the one its argument names (a record, a folder), or those
    of a config's configurations' latest records; a record without one gets it written first (from its
    snapshot, or the config and its points.json), and says so. The config's [plot] differing from a document's
    is said, with the sync."""
    found = plotdoc.find(args.config)
    if found is not None:
        return [found]
    if getattr(args, "record", None) is not None:          # a record from before plot documents: its own, written
        run, configuration = _record_config(args.record)
        target, _ = write_documents(run, configuration, plot.recorded(run, configuration))
        print(f"plot: wrote {target}, from its snapshot and its points.json (heimdall migrate --plot-docs writes "
              "every record's)")
        return [target]
    run = configmod.load(args.config, sets=args.set)
    plot.validate(run)
    out, read = [], run
    for key in read.runs(args.configuration):
        run, configuration = configmod.for_configuration(read, key)        # V179: its own vars and data
        if configuration.serial_auto:                       # the newest folder: what a run last made
            taken = tools.serials_taken(run, configuration)
            if taken:
                configuration.serial = max(taken)
        folders = tools.run_folders(run, configuration)
        target = plotdoc.path_of(folders.results)
        if not target.is_file():
            if not folders.manifest.is_file():
                raise HeimdallError(f"configuration '{key}' has no record yet: nothing to draw", where=str(folders.record),
                               hint=f"heimdall run {args.config} {key}")
            target, notes = write_documents(run, configuration, plot.recorded(run, configuration))
            print(f"plot: wrote {target}, from the config and its points.json (heimdall migrate --plot-docs writes "
                  "every record's)")
        else:
            kept, axes, members = plotdoc.load(target)
            if (kept.plot, kept.stats) != plotdoc.chosen_of(run, axes, members, picks=configuration):
                rel = folders.results.relative_to(results_root())
                print(f"note: the config's [plot] differs from {rel}/{plotdoc.FILE}'s, which is drawn: heimdall plot {rel} "
                      f"--style-sync {args.config} takes the config's", file=sys.stderr)
        out.append(target)
    return out


def cmd_check(args) -> int:
    """`heimdall check [CONFIG…]` (V57): each config loaded, its [plot] validated and every configuration's
    points planned (the C-rules, paths, consumers, connections, cards), nothing run or written. 0 when
    all are well, 2 when any is not: for a pre-commit hook, or before a long sweep."""
    from .paths import configs_root
    names = list(args.configs)
    if not names:
        root = configs_root()
        for path in sorted(root.glob("*/*.toml")):
            try:
                has_run = "run" in tomllib.loads(path.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError):
                has_run = True                                   # a broken file is checked, and fails
            if has_run:
                names.append(str(path.relative_to(root).with_suffix("")))
    importers = house.importers()                              # a shared file: checked through them
    failed = 0
    for name in names:
        try:
            sets = list(getattr(args, "set", []))
            run = configmod.load(name, sets=sets)
            heimdall_flags(configmod.heimdall_table(name, sets=sets), f"{run.path}: [heimdall]")   # V188
            points = 0
            for key in run.configurations:
                planned = build_plans(argparse.Namespace(config=name, set=sets, points=None, rerun=False, only=None), key)
                points += len(planned.every)
            print(f"ok    {name}: {len(run.configurations)} configuration(s), {points} point(s)")
            for warning in [*tools.meta_notes(run), *house.unused_tools(run)]:   # said, never failed
                print(f"      warning: {warning}")
        except HeimdallError as error:
            if importers.get(name) and not args.configs and not _has_configurations(name):
                print(f"ok    {name}: shared, imported by {', '.join(importers[name])} (checked through them)")
                continue
            failed += 1
            print(f"FAIL  {name}")
            print("      " + error.render().replace("\n", "\n      "))
    from . import report as reportmod
    for name in (reportmod.recipes() if not args.configs else ()) or ():   # V207: a report's recipe, its keys
        try:
            recipe = reportmod.load_recipe(configs_root() / name)
            print(f"ok    {name}: a report, {len(recipe.get('section', []))} section(s)")
        except HeimdallError as error:
            failed += 1
            print(f"FAIL  {name}")
            print("      " + error.render().replace("\n", "\n      "))
    return 2 if failed else 0


def _has_configurations(name: str) -> bool:
    """A run TOML with configurations of its own is a study, checked on its own even when imported; one
    without (a shared file of tools and quantities) is checked through the files that import it."""
    try:
        data = tomllib.loads(configmod.config_file(name).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, HeimdallError):
        return True
    return bool(data.get("cfgs") or data.get("run", {}).get("cfgs"))


def cmd_runs(args) -> int:
    """`heimdall runs [--5|--10|--20|--50|--week|--month]`: active jobs or recent runs."""
    from . import workdirs
    try:
        titles = {entry["path"]: title for title, entry in workdirs.load().items()}
    except HeimdallError:
        titles = {}
    for line in house.runs_listing(runs.entries(), house.live_runs(), titles, limit=args.limit, days=args.days):
        print(line)
    return 0


def cmd_log(args) -> int:
    """`heimdall log RECORD[/POINT[/TAG]] [--full] [--attempt N]` (V202): a record's own account, its run.jsonl, as the
    plain view prints it (each of its runs in turn); a point's attempts and its tools' digests (--full: their whole
    logs; --attempt N: an earlier attempt's, from its history/); a tool's log."""
    record_dir, point, tag = house.log_target(args.target)
    if point is None:
        if args.full or args.attempt is not None:
            raise HeimdallError("--full and --attempt are a point's: name one", hint=f"heimdall log {args.target}/<point>")
        path = record_dir / "run.jsonl"
        if not path.is_file():
            raise HeimdallError("this record has no run.jsonl: it ran before runs kept their own log", where=str(record_dir),
                           hint=f"heimdall log {args.target}/<point> shows a point's attempts and logs")
        shown = PlainView(stream=sys.stdout, every=float("inf"))
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                shown.event(event)
            shown.screen.drain(timeout=60.0)
        finally:
            shown.end()
        return 0
    full = args.full or args.target.endswith(".full.log")              # a whole log named by its path
    for line in house.point_log(record_dir, point, tag, full=full, attempt=args.attempt):
        print(line)
    return 0


def cmd_watch(args) -> int:
    """Follow a job from another terminal (V72): a running `heimdall run`'s watch socket (the latest one, or
    the one running CONFIG [CONFIGURATION]), or with --file a --journal run's status.jsonl."""
    if args.file:
        path = Path(args.file)
        if not path.exists():
            raise HeimdallError("no such status file", where=str(path), hint="a run writes one with heimdall run … --journal")
        return follow_file(path, plain=args.plain)
    wanted = configmod.load(args.config) if args.config else None
    found = house.live_runs(str(wanted.path) if wanted else None, args.configuration, getattr(args, "pid", None))
    if not found:
        last = next((e for e in runs.entries() if e.get("kind") == "run" and e.get("finished") is not None
                     and (wanted is None or e.get("config") == str(wanted.path))), None)
        ended = (f"; the last ({last['id']}) ended {runs.state(last)}" + (f", its log {last['log']}" if last.get("log") else "")
                 if last else "")
        raise HeimdallError("no running job to watch" + (f" for {wanted.path}" if wanted else "")
                       + (f" with pid {args.pid}" if getattr(args, "pid", None) else ""),
                       hint=f"heimdall runs lists them{ended}; a finished run's events: heimdall run … --journal, then "
                            "heimdall watch --file records/<P>/<run>/<cfg>/status.jsonl")
    name, hello = found[0]
    where = hello.get("address") or name
    if not live(args):
        return follow_events(connect(where), plain=args.plain)
    from .events import namespace, open_stream
    from .watch import Keys, follow
    hint = "d or Ctrl-C: detach · q: stop the run"
    stopping = []

    def on_key(key: str, shown) -> str | None:              # d leaves; q stops the run, once (V183)
        if key in "dD":
            return "detached"
        if key not in "qQ":
            return None
        if hello.get("pidns") and namespace("pid") and hello["pidns"] != namespace("pid"):
            shown.say("not stopped: its process is another PID namespace's; stop it from where it runs")
        elif stopping:                                      # a second q is no hard stop: that is asked for by name
            shown.say(f"already stopping; heimdall stop --pid {hello['pid']} asks again: a hard stop, its tools killed at once")
        else:
            stopping.append(True)
            os.kill(hello["pid"], signal.SIGINT)
            shown.keys("stopping: each point ends cleanly · d or Ctrl-C: detach")
        return None

    with Keys(sys.stdin) as keys_in:
        outcome = follow(open_stream(where), plain=args.plain, keys=keys_in.fd, on_key=on_key,
                         on_interrupt=lambda shown: "detached", hint=hint)
    if outcome == "dropped":
        print(f"this terminal fell behind the run: heimdall watch --pid {hello.get('pid')} follows it again", file=sys.stderr)
    return 0


def _planned_all(names: list[str], configuration: str | None = None, sets=()) -> tuple[list, list[str]]:
    """Every configuration of these configs, planned as for a run (with its --set's): the plans, and
    what did not plan."""
    planned, failed = [], []
    for name in names:
        try:
            run = configmod.load(name, sets=list(sets))
            for key in ([configuration] if configuration else list(run.configurations)):
                planned.append(build_plans(argparse.Namespace(config=name, set=list(sets), points=None, rerun=False, only=None), key))
        except HeimdallError as error:
            failed.append(f"{name}: {error.message}")
    return planned, failed


def cmd_status(args) -> int:
    """`heimdall status [CONFIG [CONFIGURATION]]` (V74): each configuration's points and stages. `--stack`
    (V78, V123): every recipe installed in the loaded stack, then env/stack.toml's libraries and versions."""
    if getattr(args, "stack", False):
        from .doctor import stack_status
        for line in stack_status():
            print(line)
        return 0
    names = [args.config] if args.config else house.config_names()
    planned, failed = _planned_all(names, args.configuration, getattr(args, "set", []))
    for line in house.status(planned, house.running_configs()):
        print(line)
    for line in failed:
        print(f"not planned: {line}")
    return 2 if failed else 0


def cmd_clean(args) -> int:
    """`heimdall clean [CONFIG] [--dry-run] [--yes]` (V74): the output folders no plan uses, `.partial`
    leftovers and (with no config) unused run folders and prepare caches. It lists them first, and asks
    on a terminal (or needs --yes); results/ is never cleaned but for `.partial` leftovers."""
    if (going := house.runs_here(paths.work_root())):        # V182: this work dir's, this user's
        raise HeimdallError(f"a run of this work dir is going (pid {going[0].get('pid')})",
                       hint="clean when it has ended (heimdall runs lists it, heimdall watch shows it)")
    names = [args.config] if args.config else house.config_names()
    planned, failed = _planned_all(names, sets=getattr(args, "set", []))
    if failed and not args.config:
        for line in failed:
            print(f"not planned: {line}")
        raise HeimdallError("every config must plan before a whole clean: one that does not might own what would go",
                       hint="fix it, or clean one config: heimdall clean CONFIG")
    if failed:
        raise HeimdallError(failed[0])
    records = getattr(args, "records", False)
    targets, kept = house.clean_targets(planned, everything=not args.config, records=records)
    for path in targets:
        print(f"remove  {path}")
    for path in kept:
        print(f"kept    {path}   (results are yours: remove by hand if you mean to)")
    if not targets:
        print("nothing to clean")
        return 0
    if args.dry_run:
        print(f"{len(targets)} to remove (dry run)")
        return 0
    from .paths import records_root
    gone = [t for t in targets if t.is_relative_to(records_root()) and "points" in t.relative_to(records_root()).parts[3:4]]
    if gone:                                  # records are precious: always asked for, by name (U21)
        if not sys.stdin.isatty():
            raise HeimdallError(f"{len(gone)} record folders to remove: not deleted", hint="run it on a terminal, which asks")
        if input(f"remove {len(gone)} record folders (their points' provenance and completion)? type 'records': ").strip() != "records":
            print("nothing removed")
            return 0
    elif not args.yes:
        if not sys.stdin.isatty():
            raise HeimdallError(f"{len(targets)} to remove: not deleted", hint="--yes to delete, --dry-run to only list")
        if input(f"remove these {len(targets)}? [y/N] ").strip().lower() not in ("y", "yes"):
            print("nothing removed")
            return 0
    freed = house.remove(targets)
    print(f"removed {len(targets)}, {freed / 1e6:.1f} MB freed")
    return 0


def cmd_migrate(args) -> int:
    """`heimdall migrate [CONFIG…] [--apply]` (V79): the diff of each file today's forms change, or (--apply)
    the files rewritten. Configs are read as they are (the forms the runner now refuses included)."""
    from . import migrate
    if getattr(args, "names", False):
        return migrate_names(args)
    if getattr(args, "layout", False):
        return migrate_layout(args)
    if getattr(args, "snapshot", None):
        return migrate_snapshot(args)
    if getattr(args, "plot_docs", None) is not None:
        return migrate_plot_docs(args)
    names = list(args.configs) or house.config_names()
    changes = migrate.plan(names, v3=getattr(args, "v3", False))   # every one must read, leniently, first
    for path, (old, new) in changes.items():
        sys.stdout.write(migrate.diff(path, old, new))
    if not changes:
        print("nothing to migrate")
        return 0
    if args.apply:
        migrate.apply(changes)
        print(f"migrated {len(changes)} file(s)")
        for name in names:                   # and now they read strictly
            configmod.load(name)
        return 0
    print(f"{len(changes)} file(s) to migrate (a dry run: --apply writes them)")
    return 0


def migrate_names(args) -> int:
    """`heimdall migrate --names [--apply]` (I-109, V213): a work dir from before the rename, here or above: its
    marker hep.toml → heimdall.toml, and Heimdall's old names in its own files rewritten (migrate.names_changes:
    `{hep}`, `HEP_*`, `$HEP`, `hepkit`, Whizard's `# hep:`, the editor's themes). A dry run prints each diff;
    --apply writes them. `heimdall setup . --refresh` then brings the framework's own files to today's."""
    from . import migrate
    work = find_work() or migrate.old_marker()
    if work is None:
        raise HeimdallError("not inside a work dir", hint="run it in a work dir: one with heimdall.toml, or hep.toml from before the rename")
    marker, today = work / migrate.OLD_MARKER, work / paths.MARKER_FILE
    changes = migrate.names_changes(work)
    for path, (old, new) in changes.items():
        sys.stdout.write(migrate.diff(path, old, new))
    moving = marker.is_file()
    if moving:
        print(f"rename {marker} → {today}")
    if not changes and not moving:
        print("nothing to migrate: the names are today's")
        return 0
    if not args.apply:
        print(f"{len(changes)} file(s) to rewrite" + (", the marker to rename" if moving else "") + " (a dry run: --apply writes them)")
        return 0
    if moving:
        if today.exists():
            raise HeimdallError(f"{today} is there already, beside {marker}", hint="keep one marker: remove hep.toml by hand")
        if marker in changes:
            changes[today] = changes.pop(marker)
        marker.rename(today)
        paths._search.cache_clear()                  # the walk up finds it now
    migrate.apply(changes)
    print(f"migrated {len(changes)} file(s)" + (f", {migrate.OLD_MARKER} → {paths.MARKER_FILE}" if moving else "")
          + ": heimdall setup . --refresh brings the framework's own files (Makefile, CLAUDE.md, …) to today's")
    return 0


def migrate_plot_docs(args) -> int:
    """`heimdall migrate --plot-docs [RECORD…] [--apply]` (V165): a plot document for each record that has none
    (every record's, or those named), from its snapshot's config (else the config its points.json names), its
    points as points.json and their .complete have them. A dry run lists them; --apply writes them. A document
    already there is left: a run rewrites what it knows, and its [plot] is yours."""
    names = list(args.plot_docs)
    if names:
        found = []
        for name in names:
            folder = record.record_of(name, need_snapshot=False)
            if folder is None:
                raise HeimdallError(f"'{name}' is no record", hint="a record is <P>/<name>/<cfg>, a folder of records/")
            found.append(folder)
    else:
        root = records_root()
        found = sorted(p.parent for p in root.glob("*/*/*/points.json"))
    todo, upgraded = [], 0
    for folder in found:
        rel = folder.relative_to(records_root())
        target = plotdoc.path_of(results_root() / rel)
        if target.is_file():
            old = plotdoc.needs_upgrade(target)
            if old and args.apply:                          # V172: its quantities as points
                plotdoc.upgrade(target)
                upgraded += 1
            print(f"{'there  ' if not old else 'upgraded' if args.apply else 'would  upgrade'} {rel}/{plotdoc.FILE}"
                  + (" (in today's layout: its quantities as points, nothing below a member or a set under a header)" if old else ""))
            continue
        if not (folder / "points.json").is_file():
            print(f"skip    {rel}: no points.json")
            continue
        todo.append(folder)
        print(f"{'write' if args.apply else 'would  write'} {rel}/{plotdoc.FILE}"
              + ("" if (folder / "config" / record.SNAPSHOT).is_file() else
                 " (no snapshot: its points from points.json, [plot] from the config it names)"))
    for target in sorted(results_root().glob(f"*/*/{plotdoc.FILE}")) if not names else ():   # the runs together (V169)
        if plotdoc.needs_upgrade(target):
            if args.apply:
                plotdoc.upgrade(target)
                upgraded += 1
            print(f"{'upgraded' if args.apply else 'would  upgrade'} {target.relative_to(results_root())}")
    if not args.apply:
        print(f"{len(todo)} to write (a dry run: --apply writes them)")
        return 0
    if upgraded:
        print(f"upgraded {upgraded}: in today's layout")
    for folder in todo:
        run, configuration = _record_config(folder)
        if (folder / "config" / record.SNAPSHOT).is_file():
            target, _ = write_documents(run, configuration, plot.recorded(run, configuration))
        else:                                               # no snapshot: its points as points.json has them
            target = plotdoc.from_manifest(folder, run, configuration)
            _write_recipe(run, target, print)
        drawn = sum(1 for m in plotdoc.load(target)[2] if m.recorded is not None and m.recorded == m.identity)
        print(f"wrote   {target} ({drawn} complete member(s))")
    return 0


def _record_config(folder: Path):
    """A record's run and configuration: its snapshot's (read as configs/ is), else the config its points.json
    names; its serial the folder's own."""
    snapshot = folder / "config" / record.SNAPSHOT
    data = json.loads((folder / "points.json").read_text(encoding="utf-8"))
    if snapshot.is_file():
        snap = record.read_snapshot(folder)
        key = snap["configuration"]
        with paths.configs_at(folder / "config"):                          # V179: read for its configuration
            run = configmod.load(snap["config"], sets=list(snap.get("sets", [])), configuration=key)
    else:
        source = data.get("config_file", "")
        try:
            source = str(Path(source).resolve().relative_to(paths.configs_root().resolve()).with_suffix(""))
        except ValueError:
            pass
        key = data.get("configuration")
        run = configmod.load(source, configuration=key)                     # V179: read for its configuration
    configuration = run.configuration(key)
    head = folder.name.split("_", 1)[0]
    if head.isdigit():                                      # a serial is location only: the folder's own
        configuration.serial = int(head)
    if snapshot.is_file() and tools.run_folders(run, configuration).record.resolve() != folder.resolve():
        raise HeimdallError(f"{folder} is not where its config runs '{key}' ({tools.run_folders(run, configuration).record})",
                       hint="the record's config has moved or been renamed: write its plot.toml by hand, or rerun it")
    return run, configuration


def migrate_snapshot(args) -> int:
    """`heimdall migrate --snapshot RECORD [--from CONFIG] [--apply]` (V158): a record that ran before snapshots
    is given one: the config (by default the one its points.json names, with the --set overrides its points'
    provenance records) is planned, its files copied into records/<run>/config/, and each recorded point said
    to have the same identity under it, or what differs (--why). A snapshot already there is replaced only with
    --apply. Edit the snapshot's files to match what ran (a value since left out), then `heimdall status RECORD`."""
    found = record.record_of(args.snapshot, need_snapshot=False)
    if found is None:
        raise HeimdallError(f"'{args.snapshot}' is no record", hint="a record is <P>/<run>/<NN_cfg>, a folder of records/")
    manifest = found / "points.json"
    if not manifest.is_file():
        raise HeimdallError("this record has no points.json", where=str(manifest))
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if (found / "config" / record.SNAPSHOT).is_file() and not args.apply:
        raise HeimdallError(f"{found / 'config'} is there already", hint="--apply replaces it")
    source = args.source or data.get("config_file", "")
    if not args.source:
        try:
            source = str(Path(source).resolve().relative_to(paths.configs_root().resolve()).with_suffix(""))
        except ValueError:
            pass
    sets = list(args.set) if getattr(args, "set", None) else []
    entries = data.get("points", [])
    for entry in entries:                                    # the overrides it ran with, from a point's provenance
        prov = found / "points" / entry.get("name", "") / "provenance.json"
        if not sets and prov.is_file():
            sets = list(json.loads(prov.read_text(encoding="utf-8")).get("sets", []))
            break
    planned = build_plans(argparse.Namespace(config=source, set=sets, points=None, rerun=False, only=None),
                          data.get("configuration"))
    rel = found.relative_to(records_root())
    if planned.every and planned.every[0].folders.record.resolve() != found.resolve():
        raise HeimdallError(f"{source} runs '{data.get('configuration')}' into {planned.every[0].folders.record.relative_to(records_root())}, "
                       f"not {rel}", hint="--from the config that ran it (its serial and name)")
    made = record.write_snapshot(planned.run, planned.configuration, planned.every)
    print(f"snapshot: {made} ({len(list(made.rglob('*')))} files) from {source}" + (f" with {' '.join(sets)}" if sets else ""))
    plans = {p.point.name: p for p in planned.every}
    same = 0
    for entry in entries:
        plan = plans.get(entry.get("name"))
        if plan is None:
            print(f"  {entry.get('name')}: recorded, but this config does not make it (a value left out since?)")
        elif plan.identity == entry.get("identity"):
            same += 1
        else:
            why = record.why(plan)
            print(f"  {entry.get('name')}: another identity under it" + (f": {why[0]}" if why else ""))
    print(f"{same} of {len(entries)} recorded point(s) have the same identity under it"
          + ("" if same == len(entries) else f"; edit {made} until they do (heimdall status {rel} says), or keep it: "
                                             "heimdall plot draws a record as it was recorded either way"))
    return 0


def migrate_layout(args) -> int:
    """`heimdall migrate --layout [--apply]`: a work dir's older layouts moved into today's, counted (a dry
    run) or moved. 5.1: output/ by lifecycle into records/, logs/ and .cache/; V157: logs/ into records/<run>/,
    and each configuration's points into points/ of records/ and results/; V164: pages into plots/<set>/, numbers
    into statistics/<set>/, the drawing's working files into .cache/."""
    from . import migrate
    from .paths import work_root
    if (going := house.runs_here(work_root())):               # V182: this work dir's, this user's
        raise HeimdallError(f"a run of this work dir is going (pid {going[0].get('pid')})",
                       hint="move the layout when it has ended (heimdall runs lists it)")
    work = work_root()
    first = migrate.layout_moves(work)
    then = [] if (work / "output").is_dir() else migrate.logs_moves(work)
    last = [] if first or then else migrate.sets_moves(work)
    if not first and not then and not last:
        print("nothing to move: the layout is today's")
        return 0
    for title, moves in (("output/ (5.1)", first), ("logs/ and points/ (V157)", then), ("plots/ by set (V164)", last)):
        counts: dict[str, int] = {}
        for source, target in moves:
            kind = f"{source.relative_to(work).parts[0]}/ → {target.relative_to(work).parts[0]}/"
            counts[kind] = counts.get(kind, 0) + 1
        for kind, n in sorted(counts.items()):
            print(f"{title}: {kind:22s} {n} file(s) or folder(s)")
        if getattr(args, "list", False):
            for source, target in moves:
                print(f"  {source.relative_to(work)} → {target.relative_to(work)}")
    if not args.apply:
        later = (" (then logs/ and points/, once output/ has moved)" if (work / "output").is_dir() else
                 " (then plots/ by set, once these have moved)" if (first or then) and migrate.old_plots(work) else "")
        print(f"{len(first) + len(then) + len(last)} to move{later} (a dry run: --apply moves them)")
        return 0
    left = migrate.apply_layout(first, work) if first else 0
    if first:
        then = migrate.logs_moves(work)
    left += migrate.apply_logs(then, work) if then else 0
    if first or then:
        last = migrate.sets_moves(work)
    left += migrate.apply_sets(last, work) if last else 0
    print(f"moved {len(first) + len(then) + len(last) - left}" + (f"; {left} left (already there)" if left else ""))
    return 0


def cmd_reproduce(args) -> int:
    """`heimdall reproduce records/…/<point>/provenance.json` (V77, F10): the point again, exactly as it ran,
    into .cache/<P>/reproduce/<identity>/ (its own records/ and results/), never over the original; then
    each product compared with the original's. The setup must still be the one that ran (the identity
    the provenance records), else it says what changed (--why) and stops, unless --anyway. A random
    seed is the recorded one; any other seed follows from the identity, as it did."""
    import hashlib
    path = Path(args.provenance)
    if path.is_dir():
        path = path / "provenance.json"
    try:
        record_ = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HeimdallError(f"cannot read {path}: {error}", hint="give a finished point's provenance.json")
    from .paths import unportable
    config_file, key, name = unportable(record_["config_file"]), record_["configuration"], record_["point"]
    for line in record.revision_changes(record_.get("git", {})):    # the code may differ, though the setup does not
        print(f"warning: {line}", file=sys.stderr)
    given = list(record_.get("sets", []))                     # the --set overrides it ran with
    planned = build_plans(argparse.Namespace(config=config_file, set=given, points=None, rerun=False, only=None), key)
    plan = next((p for p in planned.every if p.point.name == name), None)
    if plan is None:
        raise HeimdallError(f"configuration '{key}' has no point '{name}' any more", where=config_file)
    if plan.identity != record_["identity"]:
        print(f"the setup of {name} changed since it ran ({record_['identity'][:12]} → {plan.identity[:12]}):")
        for line in record.why(plan):
            print(f"  {line}")
        if not args.anyway:
            raise HeimdallError("not reproduced: this would be a different point", hint="--anyway runs today's setup with its seed")
    where = cache_root() / record_["project"] / "reproduce" / record_["identity"][:12]
    sets = []
    if planned.configuration.seed_type == "random":                      # in the file's own names
        sets = (["--set", f"cfgs.{key}.seed={record_['seed']}"] if planned.run.form == 3 else
                ["--set", f'run.cfgs.{key}.seed_type="manual"', "--set", f"run.cfgs.{key}.manual_seed={record_['seed']}"])
    argv = [sys.executable, str(Path(__file__).resolve().parents[1] / "bin" / "run"), "run", config_file, key,
            "--points", name, "--rerun", *[x for item in given for x in ("--set", item)], *sets,
            *(["--plain"] if args.plain else [])]
    env = dict(os.environ, HEIMDALL_RECORDS=str(where / "records"), HEIMDALL_RESULTS=str(where / "results"))
    print(f"reproducing {record_['run']} · {key} · {name} (seed {record_['seed']}) in {where}", flush=True)
    code = subprocess.run(argv, env=env).returncode
    if code != 0:
        return code
    original, again_ = plan.res, where / "results" / plan.res.relative_to(results_root())

    same = True
    for made in sorted(f for f in again_.rglob("*") if f.is_file() and not f.name.endswith(".json")):
        rel = made.relative_to(again_)
        before = original / rel
        verdict = same_contents(before, made) if before.is_file() else "missing in the original"
        same = same and verdict in ("identical", "the same values")
        print(f"  {rel}: {verdict}")
    return 0 if same else 1


def same_contents(a: Path, b: Path) -> str:
    """Two products compared by what they hold (V77): a YODA file object by object (values and errors),
    a ROOT file histogram by histogram (uproot), anything else byte for byte. Bytes alone differ for
    the same physics: a sharded Rivet's merge order and ROOT's write times are in the files."""
    import hashlib
    if hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest():
        return "identical"
    try:
        if a.name.endswith((".yoda", ".yoda.gz")):
            import yoda

            def table(path):
                out = {}
                for key, obj in yoda.read(str(path)).items():
                    vals = [obj.vals()] if hasattr(obj, "vals") else []
                    errs = [obj.errs()] if hasattr(obj, "errs") else []
                    out[key] = (obj.type(), repr(vals), repr(errs))
                return out
            return "the same values" if table(a) == table(b) else "differs"
        if a.suffix == ".root":
            import numpy as np
            import uproot

            def histograms(path):
                with uproot.open(path) as file:
                    return {k: np.asarray(file[k].values()).tolist() for k in file.keys(cycle=False)
                            if hasattr(file[k], "values") and callable(getattr(file[k], "values"))}
            return "the same values" if histograms(a) == histograms(b) else "differs"
    except ImportError:
        return "differs in bytes (not read: no yoda/uproot)"
    return "differs"


#: Commands whose arguments go on as they are: to make, to the stack's builder, to the shell function.
PASSED_ON = ("make", "stack", "refresh", "quit", "cd")


def _described(top: argparse.ArgumentParser) -> argparse._SubParsersAction:
    """Each command's description is its help, said in full (`heimdall run --help`, `heimdall help run`)."""
    commands = next(a for a in top._actions if isinstance(a, argparse._SubParsersAction))
    helps = {a.dest: a.help for a in commands._choices_actions}
    for name, sub_parser in commands.choices.items():
        if not sub_parser.description and helps.get(name):
            sub_parser.description = helps[name][:1].upper() + helps[name][1:] + "."
    return commands


def parse(argv: list[str]) -> argparse.Namespace:
    """The command line, with options and positionals in any order (`heimdall run jets --plain pdf`, V54):
    argparse's intermixed parsing does not take subcommands, so the subcommand's own parser reads the rest.
    `--plain` may come anywhere, for any command; an unknown command gets the nearest (U59)."""
    top = parser()
    commands = _described(top)
    typed = list(argv)                                             # as typed: a worker's own (V181)
    plain = "--plain" in argv
    argv = [a for a in argv if a != "--plain"]
    if not argv or argv[0] in ("-h", "--help"):
        top.print_help()
        raise SystemExit(0)
    if argv[0] in PASSED_ON:
        return argparse.Namespace(command=argv[0], rest=argv[1:], plain=plain)
    if argv[0] not in commands.choices:
        if argv[0].startswith("-"):
            return top.parse_args(argv)
        raise HeimdallError(f"no command '{argv[0]}'", hint=did_you_mean(argv[0], commands.choices) or "heimdall help lists them")
    if argv[0] == "bifrost":                                       # -c, -b, -b@<toolkit> (runner/bifrost.py)
        from .bifrost import flags
        argv = [argv[0], *flags(argv[1:])]
    args = commands.choices[argv[0]].parse_intermixed_args(argv[1:])
    args.command = argv[0]
    args.plain = plain or getattr(args, "plain", False)
    args.argv = typed
    return args


#: The commands whose flags a run TOML's [heimdall] gives (V188): those that read one config.
FLAGGED = ("run", "plot", "stats", "cluster", "status", "watch", "stop")
#: Options a file never sets: what it would name of itself, or change of itself (its own text does that).
UNFLAGGED = {"set", "worker", "help"}
#: What [heimdall] may set (the user, 2026-10-25): switches that say how you like a command to run, and keep.
PREFERENCES = ("rerun", "wait", "detach", "plain", "journal", "logs", "replot", "keep")
#: Every other option, by its dest, and why a file never sets it: a mode or a target is one command's job, a
#: selection one run's choice, and the study's own settings are [run]'s keys.
NOT_PREFERENCES = {
    **dict.fromkeys(("plan", "why", "show_config", "dry_run", "status", "cancel", "style_sync", "across", "stack",
                     "no_wait"), ("a mode: what this one command does", "type it on the command line")),
    **dict.fromkeys(("card", "pid", "file", "plot_file"), ("a target: what this one command acts on",
                                                            "type it on the command line")),
    **dict.fromkeys(("points", "page_points", "draw_sets", "stages", "only"),
                    ("a selection: a part of the run, chosen when it is run",
                     "type it on the command line; a run's sets are [run] plot = [...] or a configuration's plot")),
    "no_plot": ("the study's own setting", "[run] plot = false"),
    "no_stats": ("the study's own setting", "[run] stats = false"),
}


def _options() -> dict[str, dict[str, argparse.Action]]:
    """Each FLAGGED command's options by their names (dest), --plain beside them (every command has it)."""
    commands = _described(parser())
    plain = argparse.Namespace(dest="plain", option_strings=["--plain"], default=False, nargs=0, type=None,
                               const=True, help="plain lines")
    out = {}
    for command in FLAGGED:
        actions = {}
        for a in commands.choices[command]._actions:
            if a.option_strings and a.dest not in UNFLAGGED and a.help != argparse.SUPPRESS:
                for typed in a.option_strings:              # by the option as typed (sets, no-plot), its dest too
                    if typed.startswith("--"):
                        actions[typed[2:].replace("-", "_")] = a
                actions.setdefault(a.dest, a)
        out[command] = {**actions, "plain": actions.get("plain", plain)}
    return out


def _flag_value(action, value, where: str):
    """A [heimdall] value as its option takes it: true/false for a switch, a list for one given many times or
    taking several, else a string (an int for a number)."""
    switch = action.nargs == 0
    many = isinstance(action, argparse._AppendAction) or action.nargs in ("*", "+")
    name = action.option_strings[-1]
    if switch:
        if not isinstance(value, bool):
            raise HeimdallError(f"{where}: {name} is a switch: true or false", where=where)
        return value if action.const is not False else not value
    if many:
        items = value if isinstance(value, list) else [value]
        if not all(isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in items):
            raise HeimdallError(f"{where}: {name} takes values: a list of them", where=where)
        return [str(v) for v in items]
    if action.type is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise HeimdallError(f"{where}: {name} takes a whole number", where=where)
        return value
    if isinstance(value, (bool, dict, list)):
        raise HeimdallError(f"{where}: {name} takes one value", where=where)
    return str(value)


def heimdall_flags(table: dict, where: str, command: str | None = None) -> dict[str, tuple]:
    """[heimdall] checked (V188, V190): a key there is an option of a command that reads a config, for every such
    command that has it; [heimdall.<command>] keys that command's own, over those. Only PREFERENCES are taken;
    any other option is refused with why (NOT_PREFERENCES). For `command`: its option name → (value, the option
    as typed). `heimdall check` checks every command's."""
    options = _options()
    def dest_of(key: str) -> str:
        return key.lstrip("-").replace("-", "_")

    def refused(key: str, dest: str, at: str) -> None:
        """A known option that is not a preference: said, with why (V190)."""
        if dest not in PREFERENCES:
            what, hint = NOT_PREFERENCES.get(dest, ("not a preference", "type it on the command line"))
            raise HeimdallError(f"{at} {key}: {what}, which a file does not set", where=where,
                           hint=f"{hint}; [heimdall] takes {', '.join(PREFERENCES)}")
    every = {d for o in options.values() for d in o}
    mine: dict[str, tuple] = {}
    for key, value in table.items():
        if isinstance(value, dict):
            if key not in FLAGGED:
                raise HeimdallError(f"[heimdall.{key}]: no such command reads a config", where=where,
                               hint=did_you_mean(key, FLAGGED) or f"the commands: {', '.join(FLAGGED)}")
            continue
        dest = dest_of(key)
        if dest not in every:
            raise HeimdallError(f"[heimdall] {key}: no command that reads a config has that option", where=where,
                           hint=did_you_mean(dest, sorted(every)) or "a command's options: heimdall help <command>")
        refused(key, next(o[dest].dest for o in options.values() if dest in o), "[heimdall]")
        for name, actions in options.items():
            if dest in actions:
                value_ = _flag_value(actions[dest], value, f"{where}.{key}")
                if name == command:
                    mine[actions[dest].dest] = (value_, actions[dest].option_strings[-1])
    for name, sub in ((k, v) for k, v in table.items() if isinstance(v, dict)):
        for key, value in sub.items():
            dest = dest_of(key)
            if dest not in options[name]:
                raise HeimdallError(f"[heimdall.{name}] {key}: heimdall {name} has no such option", where=where,
                               hint=did_you_mean(dest, list(options[name])) or f"heimdall help {name}")
            refused(key, options[name][dest].dest, f"[heimdall.{name}]")
            value_ = _flag_value(options[name][dest], value, f"{where}.{name}.{key}")
            if name == command:
                mine[options[name][dest].dest] = (value_, options[name][dest].option_strings[-1])
    return mine


def config_flags(args) -> list[str]:
    """A run TOML's [heimdall] (V188) for the command reading it: each option the command line left unset takes
    the file's value (the command line always wins). The options it set, as they would be typed."""
    name = getattr(args, "config", None)
    if args.command not in FLAGGED or not isinstance(name, str) or not name:
        return []
    try:
        path = paths.config_file(name)
    except HeimdallError:
        return []
    if path.suffix != ".toml" or not path.is_file():
        return []
    table = configmod.heimdall_table(name, sets=getattr(args, "set", None) or [])
    if not table:
        return []
    options = {a.dest: a for a in _options()[args.command].values()}
    given = []
    for dest, (value, typed) in heimdall_flags(table, f"{path}: [heimdall]", args.command).items():
        action = options[dest]
        if getattr(args, dest, action.default) not in (action.default, None, []):   # the command line said
            continue
        if getattr(args, dest, None) == value:
            continue
        setattr(args, dest, value)
        given.append(typed if value is True else f"{typed} {' '.join(map(str, value))}" if isinstance(value, list)
                     else "" if value is False else f"{typed} {value}")
    return [g for g in given if g]


def cmd_help(args) -> int:
    """`heimdall help [command]`: that command's help, or every command's one line."""
    top = parser()
    commands = _described(top)
    if not args.topic:
        top.print_help()
        return 0
    if args.topic not in commands.choices:
        raise HeimdallError(f"no command '{args.topic}'", hint=did_you_mean(args.topic, commands.choices) or "heimdall help lists them")
    if args.topic in PASSED_ON:
        print(f"heimdall {args.topic}: {commands.choices[args.topic].description}")
        if args.topic == "stack":
            print("  heimdall stack build [packages=@kit] [key=value…] [--dry-run]   the stack's builder (recipes/build_stack.py),\n"
                  "                                                              on a conda base (base=system: apt, a venv)\n"
                  "  heimdall stack build --base | --update-base                     the base only; its packages to their newest\n"
                  "  heimdall stack build packages=@core-conda                       the core ready-made from conda-forge\n"
                  "  heimdall stack list [@kit]                                       its recipes and what is installed\n"
                  "  heimdall stack status                                            each package, its release and state\n"
                  "  heimdall stack doctor [--quick]                                  what the stack can do, checked")
        return 0
    commands.choices[args.topic].print_help()
    return 0


def cmd_image(args) -> int:
    """`heimdall image [list]` and `heimdall image build [packages=@kit cores=N root_cores=N]` (image.py, V150)."""
    from . import image
    if args.action == "list":
        if args.settings:
            raise HeimdallError("heimdall image lists; heimdall image build packages=@kit builds")
        for line in image.listing():
            print(line)
        return 0
    given = dict(item.split("=", 1) for item in args.settings if "=" in item)
    if unknown := sorted(set(given) - {"packages", "cores", "root_cores"}) or [s for s in args.settings if "=" not in s]:
        raise HeimdallError(f"heimdall image build takes packages=, cores=, root_cores=, not {', '.join(unknown)}")
    return image.build(given.get("packages", "@primary"), given.get("cores", "0"), given.get("root_cores", "0"),
                       name=args.name, allow_dirty=args.dirty)


def cmd_recognise(args) -> int:
    """`heimdall recognise`: the work dirs this machine knows, by title (workdirs.py, V143)."""
    from . import workdirs
    if args.path_of:
        print(workdirs.path_of(args.path_of))
        return 0
    if args.forget:
        print(f"forgot {args.forget!r}: {workdirs.forget(args.forget)}")
        return 0
    if args.list:
        entries = workdirs.load()
        if not entries:
            print(f"no work dir recorded yet ({workdirs.registry_file()}): heimdall recognise <work dir>")
            return 0
        width = max(len(title) for title in entries)
        for title in sorted(entries, key=str.casefold):
            state = workdirs.state(entries[title])
            print(f"{title:{width}}  {entries[title]['path']}" + ("" if state == "work dir" else f"  ({state})"))
        return 0
    start = Path(args.path or ".").expanduser().resolve()
    if not start.is_dir():
        raise HeimdallError(f"{start} is not a folder", hint="heimdall recognise <work dir or a folder holding some>")
    inside = workdirs.enclosing(start)
    found = [inside] if inside else workdirs.scan(start)
    if args.title and len(found) != 1:
        raise HeimdallError(f"--as titles one work dir, and {len(found)} were found below {start}",
                       hint="name the work dir itself: heimdall recognise <work dir> --as <title>")
    if not found:
        print(f"no work dir in or below {start} ({workdirs.DEPTH} folders deep): heimdall setup <dir> makes one")
        return 0
    refused = 0
    for where in found:
        try:
            title, happened = workdirs.record(where, args.title)
        except HeimdallError as error:
            refused += 1
            print(error.render(), file=sys.stderr)
            continue
        print(f"{title}: {where} ({happened})")
    return 2 if refused else 0


def cmd_build(args) -> int:
    """`heimdall build` (U61): make, in the work dir (or, --framework, Heimdall): the module programs and
    Rivet plugins, or Heimdall's apps and (--tests) its C++ tests."""
    from .paths import heimdall_root, work_root
    if args.tests and not args.framework:
        raise HeimdallError("--tests builds Heimdall's C++ tests", hint="heimdall build --framework --tests")
    where = heimdall_root() if args.framework else work_root()
    make = ["make", "-C", str(where), "--no-print-directory"]
    if shutil.which("make") is None:
        raise HeimdallError("make is not on PATH", hint="install it (build-essential; on macOS, Xcode's command line tools)")
    for step in (["clean"] if args.clean else []) + (["configure"] if args.configure else []):
        if subprocess.run(make + [step]).returncode:
            return 1
    goals = list(args.targets) or ["all"]
    goals += ["tests"] if args.tests and "tests" not in goals else []
    os.execvp("make", make + ["-j", str(args.jobs or os.cpu_count() or 1), *(["-n"] if args.dry_run else []), *goals])


def cmd_make(args) -> int:
    """`heimdall make [--framework] <path>/<X>.exe | <path>/<x>.so`: one source, through make."""
    from .paths import heimdall_root, work_root
    rest = list(args.rest)
    framework = "--framework" in rest
    rest = [a for a in rest if a != "--framework"]
    if not rest or rest[0] in ("-h", "--help"):
        print("usage: heimdall make [--framework] <path>/<X>.exe | <path>/<x>.so   (docs/06_Internals.md §15)")
        return 0
    os.execvp("make", ["make", "-C", str(heimdall_root() if framework else work_root()), "--no-print-directory", *rest])


def _system_python() -> str:
    """The first python3 on PATH that is not the machine's venv's or base's: the stack's builder makes them."""
    from .paths import machine_root
    venvs = {str((machine_root() / "venv" / "bin").resolve())}
    if os.environ.get("HEIMDALL_VENV"):
        venvs.add(str((Path(os.environ["HEIMDALL_VENV"]) / "bin").resolve()))
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(folder) / "python3"
        if folder and str(Path(folder).resolve()) not in venvs and candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


def cmd_stack(args) -> int:
    """`heimdall stack build|list|status|doctor` (U60): the stack's builder (recipes/build_stack.py; on macOS
    recipes/platforms/mac/build.sh), and the stack's status and checks, under one noun."""
    import platform
    from .paths import heimdall_root
    rest = list(args.rest)
    action = rest.pop(0) if rest else "help"
    if action in ("help", "-h", "--help"):
        return cmd_help(argparse.Namespace(topic="stack"))
    if action == "status":
        from .doctor import stack_status, stack_toml
        if "--toml" in rest:
            print(stack_toml(), end="")
            return 0
        for line in stack_status():
            print(line)
        return 0
    if action == "doctor":
        return doctormod.main(quick="--quick" in rest, record_it="--record" in rest, show_matrix="--matrix" in rest)
    if action not in ("build", "list"):
        raise HeimdallError(f"no 'heimdall stack {action}'", hint=did_you_mean(action, ("build", "list", "status", "doctor"))
                       or "heimdall stack build|list|status|doctor")
    root = heimdall_root()
    if platform.system() == "Darwin" and action == "build":
        argv = ["bash", str(root / "recipes" / "platforms" / "mac" / "build.sh"), *rest]
    else:
        argv = [_system_python(), str(root / "recipes" / "build_stack.py"), *(["--list"] if action == "list" else []), *rest]
    os.execvp(argv[0], argv)


def cmd_shell_verb(args) -> int:
    """`heimdall refresh | quit | cd`: they change the shell they are typed in, which only gjallarhorn.sh's shell
    function can (env/heimdall_env.sh)."""
    from .paths import heimdall_root
    raise HeimdallError(f"heimdall {args.command} changes the shell it is typed in, so it is gjallarhorn.sh's shell function, "
                   "and this shell does not have it (a script, or a shell started from one)",
                   hint=f"source {heimdall_root() / 'gjallarhorn.sh'}")


def main(argv: list[str]) -> int:
    try:
        args = parse(argv)
    except HeimdallError as error:
        print(error.render(), file=sys.stderr)
        return 2
    try:
        _ask_keep(args)
        check_retired()                                            # a shell with High-Energy's names (K15)
        from .migrate import old_marker, old_plots
        if args.command != "setup" and find_work() is None and not getattr(args, "names", False) and (old := old_marker()):
            print(f"note: {old} is a work dir from before Heimdall's names moved (its marker is hep.toml): "
                  "`heimdall migrate --names --apply` renames it and the old names in its files", file=sys.stderr)
        if args.command != "setup" and (work := find_work()) is not None:
            if warning := setupmod.expects_warning(work):          # once per command (framework/01 §4.2)
                print(warning, file=sys.stderr)
            if (work / "output").is_dir() and not getattr(args, "layout", False):   # made before 5.1's split
                print("note: this work dir has output/ from before records/ and .cache/: its points rerun "
                      "until `heimdall migrate --layout --apply` moves it", file=sys.stderr)
            elif (work / "logs").is_dir() and any((work / "logs").iterdir()) and not getattr(args, "layout", False):
                print("note: this work dir has logs/ from before records/<run>/logs/ and points/ (V157): its points "
                      "rerun and its pages miss them until `heimdall migrate --layout --apply` moves them", file=sys.stderr)
            elif not getattr(args, "layout", False) and old_plots(work):
                print("note: this work dir has pages in results/…/plots/<backend>/ from before plots/<set>/ (V164): "
                      "`heimdall migrate --layout --apply` moves them, and the numbers into statistics/<set>/", file=sys.stderr)
        if args.command == "setup":
            if args.refresh:
                ask = input if sys.stdin.isatty() else None
                setupmod.refresh(Path(args.dir), yes=args.yes, ask=ask)
                return 0
            added = setupmod.setup(Path(args.dir), project=args.project, git=args.git, adopt=args.adopt, name=args.name,
                                   example=args.example)
            for line in setupmod.next_steps(Path(args.dir).expanduser().resolve(), added, args.project, args.git,
                                            example=args.example):
                print(line)
            return 0
        if args.command == "where":
            return setupmod.where(args.which)
        if args.command == "recognise":
            return cmd_recognise(args)
        if args.command == "image":
            return cmd_image(args)
        if args.command == "bifrost":
            from . import bifrost
            return bifrost.main(args)
        if args.command == "help":
            return cmd_help(args)
        if args.command == "build":
            return cmd_build(args)
        if args.command == "make":
            return cmd_make(args)
        if args.command == "stack":
            return cmd_stack(args)
        if args.command in ("refresh", "quit", "cd"):
            return cmd_shell_verb(args)
        if args.command == "doctor":
            return doctormod.main(quick=args.quick, record_it=args.record, show_matrix=args.matrix)
        if args.command == "tools":
            from . import tools as toolsmod
            if args.what[:1] == ["new"]:
                if len(args.what) != 2 or not args.source:
                    raise HeimdallError("heimdall tools new <name> --from <tool>", hint="--from a template folder (copied) or any tool (extended): heimdall tools lists them")
                print(f"made {toolsmod.new_folder(args.what[1], args.source, args.package, args.runs)}/tool.toml")
                return 0
            if len(args.what) > 1:
                raise HeimdallError("heimdall tools [<name>] | new <name> --from <tool>")
            for line in (toolsmod.folder_lines(args.what[0]) if args.what else toolsmod.folder_rows()):
                print(line)
            return 0
        if args.command in ("run", "plot", "status", "stats") and getattr(args, "config", None):
            if not (args.command in ("plot", "stats") and (plotdoc.find(args.config) or getattr(args, "style_sync", None))):
                opened(args)                              # a record: its snapshot (V158)
        if (given := config_flags(args)):                 # V188: the file's own flags, where the command line has none
            print(f"heimdall: from [heimdall]: {' '.join(given)}", file=sys.stderr)
            _ask_keep(args)
        if args.command == "run":
            return cmd_run(args)
        if args.command == "plot":
            return cmd_plot(args)
        if args.command == "stats":
            return cmd_stats(args)
        if args.command == "check":
            return cmd_check(args)
        if args.command == "overlay":
            return cmd_overlay(args)
        if args.command == "deck":
            return cmd_deck(args)
        if args.command == "report":
            return cmd_report(args)
        if args.command == "ls":
            for line in house.ls(args.project):
                print(line)
            return 0
        if args.command == "explain":
            for line in house.explain(args.key):
                print(line)
            return 0
        if args.command == "status":
            return cmd_status(args)
        if args.command == "clean":
            return cmd_clean(args)
        if args.command == "reproduce":
            return cmd_reproduce(args)
        if args.command == "migrate":
            return cmd_migrate(args)
        if args.command == "cluster":
            return cmd_cluster(args)
        if args.command == "runs":
            return cmd_runs(args)
        if args.command == "stop":
            return cmd_stop(args)
        if args.command == "log":
            return cmd_log(args)
        return cmd_watch(args)
    except HeimdallError as error:
        print(error.render(), file=sys.stderr)
        return 2
    except KeyboardInterrupt:                                      # Ctrl-C before a run catches it (V181)
        print("heimdall: stopped", file=sys.stderr)
        return 6
