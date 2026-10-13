"""P4 S1's gates, kept runnable: module programs through the runner (slow: real generators).

* Lambda (rows 1–2): App_Pythia fans out to DecayRiv (Rivet) and Lambda (the module) on the same
  events; the module's histograms equal Rivet's to the precision YODA writes (7 significant digits).
* InprocJets (rows 6–8): an integrated Pythia + Rivet program gets the chain's card and seeds, so at
  one thread its YODA equals the chain's bin for bin; at four its σ equals App_Pythia's sidecar;
  four Rivets on threads equal one (V34, L29); and the serial engine is reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from support import apps, folder, hep_ok
BUILT = [apps() / "App_Pythia.exe"]          # the module programs: work_built (every slow test has it)
uproot = pytest.importorskip("uproot")
yoda = pytest.importorskip("yoda")

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not all(p.exists() for p in BUILT), reason="hep build --framework")]


def hep_run(scratch: Path, *args: str) -> tuple[Path, Path]:
    hep_ok(scratch, *args)
    return scratch / "output", scratch / "results"


def test_lambda_module_and_rivet_agree_on_the_same_events(scratch):
    _, results = hep_run(scratch, "Decay/decay", "single", "--set", "run.events=200", "--set", "run.threads=2")
    point = results / "Decay" / "decay" / "single" / "point"
    report = json.loads((point / "decay.root.json").read_text(encoding="utf-8", errors="replace"))
    assert report["events"] == json.loads((scratch / "output" / "Decay" / "decay" / "single" / "point" /
                                           "to_rivet.hepmc.json").read_text(encoding="utf-8", errors="replace"))["written"]   # named after its first output
    module, rivet = uproot.open(point / "decay.root"), uproot.open(point / "decayriv.root")
    compared = 0
    for key in module.keys():
        if not key.startswith("Lambda/"):
            continue
        name = key.split("/")[1].split(";")[0]
        mine, theirs = module[key], rivet[f"DecayRiv__RESERVED-2/{name}"]
        for a, b in ((mine.values(), theirs.values()), (mine.errors(), theirs.errors())):
            half = np.where(b != 0, 0.5 * 10.0 ** (np.floor(np.log10(np.abs(np.where(b != 0, b, 1)))) - 6), 0)
            assert np.all(np.abs(a - b) <= half * 1.0000001 + 1e-300), name     # YODA's rounding, nothing else
            assert np.array_equal(a == 0, b == 0), name
        compared += 1
    assert compared == 21


def test_inproc_equals_the_chain_at_one_thread(scratch):
    for configuration in ("single", "inproc"):
        hep_run(scratch, "Demo/jets", configuration, "--set", "run.events=2000", "--set", "run.threads=1")
    chain, inproc = (scratch / "results" / folder("Demo/jets", c) / "point" for c in ("single", "inproc"))
    seeds = [json.loads((scratch / "output" / folder("Demo/jets", c) / "point" / "provenance.json")
                        .read_text(encoding="utf-8"))["seed"] for c in ("single", "inproc")]
    assert seeds[0] == seeds[1]
    a, b = yoda.read(str(chain / "jets.yoda")), yoda.read(str(inproc / "jets.yoda"))
    finals = [p for p in a if not p.startswith("/RAW") and "Estimate1D" in a[p].type()]
    assert len(finals) == 19                       # d01…d19: d18, d19 since b2b5ee5
    for path in finals:                            # the chain's is merged from its shards' YODAs (V31), each
        mine, theirs = (np.nan_to_num(x[path].vals(), nan=-1) for x in (a, b))   # written to 7 digits
        assert np.array_equal(mine == 0, theirs == 0), path
        assert np.allclose(mine, theirs, rtol=1e-5, atol=0), path


def test_inproc_sigma_equals_the_sidecar_at_four_threads(scratch):
    for configuration in ("single", "inproc"):
        output, results = hep_run(scratch, "Demo/jets", configuration, "--set", "run.events=4000",
                                  "--set", "run.threads=4")
    point = output / folder("Demo/jets", "single") / "point"
    sidecar = json.loads(min(point.glob("events*.hepmc.json")).read_text(encoding="utf-8", errors="replace"))  # sharded: .s1
    report = json.loads((results / folder("Demo/jets", "inproc") / "point" / "jets.yoda.json").read_text(encoding="utf-8", errors="replace"))
    assert report["events"] == sidecar["written"]
    assert report["sigma_pb"] == pytest.approx(sidecar["sigma_pb"], rel=1e-6)


@pytest.mark.parametrize("config, product", [("Demo/inproc_jets", "jets.yoda"),
                                             ("Demo/inproc_validation", "validation.yoda")])
def test_rivet_threads_equal_one_rivet(scratch, config, product):
    """V34, the gate: four Rivets on threads of their own, merged, equal one Rivet on the same events.
    Both analyses cluster with SISCone, which needs the patch for this (L29): without it the jets
    change or FastJet stops with an internal error."""
    results = []
    for k in (1, 4):
        _, res = hep_run(scratch / f"k{k}", config, "single", "--set", "run.events=4000", "--set", "run.threads=4",
                         "--set", f"tools.inproc.config.rivet_threads={k}")
        results.append(yoda.read(str(next(res.rglob(product)))))
    one, four = results
    assert one["/RAW/_EVTCOUNT"].numEntries() == four["/RAW/_EVTCOUNT"].numEntries()
    assert four["/_XSEC"].val() == pytest.approx(one["/_XSEC"].val(), rel=1e-12)
    compared = 0
    for path, histo in one.items():
        if path.startswith("/RAW/") and hasattr(histo, "sumW"):
            assert four[path].sumW() == pytest.approx(histo.sumW(), rel=1e-12), path
        elif histo.type() == "Estimate1D":
            assert np.array_equal(np.nan_to_num(histo.vals(), nan=-1), np.nan_to_num(four[path].vals(), nan=-1)), path
            compared += 1
    assert compared > 10


def test_the_serial_engine_is_reproducible(scratch):
    runs = []
    for attempt in range(2):
        _, results = hep_run(scratch, "Demo/jets", "inproc", "--rerun", "--set", "run.events=1000",
                             "--set", "run.threads=1", "--set", "tools.jets.config.engine=serial")
        runs.append((results / folder("Demo/jets", "inproc") / "point" / "jets.yoda").read_bytes())
    assert runs[0] == runs[1]
