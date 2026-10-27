"""heimdall report draws for itself (I-108 P6, V211): what a run's folder has not drawn or measured, what it drew as
PNG alone, a section's plot keys and a set of a section's own, drawn by plot.draw and plot.measure from the folder's
plot document into the report's cache; the folder's results/ and records/ byte for byte as they were.

The points are test_plot_stage's: four (lepton × pdf), their products the two legacy mini YODAs, complete.
"""

from __future__ import annotations

import csv
import hashlib
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from runner import cli, paths, report, tools

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "runner"))
sys.path.insert(0, str(REPO / "tests" / "integration"))
from helpers import parse, raw  # noqa: E402
from test_plot_stage import BUILT, BY_PDF, LEGACY, completed  # noqa: E402

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not BUILT, reason="heimdall build --framework"),
              pytest.mark.skipif(not shutil.which("pdflatex"), reason="pdflatex makes report.pdf")]


@pytest.fixture
def folder(scratch):
    """A configuration whose points are complete and whose run wrote its plot document (its sets: the totality and
    by_pdf; PNG alone) and report.toml, nothing drawn or measured: (run, configuration, plans, its address)."""
    data = raw(run__name="reportdraw", run__cfgs__one__sweeps=["lepton", "pdf"], run__cfgs__one__plot_points=["lepton"],
               quantities__lepton={"key": {"pythia": "Beams:idB"}, "values": [11, -11], "tags": ["em", "ep"]},
               quantities__pdf__labels=["MSTW 2008 LO", "NNPDF 2.3 LO"],
               plot={"backend": "root", "formats": ["png"], "ratio": True, "min_entries": 10, "range_pad": 1,
                     "data": {"file": str(LEGACY / "ydmrg" / "photo_eic_data.yoda"), "legend": "legacy",
                              "map": {"d01-x01-y01": "/REF/photo_eic/d01-x01-y01"}},
                     "sets": [BY_PDF], "style": {"page": {"dpi": 100}}})
    run = parse(data, scratch)
    configuration = run.configuration(None)
    plans = completed(run, configuration)
    assert cli.draw_run(run, configuration, plans, lambda line: None, draw=False, stats=False) == 0
    here = plans[0].folders
    assert (here.results / "report.toml").is_file() and not here.plots.exists() and not here.statistics.exists()
    return run, configuration, plans, tools.run_dir(run, configuration).as_posix()


def tree(*roots: Path) -> dict[str, str]:
    """Every file and folder under these, and each file's sha256."""
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "folder"
            for root in roots for p in sorted(root.rglob("*"))}


def text_of(pdf: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, encoding="utf-8").stdout


def test_a_folder_never_drawn_is_drawn_for_its_report(folder):
    """Its report.toml's default sections: the totality's numbers measured and both sets' pages drawn, into the
    report's cache, never into results/; a rebuild draws and copies nothing."""
    run, configuration, plans, address = folder
    here = plans[0].folders
    before = tree(here.results, here.record)
    plan = report.planned(address, [])
    (drawing,) = plan.drawings
    assert drawing.sets == {"totality": "not drawn there", "by_pdf": "not drawn there"}
    assert drawing.measured == {"totality": "not measured there"}
    said: list[str] = []
    report.build(plan, said.append)
    assert tree(here.results, here.record) == before, "the source was written"
    assert f"report: drawing {address}: pages of totality (not drawn there), by_pdf (not drawn there); " \
           "numbers of totality (not measured there)" in said
    root = report.drawings_root(plan)
    assert root == paths.cache_root() / run.project / "reports" / Path(address).relative_to(run.project) / ".drawn"
    drawn = root / report.slug(address) / "results"
    assert (drawn / "plots" / "totality" / "root" / "em" / "d01-x01-y01.pdf").is_file()       # pdf and png, for the report
    assert (drawn / "statistics" / "totality" / "statistics.csv").is_file() and (root / report.slug(address) / "drawn.key").is_file()
    out = paths.reports_root() / address
    assert plan.out == out and (out / "report.pdf").is_file()
    assert [s.title for s in plan.sections] == ["Standings", "Pages: totality", "Pages: by_pdf"] and not plan.drawn()
    shown = sorted(p.relative_to(out / "figures").as_posix() for p in (out / "figures").rglob("*.pdf"))
    assert len(shown) == 34 + 4 and "02_Pages_totality/001_one_em_d01-x01-y01.pdf" in shown        # 34 pages, by_pdf's 4
    assert list((out / "stats" / "01_Standings").glob("*.csv")) and not list((out / "stats").rglob("*.pdf"))   # typeset
    rows = list(csv.reader(open(out / "figures" / "02_Pages_totality" / "001_one_em_d01-x01-y01.csv", encoding="utf-8")))
    assert rows[0] == list(report.FIGURE_COLUMNS) and {r[0] for r in rows[1:]} >= {p.point.name for p in plans if p.point.name.startswith("em_")}
    words = text_of(out / "report.pdf")
    assert "Drawn for this report" in words and "Standings" in words
    again: list[str] = []
    report.build(report.planned(address, []), again.append)
    assert not any(line.startswith("report: drawing") for line in again), again
    assert "0 file(s) copied" in again[0] and again[0].endswith("0 drawn") and "report.pdf unchanged" in again[1]
    assert tree(here.results, here.record) == before


