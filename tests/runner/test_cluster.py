"""hep cluster (V114): [cluster] in its layers, the Slurm scripts, the chain of submissions, --status and
--cancel, with stub sbatch, squeue, sacct and scancel on PATH; and hep run's --stages, which the jobs
are. Every test has a work dir of its own, with a custom tool that writes its config: no generator."""

from __future__ import annotations

import argparse
import multiprocessing
import os
import subprocess
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner import cli, cluster, paths, record, sweep
from runner.errors import HepError
from support import HEP

STUB = {
    "sbatch": '#!/bin/bash\nn=$(( $(cat "$STUBLOG.n" 2>/dev/null || echo 100) + 1 )); echo $n > "$STUBLOG.n"\n'
              'echo "sbatch $*" >> "$STUBLOG"; echo "$n"\n',
    "squeue": '#!/bin/bash\necho "squeue $*" >> "$STUBLOG"; cat "$STUBLOG.squeue" 2>/dev/null; exit 0\n',
    "sacct": '#!/bin/bash\necho "sacct $*" >> "$STUBLOG"; cat "$STUBLOG.sacct" 2>/dev/null; exit 0\n',
    "scancel": '#!/bin/bash\necho "scancel $*" >> "$STUBLOG"\n',
}
TOOL = ('#!/usr/bin/env python3\nimport sys\nargs = [a for a in sys.argv[1:] if a]          # [config,] output\n'
        'open(args[-1], "w").write(open(args[0]).read() if len(args) > 1 else "pre\\n")\n')


def run_toml(tool: Path, *, cluster_lines: str = 'time = "00:10:00"', pre: bool = False, own: str = "") -> str:
    return f"""[run]
name = "c"
project = "P"
configuration = "three"
event_count = 10
threads = 1

[run.cfgs.three]
sweeps = ["q"]
tools  = ["make"]
{'pre = ["prep"]' if pre else ''}
{own}

[tools.make]
tool        = "custom"
executable  = "{tool}"
arguments   = ["{{partial:output}}"]
consumes    = ["q"]
output_file = "x.txt"
cores       = 3

[tools.prep]
tool        = "custom"
executable  = "{tool}"
arguments   = ["{{partial:output}}"]
output_file = "y.txt"

[quantities.q]
values = [1, 2, 3]
tags   = ["a", "b", "c"]

[cluster]
{cluster_lines}
"""


