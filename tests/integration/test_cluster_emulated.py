"""hep cluster's jobs, run (V114; slow): an emulated sbatch runs each script at once, here, an array's
tasks one after another, so the chain of jobs runs as Slurm would run it on one node. A point run as
a job must equal the same point run by `hep run`, byte for byte: nothing about the cluster enters an
identity or a seed."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from support import HEP, apps

pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(not (apps() / "App_Pythia.exe").exists(), reason="hep build --framework")]

#: sbatch, emulated: job ids from 201; no dependency honoured, since the chain is submitted in its order.
SBATCH = '''#!/usr/bin/env python3
import os, re, subprocess, sys
from pathlib import Path
script = Path(sys.argv[-1])
counter = Path(os.environ["STUBLOG"] + ".n")
job = int(counter.read_text()) + 1 if counter.exists() else 201
counter.write_text(str(job))
with open(os.environ["STUBLOG"], "a") as log:
    log.write("sbatch " + " ".join(sys.argv[1:]) + "\\n")
text = script.read_text()
array = re.search(r"^#SBATCH --array=1-(\\d+)", text, re.M)
output = re.search(r"^#SBATCH --output=(\\S+)", text, re.M).group(1)
for task in range(1, int(array.group(1)) + 1) if array else [0]:
    env = dict(os.environ, SLURM_JOB_ID=str(job))
    if task:
        env.update(SLURM_ARRAY_JOB_ID=str(job), SLURM_ARRAY_TASK_ID=str(task))
    with open(output.replace("%A", str(job)).replace("%a", str(task)).replace("%j", str(job)), "w") as out:
        subprocess.run(["bash", str(script)], env=env, stdout=out, stderr=subprocess.STDOUT)
print(job)
'''


def test_a_point_run_as_a_job_equals_the_same_point_run_here(scratch):
    work, stubs = scratch / "W", scratch / "bin"
    stubs.mkdir()
    (stubs / "sbatch").write_text(SBATCH, encoding="utf-8")
    (stubs / "sbatch").chmod(0o755)
    made = subprocess.run([str(HEP), "setup", str(work), "--project", "Starter"], capture_output=True, text=True)
    assert made.returncode == 0, made.stderr
    with (work / "configs" / "Starter" / "starter.toml").open("a", encoding="utf-8") as toml:
        toml.write('\n[cluster]\ntime = "00:20:00"\n')
    env = {**{k: v for k, v in os.environ.items() if k != "HEP_CONFIGS"}, "HEP_WORK": str(work),
           "HEP_OUTPUT": str(work / "output"), "HEP_RESULTS": str(work / "results"),
           "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}", "STUBLOG": str(scratch / "stub.log")}

    done = subprocess.run([str(HEP), "cluster", "Starter/starter"], cwd=work, env=env, capture_output=True, text=True,
                          timeout=1800)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "points: job 201 (an array of 2)" in done.stdout and "finish: job 202" in done.stdout
    [folder] = sorted((work / "output" / "Starter" / "starter" / "pdf" / "cluster").glob("*/jobs.toml"))
    logs = folder.parent / "logs"
    assert sorted(p.name for p in logs.iterdir()) == ["finish-202.log", "points-201_1.log", "points-201_2.log"]
    assert "combine, post, plot done" in (logs / "finish-202.log").read_text()

    status = subprocess.run([str(HEP), "status", "Starter/starter", "pdf"], cwd=work, env=env, capture_output=True,
                            text=True)
    assert status.stdout.count(" complete ") == 2, status.stdout

    ref = scratch / "ref"
    here = subprocess.run([str(HEP), "run", "Starter/starter", "--plain"], cwd=work, capture_output=True, text=True,
                          env={**env, "HEP_OUTPUT": str(ref / "output"), "HEP_RESULTS": str(ref / "results")}, timeout=1800)
    assert here.returncode == 0, here.stdout + here.stderr
    for point in ("nnpdf23", "cteq6l1"):
        job = work / "results" / "Starter" / "starter" / "pdf" / point / "jets.yoda"
        assert job.read_bytes() == (ref / "results" / "Starter" / "starter" / "pdf" / point / "jets.yoda").read_bytes()
    pages = sorted(p.name for p in (work / "results" / "Starter" / "starter" / "pdf" / "plots" / "root").glob("*.png"))
    assert pages and pages == sorted(p.name for p in (ref / "results" / "Starter" / "starter" / "pdf" / "plots" / "root").glob("*.png"))
