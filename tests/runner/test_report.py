"""runner/report.py (I-108 P2, V207): a report's sources and recipe resolved into sections of figures and statistics,
the default recipe, both layouts, --list and --init. Every tree is tmp_path's: HEP_RESULTS, HEP_RECORDS, HEP_CONFIGS
and HEP_REPORTS."""

from __future__ import annotations

import argparse
import csv

import pytest

from runner import cli, report
from runner.errors import HepError

DOCUMENT = """[source]
config = "P/study"
configuration = "{label}"
label = "{label}"
title = "{label}"
run = "validation"
project = "P"
folder = "P/validation/{folder}"
serial = 1
heimdall = "0123456789abcdef"
written = "2026-10-26T10:00:00+00:00"

[axes]
vary = ["pdf"]
plot_points = []
combine = []
fixed = {{}}

[quantities.pdf]
points = [
  {{ tag = "A", value = "A", label = "PDF A" }},
  {{ tag = "B", value = "B", label = "PDF B" }},
]

[plot]
backend = ["mpl"]
draw = ["totality"]

[members.A]
index = 0
choice = {{ pdf = 0 }}
values = {{ pdf = 0 }}
yoda = "points/A/run.yoda"
identity = "one"
complete = true
events = {events}

[members.B]
index = 1
choice = {{ pdf = 1 }}
values = {{ pdf = 1 }}
yoda = "points/B/run.yoda"
identity = "two"
complete = {complete}
events = {events}
"""

COLUMNS = ("page", "cell", "object", "curve", "point", "reference", "is_reference", "bins", "area", "area_err", "ref_area",
           "cmp_area", "abs_area", "rel_abs_area", "area_ratio", "ratio_mean", "ratio_dev", "chi2", "ndf", "chi2_ndf")


