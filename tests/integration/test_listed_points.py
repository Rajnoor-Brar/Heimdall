"""Listed points through a real run and its plot stage (V154): a page per PDF, a curve per row on it, a row that
leaves pT0Ref out at the card's own value, and a bare PDF set name that Pythia gets with its prefix (V152).

The test makes a small work dir of its own under its scratch folder, with Rivet's MC_JETS (no plugin of the
fixture's), so no fixture config is added.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest

import support
from support import HEP, REPO, apps, env

pytestmark = [pytest.mark.slow,
              pytest.mark.skipif(not (apps() / "App_Pythia.exe").exists(), reason="heimdall build --framework")]

LISTED = """[run]
project = "T"
name    = "listed"
run     = "listed"
events  = 200
threads = 1
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
  { tag = "MSTW08lo",  value = "MSTW2008lo68cl",                 label = "MSTW 2008 LO" },
  { tag = "NNPDF23lo", value = "LHAPDF6:NNPDF23_lo_as_0130_qed", label = "NNPDF 2.3 LO" },
]

[quantities.pt0ref]
to     = { pythia = "MultipartonInteractions:pT0Ref" }
points = [{ tag = "p30", value = 3.0, label = "pT0 3.0" }, { tag = "p34", value = 3.4, label = "pT0 3.4" }]

[cfgs.listed]
vary        = [{ points = [{ pdf = "MSTW08lo", pt0ref = "p30" }, { pdf = "MSTW08lo", pt0ref = "p34" }, { pdf = "NNPDF23lo" }] }]
plot_points = ["pdf"]

[plot]
formats = ["png"]
"""


def test_listed_points_run_and_draw_a_page_per_pdf(scratch):
    work = scratch / "Listed"
    (work / "configs" / "T").mkdir(parents=True)
    (work / "hep.toml").write_text('[work]\nname = "Listed"\n', encoding="utf-8")
    (work / "configs" / "T" / "listed.toml").write_text(LISTED, encoding="utf-8")
    (work / "configs" / "T" / "ep.cmnd").write_bytes((REPO / "tests" / "fixtures" / "work" / "configs" / "Demo" / "ep.cmnd").read_bytes())
    done = subprocess.run([str(HEP), "run", "T/listed", "--plain"], cwd=work, env={**env(scratch), "HEP_WORK": str(work)},
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    records = scratch / "records" / "T" / "listed" / "01_listed"
    assert sorted(p.name for p in (records / "points").iterdir() if p.is_dir()) == ["MSTW08lo_p30", "MSTW08lo_p34", "NNPDF23lo"]
    cards = records / "logs"
    mstw = (cards / "MSTW08lo_p34" / "cards" / "pythia.cmnd").read_text(encoding="utf-8").splitlines()
    overrides = (cards / "NNPDF23lo" / "cards" / "pythia.point.cmnd").read_text(encoding="utf-8")
    assert "PDF:pSet = LHAPDF6:MSTW2008lo68cl" in mstw and "MultipartonInteractions:pT0Ref = 3.4" in mstw
    assert "pT0Ref" not in overrides                                       # the base card's own value stands
    pages = support.pages(scratch, Path("T") / "listed" / "01_listed")
    one = next((pages / "MSTW08lo").rglob("*.toml"))
    assert [c["label"] for c in tomllib.loads(one.read_text(encoding="utf-8"))["curve"]] == ["pT0 3.0", "pT0 3.4"]
    other = pages / "NNPDF23lo" / one.relative_to(pages / "MSTW08lo")
    assert len(tomllib.loads(other.read_text(encoding="utf-8"))["curve"]) == 1
    pngs = scratch / "results" / "T" / "listed" / "01_listed" / "plots" / "totality" / "root"
    assert {p.parent.name for p in pngs.rglob("*.png")} >= {"MSTW08lo", "NNPDF23lo"}
