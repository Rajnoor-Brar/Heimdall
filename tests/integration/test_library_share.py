"""The points library through real runs (points-library P4): two Errands share a point, and the second
runs nothing; `--rerun` reruns it in its entry; a `library = "only"` run keeps no points folders.

The test makes a small work dir of its own under its scratch folder, with Rivet's MC_JETS, so no fixture config is added.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from support import HEIMDALL, REPO, apps, env

pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(not (apps() / "App_Pythia.exe").exists(), reason="heimdall build --framework")]

TEMPLATE = """[errand]
assignment = "T"
name    = "{name}"
run     = "one"
events  = 200
threads = 1
library = {library}
plot    = false
stats   = false
chain   = [["pythia", "rivet"]]

[tools.pythia]
card   = "ep.cmnd"
output = "events.hepmc"

[tools.rivet]
input    = "pythia"
analyses = ["MC_JETS"]
output   = "jets.yoda"

[quantities.pdf]
points = [
  {{ tag = "{first}",  value = "MSTW2008lo68cl",                 label = "MSTW 2008 LO" }},
  {{ tag = "{second}", value = "LHAPDF6:NNPDF23_lo_as_0130_qed", label = "NNPDF 2.3 LO" }},
]

[cfgs.one]
vary = ["pdf"]
"""


def run(work: Path, scratch: Path, name: str, *extra: str):
    return subprocess.run([str(HEIMDALL), "run", f"T/{name}", "--plain", *extra], cwd=work,
                          env={**env(scratch), "HEIMDALL_WORK": str(work)}, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=1800)


def attempts(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def test_two_errands_share_a_point_and_the_second_runs_nothing(scratch):
    work = scratch / "Library"
    (work / "configs" / "T").mkdir(parents=True)
    (work / "heimdall.toml").write_text('[work]\nname = "Library"\n', encoding="utf-8")
    (work / "configs" / "T" / "ep.cmnd").write_bytes((REPO / "tests" / "fixtures" / "work" / "configs" / "Demo" / "ep.cmnd").read_bytes())
    for name, library, tags in (("first", "true", ("mstw", "nnpdf")), ("second", "true", ("old_mstw", "old_nnpdf")),
                                ("third", '"only"', ("a", "b"))):
        (work / "configs" / "T" / f"{name}.toml").write_text(
            TEMPLATE.format(name=name, library=library, first=tags[0], second=tags[1]), encoding="utf-8")
    records, results = scratch / "records" / "T", scratch / "results" / "T"

    done = run(work, scratch, "first")
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    entries = sorted(p.name for p in (records / "library").iterdir() if p.is_dir())
    assert len(entries) == 2
    link = records / "first" / "01_one" / "points" / "mstw"
    assert link.is_symlink() and link.resolve().parent == (records / "library").resolve()
    assert (results / "first" / "01_one" / "points" / "mstw").resolve().parent == (results / "library").resolve()
    assert (results / "first" / "01_one" / "points" / "mstw" / "jets.yoda").is_file()          # through the link
    assert all(attempts(records / "library" / e / "attempts.jsonl") == 1 for e in entries)

    shared = run(work, scratch, "second")                                  # the same physics under other names
    assert shared.returncode == 0, shared.stdout[-2000:] + shared.stderr[-2000:]
    assert "2 point(s) come from the library, not run again" in shared.stdout
    assert sorted(p.name for p in (records / "library").iterdir() if p.is_dir()) == entries       # no new entry
    assert all(attempts(records / "library" / e / "attempts.jsonl") == 1 for e in entries)        # nothing ran
    for name in ("old_mstw", "old_nnpdf"):
        assert (records / "second" / "01_one" / "points" / name).resolve().parent == (records / "library").resolve()
    assert (results / "second" / "01_one" / "points" / "old_mstw" / "jets.yoda").is_file()
    index = [json.loads(line) for line in (records / "library" / "points.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {line["kind"] for line in index} == {"created", "used"}

    again = run(work, scratch, "second", "--rerun")
    assert again.returncode == 0, again.stdout[-2000:] + again.stderr[-2000:]
    assert "--rerun replaces the library point" in again.stdout and "T/first/01_one" in again.stdout
    assert all(attempts(records / "library" / e / "attempts.jsonl") == 2 for e in entries)

    only = run(work, scratch, "third")                                     # "only": the points are all in the library
    assert only.returncode == 0, only.stdout[-2000:] + only.stderr[-2000:]
    assert not (records / "third" / "01_one" / "points").exists() and not (records / "third" / "01_one" / "points.json").exists()
    assert not (results / "third").exists() or not any((results / "third").rglob("points"))
    assert sorted(p.name for p in (records / "library").iterdir() if p.is_dir()) == entries
