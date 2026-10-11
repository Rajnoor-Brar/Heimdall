"""`hep cluster`: a run as Slurm jobs (rank 4, V114).

docs/04_Config_Reference.md §16, docs/02_User_Guide.md §7.5. A job is an ordinary `hep run`, so each one
does exactly what the same command does when typed:

    pre job        hep run C cfg --stages pre                       when there are pre tools to run
    points array   hep run C cfg --points <name> --stages points    a task per point to run
    finish job     hep run C cfg --stages combine,post,plot         after the array, whatever its outcome

`hep cluster` plans everything first (every check of `hep run --plan`), writes the scripts into
output/<P>/<run>/<cfg>/cluster/<stamp>/ and submits them with sbatch, chained by dependencies: the
points after the pre job succeeded (afterok), the finish job after every point ended (afterany). A
point is skipped in its job when its identity is complete, as anywhere. Nothing here enters an
identity or a seed, so a point run as a job equals the same point run by hand.

[cluster] comes in layers, lowest first: the work dir's hep.toml (the machine's defaults: account,
partition, setup lines), the run TOML's (imports merge it key by key), the configuration's
([run.cfgs.<cfg>].cluster), and --set cluster.<key>=…; `time` must be in one of them.

The nodes see Heimdall and the work dir on a shared filesystem: each job sources Heimdall's setup.sh
after the `setup` lines, and runs in the work dir.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import tomli_w

from . import tools
from .config import check_cluster
from .errors import HepError
from .execute import cores
from .paths import MARKER_FILE, STACK_VAR, hep_root, output_root, work_meta, work_root
from .record import git_state, is_complete, write_atomic

#: A job's resources, as sbatch takes them: [cluster] key → option.
OPTIONS = {"time": "--time", "partition": "--partition", "account": "--account", "qos": "--qos",
           "constraint": "--constraint", "gres": "--gres", "memory": "--mem"}
#: Where a submission's files go, under the configuration's output folder.
FOLDER = "cluster"
RECORD = "jobs.toml"
POINTS = "points.txt"
#: The roots a job keeps from the shell that submitted it, when set there (the tests set them).
ROOTS = ("HEP_OUTPUT", "HEP_RESULTS", "HEP_REPORTS", "HEP_CONFIGS")
#: What squeue and sacct are asked for: a job's (or array task's) id, state, time and reason or node; and
#: id, state, exit code and elapsed time.
SQUEUE = "%i|%T|%M|%R"
SACCT = "JobID,State,ExitCode,Elapsed"
#: squeue's states of a job that has not ended.
ACTIVE = {"PENDING", "RUNNING", "CONFIGURING", "COMPLETING", "SUSPENDED", "REQUEUED", "RESIZING", "STAGE_OUT"}


def _deep(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in over.items():
        out[key] = _deep(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def settings(configuration) -> dict:
    """[cluster] for this configuration: the work dir's hep.toml under the run TOML's and the
    configuration's (merged by config.py), checked whole; `time` is required."""
    work = work_root()
    machine = work_meta(work)["cluster"]
    check_cluster(machine, f"{work / MARKER_FILE}: [cluster]")
    merged = _deep(machine, configuration.cluster)
    if not merged.get("time"):
        raise HepError("hep cluster needs each job's time limit", where="[cluster] time",
                       hint='[cluster] time = "02:00:00" in the run TOML (or the work dir\'s hep.toml): a site\'s default '
                            'limit is a surprise TIMEOUT')
    return merged


def job_settings(merged: dict, job: str) -> dict:
    """One job's keys: the run's, then its own [cluster.pre] or [cluster.finish]."""
    out = {k: v for k, v in merged.items() if k not in ("pre", "finish")}
    return {**out, **merged.get(job, {})} if job in ("pre", "finish") else out


def directives(keys: dict, *, name: str, log: Path, cpus: int, array: str = "") -> list[str]:
    """The #SBATCH options of one job."""
    out = [f"--job-name={name}", f"--output={log}", "--nodes=1", "--ntasks=1", f"--cpus-per-task={cpus}"]
    if array:
        out.append(f"--array={array}")
    out += [f"{option}={keys[key]}" for key, option in OPTIONS.items() if keys.get(key)]
    if keys.get("mail"):
        out += [f"--mail-user={keys['mail']}", "--mail-type=END,FAIL"]
    return out + list(keys.get("sbatch", []))


def loader() -> Path:
    """The setup.sh a job sources: Heimdall's, or the loaded isolated stack's (recipes/README.md §6)."""
    stack = os.environ.get(STACK_VAR)
    return hep_root() / "stacks" / stack / "setup.sh" if stack else hep_root() / "setup.sh"


