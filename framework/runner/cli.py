"""`heimdall run`, `heimdall plot`, `heimdall overlay`, `heimdall watch`, `heimdall check` and the housekeeping commands (`ls`,
`explain`, `status`, `clean`: house.py) (rank 5): argument parsing and the order of events.

doc:everyday. `heimdall build` is handled by the shell dispatcher
(framework/bin/heimdall), which runs make.

Exit codes: 0 every point done (or skipped), 1 a point failed, 2 a config error before anything ran,
6 stopped or paused by the user. Under [errand].sweep_runs (V38), several runs one after another: 6 if one was
stopped or paused, else 1 if any failed (or could not be planned at its turn), else 0.
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
from . import execute, house, library, paths, plot, plotdoc, post, record, runs, sweep, tools
from . import doctor as doctormod
from . import setup as setupmod
from .errors import HeimdallError, did_you_mean
from .paths import cache_root, check_retired, find_work, records_root, results_root
from .quantities import load_master
from .events import Bus, Hub, Journal, RunBus, RunLog, greeting, connect, hubs
from .watch import PlainView, follow_events, follow_file, view


def record_options(parser: argparse.ArgumentParser, target_help: str, own=None) -> None:
    """What `log` and `show` take alike: a record's `target`, then (`own` adds them) the command's own options, then `--full`
    and `--attempt`."""
    parser.add_argument("target", metavar="RECORD[/POINT[/TAG]]", help=target_help)
    if own is not None:
        own(parser)
    parser.add_argument("--full", action="store_true", help="the whole logs (a job with --logs) instead of the digests")
    parser.add_argument("--attempt", type=int, metavar="N", help="an earlier attempt's logs, from the point's history/")


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="heimdall", description="Heimdall: plan, run, draw and record studies (docs/README.md). "
                                                       "`heimdall help <command>` for one command.")
    top.add_argument("--plain", action="store_true", help="plain lines instead of the live view (any command, anywhere)")
    commands = top.add_subparsers(dest="command", required=True, metavar="<command>")

    run = commands.add_parser("run", help="plan and run a configuration")
    run.add_argument("config", help="configs/<A>/<E>[.toml], ./path from the work dir, or a record "
                                    "<A>/<E>/<R> (what it ran with: its snapshot)")
    run.add_argument("configuration", nargs="?", help="overrides [errand].configuration; under [errand].sweep_runs, runs only it")
    run.add_argument("--plan", "--dry-run", dest="plan", action="store_true", help="print the plan; run nothing")
    run.add_argument("--why", action="store_true",
                     help="for each point that would run, what changed since it last completed; run nothing")
    run.add_argument("--show-config", action="store_true",
                     help="print each configuration's resolved values and where each came from; run nothing")
    run.add_argument("--card", metavar="TAG", help="with --plan: that tool's card for the first point, each line with "
                                                   "where its value comes from")
    run.add_argument("--points", metavar="SEL", help="run a subset: tags, indices or quantity=tag")
    run.add_argument("--detach", action="store_true",
                     help="start the job in the background and return: heimdall watch follows it, heimdall stop stops it "
                          "(on a terminal, a job started without it leaves on d too)")
    run.add_argument("--worker", metavar="ID", help=argparse.SUPPRESS)       # a detached run's own process (V183)
    run.add_argument("--queued-to", metavar="ID|N",
                     help="queue the run after another (its id, or its [N] in heimdall runs): it starts, detached, when that "
                          "one ends (done, failed or lost; one stopped holds it until heimdall runs --dispatch); queues chain")
    run.add_argument("--sweep-member", metavar="KEY", help=argparse.SUPPRESS)  # one configuration of a sweep's chain
    run.add_argument("--set", metavar="KEY=VALUE", action="append", default=[],
                     help="override one value for this invocation (repeatable), in the file's own names: "
                          "errand.events=100 (v3), errand.event_count=100 (v2)")
    run.add_argument("--tag", metavar="NAME",
                     help="tag each Run this job makes or resumes (over the one it has and its "
                          "configuration's tag): a letter or digit, then letters, digits, . _ + -, at most 40")
    run.add_argument("--rerun", action="store_true", help="ignore skip-unchanged; under a serial the file sets, "
                                                          "overwrite points made from other inputs")
    run.add_argument("--rerun-since", type=float, metavar="TIME", dest="rerun_since",
                     help=argparse.SUPPRESS)     # a resumed --rerun job: what completed before TIME runs again
    run.add_argument("--only", choices=["pre", "post", "plot"], help="rerun only the pre tools, the post tools or the plots")
    run.add_argument("--no-plot", action="store_true", dest="no_plot",
                     help="draw nothing after the points (its plot.toml is written all the same), whatever [errand].plot says")
    run.add_argument("--no-stats", action="store_true", dest="no_stats",
                     help="measure nothing after the points, whatever [errand].stats says")
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
    draw.add_argument("config", help="the errand file, or a record <A>/<E>/<R>: its points as they were "
                                     "recorded, with the config they ran with (its snapshot, which you may edit)")
    draw.add_argument("--plot", metavar="FILE", dest="plot_file",
                      help="a file whose [plot] draws instead of the run's: configs/<A>/<E>, ./… or /…")
    draw.add_argument("--sets", metavar="NAMES", dest="draw_sets",
                      help="draw these sets only (comma-separated; default: the document's [plot].draw, else every set)")
    draw.add_argument("--points", metavar="SEL", dest="page_points",
                      help="pages of these points only, in this order, in the folder points/: indices, names, globs, "
                           "tags or quantity=tag, comma-separated ([plot].sets for one set)")
    draw.add_argument("--plan", action="store_true",
                      help="say each set's page cells and their curves, from the complete points; draw nothing; "
                           "with --style-sync: what would change, written nowhere")
    draw.add_argument("--style-sync", metavar="CONFIG", dest="style_sync",
                      help="take this config's [plot] and [stats] into the plot documents named (<A>/<E>/<R>, or "
                           "<A>/<E>: each of its Runs), what each Run knows left as it is; nothing is drawn unless --replot")
    draw.add_argument("--replot", action="store_true", help="with --style-sync: then draw what was synced")
    draw.add_argument("--across", action="store_true",
                      help="the Runs of this errand together, results/<A>/<E>/plot.toml: its [plot.across] sets")
    draw.add_argument("--stats-only", action="store_true", dest="stats_only",
                      help="the statistics alone: the pages' numbers against the data, read by Paint into statistics/<set>/, "
                           "no page drawn (--sets: these sets only; target also <A>/<E>, each of its Runs)")
    draw.add_argument("--keep", action="append", default=[], metavar="WHAT",
                      help="cache: keep the card checks (as heimdall run --keep); the drawing's working files are .cache/'s anyway")
    draw.add_argument("configuration", nargs="?", help="overrides [errand].configuration; under sweep_runs, only it")
    draw.add_argument("--set", metavar="KEY=VALUE", action="append", default=[], help="as for heimdall run")

    numbers = commands.add_parser("stats", help="retired: heimdall plot RUN --stats-only measures a Run's statistics, heimdall score reads them")
    numbers.add_argument("rest", nargs="*", help=argparse.SUPPRESS)       # what it took, so any old line stops with the message
    numbers.add_argument("--sets", dest="draw_sets", help=argparse.SUPPRESS)
    numbers.add_argument("--set", action="append", default=[], help=argparse.SUPPRESS)
    numbers.add_argument("--across", action="store_true", help=argparse.SUPPRESS)

    scored = commands.add_parser("score", help="a Run's standings, marginals and baseline from its statistics.csv, drawing nothing")
    scored.add_argument("target", help="a Run <A>/<E>/<R>, or <A>/<E>: a row for each of its Runs (their score over the pages "
                                       "they share); with --across, the errand's own results folder")
    scored.add_argument("--set", metavar="SET", dest="set_name", help="this set's statistics only (default: every set found)")
    scored.add_argument("--across", action="store_true", help="the errand's own statistics (its Runs together, heimdall plot --across)")
    scored.add_argument("--by", metavar="AXES", help="marginals by these axes (comma-separated), over the table's own [score].by")
    scored.add_argument("--baseline", metavar="FILTER",
                        help="deltas against a baseline: axis=tag[,axis=tag…], or a point's name, over the table's own")
    scored.add_argument("--json", action="store_true", help="the same numbers as JSON")

    overlay = commands.add_parser("overlay", help="overlay any YODA/ROOT files through Paint, with no errand file")
    overlay.add_argument("files", nargs="+", metavar="FILE", help="YODA (.yoda, .yoda.gz) or ROOT files")
    overlay.add_argument("-o", "--output", help="where the pages go (default results/plots/<first file>)")
    overlay.add_argument("--labels", help="legend labels, comma-separated, one per file")
    overlay.add_argument("--objects", nargs="+", default=[], metavar="GLOB", help="only these YODA paths")
    overlay.add_argument("--formats", default="pdf,png", help="pdf, png, svg, eps (default pdf,png)")
    overlay.add_argument("--ratio", action="store_true", help="a ratio panel against the first curve")
    overlay.add_argument("--style", metavar="FILE", help="a style file over src/Apps/Paint/base.toml")

    deck = commands.add_parser("deck", help="retired: heimdall report makes a report of Runs' pages and numbers")
    deck.add_argument("rest", nargs="*", help=argparse.SUPPRESS)          # what it took, so any old line stops with the message
    deck.add_argument("--list", "--dry-run", dest="list", action="store_true", help=argparse.SUPPRESS)
    deck.add_argument("--only", help=argparse.SUPPRESS)
    deck.add_argument("--init", action="store_true", help=argparse.SUPPRESS)

    reported = commands.add_parser("report", help="a quick report of Runs' pages and numbers, built only when asked into "
                                                  "reports/, where results/ has its sources (a folder's: its report.toml)")
    reported.add_argument("names", nargs="*", metavar="RECIPE.toml|SOURCE",
                          help="sources alone: one folder's report.toml (else the default report), or the default over several: "
                               "<A>/<E>/<R>, <A>/<E>, a path or a glob; or a recipe first, always named .toml (<A>/<E>.toml "
                               "under configs/, ./… or /…: a recipe of its own, an errand file's [report], a report.toml), "
                               "then its sources, which replace its [report].from")
    reported.add_argument("--list", "--dry-run", dest="list", action="store_true",
                          help="its sources, sections and figures, each copied or drawn for the report; nothing written")
    reported.add_argument("--init", metavar="SOURCE", help="write the recipe RECIPE.toml (<A>/<E>.toml) once: SOURCE's sets and "
                                                           "pages, listed")
    reported.add_argument("-o", "--output", metavar="DIR", help="build into DIR (default: its recipe's [report].output, "
                                                                "else reports/<A>/<E>/<R>/ as results/ has its sources)")

    listing = commands.add_parser("ls", help="every config and its configurations")
    listing.add_argument("assignment", nargs="?", help="only this assignment's errand files")

    explain = commands.add_parser("explain", help="a key of an errand file: its type, default and meaning (the schema's)")
    explain.add_argument("key", help="e.g. plot.y_gutter, errand.events, cfgs.pdf.threads, quantities.<q>.points, rivet.analyses")

    commands.add_parser("context", help="what an AI working in a work dir needs first: the model, a whole errand file, commands, where to read more")

    documents = commands.add_parser("docs", help="the docs as one searchable page: settings, pages by reader, their graph")
    documents.add_argument("--drift", action="store_true", help="instead: pages whose code changed since the docs were last "
                                                                "crystallised, with no live doc naming them")
    documents.add_argument("--no-open", action="store_true", help="build it and print where, without opening a browser")

    state = commands.add_parser("status", help="each configuration's points: complete, stale, running, failed or stopped "
                                                "(when, and why), incomplete or to run; its events, seeds and tools")
    state.add_argument("config", nargs="?", help="one config, or a record <A>/<E>/<R> (default: every config)")
    state.add_argument("configuration", nargs="?", help="one configuration of it")
    state.add_argument("--set", metavar="KEY=VALUE", action="append", default=[], help="as heimdall run's, for the view")
    state.add_argument("--stack", action="store_true", help="the loaded stack instead: each package installed, its release and state; the libraries' versions")

    recs = commands.add_parser("records", help="the record files: `records upgrade` brings them to today's format (a backup of each beside it)")
    recs.add_argument("action", choices=["upgrade"], help="upgrade: add `format` to points.json, provenance.json, identity.json and plot.toml that lack it")
    recs.add_argument("scope", nargs="?", default="", metavar="A[/E[/R]]", help="only this Assignment, Errand or Run (default: every record)")
    recs.add_argument("--dry-run", action="store_true", help="list what it would do, change nothing")
    move = commands.add_parser("migrate", help="rewrite errand files and their cards in today's forms (a diff, or --apply)")
    move.add_argument("configs", nargs="*", metavar="CONFIG", help="configs to migrate (default: every config)")
    move.add_argument("--v3", action="store_true", help="into the errand file's third form (docs/stable/guide/errand-file.md, runner/v3.py)")
    move.add_argument("--layout", action="store_true",
                      help="move the work dir's older layouts into today's: logs/ into records/<A>/<E>/<R>/logs/, points into "
                           "points/ (and output/ first, if any); no configs are read")
    move.add_argument("--list", action="store_true", help="with --layout: every move, one a line")
    move.add_argument("--names", action="store_true",
                      help="a work dir from before Heimdall's names moved: hep → heimdall (its marker hep.toml → "
                           "heimdall.toml, the old names in its own files: configs, modules, Makefile, editor settings) and "
                           "[run] → [errand], [run].project → [errand].assignment (its configs, its records' snapshots, its "
                           "plot documents' [source])")
    move.add_argument("--snapshot", metavar="RECORD",
                      help="give a record that ran before snapshots one: copy a config's files into <record>/config/ "
                           "(--from, default the config its points.json names) and say which points it gives the same identity")
    move.add_argument("--plot-docs", nargs="*", metavar="RECORD",
                      help="write the plot document (results/<A>/<E>/<R>/plot.toml) of every record without one, or of these "
                           "(<A>/<E>/<R>), from its snapshot (else the config its points.json names)")
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

    check = commands.add_parser("check", help="check errand files: every configuration loaded, validated and planned")
    check.add_argument("configs", nargs="*", metavar="CONFIG",
                       help="configs to check (default: every configs/<A>/*.toml with an [errand])")
    check.add_argument("--set", metavar="KEY=VALUE", action="append", default=[], help="as heimdall run's: check what that job would")

    watch = commands.add_parser("watch", help="attach the live view to a running job")
    watch.add_argument("config", nargs="?", help="the errand file whose job to watch (default: the latest job)")
    watch.add_argument("configuration", nargs="?", help="overrides [errand].configuration (or the sweep's latest)")
    watch.add_argument("--plain", action="store_true", help="plain lines instead of the live view")
    watch.add_argument("--file", metavar="EVENTS.JSONL",
                       help="follow a Run's run.jsonl, or a --journal job's status.jsonl, instead")
    watch.add_argument("--pid", type=int, metavar="N", help="the job of this process (heimdall runs lists them)")
    watch.add_argument("-i", "--index", type=int, metavar="N", help="the live job [N] of heimdall runs (not a paused one)")

    listed = commands.add_parser("runs", allow_abbrev=False,       # --1 is no --10
                                 help="live jobs (running and paused), each with its index [N]; with --5, --10, --20 or --50 "
                                      "the latest jobs, with --week or --month jobs of the last 7 or 28 days")
    run_limits = listed.add_mutually_exclusive_group()
    for limit in (5, 10, 20, 50):
        run_limits.add_argument(f"--{limit}", dest="limit", action="store_const", const=limit,
                                help=f"show the latest {limit} jobs, including ended ones")
    run_limits.add_argument("--week", dest="days", action="store_const", const=7,
                            help="show all jobs from the last 7 days")
    run_limits.add_argument("--month", dest="days", action="store_const", const=28,
                            help="show all jobs from the last 28 days")
    run_limits.add_argument("--resume", type=int, metavar="N",
                            help="resume the paused job [N]: its own command again, detached, in its work dir and "
                                 "checkout (its complete points skipped)")
    run_limits.add_argument("--forget", metavar="N|ID",
                            help="drop the paused job [N] from the live list (its entry is kept); a queued or held one leaves "
                                 "its queue unrun, the run after it queued to the one before it")
    run_limits.add_argument("--dispatch", metavar="ID|N",
                            help="start a queued or held run now, before its turn: it heads a queue of its own, the runs "
                                 "after it following it")
    run_limits.add_argument("--again", metavar="ID|N",
                            help="run a failed, stopped or lost run's own command again, detached, from its records' "
                                 "config snapshot (its complete points skipped); not a running or paused one")
    run_limits.add_argument("-i", "--index", metavar="N|ID",
                            help="the run [N] of the live list (or an id): its block, and on a terminal a prompt of what "
                                 "to do with it: watch, stop, resume, run again, forget (the word typed to confirm)")
    listed.add_argument("--jobs", type=int, metavar="M",
                        help="with -i N: change the running job's points at once to M, while it runs (never stops a running "
                             "point; lowering waits for them to end)")
    listed.add_argument("--state", metavar="S[,S]", help="only the runs in these states: " + ", ".join(runs.STATES))
    listed.add_argument("--plain", action="store_true", help="no colour or links")

    tagged = commands.add_parser("tag", help="a Run's tag and labels: show them, set them (word, or key=value; key= removes), or --clear them")
    tagged.add_argument("target", metavar="RECORD", help="a Run, <A>/<E>/<R>, or a path under records/ or results/")
    tagged.add_argument("words", nargs="*", metavar="WORD", help="a tag to give it (a letter or digit, then letters, digits, . _ + -, at most 40), "
                                                                 "or key=value: a label an across page can draw as @key (key= removes it)")
    tagged.add_argument("--clear", action="store_true", help="remove its tag and labels")

    logged = commands.add_parser("log", help="a record's own account, a point's attempts and logs, or a tool's log")
    record_options(logged, "a record, <A>/<E>/<R>, then a point and a tool, or a path under records/")

    shown = commands.add_parser("show", help="what a Run, a point or a tool did, read from its record: identity, seed, tools, "
                                              "cross section, products, attempts")
    record_options(shown, "a Run, <A>/<E>/<R>, then a point and a tool, or a path under records/", own=lambda p: (
        p.add_argument("--parts", action="store_true", help="a point's identity parts too (what its identity hashes)"),
        p.add_argument("--json", action="store_true", help="the view as JSON"),
        p.add_argument("--log", action="store_true", help="the logs, as heimdall log prints them (--full and --attempt imply it)")))

    pool = commands.add_parser("library", help="the points library: list its points, verify them, prune the unlinked, adopt a Run's points")
    pool.add_argument("action", choices=["list", "verify", "prune", "adopt"],
                      help="list: its points and who links them; verify: complete for their keys, links resolve (reports only); "
                           "prune: the unlinked points (a dry run unless --yes); adopt: a Run's complete points into it (a dry run unless --yes)")
    pool.add_argument("scope", nargs="?", default="", metavar="A | A/E/R",
                      help="an Assignment (list, verify, prune: default every one), or for adopt the Run <A>/<E>/<R>")
    pool.add_argument("--yes", action="store_true", help="prune and adopt: do it (without it they only say what they would do)")
    pool.add_argument("--dry-run", action="store_true", help="prune and adopt: say what they would do (the default)")
    pool.add_argument("--duplicates", action="store_true", help="prune: also the <name>.adopted-duplicate folders adopt kept")

    compared = commands.add_parser("diff", help="what two Runs of one Errand did differently: the config each ran with, and each "
                                                 "point's identity parts, tool by tool")
    compared.add_argument("first", metavar="RUN", help="a Run, <A>/<E>/<R1>")
    compared.add_argument("second", metavar="RUN", help="the other Run of it: <A>/<E>/<R2>, or its folder <R2> alone")
    compared.add_argument("--points", metavar="SEL", help="these points only (names or globs, comma-separated)")
    compared.add_argument("--full", action="store_true", help="every line of a file's or a point's difference")
    compared.add_argument("--json", action="store_true", help="the same as JSON")

    stop = commands.add_parser("stop", help="stop a running job as Ctrl-C would: its points end cleanly, a rerun resumes "
                                            "(a second stop kills its tools at once)")
    stop.add_argument("config", nargs="?", help="the errand file whose job to stop (default: your only running job)")
    stop.add_argument("configuration", nargs="?", help="the configuration it runs")
    stop.add_argument("--pid", type=int, metavar="N", help="the job of this process (heimdall runs lists them)")
    stop.add_argument("-i", "--index", type=int, metavar="N", help="the live job [N] of heimdall runs (a running one)")
    stop.add_argument("--no-wait", action="store_true", help="ask it to stop and return, without waiting for it to end")

    batch = commands.add_parser("cluster", help="run a configuration as Slurm jobs (sbatch): a pre job, a point per array task, a finish job")
    batch.add_argument("config", help="the errand file, as heimdall run names it")
    batch.add_argument("configuration", nargs="?", help="overrides [errand].configuration; under [errand].sweep_runs, submits only it")
    batch.add_argument("--points", metavar="SEL", help="submit a subset: tags, indices or quantity=tag")
    batch.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                       help="override one value for this submission (repeatable; cluster.time=… too); the jobs get it")
    batch.add_argument("--keep", action="append", default=[], metavar="WHAT",
                       help="what each job also keeps (as heimdall run --keep)")
    batch.add_argument("--rerun", action="store_true", help="submit complete points too, and rerun them")
    what = batch.add_mutually_exclusive_group()
    what.add_argument("--dry-run", action="store_true", help="write the job scripts and print the sbatch lines; submit nothing")
    what.add_argument("--status", action="store_true", help="the latest submission: each point's state (sacct, squeue)")
    what.add_argument("--cancel", action="store_true", help="scancel the latest submission's jobs")

    make = commands.add_parser("setup", help="make a work dir: the key folders, heimdall.toml and the template's files (never overwrites)")
    make.add_argument("dir", help="the work dir's folder: new, empty, or a work dir to complete")
    make.add_argument("--assignment", metavar="A", help="also configs/<A>/ with a starter errand file and card, and modules/<A>/")
    make.add_argument("--project", dest="old_project", metavar="P", help=argparse.SUPPRESS)    # --assignment, said
    make.add_argument("--git", nargs="?", const="yes", choices=["yes", "new"],
                      help="commit what was added (only that), in the git repository the folder is in, or a new one "
                           "when it is in none; --git=new: a repository of its own even inside another")
    make.add_argument("--adopt", action="store_true", help="make a work dir of a folder that has files but no heimdall.toml")
    make.add_argument("--name", help="the work dir's name in heimdall.toml (default: the folder's)")
    make.add_argument("--example", metavar="NAME", help="also a working example assignment to run first: jets "
                                                        "(the guide's Demo assignment: Pythia → Rivet → pages against ZEUS data)")
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

    folders_ = commands.add_parser("tools", help="every tool folder: the work dir's tools/, Himinbjorg's, Heimdall's",
                                   description="Each tool folder by name, nearest first: a work dir's tools/<name>/, the "
                                               "Himinbjorg's tools/<name>/, Heimdall's framework/tools/<name>/. A nearer "
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
                       ("cd", "cd to a work dir's folder: heimdall cd ASSIGNMENT [configs|modules|results|records|logs]")):
        commands.add_parser(verb, help=f"{what} (gjallarhorn.sh's shell function)", add_help=False)

    known = commands.add_parser("recognise", help="record work dirs by title, in Himinbjorg's workdirs.toml "
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
                                 description="Added packages are recorded in Himinbjorg's machine.toml "
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

    images = commands.add_parser("image", help="Apptainer images of Heimdall and a Himinbjorg: list them, or build one",
                                 description="An image holds a clean copy of this Heimdall and a Himinbjorg built "
                                             "inside it; it lives in Himinbjorg's images/. The runtime is the "
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
    errand: configmod.Errand
    configuration: configmod.Configuration
    every: list                                    # every point's plan
    plans: list                                    # the points to run (--points)
    post: object                                   # the post stage's plan, or None
    pre: object                                    # the pre stage's plan, or None
    combined: list                                 # the combined groups (V35)


def build_plans(args, key: str | None) -> Planned:
    errand, configuration = configmod.for_configuration(configmod.load(args.config, sets=args.set), key)   # V179
    plot.validate(errand)                    # before anything is planned (V54): a [plot] typo costs no planning
    master = load_master(errand.assignment, errand.master_toml, errand.folder)
    points = sweep.points(errand, configuration)
    chosen = {p.index for p in sweep.select_points(errand, configuration, points, args.points)}
    if configuration.serial_auto:
        pre_plan, plans = _numbered(errand, configuration, master, points)
    else:
        pre_plan, plans = _planned_points(errand, configuration, master, points)
    again = getattr(args, "rerun", False) and getattr(args, "only", None) is None   # the points run anew
    record.assign_seeds(plans, frozenset(p.point.name for p in plans if again and p.point.index in chosen
                                         and record.stale(p, args.rerun)))
    for plan in plans:
        tools.finalise(plan, plan.seed)
        tools.check_cards(plan)                  # the tools read their cards (V59), cached by text
    if configuration.parallelism_auto:           # "auto" (V75): from the plans' cores
        configuration.parallelism = execute.auto_parallelism(plans)
    plot.check_texts(errand, plans)              # a placeholder typo costs no point run (V66) …
    plot.check_figures(errand, configuration)    # … nor a band's (V69), nor what a figure merges (V82)
    return Planned(errand, configuration, plans, [p for p in plans if p.point.index in chosen],
                   post.plan(errand, configuration, master, plans), pre_plan,
                   post.plan_combined(errand, configuration, master, plans))


def _planned_points(errand, configuration, master, points):
    """The pre stage and every point, planned in the configuration's folder, with their identities."""
    pre_plan = post.plan_pre(errand, configuration, master, points)
    plans = []
    for point in points:
        plan = tools.plan_point(errand, configuration, point, master, pre=pre_plan)
        plan.identity = record.identity(plan)
        if configuration.library:                # the points library (points-library P4): the key it pools the point by
            plan.library = library.key(plan)
        plans.append(plan)
    return pre_plan, plans