def test_a_sections_plot_keys_and_a_set_of_its_own_are_drawn_for_the_report(folder, scratch):
    """Drawn as PNG alone, the folder's pages are drawn again for the report (as PDFs); a section's plot = {…}
    draws its pages and measures its numbers so (normalise = "area": every area one), its bar graphs from those
    numbers; a set the run never had is drawn from the section's own sets."""
    run, configuration, plans, address = folder
    here = plans[0].folders
    assert cli.draw_run(run, configuration, plans, lambda line: None) == 0          # pages as PNG, and their numbers
    before = tree(here.results, here.record)
    recipe = scratch / "shapes.toml"
    recipe.write_text("""[report]
title = "Shapes of {configuration}"

[[report.section]]
title = "As drawn"
pages = ["d01-*"]

[[report.section]]
title = "Shapes"
pages = ["d01-*"]
plot = { normalise = "area" }

[[report.section]]
title = "Shape numbers"
stats = ["area:table"]
plot = { normalise = "area" }

[[report.section]]
title = "Shape bars"
bars = ["*d01-x01-y01"]
plot = { normalise = "area" }

[[report.section]]
title = "Mine"
set = "mine"
pages = ["*"]
plot = { sets = { mine = { pages = { lepton = "all" }, curves = { pdf = "all" }, objects = ["d02-*"] } } }
""", encoding="utf-8")
    plan = report.planned(str(recipe), [address])
    own, area, mine = plan.drawings
    assert own.sets == {"totality": "drawn there as PNG alone"} and not own.measured
    assert area.look == {"normalise": "area"} and set(area.sets) == set(area.measured) == {"totality"}
    assert set(mine.sets) == {"mine"}
    said: list[str] = []
    report.build(plan, said.append)
    assert tree(here.results, here.record) == before, "the source was written"
    root = report.drawings_root(plan)
    page = tomllib.loads((area.folder / "work" / "totality" / "em" / "d01-x01-y01.toml").read_text(encoding="utf-8"))
    assert page["page"]["normalise"] == "area"
    rows = list(csv.DictReader(open(area.results / "statistics" / "totality" / "statistics.csv", encoding="utf-8")))
    assert rows and all(abs(float(r["area"]) - 1) < 1e-6 for r in rows if r["area"] and r["is_reference"] != "True")
    assert sorted(p.name for p in root.iterdir()) == sorted(d.folder.name for d in plan.drawings)
    out = plan.out
    assert out == paths.reports_root() / address
    for section, count in (("01_As_drawn", 2), ("02_Shapes", 2), ("05_Mine", 2)):
        assert len(list((out / "figures" / section).glob("*.pdf"))) == count, section
    assert all("d02-x01-y01" in p.name for p in (out / "figures" / "05_Mine").glob("*.pdf"))
    assert list((out / "stats" / "03_Shape_numbers").glob("*.csv")) and list((out / "stats" / "04_Shape_bars").glob("*/*.csv"))
    assert not (here.plots / "mine").exists()
    words = text_of(out / "report.pdf")
    assert "as this report measures it" in words and 'normalise = "area"' in words
