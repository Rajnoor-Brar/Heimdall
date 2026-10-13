"""`hep run`, `hep plot`, `hep overlay`, `hep watch`, `hep check` and the housekeeping commands (`ls`,
`explain`, `status`, `clean`: house.py) (rank 5): argument parsing and the order of events.

docs/05_Commands_and_Tools.md §1. `hep build` is handled by the shell dispatcher
(framework/bin/hep), which runs make.

Exit codes: 0 every point done (or skipped), 1 a point failed, 2 a config error before anything ran,
6 stopped by the user. Under [run].sweep_runs (V38), several runs one after another: 6 if one was
stopped, else 1 if any failed (or could not be planned at its turn), else 0.
"""

from __future__ import annotations

import argparse
import json
import os
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
from . import deck as deckmod
from . import execute, house, plot, post, record, sweep, tools
from . import doctor as doctormod
from . import setup as setupmod
from .errors import HepError, did_you_mean
from .paths import check_retired, find_work, logs_root, records_root, results_root
from .quantities import load_master
from .events import Bus, Hub, Journal, RunBus, greeting, connect, hubs
from .watch import follow_events, follow_file, view


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="hep", description="the v2 runner")
    commands = top.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="plan and run a configuration")
    run.add_argument("config", help="configs/<Project>/<name>[.toml], or ./path from the work dir")
    run.add_argument("configuration", nargs="?", help="overrides [run].configuration; under [run].sweep_runs, runs only it")
    run.add_argument("--plan", action="store_true", help="print the plan; run nothing")
    run.add_argument("--why", action="store_true",
                     help="for each point that would run, what changed since it last completed; run nothing")
    run.add_argument("--show-config", action="store_true",
                     help="print each configuration's resolved values and where each came from; run nothing")
    run.add_argument("--card", metavar="TAG", help="with --plan: that tool's card for the first point, each line with "
                                                   "where its value comes from")
    run.add_argument("--points", metavar="SEL", help="run a subset: tags, indices or quantity=tag")
    run.add_argument("--set", metavar="KEY=VALUE", action="append", default=[],
                     help="override one value for this invocation (repeatable), in the file's own names: "
                          "run.events=100 (v3), run.event_count=100 (v2)")
    run.add_argument("--rerun", action="store_true", help="ignore skip-unchanged; under a serial the file sets, "
                                                          "overwrite points made from other inputs")
    run.add_argument("--only", choices=["pre", "post", "plot"], help="rerun only the pre tools, the post tools or the plots")
    run.add_argument("--stages", metavar="LIST",
                     help="run only these stages, skip-unchanged: pre, points, combine, post, plot (comma-separated; hep cluster's jobs)")
    run.add_argument("--plain", action="store_true", help="plain lines instead of the live view")
    run.add_argument("--wait", action="store_true",
                     help="a point another session is running: wait for it (default: skip it, naming who runs it)")
    run.add_argument("--journal", action="store_true",
                     help="also write every status event to logs/…/status.jsonl (for hep watch --file and replay)")
    run.add_argument("--logs", action="store_true",
                     help="keep every tool's whole output in logs/<tag>.log (default: only a failed tool's last lines)")

    draw = commands.add_parser("plot", help="draw a configuration's pages from its complete points")
    draw.add_argument("config", help="the run config")
    draw.add_argument("configuration", nargs="?", help="overrides [run].configuration; under sweep_runs, only it")
    draw.add_argument("--set", metavar="KEY=VALUE", action="append", default=[], help="as for hep run")

    overlay = commands.add_parser("overlay", help="overlay any YODA/ROOT files through Paint, with no run TOML")
    overlay.add_argument("files", nargs="+", metavar="FILE", help="YODA (.yoda, .yoda.gz) or ROOT files")
    overlay.add_argument("-o", "--output", help="where the pages go (default results/plots/<first file>)")
    overlay.add_argument("--labels", help="legend labels, comma-separated, one per file")
    overlay.add_argument("--objects", nargs="+", default=[], metavar="GLOB", help="only these YODA paths")
    overlay.add_argument("--formats", default="pdf,png", help="pdf, png, svg, eps (default pdf,png)")
    overlay.add_argument("--ratio", action="store_true", help="a ratio panel against the first curve")
    overlay.add_argument("--style", metavar="FILE", help="a style file over src/Apps/Paint/base.toml")

    deck = commands.add_parser("deck", help="a deck of slides from drawn pages, in reports/<deck>/ (deck.toml, deck.md)")
    deck.add_argument("deck", help="reports/<deck>, or a path starting ./, ../ or /")
    deck.add_argument("--list", action="store_true", help="each block, its panels and where they came from; nothing written")
    deck.add_argument("--only", metavar="TARGETS", help="some of pdf, pptx, html, overleaf, viewer (comma-separated)")
    deck.add_argument("--init", action="store_true", help="write deck.md once: a title slide and a slide per block")

    listing = commands.add_parser("ls", help="every config and its configurations")
    listing.add_argument("project", nargs="?", help="only this project's configs")

    explain = commands.add_parser("explain", help="a run TOML key: its type, default and meaning (the schema's)")
    explain.add_argument("key", help="e.g. plot.y_gutter, run.events, cfgs.pdf.threads, quantities.<q>.points, rivet.analyses")

    state = commands.add_parser("status", help="each configuration's points: complete, stale, incomplete or to run")
    state.add_argument("config", nargs="?", help="one config (default: every config)")
    state.add_argument("configuration", nargs="?", help="one configuration of it")
    state.add_argument("--stack", action="store_true", help="the loaded stack instead: each package installed, its release and state; the libraries' versions")

    move = commands.add_parser("migrate", help="rewrite run TOMLs and their cards in today's forms (a diff, or --apply)")
    move.add_argument("configs", nargs="*", metavar="CONFIG", help="configs to migrate (default: every config)")
    move.add_argument("--v3", action="store_true", help="into the run TOML's third form (03 §6, runner/v3.py)")
    move.add_argument("--layout", action="store_true",
                      help="move the work dir's output/ into records/, logs/ and .cache/ (no configs are read)")
    move.add_argument("--apply", action="store_true", help="write the changes (default: print the diff)")

    again = commands.add_parser("reproduce", help="run a finished point again, from its provenance, beside it")
    again.add_argument("provenance", help="records/…/<point>/provenance.json")
    again.add_argument("--anyway", action="store_true", help="run it even though the setup changed since")
    again.add_argument("--plain", action="store_true", help="plain lines instead of the live view")

    clean = commands.add_parser("clean", help="remove what the runner made and no plan uses: logs/ and .cache/ (records/ with --records)")
    clean.add_argument("config", nargs="?", help="one config (default: every config, and the unused caches)")
    clean.add_argument("--dry-run", action="store_true", help="list only")
    clean.add_argument("--yes", action="store_true", help="delete without asking")
    clean.add_argument("--records", action="store_true",
                       help="also the records no plan has (provenance, identities, completion): asked for even with --yes")

    check = commands.add_parser("check", help="check run TOMLs: every configuration loaded, validated and planned")
    check.add_argument("configs", nargs="*", metavar="CONFIG",
                       help="configs to check (default: every configs/<Project>/*.toml with a [run])")

    watch = commands.add_parser("watch", help="attach the live view to a running job")
    watch.add_argument("config", nargs="?", help="the run config whose job to watch (default: the latest job)")
    watch.add_argument("configuration", nargs="?", help="overrides [run].configuration (or the sweep's latest)")
    watch.add_argument("--plain", action="store_true", help="plain lines instead of the live view")
    watch.add_argument("--file", metavar="STATUS.JSONL", help="follow a --journal run's status file instead")

    batch = commands.add_parser("cluster", help="run a configuration as Slurm jobs (sbatch): a pre job, a point per array task, a finish job")
    batch.add_argument("config", help="the run config, as hep run names it")
    batch.add_argument("configuration", nargs="?", help="overrides [run].configuration; under [run].sweep_runs, submits only it")
    batch.add_argument("--points", metavar="SEL", help="submit a subset: tags, indices or quantity=tag")
    batch.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                       help="override one value for this submission (repeatable; cluster.time=… too); the jobs get it")
    batch.add_argument("--rerun", action="store_true", help="submit complete points too, and rerun them")
    what = batch.add_mutually_exclusive_group()
    what.add_argument("--dry-run", action="store_true", help="write the job scripts and print the sbatch lines; submit nothing")
    what.add_argument("--status", action="store_true", help="the latest submission: each point's state (sacct, squeue)")
    what.add_argument("--cancel", action="store_true", help="scancel the latest submission's jobs")

    make = commands.add_parser("setup", help="make a work dir: the key folders, hep.toml and the template's files (never overwrites)")
    make.add_argument("dir", help="the work dir's folder: new, empty, or a work dir to complete")
    make.add_argument("--project", metavar="P", help="also configs/<P>/ with a starter run TOML and card, and modules/<P>/")
    make.add_argument("--git", action="store_true", help="git init, and commit what was added")
    make.add_argument("--adopt", action="store_true", help="make a work dir of a folder that has files but no hep.toml")
    make.add_argument("--name", help="the work dir's name in hep.toml (default: the folder's)")

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
                                               "tool.toml, is laid over it. `hep tools <name>`: one folder in full; "
                                               "`hep tools new <name> --from <tool>`: a folder in this work dir's tools/.")
    folders_.add_argument("what", nargs="*", metavar="NAME | new NAME", help="a folder to show, or new and a folder to make")
    folders_.add_argument("--from", dest="source", help="hep tools new: the folder it starts from (exec, module: a copy; "
                                                        "any other: extends it)")

    where = commands.add_parser("where", help="which Heimdall and which work dir this shell sees")
    which = where.add_mutually_exclusive_group()
    which.add_argument("--hep", action="store_const", const="hep", dest="which", help="only Heimdall's folder")
    which.add_argument("--work", action="store_const", const="work", dest="which", help="only the work dir (exit 2 outside one)")
    return top