def _numbered(errand, configuration, master, points):
    """A v3 configuration without a serial (doc:errand-file): the runner numbers its folder. The newest folder its
    points completed in as it stands now (an older one, when a change was undone); else the newest, when
    nothing in it was made from other inputs (a run under way, or one never begun); else a new number,
    so that a change never overwrites what was made."""
    taken = tools.serials_taken(errand, configuration)
    newest = None
    for number in sorted(taken, reverse=True):
        configuration.serial = number
        pre_plan, plans = _planned_points(errand, configuration, master, points)
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
    return _planned_points(errand, configuration, master, points)


def overwrites(planned: Planned, stages=None) -> list:
    """What running would replace that was made from other inputs, under a serial the file sets (v3,
    doc:errand-file): the pre stage and the chosen points, as the stages run them."""
    if planned.errand.form != 3 or planned.configuration.serial_auto:
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
        where = c.origins.get("serial", "[errand]").replace("[errand.cfgs.", "[cfgs.")   # a v3 file: its own names
        raise HeimdallError(f"configuration '{c.key}': {len(changed)} of its points in {tools.run_dir(planned.errand, c)} were "
                       f"made from other inputs ({names}); running would overwrite them",
                       where=f"{planned.errand.path}: {where}",
                       hint=f"serial = {c.serial + 1} gives a fresh folder; or leave serial out and the runner numbers it; "
                            f"--rerun replaces them; --why says what changed")


def write_documents(errand, configuration, members: list, say=print) -> tuple[Path | None, list[str]]:
    """A folder's plot document (plotdoc.write, V165) and beside it its report's recipe, report.toml (V209): the run
    TOML's [report], else the default report, written again each time. Its failure is said, never the run's."""
    target, notes = plotdoc.write(errand, configuration, members)
    if target is not None:
        _write_recipe(errand, target, say)
    return target, notes


def _write_recipe(errand, target: Path, say) -> None:
    from . import report as reportmod
    try:
        reportmod.write_recipe(errand, target)
    except (HeimdallError, OSError) as error:
        say(f"report: {target.with_name(reportmod.RECIPE)} not written: {getattr(error, 'message', error)}")


def draw_run(errand, configuration, members: list, say, draw: bool = True, stats=True) -> int:
    """A run's plot stage (V165): its plot document written, results/<A>/<E>/<R>/plot.toml (what the run knows
    rewritten, the user's [plot] and [stats] kept), then its pages drawn from that document alone, as
    `heimdall plot` draws them, and their statistics (V168: `stats` true, false or the sets measured); with
    `draw` false, the statistics alone. The pages that failed."""
    target, notes = write_documents(errand, configuration, members, say)
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


def journal_path(errand, configuration) -> Path:
    """records/<A>/<E>/<R>/status.jsonl: a --journal run's events, which heimdall watch --file follows."""
    return tools.run_folders(errand, configuration).journal


def header(number: int, configuration) -> str:
    """'run 02 - Beam energies -': a run's place in a sweep of runs, and its title (V38)."""
    return f"run {number:02d} - {configuration.title} -"


def _print_stage(title: str, stage, errand) -> None:
    print(f"{title}   identity {stage.identity[:12]}")
    for line in tools.describe(stage, errand)[1:]:
        print(line)
    print(f"  results {stage.res}   ({'complete' if record.is_complete(stage) else 'to run'})")


def run_title(errand, configuration, plans, tag: str | None = None) -> str:
    """A run's title, two lines (the user's form, 2026-10-26):

        zeus_validation · 12  ·  generator_pdf [nlo]
           - 16 point(s), 1000000 events, 1 threads, 19 at once (~38 of 24 cores)

    the run's name, its record's serial (none when the folder has none) and the configuration, with its tag when
    it has one; then its size."""
    serial = re.match(r"(\d+)_", tools.run_dir(errand, configuration).name)
    head = f"{errand.name} · {serial.group(1)}  ·  {configuration.key}" if serial else f"{errand.name}  ·  {configuration.key}"
    head += f" [{tag}]" if tag else ""
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


def totality_pages(errand, configuration, points: list) -> tuple[int, str]:
    """The pages per object the totality set draws (V195: its own axes, not plot_points'), and what other sets
    the configuration draws, for --plan's plot line."""
    try:
        spec = sweep.set_entries({sweep.TOTALITY: sweep.totality(configuration, points)}, sweep.TOTALITY)[0]
        count = len(sweep.set_cells(errand, points, spec)[0])
    except Exception:                    # a count never stops a plan (listed points' KeyError): plot_points'
        count = len(sweep.pages(configuration, points))
    drawn = configuration.draw
    others = ([s for s in drawn if s != sweep.TOTALITY] if isinstance(drawn, list)
              else [s for s in (errand.plot or {}).get("sets", {}) if s != sweep.TOTALITY] if drawn else [])
    return count, f", and {len(others)} more set(s) ({', '.join(others)})" if others else ""


def print_plan(errand, configuration, plans, post_plan=None, pre_plan=None, combined=(), tag=(None, "")) -> None:
    print(f"run {errand.name} ({errand.path}) · configuration {configuration.key}: {len(plans)} point(s), "
          f"{configuration.event_count} events, {configuration.threads} threads" + parallel_note(configuration, plans))
    if tag[0]:
        print(f"tag: {tag[0]} ({tag[1]})")
    if crowded(configuration, plans):
        print(f"note: {crowded(configuration, plans)}")
    for note in notes_of(plans):
        print(f"note: {note}")
    for warning in tools.meta_notes(errand):                    # V97
        print(f"warning: {warning}")
    if configuration.serial_note:
        print(f"note: {configuration.serial_note} (no serial set: the runner numbers the folder)")
    if errand.form == 3 and not configuration.serial_auto:
        changed = record.overwritten([s for s in (pre_plan, *plans) if s is not None])
        if changed:
            print(f"warning: {len(changed)} of these were made from other inputs: running refuses to overwrite them "
                  f"(serial = {configuration.serial + 1}, or --rerun)")
    if configuration.seed_type != "identity":
        print(f"seeds: {configuration.seed_type}")
    if configuration.manual_seed is not None and configuration.seed_type != "manual":
        print(f"note: manual_seed = {configuration.manual_seed} is unused: seed_type is '{configuration.seed_type}'")
    if pre_plan is not None:
        _print_stage("pre (before every point)", pre_plan, errand)
    for plan in plans:
        state = "complete" if record.is_complete(plan) else "to run"
        if plan.library:
            state += f"; library {plan.library[:16]}" + (f", first by {first}" if (first := library.first(plan)) else "")
        for line in tools.describe(plan, errand):
            print(line)
        print(f"  output  {plan.out}\n  results {plan.res}   ({state})")
    for group in combined:
        _print_stage(f"combined {group.point.name} (merges {len(group.upstream)} points: "
                     f"{', '.join(configuration.combine)})", group, errand)
    if post_plan is not None:
        _print_stage("post (after every point)", post_plan, errand)
    if errand.plot and plans:
        count, more = totality_pages(errand, configuration, [p.point for p in plans])
        print(f"plot ({', '.join(plot.backends(errand.plot))}): {count} page(s) per object in totality{more}, "
              f"{', '.join(plot.formats_of(errand.plot))} → {plans[0].folders.plots}")