def script(directive_list: list[str], keys: dict, command: list[str], *, title: str, points: Path | None = None) -> str:
    """A job script: the directives; the setup lines and Heimdall's environment; the work dir; the hep run."""
    q = shlex.quote
    lines = ["#!/bin/bash", f"# {title}: written by hep cluster (V114). A job is an ordinary hep run.",
             *(f"#SBATCH {d}" for d in directive_list), ""]
    lines += list(keys.get("setup", []))
    lines += [f"source {q(str(loader()))}", "set -eo pipefail",
              f"export HEP_WORK={q(str(work_root()))}",
              *(f"export {var}={q(os.environ[var])}" for var in ROOTS if os.environ.get(var)),
              f"cd {q(str(work_root()))}"]
    if points is not None:
        lines += [f'point=$(sed -n "${{SLURM_ARRAY_TASK_ID}}p" {q(str(points))})',
                  'echo "hep cluster: point $point (task ${SLURM_ARRAY_TASK_ID} of job ${SLURM_ARRAY_JOB_ID:-?}) on $(hostname)"']
    else:
        lines.append(f'echo "hep cluster: {title} (job ${{SLURM_JOB_ID:-?}}) on $(hostname)"')
    lines.append("exec " + " ".join(command))
    return "\n".join(lines) + "\n"


def hep_run(planned, args, stages: str, point: bool = False) -> list[str]:
    """The hep run a job makes: the same config file, configuration and --set's as the submission."""
    q = shlex.quote
    argv = [q(str(hep_root() / "framework" / "bin" / "hep")), "run", q(str(planned.run.path)), q(planned.configuration.key)]
    if point:
        argv += ["--points", '"$point"']
    argv += ["--stages", stages, "--plain"]
    for item in getattr(args, "set", None) or []:
        argv += ["--set", q(item)]
    return argv + (["--rerun"] if getattr(args, "rerun", False) else [])


def base(planned) -> Path:
    """output/<P>/<run>/<cfg>/cluster: every submission's folder."""
    return output_root() / tools.run_dir(planned.run, planned.configuration) / FOLDER


def _stamp(folder: Path) -> Path:
    now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target, n = folder / now, 1
    while target.exists():
        n += 1
        target = folder / f"{now}-{n}"
    return target


def latest(planned) -> Path | None:
    """The latest submission's folder (one with a record; a --dry-run's has none)."""
    found = sorted(p.parent for p in base(planned).glob(f"*/{RECORD}")) if base(planned).is_dir() else []
    return found[-1] if found else None


def _need(command: str) -> None:
    if not shutil.which(command):
        raise HepError(f"no {command} here: hep cluster submits to Slurm", hint="run it on the cluster's login node, "
                       "with Heimdall loaded (source <Heimdall>/setup.sh)")


def _sbatch(argv: list[str]) -> str:
    done = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise HepError(f"sbatch failed: {(done.stderr or done.stdout).strip()[-300:]}", where=argv[-1])
    job = done.stdout.strip().split(";")[0]
    if not job.isdigit():
        raise HepError(f"sbatch said '{done.stdout.strip()}', not a job id", where=argv[-1])
    return job