@dataclass
class Planned:
    """One run, planned: what `hep run CONFIG CONFIGURATION` executes."""
    run: configmod.RunConfig
    configuration: configmod.Configuration
    every: list                                    # every point's plan
    plans: list                                    # the points to run (--points)
    post: object                                   # the post stage's plan, or None
    pre: object                                    # the pre stage's plan, or None
    combined: list                                 # the combined groups (V35)


def build_plans(args, key: str | None) -> Planned:
    run = configmod.load(args.config, sets=args.set)
    plot.validate(run)                       # before anything is planned (V54): a [plot] typo costs no planning
    configuration = run.configuration(key)
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
        raise HepError(f"configuration '{c.key}': {len(changed)} of its points in {tools.run_dir(planned.run, c)} were "
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


def journal_path(run, configuration) -> Path:
    """logs/<P>/<run>/<cfg>/status.jsonl: a --journal run's events, which hep watch --file follows."""
    return logs_root() / tools.run_dir(run, configuration) / "status.jsonl"


def header(number: int, configuration) -> str:
    """'run 02 - Beam energies -': a run's place in a sweep of runs, and its title (V38)."""
    return f"run {number:02d} - {configuration.title} -"


def _print_stage(title: str, stage, run) -> None:
    print(f"{title}   identity {stage.identity[:12]}")
    for line in tools.describe(stage, run)[1:]:
        print(line)
    print(f"  results {stage.res}   ({'complete' if record.is_complete(stage) else 'to run'})")


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
        count = len(sweep.pages(configuration, [p.point for p in plans]))
        print(f"plot ({', '.join(plot.backends(run.plot))}): {count} page(s) per object, "
              f"{', '.join(plot.formats_of(run.plot))} → {plans[0].res.parent / 'plots'}")


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


def catch_signals(stopper: execute.Stopper) -> None:
    """Ctrl-C (SIGINT) and SIGTERM ask the run to stop; a second one is the default behaviour."""
    def on_signal(signum, frame):
        if stopper.requested:
            signal.signal(signum, signal.SIG_DFL)
        stopper.requested = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)