def print_why(errand, configuration, plans, post_plan=None, pre_plan=None, combined=()) -> None:
    """--why (V57): each point and stage that would run, and what changed since it last completed."""
    stages = [*([pre_plan] if pre_plan else []), *plans, *combined, *([post_plan] if post_plan else [])]
    todo = [p for p in stages if not record.is_complete(p)]
    print(f"run {errand.name} · configuration {configuration.key}: {len(todo)} of {len(stages)} to run")
    for plan in stages:
        if plan.library and record.is_complete(plan):
            print(f"{plan.point.name}   from the library (first by {library.first(plan) or '?'})")
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
    output at /dev/null; a SIGHUP ignored when the run began (nohup) stays ignored. After a pause the
    first is a stop, as ever, recorded so: after a force pause (already hard) it does not kill the run, the next
    does. Returns the handlers it replaced."""
    def on_signal(signum, frame):
        if signum == signal.SIGHUP:
            _quiet()
        if stopper.hard and not stopper.paused:
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)
            return
        stopper.hard = stopper.requested
        stopper.requested = True
        stopper.paused = False

    previous = {}
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        if signum == signal.SIGHUP and signal.getsignal(signum) is signal.SIG_IGN:
            continue
        previous[signum] = signal.signal(signum, on_signal)
    return previous


def catch_pause(stopper: execute.Stopper):
    """SIGUSR1, a `p` in a watch or in the run's own view: the first a pause (`pausing`: no point, stage
    or run is begun any more, the running points run to their end, then the run quits without its later stages,
    exit 6, recorded paused); the second a force pause (`requested` and `hard`, as a hard stop: the running
    points' tools killed at once, recorded stopped, their partial outputs kept; the run still paused). A stop
    stays a stop. Returns the handler it replaced."""
    def on_pause(signum, frame):
        if stopper.requested and not stopper.paused:
            return
        if stopper.pausing:
            stopper.requested = stopper.hard = True
        stopper.pausing = stopper.paused = True

    return signal.signal(signal.SIGUSR1, on_pause)


def catch_control(stopper: execute.Stopper) -> None:
    """SIGUSR2, a `heimdall runs -i N --jobs M`: the control file is to be read. The handler only says so
    (`stopper.control`); `control_thread` does the rest, never inside a handler (the bus has locks)."""
    signal.signal(signal.SIGUSR2, lambda signum, frame: stopper.control.set())


def apply_control(stopper: execute.Stopper, run_id: str, bus, recorder) -> None:
    """The request `runs/<id>.control.json` holds, applied: the cap changes (execute.Stopper.set_parallelism), the entry
    says it, `run.jsonl` and the views hear a `parallelism` event. A missing or bad file is ignored with a note in the
    log, and a cap above the ceiling is refused."""
    try:
        request = runs.read_control(run_id)
    except ValueError as error:
        bus.say(f"   note: a --jobs request was ignored: {error}")
        return
    count = request["parallelism"]
    if count > execute.Stopper.CEILING:
        bus.say(f"   note: a --jobs request was ignored: {count} is more than the {execute.Stopper.CEILING} at once it can take")
        return
    before = recorder.parallelism if recorder is not None else stopper.parallelism
    stopper.set_parallelism(count)
    if recorder is not None:
        recorder.set_parallelism(count)
    bus.emit("", "", {"k": "parallelism", "from": before, "to": count, **({"by": request["by"]} if request.get("by") else {})})


def control_thread(stopper: execute.Stopper, run_id: str, bus, recorder) -> threading.Thread:
    """A daemon thread that applies a control request each time SIGUSR2 sets `stopper.control` (one that came before it
    started is waiting)."""
    def loop() -> None:
        while True:
            stopper.control.wait()
            stopper.control.clear()
            try:
                apply_control(stopper, run_id, bus, recorder)
            except Exception as error:                      # never the run's end
                bus.say(f"   note: a --jobs request failed: {error}")

    thread = threading.Thread(target=loop, name="heimdall-control", daemon=True)
    thread.start()
    return thread


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
    """A record named where a config goes (V158): `heimdall run|plot|status <A>/<E>/<R>`, or a path into
    records/ or results/. Its snapshot is read: its config, its configuration, its --set overrides (yours after
    them), with configs/ at records/<A>/<E>/<R>/config/ for the command, so its imports and cards are the ones it
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


def run_tag(args, errand, configuration) -> tuple[str | None, str]:
    """A run's tag (V223) and where it comes from: --tag, else the one its folder's record has (a folder run again
    keeps what heimdall tag gave it), else its configuration's `tag` key; (None, "") for none."""
    if getattr(args, "tag", None):
        return args.tag, "--tag"
    if (kept := record.run_tag(tools.run_folders(errand, configuration).record)) is not None:
        return kept or None, "its folder's"                    # "": cleared by heimdall tag, the key no more
    if configuration.tag:
        origin = configuration.origins.get("tag", "the configuration")
        return configuration.tag, (origin.replace(f"[errand.{configmod.CFGS}.", "[cfgs.") if errand.form == 3 else origin)
    return None, ""


def give_tag(args, errand, configuration) -> str | None:
    """The run's tag written into its folder's record (records/<A>/<E>/<R>/tag), the plot document's [source].tag
    being written from it; nothing for an untagged run."""
    tag, _ = run_tag(args, errand, configuration)
    folders = tools.run_folders(errand, configuration)
    if tag and tag != record.run_tag(folders.record):
        record.write_run_tag(folders.record, tag)
        if (document := plotdoc.path_of(folders.results)).is_file():
            plotdoc.write_tag(document, tag, record.run_labels(folders.record))       # drawn across before its plot stage: the new tag
    return tag


def cmd_run(args) -> int:
    """One run; or, under [errand].sweep_runs, every swept configuration as a run of its own, one after
    another (V38). Each is exactly `heimdall run CONFIG <cfg>`, after a `run NN - <title> -` line. All are
    planned before the first starts, so a config error anywhere exits 2 with nothing run; one is
    planned again at its turn only if the TOML was edited meanwhile, so edits still count. A failed run leaves the next to
    start; a stop or a pause starts no more. On a terminal, and with --detach, the run is a worker of its own, which
    this process follows (or leaves) (V183)."""
    worker = getattr(args, "worker", None)
    if getattr(args, "rerun_since", None):                  # a resumed --rerun job: its points since kept
        args.rerun = args.rerun_since
    resumes = os.environ.pop(runs.RESUMES_VAR, "") if worker else ""
    try:
        return _cmd_run(args, worker)
    except HeimdallError:                    # it never ran: the pause it resumed stays live
        if resumes:
            runs.update(resumes, resumed_by=None, resumed=None)
        raise


def _cmd_run(args, worker) -> int:
    stopper = execute.Stopper()
    if worker:
        _worker_signals()
        catch_pause(stopper)                # a p while the worker plans: a pause, never SIGUSR1's default death
        catch_control(stopper)              # a --jobs likewise: never SIGUSR2's
    _ask_keep(args)
    if getattr(args, "tag", None) is not None:              # refused here, before a worker is started
        configmod.check_tag(args.tag, "--tag")
    errand = configmod.load(args.config, sets=args.set)
    keys = errand.runs(args.configuration)
    if getattr(args, "sweep_member", None):                 # one configuration of a sweep's chain (queue_sweep)
        keys = [args.sweep_member]
    nothing_runs = getattr(args, "why", False) or args.plan or stages_of(args) == {"plot"} \
        or getattr(args, "show_config", False)
    if getattr(args, "queued_to", None) and not worker:
        return queue_run(args, errand, keys, nothing_runs)
    if getattr(args, "detach", False) and not worker:
        if nothing_runs:
            raise HeimdallError("--detach starts a job in the background, and --plan, --why, --show-config and --only plot run "
                           "nothing", hint="leave --detach out")
        if os.environ.get("SLURM_JOB_ID") or runs.cluster_job():
            raise HeimdallError("--detach in a Slurm job: its processes end with the job's allocation",
                           hint="heimdall cluster submits it as Slurm jobs; or run it here without --detach")
        return queue_sweep(args, errand, keys, None, attach=False) if len(keys) > 1 \
            else background(args, errand, keys, attach=False)
    if not worker and not nothing_runs and live(args):
        return queue_sweep(args, errand, keys, None, attach=True) if len(keys) > 1 \
            else background(args, errand, keys, attach=True)
    if getattr(args, "show_config", False):
        for line in show_config(errand, keys):
            print(line)
        return 0
    if getattr(args, "why", False) or args.plan or stages_of(args) == {"plot"}:
        bus, recorder = None, None           # nothing runs: nothing to watch
    else:                                    # one stream for the whole process, served while it lives (V72)
        catch_pause(stopper)
        catch_control(stopper)
        bus = Bus()
        worker = getattr(args, "worker", None)
        opened = runs.log_of(worker) if worker else None    # the log its parent opened, wherever it is
        log = str(opened) if opened else None
        work = find_work()
        configuration_serials = {key: errand.configurations[key].serial for key in keys}
        fields = {"config": str(errand.path), "run": errand.name, "configurations": keys, "argv": getattr(args, "argv", []),
                  "configuration_serials": configuration_serials,
                  "points_completed": 0, "points_total": None, "active_parallel_points": 0,
                  "work": str(work) if work else None, "checkout": str(paths.heimdall_root()), "detached": bool(worker), "log": log}
        if worker and getattr(args, "queued_to", None):     # its turn first: then the run, its entry the same
            fields.update(wait_turn(worker, args.queued_to, fields))
            if fields.get("verdict"):
                return int(fields["code"])
        entry = runs.begin(worker or runs.new_id(), fields)  # the registry (V182): nothing on a read-only root
        hub = Hub({"config": str(errand.path), "run": errand.name, "configurations": keys, "id": entry, "log": log,
                   "configuration_serials": configuration_serials,
                   "work": str(work) if work else None, "detached": bool(worker)})
        recorder = runs.Recorder(
            entry,
            configuration_serials,
            {key: errand.configurations[key].label for key in keys},
        )
        bus.subscribe(hub)
        bus.subscribe(recorder)
        if entry:
            control_thread(stopper, entry, bus, recorder)
    code, crashed = 2, None
    try:
        try:
            code = _runs(args, errand, keys, stopper, bus, recorder=recorder)
        except HeimdallError as error:            # what main() prints, for a watcher too (V181)
            if bus is not None:
                bus.say(error.render())
            raise
        except KeyboardInterrupt:
            code, stopper.paused = 6, False
            raise
        except Exception as error:           # the runner itself failed: said, and recorded
            crashed = f"the runner failed: {type(error).__name__}: {error}"
            if bus is not None:
                bus.say(crashed + (f" (its log: {log})" if log else ""))
            raise
        return code
    finally:
        if bus is not None:
            paused = code == 6 and stopper.paused and crashed is None
            runs.finish(entry, code, crashed, state="paused" if paused else None,
                        **{**recorder.close(), "records": recorder.records, "verdicts": recorder.verdicts,
                           "counts": recorder.counts()})                                     # before the
            hub.close()                                                                              # stream ends
            notify(errand, code, paused)
            following = [e.id for e in runs.entries() if entry and e.queued_to == entry and e.queued]
            if following:
                print(f"queue: {', '.join(following)} " + ("held: this run was stopped" if code == 6 and not paused
                      else "waits: this run is paused" if paused else "starts now"), flush=True)


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


def _with_option(argv: list[str], flag: str, value: str | None) -> list[str]:
    """`argv` with `flag`'s value replaced by `value` (`--flag X` or `--flag=X`), or the flag removed when None, or
    added when it is not there."""
    out, skip, found = [], False, False
    for arg in argv:
        if skip:
            skip = False
            continue
        if arg == flag or arg.startswith(flag + "="):
            skip, found = arg == flag, True
            if value is not None:
                out += [flag, value]
            continue
        out.append(arg)
    return out if found or value is None else [*out, flag, value]


def queue_run(args, errand, keys: list[str], nothing_runs: bool) -> int:
    """`heimdall run CONFIG [cfg] --queued-to ID|N`: the run checked now (a config error refuses it), then started
    detached as a worker that waits for that run to end (wait_turn). Refused after a run that ended (it would start at
    once: run it so) and after a cluster submission."""
    if nothing_runs:
        raise HeimdallError("--queued-to queues a run, and --plan, --why, --show-config and --only plot run nothing",
                            hint="leave --queued-to out")
    target, state, number = entry_of(args.queued_to)
    shown = f"[{number}] {target.id}" if number else target.id
    if target.cluster:
        raise HeimdallError(f"{shown} is a cluster submission: a run here is not queued to Slurm's jobs")
    if target.finished is not None and not runs.paused(target) or state.word == "lost":
        raise HeimdallError(f"{shown} has ended ({state}): a run queued to it would start at once",
                            hint="run it now: leave --queued-to out")
    if len(keys) > 1:                                       # a sweep: its chain, its head queued to that run
        return queue_sweep(args, errand, keys, target.id, attach=False)
    for key in keys:                                        # a config error now, not at its turn
        build_plans(args, key)
    run_id = runs.new_id()
    argv = _with_option(_with_option(list(getattr(args, "argv", [])), "--queued-to", target.id), "--detach", None)
    log = runs.log_file(run_id)
    proc = runs.spawn(argv, run_id, log)
    failed = _begun(proc, run_id, log, lambda e: e is not None and e.queued, queued=True)
    if failed is not None:
        return failed
    print(f"queued: {errand.name} · {', '.join(keys)} ({run_id}, pid {proc.pid}), after {shown}\n"
          f"  heimdall runs lists the queue · heimdall runs --dispatch {run_id} starts it now\n  log {log}")
    return 0


def _begun(proc, run_id: str, log: Path, ready, *, queued: bool) -> int | None:
    """None once a spawned worker's entry has begun (`ready(entry)`); else, once it has ended by itself or
    runs.BEGIN_WAIT seconds have gone by, its log's tail said and an exit code. A worker still there is ended, never left
    to begin later as a run no one waits for: a queued one asked to forget its run (it leaves unrun, its entry its own),
    then stopped (SIGTERM) if it has not ended within two of its looks."""
    until = time.monotonic() + runs.BEGIN_WAIT
    while time.monotonic() < until and proc.poll() is None and not ready(runs.entry(run_id)):
        time.sleep(0.05)
    if ready(runs.entry(run_id)):
        return None
    code = proc.poll()
    if code is None:
        if queued:
            runs.ask_queue(run_id, "forget")
            try:
                proc.wait(2 * runs.QUEUE_POLL + 1)
            except subprocess.TimeoutExpired:
                pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        print(f"{run_id} had not begun after {runs.BEGIN_WAIT:g} s: it was ended", file=sys.stderr)
    from .watch import tail
    print("\n".join(tail(log)), file=sys.stderr)
    return code if code else 1


def queue_sweep(args, errand, keys: list[str], after: str | None, *, attach: bool) -> int:
    """A sweep of runs ([errand].sweep_runs) as a queue: every configuration checked first (a config error anywhere
    refuses it, nothing started), then a worker for each (`--sweep-member KEY`), the first running (or queued `after` a
    run), each next queued to the one before (wait_turn): its own run, entry, [N] and log. `attach`: this terminal
    follows each in turn; `d` leaves them all going, and a run stopped holds the rest."""
    if args.points:
        raise HeimdallError("--points picks points of one configuration, and this sweep runs several",
                            where=f"{errand.path}: [errand].sweep_runs", hint=f"name it: heimdall run {args.config} <configuration> --points …")
    for key in keys:
        try:
            build_plans(args, key)
        except HeimdallError as error:
            error.message = f"configuration '{key}': {error.message}"
            raise
    base = _with_option(_with_option(list(getattr(args, "argv", [])), "--detach", None), "--queued-to", None)
    chain: list[tuple[str, object, Path, str]] = []
    before = after
    for key in keys:
        run_id = runs.new_id()
        log = runs.log_file(run_id)
        argv = _with_option(base, "--sweep-member", key)
        proc = runs.spawn(_with_option(argv, "--queued-to", before) if before else argv, run_id, log)
        failed = _begun(proc, run_id, log, lambda e: e is not None, queued=before is not None)
        if failed is not None:                          # it never began: the ones queued so far are forgotten
            for queued, *_ in chain[1:] if after is None else chain:
                runs.ask_queue(queued, "forget")
            if chain and after is None:
                print(f"the sweep's first run, {chain[0][3]} ({chain[0][0]}, pid {chain[0][1].pid}), runs on: "
                      f"heimdall stop --pid {chain[0][1].pid} stops it", file=sys.stderr)
            return failed
        chain.append((run_id, proc, log, key))
        before = run_id
    head = chain[0][0]
    print(f"a sweep of {len(chain)} runs, queued one after another (queue {head if after is None else runs.entry(head).queue_id}):")
    for n, (run_id, proc, log, key) in enumerate(chain, 1):
        print(f"  {n}. {key}: {run_id} (pid {proc.pid})" + ("" if n > 1 or after else " running") + f"   log {log}")
    print("  heimdall runs lists them · heimdall runs --dispatch ID starts one before its turn")
    if not attach:
        return 0
    code = 0
    for run_id, proc, log, key in chain:
        while proc.poll() is None and (got := runs.entry(run_id)) is not None and got.queued:
            if got.held:
                print(f"queue held: {key} ({run_id}) waits for a dispatch, the run before it stopped\n"
                      f"  heimdall runs --dispatch {run_id} starts it · heimdall runs --forget {run_id} drops it")
                return code or 6
            time.sleep(0.5)
        outcome, code = follow_worker(proc, run_id, log, f"{errand.name} · {key}", args.plain)
        if outcome != "ended":
            print("  the runs after it start in turn: heimdall runs lists them")
            return 0
    return code


def _queue_say(text: str) -> None:
    """A queued run's word on its wait, in its log (the worker's output) with the time."""
    print(f"{time.strftime('%H:%M:%S')}  queue: {text}", flush=True)


def wait_turn(run_id: str, queued_to: str, fields: dict) -> dict:
    """A queued run's worker: its entry written as queued (`queue`, `queued_to`, `queued`), then its turn waited
    for, its predecessor's entry read every runs.QUEUE_POLL seconds. Done, failed, not run or lost: its turn. Stopped:
    held (`held`), until dispatched. Paused: it waits, and follows a resume to the run that resumed it. Forgotten in its
    queue (`left_queue`): it is queued to that run's own predecessor. Its queue is its predecessor's, so a split goes down
    the chain. `heimdall runs --dispatch` starts it now, heading a queue of its own; `--forget` ends it unrun; a stop
    (SIGINT) ends it stopped, holding its followers. Returns the fields its run's entry keeps (or a verdict: it ends)."""
    queued_at = round(time.time(), 3)
    to = queued_to
    before = runs.entry(to)
    queue = (before.queue_id if before else None) or to
    runs.begin(run_id, {**fields, "queue": queue, "queued_to": to, "queued": True})
    ahead = runs.queue_of(runs.entries(), queue)
    _queue_say(f"queued after {to} (queue {queue}, {len(ahead)} of {len(ahead)})")
    held = False
    try:
        while True:
            asked = runs.queue_asked(run_id)
            if asked == "dispatch":
                _queue_say(f"dispatched before its turn: it starts now, heading a queue of its own (was after {to})")
                return {"queue": run_id, "queued_to": None, "dispatched_from": to, "queued": False, "held": False,
                        "began": round(time.time(), 3), "started": queued_at}
            if asked == "forget":
                _queue_say(f"forgotten: it leaves the queue unrun; the run after it waits for {to} instead")
                runs.finish(run_id, 2, "forgotten", left_queue=True, queued=False)
                return {"verdict": "forgotten", "code": 2}
            other = runs.entry(to)
            if other is None:
                _queue_say(f"{to}'s entry is gone: its turn")
                break
            if (other.queue_id or to) != queue and other.queue_id:
                queue = other.queue_id
                runs.update(run_id, queue=queue)
                _queue_say(f"its queue is now {queue}")
            if other.resumed_by:
                to = other.resumed_by
                runs.update(run_id, queued_to=to)
                _queue_say(f"its predecessor was resumed as {to}: it waits for that")
                continue
            if other.left_queue:
                if not other.queued_to:
                    _queue_say(f"{to} left the queue and was its head: its turn")
                    break
                to = other.queued_to
                runs.update(run_id, queued_to=to)
                _queue_say(f"its predecessor left the queue: it waits for {to}")
                continue
            there = runs.state_of(other)
            if there.gives_turn:
                _queue_say(f"{to} ended {there.shown or there.word}: its turn")
                break
            if there.holds and not held:
                held = True
                runs.update(run_id, held=True)
                _queue_say(f"{to} was {'stopped' if there.word == 'stopped' else 'paused and forgotten'}: held until "
                           f"heimdall runs --dispatch {run_id}")
            time.sleep(runs.QUEUE_POLL)
    except KeyboardInterrupt:
        _queue_say("stopped while queued: the runs after it are held")
        runs.finish(run_id, 6, queued=False)
        return {"verdict": "stopped", "code": 6}
    return {"queue": queue, "queued_to": to, "queued": False, "held": False, "began": round(time.time(), 3),
            "started": queued_at}


def background(args, errand, keys: list[str], *, attach: bool) -> int:
    """The run as a worker of its own (V183): this command again with --worker <id>, in a session of its own,
    its output in the registry's <id>.log. `attach`: followed here as heimdall watch does (`d` leaves it
    running; `p` pauses it, twice discards its running points; Ctrl-C stops it, once cleanly, twice hard); else
    (--detach) left once its run has started. Its id is $HEIMDALL_RUN_ID when that is a free one (`heimdall runs
    --resume` gives it), taken out of the environment its worker inherits."""
    from .watch import started, tail
    given = os.environ.pop(runs.ID_VAR, "")                 # heimdall runs --resume's new run
    run_id = given if runs.ID.fullmatch(given) and runs.entry(given) is None else runs.new_id()
    log = runs.log_file(run_id)
    proc = runs.spawn(getattr(args, "argv", []), run_id, log)
    what = f"{errand.name} · {', '.join(keys)}"
    if not attach:
        if started(proc.pid, proc) is None:
            print("\n".join(tail(log)), file=sys.stderr)
            return _ended(proc, run_id)
        print(f"running in the background: {what} (pid {proc.pid}, {run_id})")
        _left(proc, log, what)
        return 0
    return follow_worker(proc, run_id, log, what, args.plain)[1]


def _left(proc, log: Path, what: str) -> None:
    print(f"left running: {what} (pid {proc.pid})\n  heimdall watch --pid {proc.pid}   follow it again\n"
          f"  heimdall stop --pid {proc.pid}    stop it\n  log {log}")


def _ended(proc, run_id: str) -> int:
    code = proc.wait()
    if code < 0:                                         # killed: the worker could not say so itself
        runs.finish(run_id, 128 - code, f"killed by signal {-code}")
        code = 128 - code
    return code


def follow_worker(proc, run_id: str, log: Path, what: str, plain: bool) -> tuple[str, int]:
    """A worker followed here as heimdall watch does (`d` leaves it running; `p` pauses it, twice discards its running
    points; Ctrl-C stops it, once cleanly, twice hard): (how it was left: "detached", "dropped" or "ended", its code)."""
    from .watch import follow, socket_of, tail

    asked, pausing = [], []
    rest = "d: leave it running · Ctrl-C: stop it"

    def on_key(key: str, shown) -> str | None:
        if key in "dD":
            return "detached"
        if key in "pP":
            if asked:
                shown.say("already stopping: a stop is not made a pause")
            else:
                pause_key(proc.pid, shown, pausing, rest)
        return None

    def on_interrupt(shown) -> None:
        asked.append(True)
        os.kill(proc.pid, signal.SIGINT)
        shown.keys({1: "stopping: each point ends cleanly (Ctrl-C again: a hard stop)",
                    2: "stopping hard: the tools are killed (Ctrl-C again: at once)"}.get(len(asked), "killing it"))
        return None

    from .watch import Keys
    with Keys(sys.stdin) as keys_in:
        outcome = follow(socket_of(proc.pid), plain=plain, keys=keys_in.fd, on_key=on_key, on_interrupt=on_interrupt,
                         proc=proc, hint="d: leave it running · p: pause it · Ctrl-C: stop it")
    if outcome == "detached":
        _left(proc, log, what)
        return "detached", 0
    if outcome == "dropped":
        print(f"this terminal fell behind the run: heimdall watch --pid {proc.pid} follows it again", file=sys.stderr)
        _left(proc, log, what)
        return "dropped", 0
    if outcome == "gone":
        print("\n".join(tail(log)), file=sys.stderr)
    return "ended", _ended(proc, run_id)


def pause_key(pid: int, shown, pausing: list, rest: str) -> None:
    """`p` in a watch or in the run's own view: the run's process sent SIGUSR1. The first press a pause
    (its running points end first, none more is started), the second a force pause (they are stopped at once);
    a third sends nothing. Each says what it did, then the keys left (`rest`)."""
    if len(pausing) >= 2:
        shown.say("already pausing: its running points are being stopped")
        return
    running = len(shown.state.running())
    pausing.append(True)
    os.kill(pid, signal.SIGUSR1)
    if len(pausing) == 1:
        shown.keys(f"pausing: {running} running point{'' if running == 1 else 's'} end first, no more start; "
                   f"p again discards them · {rest}")
    else:
        shown.keys(f"pausing now: the running points are discarded (stopped, partial outputs kept; a rerun runs them "
                   f"again) · {rest}")


def cmd_stop(args) -> int:
    """`heimdall stop [CONFIG [CFG]] [--pid N]` (V183): a running job of yours asked to stop, as Ctrl-C does (its
    points end cleanly, partial outputs kept, a rerun resumes), then waited for (Ctrl-C leaves the waiting)."""
    from .events import namespace
    if getattr(args, "index", None) is not None:
        if args.config or args.pid is not None:
            raise HeimdallError("-i names the job itself: no config or --pid with it", hint=f"heimdall stop -i {args.index}")
        args.pid = running_at(args.index, "stopped")
    wanted = configmod.load(args.config) if args.config else None
    found = house.live_runs(str(wanted.path) if wanted else None, args.configuration, args.pid)
    if wanted is None and args.pid is None:                 # named by neither: this work dir's alone
        work = find_work()
        if work is None:
            raise HeimdallError("stop which job? outside a work dir, name it", hint="heimdall stop --pid N (heimdall runs lists them)")
        found = [(n, h) for n, h in found if h in house.runs_here(work)]
    if not found:
        cluster = next((e for e in runs.entries() if e.cluster and runs.state_of(e).word == "submitted"
                        and (wanted is None or e.config == str(wanted.path))), None)
        raise HeimdallError("no running job to stop" + (f" for {wanted.path}" if wanted else "")
                       + (f" with pid {args.pid}" if args.pid else ""),
                       hint=(f"its cluster jobs: heimdall cluster {cluster.config} {cluster.configuration or ''} --cancel"
                             if cluster else "heimdall runs lists what runs"))
    if len(found) > 1:
        raise HeimdallError(f"{len(found)} jobs match: " + "; ".join(
            f"pid {h.get('pid')} {Path(h.get('config', '')).stem} · {', '.join(h.get('configurations', []))}" for _, h in found),
            hint="name one: heimdall stop --pid N")
    _, hello = found[0]
    if hello.get("pidns") and namespace("pid") and hello["pidns"] != namespace("pid"):
        raise HeimdallError(f"pid {hello.get('pid')} is another PID namespace's (a container's): stopping it from here could "
                       "signal another process", hint="stop it from where it runs")
    refuse_newer(runs.entry(hello["id"]) if hello.get("id") else None)
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


def notify(errand, code: int, paused: bool = False) -> bool:
    """[errand] notify = "desktop" (V76): a notify-send when the command ends, for runs of hours. Never
    fails the run: no notify-send, or no desktop, and it says nothing."""
    if errand.raw.get("errand", {}).get("notify", "none") != "desktop" or not shutil.which("notify-send"):
        return False
    verdict = "paused" if paused else {0: "done", 1: "a point failed", 2: "a config error", 6: "stopped"}.get(code, f"exit {code}")
    try:
        subprocess.Popen(["notify-send", "--app-name=heimdall", f"heimdall run {errand.name}", f"{errand.path.name}: {verdict}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    return True


def _points_planned(args, planned: Planned) -> int:
    """The configuration points a run will end (run, or skip as complete): none when its stages leave them out."""
    return len(planned.plans) if "points" in stages_of(args) else 0


def _runs(args, errand, keys: list[str], stopper: execute.Stopper, bus, recorder: runs.Recorder | None = None) -> int:
    """The command's runs, each planned before the first starts; `recorder` is told how many points they plan
    (the registry's progress, `heimdall runs`)."""
    if len(keys) == 1:
        planned = build_plans(args, keys[0])
        if recorder is not None:
            recorder.plan({"": _points_planned(args, planned)})
        return run_one(args, keys[0], stopper, bus=bus, planned=planned)
    if args.points:
        raise HeimdallError("--points picks points of one configuration, and this sweep runs several",
                       where=f"{errand.path}: [errand].sweep_runs", hint=f"name it: heimdall run {args.config} <configuration> --points …")
    skipped, ahead = {}, {}
    stamp = errand.path.stat().st_mtime_ns
    for key in keys:
        try:
            ahead[key] = planned = build_plans(args, key)
        except HeimdallError as error:
            error.message = f"configuration '{key}': {error.message}"
            raise
        if args.only in ("pre", "post") and getattr(planned, args.only) is None:
            skipped[key] = f"   no {args.only} tools: skipped"
    if len(skipped) == len(keys):
        raise HeimdallError(f"no configuration of this sweep has {args.only} tools", where=f"{errand.path}: [errand].sweep_runs")
    if recorder is not None:
        recorder.plan({key: 0 if key in skipped else _points_planned(args, ahead[key]) for key in keys})
    failed = False
    for number, key in enumerate(keys, 1):
        if stopper.halted:                   # a stop or a pause: no more runs begun
            return 6
        following = next((journal_path(errand, errand.configurations[k]) for k in keys[number:] if k not in skipped), None) \
            if paths.keeping("journal") else None
        if key in skipped:
            print(("\n" if number > 1 else "") + header(number, errand.configurations[key]))
            print(skipped[key])
            if bus is not None:                  # a watcher hears it too (V181)
                bus.say(f"{header(number, errand.configurations[key])}\n{skipped[key]}")
            continue
        voice = RunBus(bus, key, alone=True) if bus is not None else None      # each run's events say which run (V75)
        try:                                 # planned again only if the TOML was edited meanwhile (V38, V54)
            unchanged = errand.path.stat().st_mtime_ns == stamp
            code = run_one(args, key, stopper, number=number, following=following,
                           planned=ahead[key] if unchanged else None, bus=voice)
        except HeimdallError as error:            # the TOML was edited since the check: this run fails alone
            print(("\n" if number > 1 else "") + header(number, errand.configurations[key]))
            print(error.render(), file=sys.stderr)
            if voice is not None:
                voice.say(f"{header(number, errand.configurations[key])}\n{error.render()}")
            not_run(journal_path(errand, errand.configurations[key]) if paths.keeping("journal") else None,
                    header(number, errand.configurations[key]), error.message, following, voice)
            code = 2
        if code == 6:
            return 6
        failed = failed or code != 0
    return 1 if failed else 0


def show_config(errand, keys: list[str]) -> list[str]:
    """--show-config (V56): every resolved value of each configuration with the layer it came from (its
    own table, one it extends, [errand], the schema's default), each fixed quantity with where it was
    fixed, the interfaces (inferred from the chain in a v3 file), then every quantity and tool table
    with the file it came from. A v3 file is shown in v3's names."""
    from . import schema
    v3 = errand.form == 3
    names = {"event_count": "events", "tools": "chain", "sweeps": "vary", "label": "folder", "prelim": "interfaces"} if v3 else {}
    order = [k for k in schema.keys("configuration") if k not in ("extends", "static", "manual_seed")]
    lines = []

    def place(origin: str) -> str:
        return origin.replace("[errand.cfgs.", "[cfgs.") if v3 else origin

    for key in keys:
        configuration = errand.configurations[key]
        lines.append(f"run {errand.name} ({errand.path}) · configuration {key}")
        seed = configuration.manual_seed if configuration.seed_type == "manual" else configuration.seed_type
        fields = {"serial": configuration.serial, "name": configuration.run_folder, "label": configuration.label,
                  "title": configuration.title, "description": configuration.description, "tag": configuration.tag,
                  "event_count": configuration.event_count, "threads": configuration.threads,
                  "parallelism": "auto" if configuration.parallelism_auto else configuration.parallelism,
                  "swept": configuration.swept, "seed_type": seed,
                  "sweeps": configuration.sweeps, "plot_points": configuration.plot_points,
                  "combine": configuration.combine, "tools": configuration.tools, "pre": configuration.pre,
                  "post": configuration.post, "generate_cards": configuration.generate_cards,
                  "prelim": configuration.prelim, "cluster": configuration.cluster}
        width = max(len(names.get(n, "seed" if n == "seed_type" and v3 else n)) for n in order) + 2
        own = errand.raw.get("errand", {}).get("cfgs", {}).get(key, {})
        for name in order:
            value = fields.get(name)
            if value in (None, [], {}, "") and name not in configuration.origins:
                continue
            shown = names.get(name, "seed" if name == "seed_type" and v3 else name)
            if name == "prelim" and v3:
                origin = "inferred from the chain"
            else:
                origin = place(configuration.origins.get(name, f"[errand.cfgs.{key}]" if name in own else "default"))
            lines.append(f"  {shown:{width}s} = {json.dumps(value, default=str):40s} {origin}")
        mine = own.get("static", {}) if isinstance(own.get("static"), dict) else {}
        for quantity, tag in configuration.static.items():
            if quantity in mine:
                origin = f"[cfgs.{key}].fixed" if v3 else f"[errand.cfgs.{key}].static"
            elif f"quantities.{quantity}" in errand.included and quantity not in errand.raw.get("static", {}):
                origin = f"included from {errand.included[f'quantities.{quantity}']}"
            else:
                origin = f"[quantities.{quantity}].fixed" if v3 else "[static]"
            label = f"fixed {quantity}" if v3 else f"static.{quantity}"
            lines.append(f"  {label:{width}s} = {json.dumps(tag, default=str):40s} {origin}")
    for quantity, q in errand.quantities.items():
        source = f"included from {errand.included[f'quantities.{quantity}']}" if f"quantities.{quantity}" in errand.included else "this file"
        lines.append(f"  quantity {quantity}: {len(q.values)} point(s){' (a compound field)' if q.silent else ''}   {source}")
    for tag, tool in errand.tools.items():
        source = f"included from {errand.included[f'tools.{tag}']}" if f"tools.{tag}" in errand.included else "this file"
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


def pool_points(plans: list, errand, rerun, bus) -> None:
    """The points library at a run's start (points-library P4): each pooled point of this run is linked into it
    (`library.link`), a Run that links an entry the index does not yet name for it is noted (`used`), and what the
    library gives and what `--rerun` replaces is said: the Runs a rerun entry serves are named."""
    pooled = [p for p in plans if p.library]
    if not pooled:
        return
    entries = library.entries(pooled[0].folders.assignment)
    here = str(pooled[0].folders.record.relative_to(records_root()))
    hits, replaced = [], {}
    for plan in pooled:
        library.link(plan)
        known = entries.get(plan.library)
        complete = record.is_complete(plan)
        if known and here not in known["runs"] and (complete or rerun):
            library.note(plan, errand, "used")
        if complete and not rerun:
            hits.append((plan, known))
        elif rerun and known:
            others = [r for r in known["runs"] if r != here]
            if others:
                replaced[plan.point.name] = others
    if hits:
        first = sorted({k["first_run"] for _, k in hits if k and k.get("first_run")})
        bus.say(f"   note: {len(hits)} point(s) come from the library, not run again"
                + (f" (first made by {', '.join(first[:3])}{', …' if len(first) > 3 else ''})" if first else ""))
    for name, others in replaced.items():
        bus.say(f"   note: --rerun replaces the library point {name} for every Run that links it: "
                f"{', '.join(others[:4])}{', …' if len(others) > 4 else ''}")


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
            planned: Planned | None = None, bus: Bus | None = None) -> int:
    """One run: the pre stage, every point not complete, the combined groups, the post stage and the
    plots, said on `bus` (V72). In a sweep of runs, `number` is its place (a `run NN - <title> -` line
    first), and `following` is the next run's journal (--journal), named in this one's `run finished`
    event so that heimdall watch --file follows on."""
    planned = planned or build_plans(args, key)
    errand, configuration, every, plans = planned.errand, planned.configuration, planned.every, planned.plans
    post_plan, pre_plan, combined = planned.post, planned.pre, planned.combined
    stages, again = stages_of(args), getattr(args, "only", None)       # again: the stage --only reruns
    only_library = configuration.library == "only"           # points into the library, and no Run kept
    if only_library:
        stages = stages & {"pre", "points"}
    title_line = header(number, configuration) if number else ""
    if getattr(args, "why", False):
        if title_line:
            print(("\n" if number > 1 else "") + title_line)
        print_why(errand, configuration, plans, post_plan, pre_plan, combined)
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
            print_plan(errand, configuration, plans, post_plan, pre_plan, combined, tag=run_tag(args, errand, configuration))
            return 0
        give_tag(args, errand, configuration)
        return 1 if draw_run(errand, configuration, combined or every, print) else 0
    if args.only == "post" and post_plan is None:
        raise HeimdallError(f"configuration '{configuration.key}' has no post tools", where=f"{errand.path}: [errand.cfgs.{configuration.key}].post")
    if args.only == "pre" and pre_plan is None:
        raise HeimdallError(f"configuration '{configuration.key}' has no pre tools", where=f"{errand.path}: [errand.cfgs.{configuration.key}].pre")
    if "points" in stages and "pre" not in stages and pre_plan is not None and not record.is_complete(pre_plan):
        raise HeimdallError(f"configuration '{configuration.key}': the pre stage is not complete, and the points need it",
                       hint="run --stages pre first (heimdall cluster's pre job does), or leave --stages out")
    refuse_overwrites(planned, args, stages)
    if stopper.halted:                       # Ctrl-C or a pause while this run was being planned
        said = f"{title_line + ': ' if title_line else ''}{'paused' if stopper.paused else 'stopped'} before it began: " \
            "nothing run"
        print(said)                          # its view is not up yet: said here, and to a watcher
        if bus is not None:
            bus.say(said)
        return 6
    tag = give_tag(args, errand, configuration)

    bus = bus if bus is not None else Bus()
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
    run_log = RunLog(tools.run_folders(errand, configuration).run_log, run=getattr(bus, "run", None))   # always (V202)
    bus.subscribe(run_log)
    title = run_title(errand, configuration, plans, tag)
    tally = runs.Tally()                     # the verdict's counts and failures (V200)
    bus.subscribe(tally)
    known = record.constants(every, errand, configuration) if every else {}    # what every point shares (V200)
    if number > 1:
        bus.say("")
    bus.emit("", "", {"k": "run", "state": "started", "points": len(plans), "title": title,
                      "parallelism": stopper.cap(configuration.parallelism),
                      "cores": max((execute.cores(p) for p in plans), default=1),
                      "record": str(records_root() / tools.run_dir(errand, configuration)),    # the registry's (V182)
                      **({"library": [str(p.folders.library_entry(p.library)) for p in plans if p.library]} if only_library else {}),
                      **({"tag": tag} if tag else {}),
                      **({"header": title_line} if title_line else {}), **({"constants": known} if known else {})})
    if crowded(configuration, plans):
        bus.say(f"   note: {crowded(configuration, plans)}")
    for note in notes_of(plans):
        bus.say(f"   note: {note}")
    for warning in tools.meta_notes(errand):                    # V97
        bus.say(f"   warning: {warning}")
    if "points" in stages:
        pool_points(plans, errand, args.rerun is True and again is None, bus)

    def manifest() -> None:                  # a points-only run (a cluster job) leaves it to the finish job
        if plans and stages != {"points"} and not only_library:
            record.write_atomic(record.manifest_file(every), json.dumps(
                record.points_manifest(every, errand, configuration, known), indent=1, default=str) + "\n")
    dropped = dropped_points(every) if every and stages != {"points"} and not only_library else []     # read before it is rewritten
    manifest()
    if every and stages != {"points"} and not only_library:              # V158: the config it ran with, beside points.json
        if record.write_snapshot(errand, configuration, every) is not None and dropped:
            bus.say(f"   note: {len(dropped)} point(s) recorded in {tools.run_dir(errand, configuration)} are not in the config now "
                    f"({', '.join(dropped[:4])}{', …' if len(dropped) > 4 else ''}): its snapshot and points.json describe "
                    "the config as it is; give the configuration a serial of its own to keep a run whole")
    failed = done = lost = 0                 # lost: the points failed (`failed` counts the later stages' too)
    verdict = "stopped"

    def halted(stage: str) -> bool:
        """Whether a stop or a pause ends the run before `stage`; a pause's verdict says what it leaves:
        "paused: 12 done, 2 discarded, 42 left; not run: combine, post, plot"."""
        nonlocal verdict
        if not stopper.halted:
            return False
        if stopper.paused:
            discarded = tally.stopped(getattr(bus, "run", "") or "")
            left = max(0, sum(not record.is_complete(p) for p in plans) - lost - discarded)
            later = [s for s in STAGES[STAGES.index(stage):] if s in stages
                     and (s != "combine" or combined) and (s != "post" or post_plan is not None)]
            verdict = "paused: " + ", ".join([f"{done} done", *([f"{lost} failed"] if lost else []),
                                              *([f"{discarded} discarded"] if discarded else []), f"{left} left"]) \
                + (f"; not run: {', '.join(later)}" if later else "")
            bus.say(verdict)                 # the view and run.jsonl (heimdall log) say it
        return True

    try:
        if "pre" in stages:
            if not post.run_pre(pre_plan, errand, configuration, bus=bus, stopper=stopper, logs=logs,
                                rerun=args.rerun or again == "pre"):
                verdict = "pre failed: no point ran"
                if stopper.requested:
                    halted("pre")
                    return 6
                return 1
            if stages == {"pre"}:
                verdict = "pre done"
                return 0
        if "points" in stages:
            if halted("points"):
                return 6
            done, failed, stopped = execute.run_points(plans, errand, configuration, bus=bus, stopper=stopper,
                                                       rerun=args.rerun, logs=logs,
                                                       wait_held=getattr(args, "wait", False))
            lost = failed
            if stopped:
                halted("combine")
                return 6
        warned = tally.warned(getattr(bus, "run", "") or "")
        verdict = (f"{done} done{f' ({warned} with warnings)' if warned else ''}, {failed} failed, "
                   f"{len(plans) - done - failed} skipped") if "points" in stages else ""
        manifest()                           # post tools read it: it must say which points are complete
        if combined and "combine" in stages:
            if halted("combine"):
                return 6
            bad = post.run_combined(combined, every, errand, configuration, bus=bus, stopper=stopper, logs=logs,
                                    rerun=args.rerun, say=bus.say)
            if stopper.halted:               # a pause cuts combine short too: it stays to run
                halted("combine")
                return 6
            if bad:
                failed += bad
                verdict = f"{verdict}, {bad} combined group(s) failed"
        if "post" in stages and post_plan is not None and halted("post"):
            return 6
        if "post" in stages and not post.run(post_plan, every, errand, configuration, bus=bus, stopper=stopper, logs=logs,
                                             rerun=args.rerun or again == "post", say=bus.say):
            if stopper.requested:
                halted("post")
                return 6
            failed += 1
            verdict = ", ".join(v for v in (verdict, "post failed") if v)
        elif post_plan is not None and again == "post":
            verdict = "post done"
        if "plot" in stages and halted("plot"):
            return 6
        if "plot" in stages:
            drawing = not (getattr(args, "no_plot", False) or configuration.draw is False)     # V167, V168: the gates
            measuring = False if getattr(args, "no_stats", False) else configuration.measure
            if not drawing:
                bus.say(f"plot: not drawn ({'--no-plot' if getattr(args, 'no_plot', False) else '[errand].plot = false'}): "
                        f"heimdall plot {tools.run_dir(errand, configuration)} draws it")
            failed += draw_run(errand, configuration, combined or every, bus.say, draw=drawing, stats=measuring) > 0
            across, written = plotdoc.write_across(errand)                 # V169: the Runs together
            if across is not None:
                bus.say(f"plot: {'wrote ' + str(across) + ': ' if written else ''}heimdall plot "
                        f"{record.config_name(errand)} --across draws this Run with the others of {errand.name}")
        verdict = verdict or ", ".join(s for s in STAGES if s in stages) + " done"         # a run without its points
        bus.say(verdict)                     # before end(): the view's thread prints it (V32)
        if failures := tally.failures(getattr(bus, "run", "") or ""):          # V200: which failed, and why
            bus.say("failed:\n" + "\n".join(failures))
    finally:
        onward = {"next": str(following)} if following and not stopper.halted else {}
        bus.emit("", "", {"k": "run", "state": "finished", "verdict": verdict, **onward})
        bus.unsubscribe(shown)
        shown.end()
        manifest()
        if only_library:                     # points into the library, no Run kept: its links go, the entries stay
            library.unlink_run(plans)
        bus.unsubscribe(tally)
        bus.unsubscribe(run_log)
        run_log.close()
        if journal:
            bus.unsubscribe(journal)
            journal.close()
    return 1 if failed else 0


def cmd_cluster(args) -> int:
    """`heimdall cluster` (V114): each configuration (every swept one under [errand].sweep_runs) planned as heimdall run
    plans it, then submitted, or its latest submission's state shown, or cancelled (runner/cluster.py)."""
    errand = configmod.load(args.config, sets=args.set)
    keys = errand.runs(args.configuration)
    if len(keys) > 1 and args.points:
        raise HeimdallError("--points picks points of one configuration, and this sweep runs several",
                       where=f"{errand.path}: [errand].sweep_runs", hint=f"name it: heimdall cluster {args.config} <configuration> --points …")
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
            for warning in tools.meta_notes(errand):
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
                   hint="heimdall report <A>/<E>/<R> (docs/stable/guide/reports.md); a deck's decks/<deck>/ is yours, left as it is")


def cmd_report(args) -> int:
    """`heimdall report [RECIPE.toml] [SOURCE…]` (V207, V209): a recipe and its sources, or sources alone (one
    folder's report.toml, else the default), resolved into sections of figures and statistics and built where
    results/ has them; --list says them, --init writes a recipe once."""
    from . import report as reportmod
    from .paths import configs_root
    if args.init:
        name = args.names[0] if len(args.names) == 1 else ""
        if not name.endswith(".toml") or name.count("/") != 1 or name.startswith(("./", "/")):
            raise HeimdallError("--init writes a recipe under configs/: name it, <A>/<E>.toml",
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
    results/<A>/<E>/<R>/plot.toml, from records alone (no tool planned, no stack beyond Paint). CONFIG names its
    configurations' latest records (the newest folder); RECORD (`<A>/<E>/<R>`) or a folder with a
    plot.toml names one. A record without a document gets one written first, from the config (or its
    snapshot). `--plot FILE`: another file's [plot] for this drawing; `--points`: one set; `--plan`: the sets'
    cells, nothing drawn."""
    if plot._is_plot_file(args.config):                     # break and migrate (V74)
        raise HeimdallError("heimdall plot draws a configuration's pages; files are overlaid by heimdall overlay",
                       hint=f"heimdall overlay {args.config} …")
    args.points = None
    if getattr(args, "stats_only", False):
        if getattr(args, "style_sync", None) or getattr(args, "plan", False):
            raise HeimdallError("--stats-only measures; --plan and --style-sync draw nothing and measure nothing",
                                hint="heimdall plot RUN --stats-only, or --plan / --style-sync alone")
        return cmd_stats(args)
    if getattr(args, "across", False) and getattr(args, "style_sync", None):
        return style_sync_across(args)
    if getattr(args, "style_sync", None):
        return style_sync(args)
    styled = configmod.plot_of(args.plot_file) if getattr(args, "plot_file", None) else None
    failed = False
    targets = [across_of(args)] if getattr(args, "across", False) else documents_of(args)
    for number, target in enumerate(targets, 1):
        doc, configuration, members = plotdoc.load(target)
        for shadowed, by in list(doc.source.get("shadowed", {}).items())[:1]:   # V169: a point two Runs have
            print(f"plot: {len(doc.source['shadowed'])} point(s) two Runs have are drawn from the later "
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
    """`heimdall plot <A>/<E>/<R> | <A>/<E> --style-sync CONFIG [--plan] [--replot]` (V166): each named plot
    document's [plot], [stats] and [score] replaced by the config's (its configuration's, resolved as a run writes them),
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
        raise HeimdallError(f"'{args.config}' names no plot document", hint="a Run, <A>/<E>/<R>, or an errand's Runs, "
                                                                      "<A>/<E> (results/<A>/<E>/*/plot.toml)")
    if not targets:
        raise HeimdallError(f"results/{name}/ holds no plot document", hint="heimdall migrate --plot-docs writes them")
    errand = configmod.load(args.style_sync, sets=args.set)
    plot.validate(errand)
    synced, left = [], 0
    for target in targets:
        doc, configuration, members = plotdoc.load(target)
        rel = target.parent.relative_to(results_root()) if target.parent.is_relative_to(results_root()) else target.parent
        if configuration.key not in errand.configurations:
            print(f"left    {rel}: {args.style_sync} has no configuration '{configuration.key}'")
            left += 1
            continue
        live, picks = configmod.for_configuration(errand, configuration.key)   # V179: its own data
        new_plot, new_stats = plotdoc.chosen_of(live, configuration, members, picks=picks)
        new_score = dict(getattr(live, "score", None) or {})
        changed = sorted(k for k in {*doc.plot, *new_plot} if doc.plot.get(k) != new_plot.get(k))
        changed += ["[stats]"] if doc.stats != new_stats else []
        changed += ["[score]"] if doc.score != new_score else []
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
            plotdoc.write_chosen(target, new_plot, new_stats, score=new_score)
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
    """`heimdall plot RUN | <folder> | <A>/<E> | CONFIG [CFG] --stats-only` (V168): each run's statistics alone, from its plot
    document: the pages [plot] defines, as [stats] measures them, read by Paint (no image drawn), into
    statistics/<set>/. `--sets`: these sets only."""
    name = args.config.strip("/")
    if getattr(args, "across", False):
        targets = [across_of(args)]
    elif plotdoc.find(name) is None and name.count("/") == 1 and (results_root() / name).is_dir() \
            and not (paths.configs_root() / f"{name}.toml").is_file():
        targets = sorted((results_root() / name).glob(f"*/{plotdoc.FILE}"))      # <A>/<E>: each of its runs
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


def cmd_stats_retired(args) -> int:
    """`heimdall stats …`, retired for a release (the way `deck` was): it stops, naming its two successors."""
    raise HeimdallError("heimdall stats is now heimdall plot RUN --stats-only: a Run's statistics measured, no page drawn; "
                        "heimdall score RUN reads them",
                        hint="heimdall plot <A>/<E>/<R> --stats-only [--sets NAMES]; heimdall score <A>/<E>/<R> [--by AXIS] [--baseline FILTER]")


def cmd_diff(args) -> int:
    """`heimdall diff RUN RUN [--points SEL] [--full] [--json]`: see diffcmd."""
    from . import diffcmd
    return diffcmd.run(args)


def cmd_score(args) -> int:
    """`heimdall score TARGET [--set S] [--across] [--by AXES] [--baseline FILTER] [--json]`: standings, marginals and
    baselines read from the statistics already measured; see scorecmd."""
    from . import scorecmd
    return scorecmd.run(args)


def across_of(args) -> Path:
    """The runs of an errand file together (V169): results/<A>/<E>/plot.toml, its argument an errand file (written from
    its [plot.across] when there is none) or that folder."""
    found = plotdoc.find(args.config)
    if found is not None:
        return found
    errand = configmod.load(args.config, sets=args.set)
    target, written = plotdoc.write_across(errand)
    if target is None:
        raise HeimdallError(f"{errand.path} has no [plot.across] sets: nothing to draw its Runs together",
                       hint="[plot.across.<set>] pages = { … }, curves = { \"@events\" = \"all\", … }: docs/stable/guide/plots-across.md")
    if written:
        print(f"plot: wrote {target}, from {args.config}'s [plot.across]")
    return target


def style_sync_across(args) -> int:
    """`heimdall plot CONFIG --across --style-sync CONFIG`: the Name level's [plot], [stats] and [score] become the config's
    (its [plot] with its [plot.across] sets), and its [from] the config's [plot.across_from] when it has one (V224);
    --plan says what would change; --replot draws."""
    errand = configmod.load(args.style_sync, sets=args.set)
    plot.validate(errand)
    target = plotdoc.across_path(errand.assignment, errand.name)
    if not target.is_file():                                # none yet: written, as a run writes it
        if plotdoc.write_across(errand)[0] is None:
            raise HeimdallError(f"{errand.path} has no [plot.across] sets", hint="[plot.across.<set>]: docs/stable/guide/plots-across.md")
        print(f"plot: wrote {target}")
        return 1 if args.replot and plot.draw(*plotdoc.load(target), print) else 0
    new_plot, new_stats = plotdoc.across_chosen(errand)
    new_score = dict(getattr(errand, "score", None) or {})
    wanted = plotdoc.from_of(errand) if (errand.plot or {}).get(plotdoc.FROM) is not None else None
    try:                                                    # read as it is: a [from] in error is what a sync mends
        kept = tomllib.loads(target.read_text(encoding="utf-8"))
        had, had_score = dict(kept.get("plot", {})), dict(kept.get("score", {}))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise HeimdallError(f"the plot document cannot be read: {error}", where=str(target)) from None
    changed = [f"[plot].{k}" for k in sorted(k for k in {*had, *new_plot} if had.get(k) != new_plot.get(k))]
    if wanted is not None and wanted != plotdoc.from_in(target):
        changed.insert(0, "[from]")
    if had_score != new_score:
        changed.append("[score]")
    print(f"{'would sync' if args.plan else 'synced '} {target}: " + (", ".join(changed) or "the same"))
    if args.plan or not changed:
        return 0
    plotdoc.write_chosen(target, new_plot, new_stats, wanted, score=new_score)
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
        errand, configuration = _record_config(args.record)
        target, _ = write_documents(errand, configuration, plot.recorded(errand, configuration))
        print(f"plot: wrote {target}, from its snapshot and its points.json (heimdall migrate --plot-docs writes "
              "every record's)")
        return [target]
    errand = configmod.load(args.config, sets=args.set)
    plot.validate(errand)
    out, read = [], errand
    for key in read.runs(args.configuration):
        errand, configuration = configmod.for_configuration(read, key)     # V179: its own vars and data
        if configuration.serial_auto:                       # the newest folder: what a run last made
            taken = tools.serials_taken(errand, configuration)
            if taken:
                configuration.serial = max(taken)
        folders = tools.run_folders(errand, configuration)
        target = plotdoc.path_of(folders.results)
        if not target.is_file():
            if not folders.manifest.is_file():
                raise HeimdallError(f"configuration '{key}' has no record yet: nothing to draw", where=str(folders.record),
                               hint=f"heimdall run {args.config} {key}")
            target, notes = write_documents(errand, configuration, plot.recorded(errand, configuration))
            print(f"plot: wrote {target}, from the config and its points.json (heimdall migrate --plot-docs writes "
                  "every record's)")
        else:
            kept, axes, members = plotdoc.load(target)
            if (kept.plot, kept.stats) != plotdoc.chosen_of(errand, axes, members, picks=configuration):
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
    names = list(args.configs) or house.config_names()     # a file with [run] too: it fails, saying what rewrites it
    importers = house.importers()                              # a shared file: checked through them
    failed = 0
    for name in names:
        try:
            sets = list(getattr(args, "set", []))
            errand = configmod.load(name, sets=sets)
            heimdall_flags(configmod.heimdall_table(name, sets=sets), f"{errand.path}: [heimdall]")   # V188
            points = 0
            for key in errand.configurations:
                planned = build_plans(argparse.Namespace(config=name, set=sets, points=None, rerun=False, only=None), key)
                points += len(planned.every)
            print(f"ok    {name}: {len(errand.configurations)} configuration(s), {points} point(s)")
            for warning in [*tools.meta_notes(errand), *house.unused_tools(errand)]:   # said, never failed
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
    """An errand file with configurations of its own is a study, checked on its own even when imported; one
    without (a shared file of tools and quantities) is checked through the files that import it."""
    try:
        data = tomllib.loads(configmod.config_file(name).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, HeimdallError):
        return True
    return bool(data.get("cfgs") or (data.get("errand") or data.get("run") or {}).get("cfgs"))   # an old file: its refusal said


def cmd_runs(args) -> int:
    """`heimdall runs [--5|--10|--20|--50|--week|--month]`: the live jobs (running and paused, indexed) or
    recent runs; `--resume N`, `--forget N`: the paused job [N]."""
    if getattr(args, "resume", None) is not None:
        return resume_run(args.resume)
    if getattr(args, "forget", None) is not None:
        return forget_run(args.forget)
    if getattr(args, "dispatch", None) is not None:
        return dispatch_run(args.dispatch)
    if getattr(args, "again", None) is not None:
        return again_run(args.again)
    from . import workdirs
    try:
        titles = {entry["path"]: title for title, entry in workdirs.load().items()}
    except HeimdallError:
        titles = {}
    if getattr(args, "jobs", None) is not None:
        if getattr(args, "index", None) is None:
            raise HeimdallError("--jobs changes one running job: name it", hint="heimdall runs -i N --jobs 4")
        return set_jobs(args.index, args.jobs)
    if getattr(args, "index", None) is not None:
        return act_on(args.index, titles, plain=getattr(args, "plain", False))
    states = house.check_states(args.state) if getattr(args, "state", None) else None
    color = house.wants_colour(sys.stdout, getattr(args, "plain", False))
    width = shutil.get_terminal_size((80, 24)).columns if sys.stdout.isatty() else None
    for line in house.runs_listing(runs.entries(), house.live_runs(), titles, limit=args.limit, days=args.days,
                                   states=states, color=color, width=width):
        print(line)
    return 0


def refuse_newer(entry: runs.RunEntry | None) -> None:
    """An entry a newer Heimdall wrote is listed and never acted on: its fields may mean something this one does not know."""
    if entry is not None and entry.newer:
        raise HeimdallError("this entry is from a newer Heimdall", hint="act on it from the checkout that started it")


def live_at(index: int) -> tuple[runs.RunEntry, runs.RunState]:
    """The live job [index] of `heimdall runs` (house.live_entries: the same list, made again now), or refused,
    naming the live ones."""
    listed = house.live_entries(runs.entries(), house.live_runs())
    if not 1 <= index <= len(listed):
        there = "; ".join(house.live_line(n, e, s) for n, (e, s) in enumerate(listed, 1))
        raise HeimdallError(f"no live job [{index}]: " + (f"there are {len(listed)}" if listed else "none is live"),
                            hint=f"the live ones: {there}" if listed else "heimdall runs --5 lists the latest, of any state")
    return listed[index - 1]


def running_at(index: int, verb: str) -> int:
    """The pid of the running job [index] of `heimdall runs`, for `watch -i` and `stop -i`: a paused job, a cluster
    submission and one that is no longer running are refused, each saying what to do."""
    entry, state = live_at(index)
    if verb == "stopped":
        refuse_newer(entry)
    if runs.paused(entry):
        raise HeimdallError(f"[{index}] is paused: heimdall runs --resume {index}",
                            hint=f"a paused job has nothing to be {verb} until it is resumed")
    if entry.cluster:
        raise HeimdallError(f"[{index}] is a cluster submission: its jobs are on Slurm's nodes",
                            hint="heimdall runs names its heimdall cluster … --status")
    if state.word in ("queued", "held"):
        if verb == "stopped":                               # its waiting worker: stopped unrun, holding the runs after it
            return entry.pid
        raise HeimdallError(f"[{index}] is {state}: nothing is {verb} until its turn",
                            hint=f"its log: {entry.log or runs.log_of(entry.id)}; heimdall runs --dispatch {index} starts it now")
    if state.word != "running":
        raise HeimdallError(f"[{index}] {entry.id} is {state}: it cannot be {verb} from here")
    return entry.pid


def relaunch_entry(entry: runs.RunEntry, ref: int | str, resuming: bool) -> int:
    """A run's own command again (runs.again: its argv without --worker, detached), by its checkout's bin/heimdall,
    from its work dir ($HEIMDALL_WORK and $HEIMDALL said so), with the latest attempted Run's recorded config snapshot
    in place of live `configs/`, so it continues from its records, its complete points skipped. Its new run's id is
    chosen here ($HEIMDALL_RUN_ID). `resuming` (a pause, by its live [N]): the paused entry points at it
    (`resumed_by`), leaving the live list; else (a finished run, by its id) the entry is left as it is."""
    label = f"[{ref}]" if isinstance(ref, int) else ref
    named = f"{label} {entry.id}" if isinstance(ref, int) else entry.id
    command = runs.again(entry)
    if not command or len(command) < 2:
        raise HeimdallError(f"{named} holds no heimdall run command to run again",
                            hint="run it again by hand; heimdall runs --forget drops it from the list" if resuming
                            else "run it again by hand")
    checkout = Path(entry.checkout or "")
    program = checkout / "framework" / "bin" / "heimdall"
    work = entry.work or ""
    if not entry.checkout or not program.is_file():
        raise HeimdallError(f"{named}'s Heimdall is not there: {program}",
                            hint=f"run it again by hand: heimdall {' '.join(command)}")
    if not work or not Path(work).is_dir():
        raise HeimdallError(f"{named}'s work dir is not there" + (f": {work}" if work else ""),
                            hint=f"run it again by hand from its work dir: heimdall {' '.join(command)}")
    config_root, config_name = resume_snapshot(entry, ref)
    command[1] = config_name
    new = runs.new_id()
    env = {**os.environ, runs.ID_VAR: new, paths.WORK_VAR: work, paths.CONFIGS_VAR: str(config_root)}
    if paths.HEIMDALL_VAR in env:                            # the checkout it ran with, not this shell's
        env[paths.HEIMDALL_VAR] = str(checkout)
    print(f"{'resuming' if resuming else 'running again'} {named}: heimdall {' '.join(command)}\n  in {work}, by {program}")
    if "--rerun-since" in command:
        print("  note: its --rerun runs again what was complete before it began, not what it completed itself",
              file=sys.stderr)
    if resuming:
        env[runs.RESUMES_VAR] = entry.id  # its worker clears resumed_by again if it never runs (exit 2)
        runs.update(entry.id, resumed_by=new, resumed=round(time.time(), 3))
    code = runs.relaunch([str(program), *command], work, env).returncode
    if code:
        if resuming:
            runs.update(entry.id, resumed_by=None, resumed=None)
            print(f"not resumed: its command exited {code}; {label} stays paused", file=sys.stderr)
        else:
            print(f"not run again: its command exited {code}", file=sys.stderr)
        return code
    print(f"{named} {'resumed' if resuming else 'run again'} as {new}: heimdall runs says whether it runs "
          "(a config error " + ("leaves it paused)" if resuming else "ends it at once)"))
    return 0


def resume_run(index: int) -> int:
    """`heimdall runs --resume N`: the paused job [N] resumed (relaunch_entry)."""
    entry, state = live_at(index)
    refuse_newer(entry)
    if not runs.paused(entry):
        raise HeimdallError(f"[{index}] is {state}, not paused: only a paused job is resumed",
                            hint=f"heimdall watch -i {index} follows it" if state.word == "running" else
                            "heimdall runs lists the live ones")
    return relaunch_entry(entry, index, True)


def entry_of(ref: str | int) -> tuple[runs.RunEntry, runs.RunState, int | None]:
    """A run `heimdall runs` names: its live [N] (digits), or its id, whole or the tail of it (`…-e17e`) when one
    entry has it. (entry, state, its live number or None)."""
    text = str(ref).strip()
    entries = runs.entries()
    if text.isdigit():
        try:
            entry, state = live_at(int(text))
            return entry, state, int(text)
        except HeimdallError:                    # past the live list: the tail of an id may be digits (…-5322)
            if not any(e.id.endswith(text) for e in entries):
                raise
    found = [e for e in entries if e.id == text] or [e for e in entries if text and e.id.endswith(text)] \
        or [e for e in entries if text and text in e.id]
    if len(found) != 1:
        raise HeimdallError(f"no run '{text}'" if not found else f"{len(found)} runs match '{text}': "
                            + ", ".join(e.id for e in found[:5]),
                            hint="its id as heimdall runs --week shows it, or its live [N]")
    by_pid = {hello.get("pid"): hello for _, hello in house.live_runs()}
    entry = found[0]
    numbers = {id(e): n for n, (e, _) in enumerate(house.live_entries(entries, house.live_runs()), 1)}
    return entry, house._states([entry], by_pid)[0][1], numbers.get(id(entry))


def again_run(ref: str | int) -> int:
    """`heimdall runs --again ID|N`: a failed, stopped or lost run's own command again (relaunch_entry); refused, with
    its state, for a run that goes or is paused (heimdall runs --resume), and a cluster submission's."""
    entry, state, number = entry_of(ref)
    refuse_newer(entry)
    shown = f"[{number}]" if number else entry.id
    if entry.cluster:
        raise HeimdallError(f"{shown} is a cluster submission: heimdall cluster submits it again",
                            hint="heimdall runs names its heimdall cluster … --status")
    if runs.paused(entry):
        raise HeimdallError(f"{shown} is paused, not finished: heimdall runs --resume {number or ''}".rstrip(),
                            hint="a pause continues from its records; --again is for a run that ended")
    if house._going(entry, state) or entry.finished is None and state.word != "lost":
        raise HeimdallError(f"{shown} is {state}, not finished: only a run that ended is run again",
                            hint=f"heimdall watch -i {number} follows it" if number else "heimdall runs lists the live ones")
    return relaunch_entry(entry, entry.id if not number else number, False)


#: The keys of `heimdall runs -i`, and the word typed to confirm each that changes something.
ACTIONS = {"w": ("watch", None), "s": ("stop", "stop"), "j": ("set jobs", None), "r": ("resume", "resume"),
           "a": ("run again", "again"), "f": ("forget", "forget"), "d": ("dispatch", "dispatch"), "q": ("leave", None)}


def offered(entry: runs.RunEntry, state: runs.RunState, number: int | None) -> list[str]:
    """The keys that fit a run: a running live one is watched or stopped, a paused one resumed or forgotten, a failed,
    stopped or lost one run again."""
    if entry.cluster:
        return ["q"]
    if number and state.word == "running":
        return ["w", "s", "j", "q"]
    if state.word in ("queued", "held"):
        return ["d", "s", "f", "q"]
    if number and runs.paused(entry):
        return ["r", "f", "q"]
    if not house._going(entry, state) and (entry.finished is not None or state.word == "lost"):
        return ["a", "q"] if state.word in ("failed", "stopped", "lost") else ["q"]
    return ["q"]


def read_key() -> str:
    """One key from the terminal, unechoed (watch.Keys); "" for the end of input."""
    from .watch import Keys
    with Keys(sys.stdin):
        return os.read(sys.stdin.fileno(), 1).decode("utf-8", "replace")


def act_on(ref: str, titles: dict, plain: bool = False, key_reader=None, line_reader=None) -> int:
    """`heimdall runs -i N|ID`: the run's block; on a terminal (or with readers given) the keys that fit it, one read; the
    ones that change something ask for their word typed (`stop`, `resume`, `again`, `forget`) and anything else cancels."""
    entry, state, number = entry_of(ref)
    tty = sys.stdin.isatty() and sys.stdout.isatty()
    color = house.wants_colour(sys.stdout, plain)
    width = shutil.get_terminal_size((80, 24)).columns if sys.stdout.isatty() else None
    for line in house.runs_listing(runs.entries(), house.live_runs(), titles, color=color, width=width, only=entry):
        print(line)
    refuse_newer(entry)
    keys = offered(entry, state, number)
    if key_reader is None and not tty:
        return 0
    if keys == ["q"]:
        print(f"nothing to do with a run that is {state}")
        return 0
    print("  " + " · ".join(f"{k} {ACTIONS[k][0]}" for k in keys))
    key = (key_reader or read_key)().lower()
    if key not in keys or key == "q":
        print("left it" if key in ("q", "", "\x03", "\x1b", "\n") else f"'{key}' is not one of: {' '.join(keys)}")
        return 0
    verb, word = ACTIONS[key]
    if word is not None:
        typed = (line_reader or input)(f"type {word} to {verb} it (anything else cancels): ").strip()
        if typed != word:
            print(f"cancelled: {verb} not done")
            return 0
    if key == "j":
        text = (line_reader or input)("points at once now: ").strip()
        if not text.isdigit():
            print(f"cancelled: '{text}' is no number of points")
            return 0
        return set_jobs(number, int(text))
    if key == "w":
        return cmd_watch(argparse.Namespace(index=number, file=None, config=None, configuration=None, plain=plain, pid=None))
    if key == "d":
        return dispatch_run(entry.id)
    if key == "s":
        return cmd_stop(argparse.Namespace(index=number, config=None, configuration=None, pid=None, no_wait=False))
    if key == "r":
        return resume_run(number)
    if key == "f":
        return forget_run(number or entry.id)
    return again_run(entry.id)


def set_jobs(ref: str | int, count: int) -> int:
    """`heimdall runs -i N --jobs M`: the running job's points at once changed while it runs (the request written to
    `runs/<id>.control.json`, then SIGUSR2): raising starts more points, lowering starts none until fewer than M run and
    stops none; the identity is untouched. Refused for a cluster submission, a run that is not running here (another PID namespace, a
    pause, an ended run; the registry lists this user's runs alone, so another uid's is none) and a count below 1; a note when M of its costliest points want more cores than
    the machine has."""
    from .events import namespace
    entry, state, number = entry_of(ref)
    refuse_newer(entry)
    shown = f"[{number}]" if number else entry.id
    if count < 1 or count > execute.Stopper.CEILING:
        raise HeimdallError(f"--jobs {count}: points at once is a number from 1 to {execute.Stopper.CEILING}", hint="heimdall runs -i N --jobs 4")
    if entry.cluster:
        raise HeimdallError(f"{shown} is a cluster submission: its jobs are on Slurm's nodes",
                            hint="heimdall cluster submits it again with another cluster.parallelism")
    if entry.pidns and namespace("pid") and entry.pidns != namespace("pid"):
        raise HeimdallError(f"{shown} (pid {entry.pid}) is another PID namespace's (a container's): signalling it from here "
                            "could reach another process", hint="change it from where it runs")
    if state.word != "running":
        raise HeimdallError(f"{shown} is {state}, not running: there is nothing to change",
                            hint=f"heimdall runs --resume {number} continues a pause" if number and runs.paused(entry) else
                            "heimdall runs lists what runs")
    if not entry.pid:
        raise HeimdallError(f"{shown} records no pid to tell", hint="heimdall runs lists what runs")
    if not runs.write_control(entry.id, count):
        raise HeimdallError(f"the request could not be written to {runs.control_file(entry.id)}", hint="is Himinbjorg writable?")
    os.kill(int(entry.pid), signal.SIGUSR2)
    was = entry.parallelism
    print(f"{shown} {entry.id}: points at once " + (f"{was} → {count}" if was else f"→ {count}")
          + " (it reads the request now; heimdall runs -i shows it, and a watch says it when it does)")
    each = entry.point_cores or 1
    if count * each > (os.cpu_count() or 1):
        print(f"  note: {count} at once × ~{each} core(s) a point is more than the {os.cpu_count()} here: it will be oversubscribed",
              file=sys.stderr)
    return 0


def forget_run(ref: str | int) -> int:
    """`heimdall runs --forget N|ID`: a paused job out of the live list; a queued or held one out of its queue, unrun
    (its waiting worker ends it: wait_turn), the run after it then waiting for the one before it."""
    entry, state, number = entry_of(ref)
    refuse_newer(entry)
    index = number or entry.id
    if state.word in ("queued", "held"):
        if not runs.ask_queue(entry.id, "forget"):
            raise HeimdallError(f"{runs.queue_file(entry.id)} cannot be written")
        print(f"forgetting: [{index}] {entry.id} leaves its queue unrun"
              + (f"; the run after it waits for {entry.queued_to}" if entry.queued_to else ""))
        return 0
    if not runs.paused(entry):
        raise HeimdallError(f"[{index}] is {state}, not paused: only a paused job is forgotten",
                            hint="heimdall runs lists the live ones")
    runs.update(entry.id, forgotten=round(time.time(), 3))
    print(f"forgotten: [{index}] {entry.id} (its entry kept: heimdall runs --week lists it)")
    return 0


def dispatch_run(ref: str | int) -> int:
    """`heimdall runs --dispatch ID|N`: a queued or held run started now (its waiting worker asked: wait_turn), heading
    a queue of its own with the runs after it."""
    entry, state, number = entry_of(ref)
    refuse_newer(entry)
    shown = f"[{number}] {entry.id}" if number else entry.id
    if state.word not in ("queued", "held"):
        raise HeimdallError(f"{shown} is {state}, not queued: only a queued or held run is dispatched",
                            hint="heimdall runs lists the queues")
    if not runs.ask_queue(entry.id, "dispatch"):
        raise HeimdallError(f"{runs.queue_file(entry.id)} cannot be written")
    print(f"dispatched: {shown} starts now (within {runs.QUEUE_POLL:g} s), heading a queue of its own; "
          f"heimdall watch --pid {entry.pid} follows it")
    return 0


def resume_snapshot(entry: runs.RunEntry, index: int | str) -> tuple[Path, str]:
    """The latest attempted Run's config snapshot for `heimdall runs --resume` and `--again`, never today's configs/."""
    named = f"[{index}] {entry.id}" if isinstance(index, int) else entry.id
    records = entry.records
    if not isinstance(records, list) or not records or not isinstance(records[-1], str):
        raise HeimdallError(f"{named} has no recorded config snapshot to resume",
                            hint="the paused job's record must contain config/snapshot.toml; run it again by hand")
    folder = Path(records[-1]).expanduser().resolve()
    try:
        snapshot = record.read_snapshot(folder)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise HeimdallError(f"{named}'s latest record has no readable config snapshot: {error}",
                            where=str(folder / "config" / record.SNAPSHOT),
                            hint="resume needs the config snapshot written by the paused Run") from None
    snapshot_name = snapshot["config"]
    if not isinstance(snapshot_name, str) or not snapshot_name:
        raise HeimdallError(f"{named}'s snapshot has no valid config name",
                            where=str(folder / "config" / record.SNAPSHOT))
    name = Path(snapshot_name)
    if name.is_absolute() or ".." in name.parts:
        raise HeimdallError(f"{named}'s snapshot has an invalid config name: {snapshot_name!r}",
                            where=str(folder / "config" / record.SNAPSHOT))
    config_root = folder / "config"
    filename = name if name.suffix == ".toml" else Path(f"{name}.toml")
    config_file = (config_root / filename).resolve()
    if not config_file.is_relative_to(config_root.resolve()) or not config_file.is_file():
        raise HeimdallError(f"{named}'s latest record has no errand file for {snapshot_name!r}",
                            where=str(config_file), hint="resume needs the errand file in the record's config/ snapshot")
    return config_root, str(config_file.relative_to(config_root.resolve()).with_suffix(""))


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
            raise HeimdallError("this record has no run.jsonl: it ran before Runs kept their own log", where=str(record_dir),
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


def cmd_show(args) -> int:
    """`heimdall show RECORD[/POINT[/TAG]]` (names P2): the views of house.show_data, read-only; `--log`, `--full` and
    `--attempt` are `heimdall log`'s output."""
    if args.log or args.full or args.attempt is not None:
        return cmd_log(args)
    record_dir, point, tag = house.log_target(args.target)
    data = house.show_data(record_dir, point, tag, parts=args.parts)
    if args.json:
        print(json.dumps(data, indent=1, sort_keys=True))
    else:
        for line in house.show_lines(data):
            print(line)
    return 0


def cmd_tag(args) -> int:
    """`heimdall tag RECORD [NAME] [--clear]` (V223): a configuration folder's tag shown, set or removed, in its
    record (the source of truth) and its plot document's [source].tag."""
    target, path = args.target, Path(args.target).expanduser().resolve()
    if path.is_relative_to(results_root()) and len(rel := path.relative_to(results_root()).parts) > 3:
        target = str(results_root().joinpath(*rel[:3]))       # into the folder (its plot.toml, plots/): the folder
    folder, point, _ = house.log_target(target)
    if point is not None:
        raise HeimdallError(f"'{args.target}' names a point: a tag is a configuration folder's",
                            hint=f"heimdall tag {folder.relative_to(records_root())} [NAME]")
    for line in house.tag_lines(folder, args.words, args.clear):
        print(line)
    return 0


def cmd_watch(args) -> int:
    """Follow a job from another terminal (V72): a running `heimdall run`'s watch socket (the latest one, or
    the one running CONFIG [CONFIGURATION]), or with --file a --journal run's status.jsonl; `-i N` the live run [N]
    of `heimdall runs`, refused for a paused one."""
    if getattr(args, "index", None) is not None:
        if args.file or args.config or args.pid is not None:
            raise HeimdallError("-i names the job itself: no config, --file or --pid with it",
                                hint=f"heimdall watch -i {args.index}")
        args.pid = running_at(args.index, "watched")
    if args.file:
        path = Path(args.file)
        if not path.exists():
            raise HeimdallError("no such status file", where=str(path), hint="a run writes one with heimdall run … --journal")
        return follow_file(path, plain=args.plain)
    wanted = configmod.load(args.config) if args.config else None
    found = house.live_runs(str(wanted.path) if wanted else None, args.configuration, getattr(args, "pid", None))
    if not found:
        last = next((e for e in runs.entries() if e.kind == "run" and e.finished is not None
                     and (wanted is None or e.config == str(wanted.path))), None)
        ended = (f"; the last ({last.id}) ended {runs.state(last)}" + (f", its log {last.log}" if last.log else "")
                 if last else "")
        raise HeimdallError("no running job to watch" + (f" for {wanted.path}" if wanted else "")
                       + (f" with pid {args.pid}" if getattr(args, "pid", None) else ""),
                       hint=f"heimdall runs lists them{ended}; a finished run's events: heimdall run … --journal, then "
                            "heimdall watch --file records/<A>/<E>/<R>/status.jsonl")
    name, hello = found[0]
    where = hello.get("address") or name
    if not live(args):
        return follow_events(connect(where), plain=args.plain)
    from .events import namespace, open_stream
    from .watch import Keys, follow
    hint = "d or Ctrl-C: detach · p: pause the run · q: stop the run"
    stopping, pausing = [], []

    def on_key(key: str, shown) -> str | None:              # d leaves; q stops the run, once (V183); p pauses it
        if key in "dD":
            return "detached"
        if key not in "qQpP":
            return None
        pause = key in "pP"
        if hello.get("pidns") and namespace("pid") and hello["pidns"] != namespace("pid"):
            shown.say(f"not {'paused' if pause else 'stopped'}: its process is another PID namespace's; "
                      f"{'pause' if pause else 'stop'} it from where it runs")
        elif pause:                                         # once a pause, twice a force pause
            if stopping:
                shown.say("already stopping: a stop is not made a pause")
            else:
                pause_key(hello["pid"], shown, pausing, "q: stop the run · d or Ctrl-C: detach")
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
            errand = configmod.load(name, sets=list(sets))
            for key in ([configuration] if configuration else list(errand.configurations)):
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
        raise HeimdallError(f"a job of this work dir is going (pid {going[0].get('pid')})",
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
    if gone:                                  # records are precious: always asked for, by name
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


def cmd_records(args) -> int:
    """`heimdall records upgrade [--dry-run] [A[/E[/R]]]`: the record files below the current format listed, and (without
    --dry-run) each given `format`, a copy of it beside it first (`<name>.bak`). The layout moves of `heimdall migrate
    --layout` are counted and left to it: they are a work dir's, staged, and its own to apply."""
    from . import migrate
    from .paths import work_root
    scope = args.scope.strip("/")
    found = migrate.format_files(scope)
    work = work_root()
    pending = len(migrate.layout_moves(work)) + len(migrate.logs_moves(work)) + len(migrate.sets_moves(work)) if work else 0
    for path, what in found:
        print(f"{what:34s} {path}")
    if pending:
        print(f"layout: {pending} move(s) pending, which heimdall migrate --layout [--list] shows and --apply makes")
    if not found:
        print("nothing to upgrade: every record file is at the current format" + (f" under {scope}" if scope else ""))
        return 0
    if args.dry_run:
        print(f"{len(found)} file(s) to upgrade (a dry run: leave out --dry-run to write them, each after a copy)")
        return 0
    if (going := house.runs_here(work_root())):
        raise HeimdallError(f"a job of this work dir is going (pid {going[0].get('pid')})",
                       hint="upgrade the records when it has ended (heimdall runs lists it)")
    done = sum(migrate.upgrade_file(path) for path, what in found if what.startswith("add format"))
    print(f"upgraded {done} of {len(found)} file(s); each has its copy beside it (<name>.bak)")
    return 0


def cmd_library(args) -> int:
    """`heimdall library list | verify | prune | adopt` (points-library P5): `library.list_lines`, `verify`, `prune` and `adopt`. `prune`
    and `adopt` change nothing without `--yes`; `verify` and `list` read only. `adopt` and a real prune wait while a job of
    the work dir goes."""
    from .paths import work_root
    if args.yes and args.dry_run:
        raise HeimdallError("--yes and --dry-run: one or the other")
    if args.action in ("list", "verify") and (args.yes or args.duplicates):
        raise HeimdallError(f"--yes and --duplicates are prune's and adopt's, not {args.action}'s")
    if args.action == "adopt":
        if not args.scope:
            raise HeimdallError("adopt names the Run: heimdall library adopt <A>/<E>/<R>", hint="heimdall runs lists them")
        if args.duplicates:
            raise HeimdallError("--duplicates is prune's")
    if args.action in ("prune", "adopt") and args.yes and (going := house.runs_here(work_root())):
        raise HeimdallError(f"a job of this work dir is going (pid {going[0].get('pid')})",
                            hint="change the library when it has ended (heimdall runs lists it)")
    if args.action == "list":
        lines = library.list_lines(args.scope)
    elif args.action == "verify":
        lines, problems = library.verify(args.scope)
        for line in lines:
            print(line)
        return 1 if problems else 0
    elif args.action == "prune":
        lines = library.prune(args.scope, yes=args.yes, duplicates=args.duplicates)
    else:
        lines = library.adopt(args.scope, apply=args.yes)
    for line in lines:
        print(line)
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
    """`heimdall migrate --names [--apply]` (V213): a work dir from before the renames, here or above:
    its marker hep.toml → heimdall.toml, and Heimdall's old names in its own files rewritten (migrate.names_changes:
    `{hep}`, `HEP_*`, `$HEP`, `hepkit`, Whizard's `# hep:`, the editor's themes); then the Errand names' (migrate.errand_changes:
    [run] → [errand] and [run].project → [errand].assignment in its configs and its records' snapshots, [source]'s
    project and run → assignment and errand in its plot documents, `--set run.…` → `--set errand.…`). A dry run
    prints each diff; --apply writes them. `heimdall setup . --refresh` then brings the framework's own files to
    today's."""
    from . import migrate
    work = find_work() or migrate.old_marker()
    if work is None:
        raise HeimdallError("not inside a work dir", hint="run it in a work dir: one with heimdall.toml, or hep.toml from before the rename")
    marker, today = work / migrate.OLD_MARKER, work / paths.MARKER_FILE
    changes = migrate.errand_changes(work, migrate.names_changes(work))
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
                raise HeimdallError(f"'{name}' is no record", hint="a record is <A>/<E>/<R>, a folder of records/")
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
        errand, configuration = _record_config(folder)
        if (folder / "config" / record.SNAPSHOT).is_file():
            target, _ = write_documents(errand, configuration, plot.recorded(errand, configuration))
        else:                                               # no snapshot: its points as points.json has them
            target = plotdoc.from_manifest(folder, errand, configuration)
            _write_recipe(errand, target, print)
        drawn = sum(1 for m in plotdoc.load(target)[2] if m.recorded is not None and m.recorded == m.identity)
        print(f"wrote   {target} ({drawn} complete member(s))")
    return 0


def _record_config(folder: Path):
    """A record's run and configuration: its snapshot's (read as configs/ is), else the config its points.json
    names; its serial the folder's own."""
    snapshot = folder / "config" / record.SNAPSHOT
    data = json.loads((folder / "points.json").read_text(encoding="utf-8"))
    record.check_format(data, folder / "points.json")
    if snapshot.is_file():
        snap = record.read_snapshot(folder)
        key = snap["configuration"]
        with paths.configs_at(folder / "config"):                          # V179: read for its configuration
            errand = configmod.load(snap["config"], sets=list(snap.get("sets", [])), configuration=key)
    else:
        source = data.get("config_file", "")
        try:
            source = str(Path(source).resolve().relative_to(paths.configs_root().resolve()).with_suffix(""))
        except ValueError:
            pass
        key = data.get("configuration")
        errand = configmod.load(source, configuration=key)                  # V179: read for its configuration
    configuration = errand.configuration(key)
    head = folder.name.split("_", 1)[0]
    if head.isdigit():                                      # a serial is location only: the folder's own
        configuration.serial = int(head)
    if snapshot.is_file() and tools.run_folders(errand, configuration).record.resolve() != folder.resolve():
        raise HeimdallError(f"{folder} is not where its config runs '{key}' ({tools.run_folders(errand, configuration).record})",
                       hint="the record's config has moved or been renamed: write its plot.toml by hand, or rerun it")
    return errand, configuration


def migrate_snapshot(args) -> int:
    """`heimdall migrate --snapshot RECORD [--from CONFIG] [--apply]` (V158): a record that ran before snapshots
    is given one: the config (by default the one its points.json names, with the --set overrides its points'
    provenance records) is planned, its files copied into records/<A>/<E>/<R>/config/, and each recorded point said
    to have the same identity under it, or what differs (--why). A snapshot already there is replaced only with
    --apply. Edit the snapshot's files to match what ran (a value since left out), then `heimdall status RECORD`."""
    found = record.record_of(args.snapshot, need_snapshot=False)
    if found is None:
        raise HeimdallError(f"'{args.snapshot}' is no record", hint="a record is <A>/<E>/<R>, a folder of records/")
    manifest = found / "points.json"
    if not manifest.is_file():
        raise HeimdallError("this record has no points.json", where=str(manifest))
    data = json.loads(manifest.read_text(encoding="utf-8"))
    record.check_format(data, manifest)
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
            given = json.loads(prov.read_text(encoding="utf-8"))
            record.check_format(given, prov)
            sets = list(given.get("sets", []))
            break
    planned = build_plans(argparse.Namespace(config=source, set=sets, points=None, rerun=False, only=None),
                          data.get("configuration"))
    rel = found.relative_to(records_root())
    if planned.every and planned.every[0].folders.record.resolve() != found.resolve():
        raise HeimdallError(f"{source} runs '{data.get('configuration')}' into {planned.every[0].folders.record.relative_to(records_root())}, "
                       f"not {rel}", hint="--from the config that ran it (its serial and name)")
    made = record.write_snapshot(planned.errand, planned.configuration, planned.every)
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
    run) or moved. 5.1: output/ by lifecycle into records/, logs/ and .cache/; V157: logs/ into records/<A>/<E>/<R>/,
    and each configuration's points into points/ of records/ and results/; V164: pages into plots/<set>/, numbers
    into statistics/<set>/, the drawing's working files into .cache/."""
    from . import migrate
    from .paths import work_root
    if (going := house.runs_here(work_root())):               # V182: this work dir's, this user's
        raise HeimdallError(f"a job of this work dir is going (pid {going[0].get('pid')})",
                       hint="move the layout when it has ended (heimdall runs lists it)")
    work = work_root()
    first = migrate.layout_moves(work)
    then = [] if (work / "output").is_dir() else migrate.logs_moves(work)
    last = [] if first or then else migrate.sets_moves(work)
    if not first and not then and not last:
        print("nothing to move: the layout is today's")
        return 0
    for title, moves in (("output/ (5.1)", first), ("logs/ and points/", then), ("plots/ by set", last)):
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
    """`heimdall reproduce records/…/<point>/provenance.json` (V77): the point again, exactly as it ran,
    into .cache/<A>/reproduce/<identity>/ (its own records/ and results/), never over the original; then
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
    record.check_format(record_, path)
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
        sets = (["--set", f"cfgs.{key}.seed={record_['seed']}"] if planned.errand.form == 3 else
                ["--set", f'errand.cfgs.{key}.seed_type="manual"', "--set", f"errand.cfgs.{key}.manual_seed={record_['seed']}"])
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
    `--plain` may come anywhere, for any command; an unknown command gets the nearest."""
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


#: The commands whose flags an errand file's [heimdall] gives (V188): those that read one config.
FLAGGED = ("run", "plot", "cluster", "status", "watch", "stop")
#: Options a file never sets: what it would name of itself, or change of itself (its own text does that).
UNFLAGGED = {"set", "worker", "sweep_member", "help"}
#: What [heimdall] may set (the user, 2026-10-25): switches that say how you like a command to run, and keep.
PREFERENCES = ("rerun", "wait", "detach", "plain", "journal", "logs", "replot", "keep")
#: Every other option, by its dest, and why a file never sets it: a mode or a target is one command's job, a
#: selection one run's choice, and the study's own settings are [errand]'s keys.
NOT_PREFERENCES = {
    **dict.fromkeys(("plan", "why", "show_config", "dry_run", "status", "cancel", "style_sync", "across", "stack",
                     "no_wait", "stats_only"), ("a mode: what this one command does", "type it on the command line")),
    **dict.fromkeys(("card", "pid", "file", "plot_file", "index", "resume", "forget", "dispatch", "queued_to"),
                    ("a target: what this one command acts on", "type it on the command line")),
    **dict.fromkeys(("points", "page_points", "draw_sets", "stages", "only"),
                    ("a selection: a part of the run, chosen when it is run",
                     "type it on the command line; a run's sets are [errand] plot = [...] or a configuration's plot")),
    "tag": ("the study's own setting", "a configuration's tag key, or [errand] tag = \"...\""),
    "no_plot": ("the study's own setting", "[errand] plot = false"),
    "no_stats": ("the study's own setting", "[errand] stats = false"),
    "rerun_since": ("heimdall runs --resume's own", "heimdall runs --resume N gives it"),
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
    """An errand file's [heimdall] (V188) for the command reading it: each option the command line left unset takes
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
    """`heimdall build`: make, in the work dir (or, --framework, Heimdall): the module programs and
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


def cmd_docs(args) -> int:
    """`heimdall docs`: one self-contained page in the forge (nothing built in Heimdall); `--drift`: what may have gone stale."""
    from . import knowledge
    if args.drift:
        found = knowledge.drift()
        for page, files in found:
            print(f"{page}: {', '.join(files)}")
        if not found:
            print(f"no page's code changed since {knowledge.crystal_commit()[:10]} without a live doc")
        return 0
    target = knowledge.build_site()
    print(target)
    if not args.no_open:
        import webbrowser
        webbrowser.open(target.as_uri())
    return 0


def cmd_make(args) -> int:
    """`heimdall make [--framework] <path>/<X>.exe | <path>/<x>.so`: one source, through make."""
    from .paths import heimdall_root, work_root
    rest = list(args.rest)
    framework = "--framework" in rest
    rest = [a for a in rest if a != "--framework"]
    if not rest or rest[0] in ("-h", "--help"):
        print("usage: heimdall make [--framework] <path>/<X>.exe | <path>/<x>.so   (docs/stable/internals/build.md)")
        return 0
    os.execvp("make", ["make", "-C", str(heimdall_root() if framework else work_root()), "--no-print-directory", *rest])


def _system_python() -> str:
    """The first python3 on PATH that is not the machine's venv's or base's: the stack's builder makes them."""
    from .paths import himinbjorg
    venvs = {str((himinbjorg() / "venv" / "bin").resolve())}
    if os.environ.get("HEIMDALL_VENV"):
        venvs.add(str((Path(os.environ["HEIMDALL_VENV"]) / "bin").resolve()))
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(folder) / "python3"
        if folder and str(Path(folder).resolve()) not in venvs and candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


def cmd_stack(args) -> int:
    """`heimdall stack build|list|status|doctor`: the stack's builder (recipes/build_stack.py; on macOS
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
            if warning := setupmod.expects_warning(work):          # once per command (doc:layout)
                print(warning, file=sys.stderr)
            if (work / "output").is_dir() and not getattr(args, "layout", False):   # made before 5.1's split
                print("note: this work dir has output/ from before records/ and .cache/: its points rerun "
                      "until `heimdall migrate --layout --apply` moves it", file=sys.stderr)
            elif (work / "logs").is_dir() and any((work / "logs").iterdir()) and not getattr(args, "layout", False):
                print("note: this work dir has logs/ from before records/<A>/<E>/<R>/logs/ and points/: its points "
                      "rerun and its pages miss them until `heimdall migrate --layout --apply` moves them", file=sys.stderr)
            elif not getattr(args, "layout", False) and old_plots(work):
                print("note: this work dir has pages in results/…/plots/<backend>/ from before plots/<set>/: "
                      "`heimdall migrate --layout --apply` moves them, and the numbers into statistics/<set>/", file=sys.stderr)
        if args.command == "setup":
            if args.refresh:
                ask = input if sys.stdin.isatty() else None
                setupmod.refresh(Path(args.dir), yes=args.yes, ask=ask)
                return 0
            if args.old_project is not None:
                raise HeimdallError("--project is now --assignment",
                               hint=f"heimdall setup {args.dir} --assignment {args.old_project}")
            added = setupmod.setup(Path(args.dir), assignment=args.assignment, git=args.git, adopt=args.adopt, name=args.name,
                                   example=args.example)
            for line in setupmod.next_steps(Path(args.dir).expanduser().resolve(), added, args.assignment, args.git,
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
        if args.command in ("run", "plot", "status") and getattr(args, "config", None):
            if not (args.command == "plot" and (plotdoc.find(args.config) or getattr(args, "style_sync", None))):
                opened(args)                              # a record: its snapshot (V158)
        if (given := config_flags(args)):                 # V188: the file's own flags, where the command line has none
            print(f"heimdall: from [heimdall]: {' '.join(given)}", file=sys.stderr)
            _ask_keep(args)
        if args.command == "run":
            return cmd_run(args)
        if args.command == "plot":
            return cmd_plot(args)
        if args.command == "stats":
            return cmd_stats_retired(args)
        if args.command == "score":
            return cmd_score(args)
        if args.command == "diff":
            return cmd_diff(args)
        if args.command == "check":
            return cmd_check(args)
        if args.command == "overlay":
            return cmd_overlay(args)
        if args.command == "deck":
            return cmd_deck(args)
        if args.command == "report":
            return cmd_report(args)
        if args.command == "ls":
            for line in house.ls(args.assignment):
                print(line)
            return 0
        if args.command == "explain":
            for line in house.explain(args.key):
                print(line)
            return 0
        if args.command == "docs":
            return cmd_docs(args)
        if args.command == "context":
            from . import knowledge
            print(knowledge.context_text(), end="")
            return 0
        if args.command == "status":
            return cmd_status(args)
        if args.command == "clean":
            return cmd_clean(args)
        if args.command == "reproduce":
            return cmd_reproduce(args)
        if args.command == "migrate":
            return cmd_migrate(args)
        if args.command == "records":
            return cmd_records(args)
        if args.command == "cluster":
            return cmd_cluster(args)
        if args.command == "runs":
            return cmd_runs(args)
        if args.command == "stop":
            return cmd_stop(args)
        if args.command == "log":
            return cmd_log(args)
        if args.command == "show":
            return cmd_show(args)
        if args.command == "library":
            return cmd_library(args)
        if args.command == "tag":
            return cmd_tag(args)
        return cmd_watch(args)
    except HeimdallError as error:
        print(error.render(), file=sys.stderr)
        return 2
    except KeyboardInterrupt:                                      # Ctrl-C before a run catches it (V181)
        print("heimdall: stopped", file=sys.stderr)
        return 6
