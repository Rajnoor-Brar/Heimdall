"""V39, the gate (slow: real Pythia → Rivet runs): `seed_type = "manual"` gives exactly the seed
asked for and the same histograms wherever it runs; `seed_type = "random"` gives a new seed, and new
histograms, each time a point runs, and records the seed it used."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from support import hep
yoda = pytest.importorskip("yoda")

pytestmark = pytest.mark.slow

PHYSICS = """\
[run]
name          = "seeds"
project       = "Demo"
configuration = "one"
event_count   = 2000
threads       = 2
seed_type     = "{seed_type}"
manual_seed   = 4242

[run.cfgs.one]
tools = [["pythia", "rivet"]]

[prelim]
fifo = ["events.hepmc"]

[tools.pythia]
tool        = "pythia"
baseconfig  = "ep.cmnd"
output_file = "events.hepmc"

[tools.rivet]
tool        = "rivet"
input       = "events.hepmc"
analyses    = ["photo_eic"]
output_file = "jets.yoda"
"""


def run(config: Path, where: Path, *args: str) -> subprocess.CompletedProcess:
    return hep(where, config, *args)


def config(scratch: Path, seed_type: str) -> Path:
    path = scratch / f"{seed_type}.toml"
    path.write_text(PHYSICS.format(seed_type=seed_type), encoding="utf-8")
    return path


def point(where: Path) -> tuple[Path, Path]:
    tail = Path("Demo") / "seeds" / "one" / "point"
    return where / "logs" / tail, where / "results" / tail


def provenance(where: Path) -> dict:
    return json.loads((where / "records" / "Demo" / "seeds" / "one" / "point" / "provenance.json").read_text(encoding="utf-8"))


def histograms(where: Path) -> dict:
    found = yoda.read(str(point(where)[1] / "jets.yoda"))
    return {path: h.sumW() for path, h in found.items() if path.startswith("/RAW/") and hasattr(h, "sumW")}


def test_a_manual_seed_is_exact_and_gives_the_same_histograms_anywhere(scratch):
    toml = config(scratch, "manual")
    first, second = run(toml, scratch / "a"), run(toml, scratch / "b")
    assert first.returncode == 0 and second.returncode == 0, first.stdout[-2000:] + first.stderr[-2000:]
    out, _ = point(scratch / "a")
    assert "Random:seed = 4242" in (out / "cards" / "pythia.point.cmnd").read_text(encoding="utf-8")
    assert provenance(scratch / "a")["seed"] == 4242
    assert histograms(scratch / "a") == histograms(scratch / "b")


def test_a_random_seed_is_new_each_time_the_point_runs_and_recorded(scratch):
    toml = config(scratch, "random")
    seeds, shapes = [], []
    for args in ((), ("--rerun",)):
        done = run(toml, scratch, *args)
        assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
        out, _ = point(scratch)
        seeds.append(provenance(scratch)["seed"])
        assert f"Random:seed = {seeds[-1]}" in (out / "cards" / "pythia.point.cmnd").read_text(encoding="utf-8")
        shapes.append(histograms(scratch))
    assert seeds[0] != seeds[1] and shapes[0] != shapes[1]
    again = run(toml, scratch)                                   # complete: kept, not drawn again
    assert again.returncode == 0 and "complete, skipped" in again.stdout
    assert provenance(scratch)["seed"] == seeds[1]