def active(ids: list[str]) -> list[str]:
    """The lines of squeue for these jobs that have not ended ([] when squeue knows none of them)."""
    done = subprocess.run(["squeue", "-h", "-o", SQUEUE, "-j", ",".join(ids)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode != 0:                           # ended long ago: squeue no longer knows the ids
        return []
    return [line for line in done.stdout.splitlines() if len(line.split("|")) >= 2 and line.split("|")[1] in ACTIVE]


def notes(planned) -> list[str]:
    out = []
    if planned.configuration.parallelism > 1:
        out.append(f"parallelism {planned.configuration.parallelism} is not used: each job runs one point; "
                   "[cluster] max_running limits how many run at once")
    if planned.configuration.seed_type == "random":
        out.append('seed_type = "random": each point draws its seed in its job (its provenance records it)')
    return out


def submit(planned, args, out=print) -> int:
    """Write a submission's scripts and submit them (--dry-run: write them, and print the sbatch lines)."""
    run, configuration = planned.run, planned.configuration
    merged = settings(configuration)
    rerun, dry = bool(getattr(args, "rerun", False)), bool(getattr(args, "dry_run", False))
    todo = [p for p in planned.plans if rerun or not is_complete(p)]
    pre = planned.pre if planned.pre is not None and (rerun or not is_complete(planned.pre)) and todo else None
    if not dry:
        _need("sbatch")
        if (last := latest(planned)) is not None:
            ids = list(tomllib.loads((last / RECORD).read_text(encoding="utf-8"))["jobs"].values())
            if ids and shutil.which("squeue") and active(ids):
                raise HepError(f"{run.name} · {configuration.key}: the submission {last.name} still has jobs pending or "
                               "running, and a second would run the same points in the same folders",
                               where=str(last), hint=f"hep cluster {args.config} {configuration.key} --status, or --cancel")
    folder = _stamp(base(planned))
    (folder / "logs").mkdir(parents=True)              # a dry run's folder has no record: never a submission
    name = f"hep-{run.name}-{configuration.key}"
    jobs: dict[str, tuple[Path, list[str]]] = {}       # job → (its script, its sbatch line once known)
    if pre is not None:
        keys = job_settings(merged, "pre")
        text = script(directives(keys, name=f"{name}-pre", log=folder / "logs" / "pre-%j.log",
                                 cpus=int(keys.get("cpus") or cores(pre))),
                      keys, hep_run(planned, args, "pre"), title=f"{run.name} · {configuration.key}: pre")
        jobs["pre"] = (folder / "pre.sbatch", [])
        (folder / "pre.sbatch").write_text(text, encoding="utf-8")
    if todo:
        keys = job_settings(merged, "points")
        write_atomic(folder / POINTS, "".join(p.point.name + "\n" for p in todo))
        throttle = f"%{merged['max_running']}" if merged.get("max_running") else ""
        text = script(directives(keys, name=f"{name}-points", log=folder / "logs" / "points-%A_%a.log",
                                 cpus=int(keys.get("cpus") or max(cores(p) for p in todo)),
                                 array=f"1-{len(todo)}{throttle}"),
                      keys, hep_run(planned, args, "points", point=True),
                      title=f"{run.name} · {configuration.key}: points", points=folder / POINTS)
        jobs["points"] = (folder / "points.sbatch", [])
        (folder / "points.sbatch").write_text(text, encoding="utf-8")
    keys = job_settings(merged, "finish")
    text = script(directives(keys, name=f"{name}-finish", log=folder / "logs" / "finish-%j.log",
                             cpus=int(merged.get("finish", {}).get("cpus") or 1)),
                  keys, hep_run(planned, args, "combine,post,plot"), title=f"{run.name} · {configuration.key}: finish")
    jobs["finish"] = (folder / "finish.sbatch", [])
    (folder / "finish.sbatch").write_text(text, encoding="utf-8")

    for note in notes(planned):
        out(f"note: {note}")
    out(f"{run.name} · {configuration.key}: {len(todo)} point(s) to run of {len(planned.plans)}"
        + (", and the pre tools" if pre is not None else "") + f" → {folder}")
    if not todo:
        out("every point is complete: only the finish job (combined groups, post tools, plots)")
    ids: dict[str, str] = {}
    previous = {"points": "pre", "finish": "points"}   # the points after the pre job, the finish after the points
    for job, (path, _) in jobs.items():
        argv = ["sbatch", "--parsable"]
        after = previous.get(job, "")
        if after in jobs:
            kind = "afterok" if job == "points" else "afterany"
            argv += [f"--dependency={kind}:{ids.get(after, f'<{after}>')}", "--kill-on-invalid-dep=yes"]
        argv.append(str(path))
        jobs[job] = (path, argv)
        if dry:
            out("  " + " ".join(argv))
            continue
        try:
            ids[job] = _sbatch(argv)
        except HepError:
            if ids and shutil.which("scancel"):        # no half a chain left queued
                subprocess.run(["scancel", *ids.values()], capture_output=True)
            raise
        out(f"  {job}: job {ids[job]}" + (f" (an array of {len(todo)})" if job == "points" else ""))
    if dry:
        out("dry run: nothing submitted; the scripts are in the folder above")
        return 0
    record = {"stamp": folder.name, "scheduler": merged.get("scheduler", "slurm"), "config": str(run.path),
              "configuration": configuration.key, "sets": list(getattr(args, "set", None) or []), "rerun": rerun,
              "work": str(work_root()), "heimdall": git_state(hep_root()), "points": [p.point.name for p in todo],
              "jobs": ids, "sbatch": {job: argv for job, (_, argv) in jobs.items()}}
    write_atomic(folder / RECORD, tomli_w.dumps(record))
    out(f"hep cluster {args.config} {configuration.key} --status: where they are")
    return 0


# ── --status and --cancel ───────────────────────────────────────────────────────────────────────

_TASKS = re.compile(r"^(\d+)(?:_(\d+|\[[^\]]*\]))?$")


def tasks_of(job_id: str) -> tuple[str, list[int] | None]:
    """'102_3' → ('102', [3]); '102_[3-5,7%2]' → ('102', [3, 4, 5, 7]); '101' → ('101', None)."""
    match = _TASKS.match(job_id.strip())
    if not match:
        return job_id.strip(), None
    job, part = match.group(1), match.group(2)
    if part is None:
        return job, None
    if part.isdigit():
        return job, [int(part)]
    found = []
    for piece in part.strip("[]").split("%")[0].split(","):
        low, _, high = piece.partition("-")
        if low.isdigit():
            found += list(range(int(low), int(high or low) + 1))
    return job, found


def _states(ids: list[str]) -> dict:
    """(job, task or None) → a short state, from sacct (what ended) under squeue (what has not)."""
    states: dict = {}
    if shutil.which("sacct"):
        done = subprocess.run(["sacct", "-n", "-P", "-X", "-j", ",".join(ids), f"--format={SACCT}"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        for line in done.stdout.splitlines():
            fields = line.split("|")
            if len(fields) < 4:
                continue
            job, found = tasks_of(fields[0])
            state = fields[1].split()[0] if fields[1] else "?"
            text = state + (f" exit {fields[2]}" if state not in ("COMPLETED", "PENDING", "RUNNING") else "") + \
                (f" {fields[3]}" if state not in ("PENDING",) else "")
            for task in found or [None]:
                states[(job, task)] = text
    if shutil.which("squeue"):
        done = subprocess.run(["squeue", "-h", "-o", SQUEUE, "-j", ",".join(ids)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        for line in done.stdout.splitlines() if done.returncode == 0 else []:
            fields = line.split("|")
            if len(fields) < 4:
                continue
            job, found = tasks_of(fields[0])
            text = f"{fields[1]} {fields[2]} {fields[3]}" if fields[1] == "RUNNING" else f"{fields[1]} {fields[3]}"
            for task in found or [None]:
                states[(job, task)] = text
    return states


def status(planned, out=print) -> int:
    """Each point of the latest submission: complete (its marker), else what Slurm says of its task."""
    run, configuration = planned.run, planned.configuration
    folder = latest(planned)
    complete = sum(is_complete(p) for p in planned.every)
    if folder is None:
        out(f"{run.name} · {configuration.key}: no submission ({complete} of {len(planned.every)} point(s) complete)")
        return 0
    record = tomllib.loads((folder / RECORD).read_text(encoding="utf-8"))
    ids = record["jobs"]
    states = _states(list(ids.values())) if ids else {}
    by_name = {p.point.name: p for p in planned.every}
    out(f"{run.name} · {configuration.key}: submission {record['stamp']} ("
        + ", ".join(f"{job} {job_id}" for job, job_id in ids.items()) + ")")
    width = max([len(n) for n in record["points"]] + [6])
    counts: dict[str, int] = {}

    def line(label: str, state: str, log: Path | None = None) -> None:
        word = state.split()[0].lower() if state else "unknown"
        counts[word] = counts.get(word, 0) + 1
        failed = word in ("failed", "timeout", "out_of_memory", "cancelled", "node_fail")
        out(f"  {label:<{width}}  {state or 'unknown'}" + (f"   log: {log}" if failed and log else ""))

    if "pre" in ids:
        line("pre", states.get((ids["pre"], None), ""), next(folder.glob(f"logs/pre-{ids['pre']}.log"), None))
    for task, point in enumerate(record["points"], 1):
        plan = by_name.get(point)
        if plan is not None and is_complete(plan):
            line(point, "complete")
            continue
        job = ids.get("points", "")
        line(point, states.get((job, task), states.get((job, None), "")) if plan is not None else "not in the plan any more",
             folder / "logs" / f"points-{job}_{task}.log")
    line("finish", states.get((ids.get("finish", ""), None), ""),
         next(folder.glob(f"logs/finish-{ids.get('finish', '')}.log"), None))
    out(", ".join(f"{n} {w}" for w, n in counts.items()) + f"; {complete} of {len(planned.every)} point(s) complete")
    return 0


def cancel(planned, out=print) -> int:
    """scancel the latest submission's jobs."""
    _need("scancel")
    folder = latest(planned)
    if folder is None:
        out(f"{planned.run.name} · {planned.configuration.key}: no submission to cancel")
        return 0
    ids = list(tomllib.loads((folder / RECORD).read_text(encoding="utf-8"))["jobs"].values())
    done = subprocess.run(["scancel", *ids], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise HepError(f"scancel failed: {(done.stderr or done.stdout).strip()[-300:]}", where=str(folder))
    out(f"{planned.run.name} · {planned.configuration.key}: cancelled the submission {folder.name} (jobs {' '.join(ids)})")
    return 0