class Work:
    """A work dir in the test's scratch, its stubs first on PATH, and `hep` run in it."""

    def __init__(self, root: Path, **toml):
        self.root, self.log = root / "W", root / "stub.log"
        (self.root / "configs" / "P").mkdir(parents=True)
        (root / "bin").mkdir()
        for name, text in STUB.items():
            (root / "bin" / name).write_text(text, encoding="utf-8")
            (root / "bin" / name).chmod(0o755)
        self.tool = self.root / "make.py"
        self.tool.write_text(TOOL, encoding="utf-8")
        self.tool.chmod(0o755)
        self.hep_toml('[work]\nname = "t"\n')
        self.config(**toml)
        self.env = {**{k: v for k, v in os.environ.items() if k != "HEP_CONFIGS"}, "HEP_WORK": str(self.root),
                    "HEP_OUTPUT": str(self.root / "output"), "HEP_RESULTS": str(self.root / "results"),
                    "PATH": f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}", "STUBLOG": str(self.log)}

    def hep_toml(self, text: str) -> None:
        (self.root / "hep.toml").write_text(text, encoding="utf-8")

    def config(self, **toml) -> None:
        (self.root / "configs" / "P" / "c.toml").write_text(run_toml(self.tool, **toml), encoding="utf-8")

    def hep(self, *args: str, **env) -> subprocess.CompletedProcess:
        return subprocess.run([str(HEP), *args], cwd=self.root, env={**self.env, **env}, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=300)

    def calls(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def stub(self, name: str, text: str) -> None:
        Path(f"{self.log}.{name}").write_text(text, encoding="utf-8")

    def submissions(self) -> list[Path]:
        return sorted(p for p in (self.root / "output" / "P" / "c" / "three" / "cluster").glob("*") if p.is_dir())


@pytest.fixture
def work(scratch):
    return Work(scratch)


@pytest.fixture
def inside(work, monkeypatch):
    """The work dir as this process's, for the tests that call the runner directly."""
    for var, value in (("HEP_WORK", work.root), ("HEP_OUTPUT", work.root / "output"), ("HEP_RESULTS", work.root / "results")):
        monkeypatch.setenv(var, str(value))
    paths.reset()
    yield work
    paths.reset()


def plans(name: str = "P/c", sets=()):
    return cli.build_plans(argparse.Namespace(config=name, set=list(sets), points=None, rerun=False, only=None), None)


# ── [cluster] ───────────────────────────────────────────────────────────────────────────────────

def test_an_unknown_cluster_key_is_refused_with_its_nearest(work):
    work.config(cluster_lines='tme = "00:10:00"')
    done = work.hep("check", "P/c")
    said = done.stdout + done.stderr                                    # hep check reports on stdout
    assert done.returncode == 2 and "unknown key 'tme'" in said and "did you mean 'time'?" in said


def test_pre_and_finish_take_only_a_jobs_resources(work):
    work.config(cluster_lines='time = "00:10:00"\n[cluster.finish]\nsetup = []')
    done = work.hep("check", "P/c")
    assert done.returncode == 2 and "unknown key 'setup'" in done.stdout + done.stderr


def test_the_layers_lowest_first(inside):
    inside.hep_toml('[work]\nname = "t"\n[cluster]\naccount = "lab"\npartition = "short"\ntime = "00:05:00"\n')
    inside.config(cluster_lines='time = "00:10:00"\ncpus = 4', own='cluster = { partition = "long" }')
    merged = cluster.settings(plans(sets=['cluster.memory="2G"']).configuration)
    assert merged == {"account": "lab", "partition": "long", "time": "00:10:00", "cpus": 4, "memory": "2G"}


def test_a_time_limit_is_required_in_some_layer(inside):
    inside.config(cluster_lines='cpus = 2')
    with pytest.raises(HepError, match="needs each job's time limit"):
        cluster.settings(plans().configuration)


def test_cluster_settings_are_in_no_identity(inside):
    first = [p.identity for p in plans().every]
    inside.config(cluster_lines='time = "09:00:00"\ncpus = 12\nmax_running = 1')
    assert [p.identity for p in plans().every] == first


# ── the scripts and the submission ──────────────────────────────────────────────────────────────

def test_a_dry_run_writes_the_scripts_and_submits_nothing(work):
    work.hep_toml('[work]\nname = "t"\n[cluster]\naccount = "lab"\nsetup = ["echo node"]\n')
    work.config(cluster_lines='time = "00:10:00"\nmax_running = 2')
    done = work.hep("cluster", "P/c", "--dry-run")
    assert done.returncode == 0, done.stderr
    assert "dry run: nothing submitted" in done.stdout and work.calls() == []
    [folder] = work.submissions()
    assert not (folder / cluster.RECORD).exists()                       # a dry run is never a submission
    assert (folder / "points.txt").read_text() == "a\nb\nc\n"
    text = (folder / "points.sbatch").read_text()
    for line in ("#SBATCH --array=1-3%2", "#SBATCH --cpus-per-task=3", "#SBATCH --time=00:10:00",
                 "#SBATCH --account=lab", "echo node", f"source {paths.hep_root() / 'setup.sh'}",
                 f"export HEP_WORK={work.root}", '--points "$point" --stages points --plain'):
        assert line in text, line
    assert text.index("echo node") < text.index("source ")              # the setup lines first
    assert "--stages combine,post,plot" in (folder / "finish.sbatch").read_text()
    assert "#SBATCH --cpus-per-task=1" in (folder / "finish.sbatch").read_text()


def test_the_points_then_the_finish_after_any(work):
    done = work.hep("cluster", "P/c")
    assert done.returncode == 0, done.stderr
    calls = [c for c in work.calls() if c.startswith("sbatch")]
    assert len(calls) == 2 and calls[0].startswith("sbatch --parsable ") and calls[0].endswith("points.sbatch")
    assert "--dependency=afterany:101 --kill-on-invalid-dep=yes" in calls[1] and calls[1].endswith("finish.sbatch")
    saved = tomllib.loads((work.submissions()[-1] / cluster.RECORD).read_text())
    assert saved["jobs"] == {"points": "101", "finish": "102"} and saved["points"] == ["a", "b", "c"]


def test_a_pre_job_comes_first_and_the_points_need_it_done(work):
    work.config(pre=True)
    assert work.hep("cluster", "P/c").returncode == 0
    calls = [c for c in work.calls() if c.startswith("sbatch")]
    assert calls[0].endswith("pre.sbatch")
    assert "--dependency=afterok:101" in calls[1] and calls[1].endswith("points.sbatch")
    assert "--dependency=afterany:102" in calls[2] and calls[2].endswith("finish.sbatch")


def test_complete_points_are_not_submitted(work):
    assert work.hep("run", "P/c", "--points", "a,b", "--stages", "points", "--plain").returncode == 0
    assert work.hep("cluster", "P/c", "--dry-run").returncode == 0
    assert (work.submissions()[-1] / "points.txt").read_text() == "c\n"


def test_nothing_to_run_submits_the_finish_job_alone(work):
    assert work.hep("run", "P/c", "--stages", "points", "--plain").returncode == 0
    done = work.hep("cluster", "P/c")
    assert done.returncode == 0 and "only the finish job" in done.stdout
    [call] = [c for c in work.calls() if c.startswith("sbatch")]
    assert call.endswith("finish.sbatch") and "--dependency" not in call


def test_a_second_submission_waits_for_the_first(work):
    assert work.hep("cluster", "P/c").returncode == 0
    work.stub("squeue", "101_2|PENDING|0:00|(JobArrayTaskLimit)\n")
    done = work.hep("cluster", "P/c")
    assert done.returncode == 2 and "still has jobs pending or running" in done.stderr and "--cancel" in done.stderr
    assert len(work.submissions()) == 1


def test_no_sbatch_is_refused_unless_a_dry_run(work):
    done = work.hep("cluster", "P/c", PATH=os.environ["PATH"])
    assert done.returncode == 2 and "no sbatch here" in done.stderr


def test_status_reads_the_markers_then_sacct_and_squeue(work):
    assert work.hep("cluster", "P/c").returncode == 0
    assert work.hep("run", "P/c", "--points", "a", "--stages", "points", "--plain").returncode == 0
    work.stub("sacct", "101_2|FAILED|1:0|00:00:40\n")
    work.stub("squeue", "101_3|RUNNING|1:02|node12\n102|PENDING|0:00|(Dependency)\n")
    done = work.hep("cluster", "P/c", "--status")
    lines = done.stdout.splitlines()
    assert done.returncode == 0 and lines[0].endswith("(points 101, finish 102)")
    assert lines[1].split() == ["a", "complete"]
    assert lines[2].split()[:4] == ["b", "FAILED", "exit", "1:0"] and lines[2].endswith("logs/points-101_2.log")
    assert lines[3].split() == ["c", "RUNNING", "1:02", "node12"]
    assert lines[4].split() == ["finish", "PENDING", "(Dependency)"]
    assert "1 of 3 point(s) complete" in lines[5]


def test_cancel_cancels_the_latest_submission(work):
    assert work.hep("cluster", "P/c").returncode == 0
    done = work.hep("cluster", "P/c", "--cancel")
    assert done.returncode == 0 and work.calls()[-1] == "scancel 101 102"


@pytest.mark.parametrize("given,expected", [("102_3", ("102", [3])), ("102_[3-5,7%2]", ("102", [3, 4, 5, 7])),
                                            ("101", ("101", None)), ("102_[2]", ("102", [2]))])
def test_array_task_ids(given, expected):
    assert cluster.tasks_of(given) == expected


# ── hep run --stages: what a job is ─────────────────────────────────────────────────────────────

def test_a_points_stage_runs_its_points_alone(work):
    done = work.hep("run", "P/c", "--points", "b", "--stages", "points", "--plain")
    assert done.returncode == 0, done.stdout + done.stderr
    base = work.root / "output" / "P" / "c" / "three"
    assert (work.root / "results" / "P" / "c" / "three" / "b" / "x.txt").exists()
    assert not (base / "points.json").exists()                          # the finish job writes it
    done = work.hep("run", "P/c", "--stages", "combine,post,plot", "--plain")
    assert done.returncode == 0 and "combine, post, plot done" in done.stdout
    assert (base / "points.json").exists() and not (base / "a").exists()  # no point ran


def test_the_points_need_their_pre_stage(work):
    work.config(pre=True)
    done = work.hep("run", "P/c", "--stages", "points", "--plain")
    assert done.returncode == 2 and "the pre stage is not complete" in done.stderr
    assert work.hep("run", "P/c", "--stages", "pre,points", "--plain").returncode == 0


@pytest.mark.parametrize("args,message", [(("--stages", "points,plots"), "'plots' is not a stage"),
                                          (("--stages", "post", "--only", "post"), "do not go together")])
def test_stages_are_named_and_alone(work, args, message):
    done = work.hep("run", "P/c", *args, "--plain")
    assert done.returncode == 2 and message in done.stderr


def test_a_whole_point_name_picks_that_point_alone():
    points = [SimpleNamespace(name="a", index=1), SimpleNamespace(name="a_x", index=2), SimpleNamespace(name="b_a", index=3)]
    assert [p.index for p in sweep.select_points(None, None, points, "a")] == [1]
    assert [p.index for p in sweep.select_points(None, None, points, "x")] == [2]      # a tag as before


def _write_many(target: str, text: str) -> None:
    for _ in range(200):
        record.write_atomic(Path(target), text)


def test_writers_on_one_file_never_rename_each_others(scratch):
    target = scratch / "points.json"
    texts = [f"{n}" * 4000 for n in range(4)]
    workers = [multiprocessing.Process(target=_write_many, args=(str(target), t)) for t in texts]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert all(w.exitcode == 0 for w in workers)
    assert target.read_text() in texts and not list(scratch.glob("*.tmp"))