def folder(results, name: str, label: str, events: int, complete: bool = True, cells=("18x275", "27x920"),
           objects=("d01-x01-y01", "d02-x01-y01", "d10-x01-y01")):
    """A configuration's result folder: its document, its points' YODAs, its totality pages (mpl) and their numbers."""
    where = results / "P" / "validation" / name
    (where / "points").mkdir(parents=True)
    (where / "plot.toml").write_text(DOCUMENT.format(label=label, folder=name, events=events,
                                                     complete=str(complete).lower()), encoding="utf-8")
    for point in ("A", "B"):
        (where / "points" / point).mkdir()
        (where / "points" / point / "run.yoda").write_text("# a YODA\n", encoding="utf-8")
    rows = []
    for cell in cells:
        for obj in objects:
            page = where / "plots" / "totality" / "mpl" / cell / f"{obj}.pdf"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_bytes(b"%PDF a page")
            page.with_suffix(".png").write_bytes(b"\x89PNG a page")
            for curve, point in (("PDF A", "A"), ("PDF B", "B")):
                rows.append({"page": f"{cell}/{obj}", "cell": cell, "object": f"/ZEUS/{obj}", "curve": curve, "point": point,
                             "reference": "ZEUS", "is_reference": False, "bins": 10, "area": 1.0, "area_err": 0.1,
                             "ref_area": 1.0, "cmp_area": 1.0, "abs_area": 0.1, "rel_abs_area": 0.1, "area_ratio": 1.0,
                             "ratio_mean": 1.0, "ratio_dev": 0.1, "chi2": 9.0, "ndf": 9, "chi2_ndf": 1.0})
    numbers = where / "statistics" / "totality" / "statistics.csv"
    numbers.parent.mkdir(parents=True)
    with open(numbers, "w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=COLUMNS)
        out.writeheader()
        out.writerows(rows)
    return where


@pytest.fixture
def trees(tmp_path, monkeypatch):
    for var in ("HEP_RESULTS", "HEP_RECORDS", "HEP_CONFIGS", "HEP_REPORTS"):
        monkeypatch.setenv(var, str(tmp_path / var.removeprefix("HEP_").lower()))
    results = tmp_path / "results"
    folder(results, "01_pdf", "pdf", 10_000_000)
    folder(results, "02_events", "events", 10_000_000, complete=False)
    return tmp_path


def recipe(trees, name: str, text: str):
    path = trees / "configs" / "P" / f"{name}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_a_source_is_a_folder_a_run_a_path_or_a_glob(trees):
    assert [s.address for s in report.sources(["P/validation/01_pdf"], "here")] == ["P/validation/01_pdf"]
    assert [s.address for s in report.sources(["P/validation"], "here")] == ["P/validation/01_pdf", "P/validation/02_events"]
    assert [s.address for s in report.sources(["P/validation/0*", "P/validation/01_pdf"], "here")] == \
        ["P/validation/01_pdf", "P/validation/02_events"]                                       # each once
    path = trees / "results" / "P" / "validation" / "02_events"
    assert [s.folder for s in report.sources([str(path)], "here")] == [path]
    with pytest.raises(HepError, match="no result folder P/validation/01_pfd") as error:
        report.sources(["P/validation/01_pfd"], "here")
    assert "01_pdf" in str(error.value.hint)


def test_a_source_says_where_it_came_from(trees):
    first, second = report.sources(["P/validation"], "here")
    facts = first.facts()
    assert facts["configuration"] == "pdf" and facts["heimdall"] == "0123456789ab" and facts["events"] == "10M"
    assert (facts["points"], facts["complete"], facts["incomplete"]) == (2, 2, [])
    assert facts["against"] == "each page's first curve"                     # the document maps no data
    assert second.facts()["incomplete"] == ["B"] and first.label("events") == "10M" and first.label("folder") == "pdf"


def test_the_default_report_is_the_headline_and_each_sets_pages_by_cell(trees):
    plan = report.planned("P/validation/01_pdf", [])
    assert plan.name == "P/validation/01_pdf" and plan.out == trees / "reports" / "P" / "validation" / "01_pdf"
    standings, pages = plan.sections
    assert standings.title == "Standings" and [p.keys for p in standings.parts] == [report.HEADLINE]
    assert pages.title == "Pages: totality"
    assert [g.caption for g in pages.grids] == ["P/validation/01_pdf · totality · 18x275", "P/validation/01_pdf · totality · 27x920"]
    assert [f.page for f in pages.grids[0].figures] == ["18x275/d01-x01-y01", "18x275/d02-x01-y01", "18x275/d10-x01-y01"]
    assert all(f.file.suffix == ".pdf" for g in pages.grids for f in g.figures) and not plan.drawn()
    assert report.planned("P/validation", []).name == "P/validation"                    # the sources' common address


def test_a_recipe_picks_pages_side_by_side_and_its_sources_can_be_replaced(trees):
    recipe(trees, "weekly", """[report]
title = "Weekly"
from  = ["P/validation/01_pdf"]

[[section]]
title  = "Side by side"
from   = ["P/validation"]
pages  = ["d1*"]
cells  = ["18x275"]
layout = "sources"

[[section]]
title = "Its own"
pages = ["d01-*"]
""")
    plan = report.planned("P/weekly", [])
    side, own = plan.sections
    assert [g.caption for g in side.grids] == ["totality · 18x275/d10-x01-y01"]
    assert [f.label for f in side.grids[0].figures] == ["pdf", "events"]
    assert {f.source.address for g in own.grids for f in g.figures} == {"P/validation/01_pdf"}
    replaced = report.planned("P/weekly", ["P/validation/02_events"])
    assert {f.source.address for g in replaced.sections[1].grids for f in g.figures} == {"P/validation/02_events"}
    assert [f.label for f in replaced.sections[0].grids[0].figures] == ["pdf", "events"]       # its own from stays
    assert plan.out == trees / "reports" / "P" / "weekly" and plan.title == "Weekly"


def test_a_recipe_is_checked(trees):
    recipe(trees, "typo", '[report]\ntitle = "x"\n\n[[section]]\ntitle = "a"\npagez = ["*"]\n')
    with pytest.raises(HepError, match="pagez") as error:
        report.planned("P/typo", ["P/validation/01_pdf"])
    assert "pages" in str(error.value.hint)
    recipe(trees, "two", '[report]\n\n[[section]]\ntitle = "a"\npages = ["*"]\nstats = ["top5"]\n')
    with pytest.raises(HepError, match="one of pages"):
        report.planned("P/two", ["P/validation/01_pdf"])
    recipe(trees, "stat", '[report]\n\n[[section]]\ntitle = "a"\nstats = ["chi2_ndf:rankin"]\n')
    with pytest.raises(HepError, match="no section 'chi2_ndf:rankin'"):
        report.planned("P/stat", ["P/validation/01_pdf"])
    recipe(trees, "look", '[report]\n\n[[section]]\ntitle = "a"\npages = ["*"]\nplot = { normalize = "area" }\n')
    with pytest.raises(HepError, match="normalize"):
        report.planned("P/look", ["P/validation/01_pdf"])
    recipe(trees, "validation", '[report]\n\n[[section]]\ntitle = "a"\npages = ["*"]\n')
    with pytest.raises(HepError, match="names both a report and a run"):
        report.planned("P/validation", ["P/validation/01_pdf"])


def test_what_is_not_drawn_is_refused_with_the_command_that_draws_it(trees):
    recipe(trees, "few", '[report]\n\n[[section]]\ntitle = "a"\nset = "few"\npages = ["*"]\n\n'
                         '[[section]]\ntitle = "b"\nset = "few"\nstats = ["top5"]\n')
    with pytest.raises(HepError, match="has no set few drawn") as error:
        report.planned("P/few", ["P/validation/01_pdf"])
    assert "heimdall plot P/validation/01_pdf --sets few" in str(error.value.hint)
    recipe(trees, "events", '[report]\n\n[[section]]\ntitle = "a"\npages = ["d01-*"]\nlayout = "sources"\nlabel = "events"\n')
    with pytest.raises(HepError, match="two sources are labelled 10M"):
        report.planned("P/events", ["P/validation"])


def test_a_configuration_run_again_is_labelled_by_its_serial(trees):
    folder(trees / "results", "03_pdf", "pdf", 1_000_000)
    found = report.sources(["P/validation"], "here")
    assert report.labels(found, "folder") == {"P/validation/01_pdf": "01_pdf", "P/validation/02_events": "02_events",
                                              "P/validation/03_pdf": "03_pdf"}
    assert report.labels(found[1:], "folder") == {"P/validation/02_events": "events", "P/validation/03_pdf": "pdf"}
    assert list(report.labels(found[1:], "events").values()) == ["10M", "1M"]


def test_list_writes_nothing_and_init_writes_a_recipe_once(trees, capsys):
    args = argparse.Namespace(names=["P/validation/01_pdf"], list=True, init=None, output=None)
    assert cli.cmd_report(args) == 0
    said = capsys.readouterr().out
    assert said.startswith("report P/validation/01_pdf → ") and "1 Standings: statistics of P/validation/01_pdf" in said
    assert "2 of 2 point(s), 10M events" in said and not (trees / "reports").exists()
    made = argparse.Namespace(names=["P/weekly"], list=False, init="P/validation/01_pdf", output=None)
    assert cli.cmd_report(made) == 0 and (trees / "configs" / "P" / "weekly.toml").is_file()
    with pytest.raises(HepError, match="there already"):
        cli.cmd_report(made)
    plan = report.planned("P/weekly", [])
    assert [s.title for s in plan.sections] == ["Standings", "totality"] and plan.sources[0].address == "P/validation/01_pdf"
    assert report.recipes("P") == ["P/weekly"]