#: A run's stages, in order (V114). `--stages` runs some of them, skip-unchanged; `--only` runs one again.
STAGES = ("pre", "points", "combine", "post", "plot")


def stages_of(args) -> frozenset[str]:
    """The stages this `hep run` runs: `--only`'s one, `--stages`'s list, or all of them."""
    given = getattr(args, "stages", None)
    if given is None:
        return frozenset([args.only]) if getattr(args, "only", None) else frozenset(STAGES)
    if getattr(args, "only", None):
        raise HepError("--only and --stages do not go together",
                       hint="--only reruns one stage; --stages runs several, skipping what is unchanged")
    named = [s.strip() for s in given.split(",") if s.strip()]
    for stage in named:
        if stage not in STAGES:
            raise HepError(f"--stages: '{stage}' is not a stage", hint=did_you_mean(stage, STAGES) or ", ".join(STAGES))
    if not named:
        raise HepError("--stages names no stage", hint=", ".join(STAGES))
    return frozenset(named)


def cmd_run(args) -> int:
    """One run; or, under [run].sweep_runs, every swept configuration as a run of its own, one after
    another (V38). Each is exactly `hep run CONFIG <cfg>`, after a `run NN - <title> -` line. All are
    planned before the first starts, so a config error anywhere exits 2 with nothing run; one is
    planned again at its turn only if the TOML was edited meanwhile, so edits still count. A failed run leaves the next to
    start; a stop starts no more."""
    run = configmod.load(args.config, sets=args.set)
    keys = run.runs(args.configuration)
    if getattr(args, "show_config", False):
        for line in show_config(run, keys):
            print(line)
        return 0
    stopper = execute.Stopper()
    if getattr(args, "why", False) or args.plan or stages_of(args) == {"plot"}:
        bus = None                           # nothing runs: nothing to watch
    else:                                    # one stream for the whole process, served while it lives (V72)
        bus = Bus()
        hub = Hub({"config": str(run.path), "run": run.name, "configurations": keys})
        bus.subscribe(hub)
    code = 2
    try:
        code = _runs(args, run, keys, stopper, bus)
        return code
    finally:
        if bus is not None:
            hub.close()
            notify(run, code)


