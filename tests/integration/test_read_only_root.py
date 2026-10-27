"""A run where the machine root is read-only, as it is inside an Apptainer image (V149, V150): it writes only the
work dir's records/, results/ and the drawing's .cache/ (V164), nothing in the machine root or in Heimdall, and a
finished point keeps its cards and configs only.

The machine root here is an empty folder of the test's own, made read-only, with the forge inside it (so it
cannot be made); the loaded stack (HEIMDALL_INSTALL, HEIMDALL_APPS, the base) is the real one's, read as an image's is.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

import support

from support import HEIMDALL, REPO, WORK, apps, env, folder

pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(not (apps() / "App_Pythia.exe").exists(), reason="heimdall build --framework")]


def checkout_state() -> list[str]:
    """Heimdall's changed, untracked and ignored paths: a run must add none (no __pycache__ either)."""
    done = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--ignored", "--untracked-files=all"],
                          capture_output=True, text=True, encoding="utf-8", check=True)
    return sorted(done.stdout.splitlines())


def test_a_run_writes_only_its_work_dir(scratch):
    root = scratch / "Himinbjorg"
    root.mkdir()
    environment = dict(env(scratch), HEIMDALL_MACHINE=str(root), HEIMDALL_FORGE=str(root / "forge"), PYTHONDONTWRITEBYTECODE="1")
    environment.pop("HEIMDALL_RUNS", None)                               # the registry aims at the read-only root (V182)
    before = checkout_state()
    root.chmod(0o555)
    try:
        done = subprocess.run([str(HEIMDALL), "run", "Demo/jets", "single", "--set", "run.events=200", "--set", "run.threads=1",
                               "--plain"], cwd=WORK, env=environment, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=1800)
    finally:
        root.chmod(0o755)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    assert list(root.iterdir()) == []
    assert checkout_state() == before
    assert sorted(p.name for p in scratch.iterdir()) == ["Himinbjorg", "cache", "records", "results"]
    assert sorted(p.name for p in (scratch / "cache" / "Demo").iterdir()) == ["datasets", "plots"]    # the drawing's alone

    run = scratch / "records" / folder("Demo/jets", "single", scratch)
    kept = {p.name for p in (run / "logs" / "point").iterdir()}
    digests = {name for name in kept if name.endswith(".log")}                  # each tool's digest (V201)
    assert digests and not {name for name in digests if name.endswith(".full.log")}
    assert {"cards", "commands.sh", "context.toml"} <= kept - digests <= {".lock", "cards", "config", "commands.sh",
                                                                         "context.toml"}   # V187
    assert not (run / "plots").exists()                                     # records/: nothing a drawing reads
    documents = support.pages(scratch, folder("Demo/jets", "single", scratch))
    assert any(documents.rglob("*.toml"))
    assert not [p for p in (scratch / "records").rglob("*") if p.is_fifo() or p.name == "status.jsonl"]
    assert os.access(support.point_results(scratch, folder("Demo/jets", "single", scratch), "point") / "jets.yoda", os.R_OK)