def notify(run, code: int) -> bool:
    """[run] notify = "desktop" (V76): a notify-send when the command ends, for runs of hours. Never
    fails the run: no notify-send, or no desktop, and it says nothing."""
    if run.raw.get("run", {}).get("notify", "none") != "desktop" or not shutil.which("notify-send"):
        return False
    verdict = {0: "done", 1: "a point failed", 2: "a config error", 6: "stopped"}.get(code, f"exit {code}")
    try:
        subprocess.Popen(["notify-send", "--app-name=hep", f"hep run {run.name}", f"{run.path.name}: {verdict}"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    return True


def _runs(args, run, keys: list[str], stopper: execute.Stopper, bus) -> int:
    if len(keys) == 1:
        return run_one(args, keys[0], stopper, bus=bus)
    if args.points:
        raise HepError("--points picks points of one configuration, and this sweep runs several",
                       where=f"{run.path}: [run].sweep_runs", hint=f"name it: hep run {args.config} <configuration> --points …")
    skipped, ahead = {}, {}
    stamp = run.path.stat().st_mtime_ns
    for key in keys:
        try:
            ahead[key] = planned = build_plans(args, key)
        except HepError as error:
            error.message = f"configuration '{key}': {error.message}"
            raise
        if args.only in ("pre", "post") and getattr(planned, args.only) is None:
            skipped[key] = f"   no {args.only} tools: skipped"
    if len(skipped) == len(keys):
        raise HepError(f"no configuration of this sweep has {args.only} tools", where=f"{run.path}: [run].sweep_runs")
    if bus is not None and args.only is None and getattr(args, "stages", None) is None:
        return _pipelined(args, run, keys, stopper, bus, ahead, stamp)
    failed = False
    for number, key in enumerate(keys, 1):
        if stopper.requested:
            return 6
        following = next((journal_path(run, run.configurations[k]) for k in keys[number:] if k not in skipped), None) \
            if args.journal else None
        if key in skipped:
            print(("\n" if number > 1 else "") + header(number, run.configurations[key]))
            print(skipped[key])
            continue
        try:                                 # planned again only if the TOML was edited meanwhile (V38, V54)
            unchanged = run.path.stat().st_mtime_ns == stamp
            code = run_one(args, key, stopper, number=number, following=following,
                           planned=ahead[key] if unchanged else None, bus=bus)
        except HepError as error:            # the TOML was edited since the check: this run fails alone
            print(("\n" if number > 1 else "") + header(number, run.configurations[key]))
            print(error.render(), file=sys.stderr)
            not_run(journal_path(run, run.configurations[key]) if args.journal else None,
                    header(number, run.configurations[key]), error.message, following, bus)
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
    shown = view(args.plain)
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
                if args.journal else None
            gate = threading.Event()

            def job(key=key, number=number, following=following, gate=gate) -> None:
                voice = RunBus(bus, key)
                try:                         # planned again only if the TOML was edited meanwhile (V38, V54)
                    unchanged = run.path.stat().st_mtime_ns == stamp
                    codes[key] = run_one(args, key, stopper, number=number, following=following,
                                         planned=ahead[key] if unchanged else None, bus=voice, shown=shown,
                                         budget=budget, gate=gate)
                except HepError as error:    # the TOML was edited since the check: this run fails alone
                    voice.say(header(number, run.configurations[key]))
                    voice.say(error.render())
                    not_run(journal_path(run, run.configurations[key]) if args.journal else None,
                            header(number, run.configurations[key]), error.message, following, voice)
                    codes[key] = 2
                except BaseException as error:           # the runner's own error: raised once all have ended
                    errors.append(error)
                    codes[key] = 1
                finally:
                    gate.set()

            thread = threading.Thread(target=job, name=f"hep-run-{key}")
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
    (--journal), so hep watch --file moves on."""
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


def run_one(args, key: str, stopper: execute.Stopper, *, number: int = 0, following: Path | None = None,
            planned: Planned | None = None, bus: Bus | None = None, shown=None, budget=None,
            gate: threading.Event | None = None) -> int:
    """One run: the pre stage, every point not complete, the combined groups, the post stage and the
    plots, said on `bus` (V72). In a sweep of runs, `number` is its place (a `run NN - <title> -` line
    first), and `following` is the next run's journal (--journal), named in this one's `run finished`
    event so that hep watch --file follows on."""
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
                    raise HepError("--card: no point to show", hint="--points picks one")
                for line in tools.card_view(plans[0], args.card):
                    print(line)
                return 0
            print_plan(run, configuration, plans, post_plan, pre_plan, combined)
            return 0
        return 1 if plot.draw(run, configuration, combined or every, print, others=others_of(args)) else 0
    if args.only == "post" and post_plan is None:
        raise HepError(f"configuration '{configuration.key}' has no post tools", where=f"{run.path}: [run.cfgs.{configuration.key}].post")
    if args.only == "pre" and pre_plan is None:
        raise HepError(f"configuration '{configuration.key}' has no pre tools", where=f"{run.path}: [run.cfgs.{configuration.key}].pre")
    if "points" in stages and "pre" not in stages and pre_plan is not None and not record.is_complete(pre_plan):
        raise HepError(f"configuration '{configuration.key}': the pre stage is not complete, and the points need it",
                       hint="run --stages pre first (hep cluster's pre job does), or leave --stages out")
    refuse_overwrites(planned, args, stages)
    if stopper.requested:                    # Ctrl-C while this run was being planned
        return 6

    bus = bus if bus is not None else Bus()
    own_view = shown is None                 # a pipelined sweep's runs share the sweep's view (V75)
    if own_view:
        shown = view(args.plain)
        bus.subscribe(shown)
    if threading.current_thread() is threading.main_thread():
        catch_signals(stopper)
    logs = bool(getattr(args, "logs", False))

    base = plans[0].out.parent if plans else None
    journal = Journal(base / "status.jsonl", run=getattr(bus, "run", None)) \
        if base and getattr(args, "journal", False) else None
    if journal:
        bus.subscribe(journal)
    title = (f"{run.name} · {configuration.key}: {len(plans)} point(s), {configuration.event_count} events, "
             f"{configuration.threads} threads" + parallel_note(configuration, plans))
    if number > 1:
        bus.say("")
    bus.emit("", "", {"k": "run", "state": "started", "points": len(plans), "title": title,
                      **({"header": title_line} if title_line else {})})
    if crowded(configuration, plans):
        bus.say(f"   note: {crowded(configuration, plans)}")
    for note in notes_of(plans):
        bus.say(f"   note: {note}")
    for warning in tools.meta_notes(run):                       # V97
        bus.say(f"   warning: {warning}")
    def manifest() -> None:                  # a points-only run (a cluster job) leaves it to the finish job
        if base and stages != {"points"}:
            record.write_atomic(record.manifest_file(every),
                                json.dumps(record.points_manifest(every, run, configuration), indent=1, default=str) + "\n")
    manifest()
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
        verdict = f"{done} done, {failed} failed, {len(plans) - done - failed} skipped" if "points" in stages else ""
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
            failed += plot.draw(run, configuration, combined or every, bus.say, others=others_of(args)) > 0   # the groups, when combined
        verdict = verdict or ", ".join(s for s in STAGES if s in stages) + " done"         # a run without its points
        bus.say(verdict)                     # before end(): the view's thread prints it (V32)
    finally:
        onward = {"next": str(following)} if following and not stopper.requested else {}
        bus.emit("", "", {"k": "run", "state": "finished", "verdict": verdict, **onward})
        if own_view:
            bus.unsubscribe(shown)
            shown.end()
        manifest()
        if journal:
            bus.unsubscribe(journal)
            journal.close()
    return 1 if failed else 0


def cmd_cluster(args) -> int:
    """`hep cluster` (V114): each configuration (every swept one under [run].sweep_runs) planned as hep run
    plans it, then submitted, or its latest submission's state shown, or cancelled (runner/cluster.py)."""
    run = configmod.load(args.config, sets=args.set)
    keys = run.runs(args.configuration)
    if len(keys) > 1 and args.points:
        raise HepError("--points picks points of one configuration, and this sweep runs several",
                       where=f"{run.path}: [run].sweep_runs", hint=f"name it: hep cluster {args.config} <configuration> --points …")
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
    """`hep overlay FILE…` (V74, was `hep plot FILE…`): any YODA/ROOT files overlaid through Paint."""
    bad = [f for f in args.files if not plot._is_plot_file(f)]
    if bad:
        raise HepError(f"{bad[0]} is not a YODA or ROOT file", hint="hep overlay takes files ending .yoda, .yoda.gz "
                                                                   "or .root; a configuration's pages: hep plot CONFIG")
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    wrong = [f for f in formats if f not in plot.FORMATS]
    if wrong:
        raise HepError(f"format '{wrong[0]}' is not one of {', '.join(plot.FORMATS)}")
    labels = [x.strip() for x in args.labels.split(",")] if args.labels else None
    return 1 if plot.files(args.files, Path(args.output) if args.output else None, labels=labels,
                           objects=args.objects, formats=formats, ratio=args.ratio, style=args.style) else 0


def cmd_deck(args) -> int:
    """`hep deck DECK` (docs/reporter): the deck's blocks, their panels collected into panels/ (V103), then
    its composites and slides built (V104); --init writes deck.md once."""
    made = deckmod.load(args.deck)
    if args.list:
        for line in deckmod.listing(made):
            print(line)
        return 0
    if args.init:
        for path in deckmod.init(made):
            print(f"deck: wrote {path}")
        return 0
    only = [t.strip() for t in args.only.split(",") if t.strip()] if args.only else None
    wrong = [t for t in only or () if t not in deckmod.TARGETS]
    if wrong:
        raise HepError(f"no target '{wrong[0]}'", hint=f"the targets: {', '.join(deckmod.TARGETS)}")
    copied = deckmod.gather(made)
    panels = sum(len(b.panels) for b in made.blocks)
    print(f"deck: {len(made.blocks)} block(s), {panels} panel(s); {copied} file(s) copied into {made.dir / deckmod.PANELS}")
    deckmod.build(made, only, print)
    return 0


def cmd_plot(args) -> int:
    """`hep plot CONFIG [CONFIGURATION]`: the configuration's pages from its complete points (what
    `hep run … --only plot` does)."""
    if plot._is_plot_file(args.config):                     # break and migrate (V74)
        raise HepError("hep plot draws a configuration's pages; files are overlaid by hep overlay",
                       hint=f"hep overlay {args.config} …")
    args.points = None
    run = configmod.load(args.config, sets=args.set)
    if not run.plot:
        raise HepError(f"{run.path} has no [plot] table", hint="add [plot], or give the files: hep plot FILE…")
    keys = run.runs(args.configuration)
    failed = False
    for number, key in enumerate(keys, 1):   # under [run].sweep_runs, every swept configuration's pages (V38)
        planned = build_plans(args, key)
        if len(keys) > 1:
            print(("\n" if number > 1 else "") + header(number, planned.configuration))
        failed = plot.draw(planned.run, planned.configuration, planned.combined or planned.every, print,
                           others=others_of(args)) or failed
    return 1 if failed else 0


def cmd_check(args) -> int:
    """`hep check [CONFIG…]` (V57): each config loaded, its [plot] validated and every configuration's
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
            run = configmod.load(name)
            points = 0
            for key in run.configurations:
                planned = build_plans(argparse.Namespace(config=name, set=[], points=None, rerun=False, only=None), key)
                points += len(planned.every)
            print(f"ok    {name}: {len(run.configurations)} configuration(s), {points} point(s)")
            for warning in [*tools.meta_notes(run), *house.unused_tools(run)]:   # said, never failed
                print(f"      warning: {warning}")
        except HepError as error:
            if importers.get(name) and not args.configs:
                print(f"ok    {name}: shared, imported by {', '.join(importers[name])} (checked through them)")
                continue
            failed += 1
            print(f"FAIL  {name}")
            print("      " + error.render().replace("\n", "\n      "))
    return 2 if failed else 0


def cmd_watch(args) -> int:
    """Follow a job from another terminal (V72): a running `hep run`'s watch socket (the latest one, or
    the one running CONFIG [CONFIGURATION]), or with --file a --journal run's status.jsonl."""
    if args.file:
        path = Path(args.file)
        if not path.exists():
            raise HepError("no such status file", where=str(path), hint="a run writes one with hep run … --journal")
        return follow_file(path, plain=args.plain)
    wanted = configmod.load(args.config) if args.config else None
    found = []
    for name in hubs():
        hello = greeting(name)
        if not hello:
            continue
        if wanted is not None and hello.get("config") != str(wanted.path):
            continue
        if args.configuration and args.configuration not in hello.get("configurations", []):
            continue
        found.append((hello.get("started", 0), name))
    if not found:
        raise HepError("no running job to watch" + (f" for {wanted.path}" if wanted else ""),
                       hint="start one with hep run; a finished run's events: hep run … --journal, then hep watch --file "
                            "logs/<P>/<run>/<cfg>/status.jsonl")
    return follow_events(connect(max(found)[1]), plain=args.plain)


def _planned_all(names: list[str], configuration: str | None = None) -> tuple[list, list[str]]:
    """Every configuration of these configs, planned as for a run: the plans, and what did not plan."""
    planned, failed = [], []
    for name in names:
        try:
            run = configmod.load(name)
            for key in ([configuration] if configuration else list(run.configurations)):
                planned.append(build_plans(argparse.Namespace(config=name, set=[], points=None, rerun=False, only=None), key))
        except HepError as error:
            failed.append(f"{name}: {error.message}")
    return planned, failed


def cmd_status(args) -> int:
    """`hep status [CONFIG [CONFIGURATION]]` (V74): each configuration's points and stages. `--stack`
    (V78, V123): every recipe installed in the loaded stack, then env/stack.toml's libraries and versions."""
    if getattr(args, "stack", False):
        from .doctor import stack_status
        for line in stack_status():
            print(line)
        return 0
    names = [args.config] if args.config else house.config_names()
    planned, failed = _planned_all(names, args.configuration)
    for line in house.status(planned, house.running_configs()):
        print(line)
    for line in failed:
        print(f"not planned: {line}")
    return 2 if failed else 0


def cmd_clean(args) -> int:
    """`hep clean [CONFIG] [--dry-run] [--yes]` (V74): the output folders no plan uses, `.partial`
    leftovers and (with no config) unused run folders and prepare caches. It lists them first, and asks
    on a terminal (or needs --yes); results/ is never cleaned but for `.partial` leftovers."""
    if hubs():
        raise HepError("a job is running on this machine", hint="clean when it has ended (hep watch shows it)")
    names = [args.config] if args.config else house.config_names()
    planned, failed = _planned_all(names)
    if failed and not args.config:
        for line in failed:
            print(f"not planned: {line}")
        raise HepError("every config must plan before a whole clean: one that does not might own what would go",
                       hint="fix it, or clean one config: hep clean CONFIG")
    if failed:
        raise HepError(failed[0])
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
    gone = [t for t in targets if t.is_relative_to(records_root())]
    if gone:                                  # records are precious: always asked for, by name (U21)
        if not sys.stdin.isatty():
            raise HepError(f"{len(gone)} record folders to remove: not deleted", hint="run it on a terminal, which asks")
        if input(f"remove {len(gone)} record folders (their points' provenance and completion)? type 'records': ").strip() != "records":
            print("nothing removed")
            return 0
    elif not args.yes:
        if not sys.stdin.isatty():
            raise HepError(f"{len(targets)} to remove: not deleted", hint="--yes to delete, --dry-run to only list")
        if input(f"remove these {len(targets)}? [y/N] ").strip().lower() not in ("y", "yes"):
            print("nothing removed")
            return 0
    freed = house.remove(targets)
    print(f"removed {len(targets)}, {freed / 1e6:.1f} MB freed")
    return 0


def cmd_migrate(args) -> int:
    """`hep migrate [CONFIG…] [--apply]` (V79): the diff of each file today's forms change, or (--apply)
    the files rewritten. Configs are read as they are (the forms the runner now refuses included)."""
    from . import migrate
    if getattr(args, "layout", False):
        return migrate_layout(args)
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


def migrate_layout(args) -> int:
    """`hep migrate --layout [--apply]` (5.1): output/ by lifecycle, counted (a dry run), or moved."""
    from . import migrate
    from .paths import work_root
    if hubs():
        raise HepError("a job is running on this machine", hint="move the layout when it has ended")
    work = work_root()
    moves = migrate.layout_moves(work)
    if not moves:
        print("nothing to move: no output/ (the layout is records/, logs/ and .cache/ already)")
        return 0
    counts: dict[str, int] = {}
    for _, target in moves:
        root = target.relative_to(work).parts[0]
        counts[root] = counts.get(root, 0) + 1
    for root, n in sorted(counts.items()):
        print(f"output/ → {root + '/':9s} {n} file(s)")
    if not args.apply:
        print(f"{len(moves)} file(s) to move (a dry run: --apply moves them)")
        return 0
    left = migrate.apply_layout(moves, work)
    print(f"moved {len(moves) - left} file(s)" + (f"; {left} left in output/ (already there)" if left else ""))
    return 0


def cmd_reproduce(args) -> int:
    """`hep reproduce records/…/<point>/provenance.json` (V77, F10): the point again, exactly as it ran,
    into logs/<P>/.reproduce/<identity>/ (its own records/, logs/ and results/), never over the original; then
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
        raise HepError(f"cannot read {path}: {error}", hint="give a finished point's provenance.json")
    from .paths import unportable
    config_file, key, name = unportable(record_["config_file"]), record_["configuration"], record_["point"]
    for line in record.revision_changes(record_.get("git", {})):    # the code may differ, though the setup does not
        print(f"warning: {line}", file=sys.stderr)
    given = list(record_.get("sets", []))                     # the --set overrides it ran with
    planned = build_plans(argparse.Namespace(config=config_file, set=given, points=None, rerun=False, only=None), key)
    plan = next((p for p in planned.every if p.point.name == name), None)
    if plan is None:
        raise HepError(f"configuration '{key}' has no point '{name}' any more", where=config_file)
    if plan.identity != record_["identity"]:
        print(f"the setup of {name} changed since it ran ({record_['identity'][:12]} → {plan.identity[:12]}):")
        for line in record.why(plan):
            print(f"  {line}")
        if not args.anyway:
            raise HepError("not reproduced: this would be a different point", hint="--anyway runs today's setup with its seed")
    where = logs_root() / record_["project"] / ".reproduce" / record_["identity"][:12]
    sets = []
    if planned.configuration.seed_type == "random":                      # in the file's own names
        sets = (["--set", f"cfgs.{key}.seed={record_['seed']}"] if planned.run.form == 3 else
                ["--set", f'run.cfgs.{key}.seed_type="manual"', "--set", f"run.cfgs.{key}.manual_seed={record_['seed']}"])
    argv = [sys.executable, str(Path(__file__).resolve().parents[1] / "bin" / "run"), "run", config_file, key,
            "--points", name, "--rerun", *[x for item in given for x in ("--set", item)], *sets,
            *(["--plain"] if args.plain else [])]
    env = dict(os.environ, HEP_RECORDS=str(where / "records"), HEP_LOGS=str(where / "logs"), HEP_RESULTS=str(where / "results"))
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


def parse(argv: list[str]) -> argparse.Namespace:
    """The command line, with options and positionals in any order (`hep run jets --plain pdf`, V54):
    argparse's intermixed parsing does not take subcommands, so the subcommand's own parser reads the rest."""
    top = parser()
    commands = next(a for a in top._actions if isinstance(a, argparse._SubParsersAction))
    if argv and argv[0] in commands.choices:
        args = commands.choices[argv[0]].parse_intermixed_args(argv[1:])
        args.command = argv[0]
        return args
    return top.parse_args(argv)                  # --help, or an unknown command: argparse's own message


def main(argv: list[str]) -> int:
    args = parse(argv)
    try:
        check_retired()                                            # a shell with High-Energy's names (K15)
        if args.command != "setup" and (work := find_work()) is not None:
            if warning := setupmod.expects_warning(work):          # once per command (framework/01 §4.2)
                print(warning, file=sys.stderr)
            if (work / "output").is_dir() and not getattr(args, "layout", False):   # made before 5.1's split
                print("note: this work dir has output/ from before records/, logs/ and .cache/: its points rerun "
                      "until `hep migrate --layout --apply` moves it", file=sys.stderr)
        if args.command == "setup":
            setupmod.setup(Path(args.dir), project=args.project, git=args.git, adopt=args.adopt, name=args.name)
            return 0
        if args.command == "where":
            return setupmod.where(args.which)
        if args.command == "doctor":
            return doctormod.main(quick=args.quick, record_it=args.record, show_matrix=args.matrix)
        if args.command == "tools":
            from . import tools as toolsmod
            if args.what[:1] == ["new"]:
                if len(args.what) != 2 or not args.source:
                    raise HepError("hep tools new <name> --from <tool>", hint="--from a template folder (copied) or any tool (extended): hep tools lists them")
                print(f"made {toolsmod.new_folder(args.what[1], args.source)}/tool.toml")
                return 0
            if len(args.what) > 1:
                raise HepError("hep tools [<name>] | new <name> --from <tool>")
            for line in (toolsmod.folder_lines(args.what[0]) if args.what else toolsmod.folder_rows()):
                print(line)
            return 0
        if args.command == "run":
            return cmd_run(args)
        if args.command == "plot":
            return cmd_plot(args)
        if args.command == "check":
            return cmd_check(args)
        if args.command == "overlay":
            return cmd_overlay(args)
        if args.command == "deck":
            return cmd_deck(args)
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
        return cmd_watch(args)
    except HepError as error:
        print(error.render(), file=sys.stderr)
        return 2
