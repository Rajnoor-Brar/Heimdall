"""runner/report.py (I-108 P2, P4; V207, V209): a report's sources and recipe resolved into sections of figures and
statistics, the default recipe, both layouts, the ways in (a folder's report.toml, a recipe, a run TOML's [report]
and its template), where each is built, --list and --init. Every tree is tmp_path's: HEP_RESULTS, HEP_RECORDS,
HEP_CONFIGS and HEP_REPORTS."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from pathlib import Path

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
draw = {draw}

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
           objects=("d01-x01-y01", "d02-x01-y01", "d10-x01-y01"), draw=("totality",), run="validation", project="P"):
    """A configuration's result folder: its document, its points' YODAs, its totality pages (mpl) and their numbers."""
    where = results / project / run / name
    (where / "points").mkdir(parents=True)
    text = DOCUMENT.format(label=label, folder=name, events=events, complete=str(complete).lower(),
                           draw="[" + ", ".join(f'"{s}"' for s in draw) + "]")
    (where / "plot.toml").write_text(text.replace('"validation"', f'"{run}"').replace('"P"', f'"{project}"')
                                     .replace("P/validation/", f"{project}/{run}/"), encoding="utf-8")
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


def test_the_default_report_is_the_headline_and_each_set_its_document_draws(trees):
    plan = report.planned("P/validation/01_pdf", [])
    assert plan.name == "P/validation/01_pdf" and plan.out == trees / "reports" / "P" / "validation" / "01_pdf"
    standings, pages = plan.sections
    assert standings.title == "Standings" and [p.keys for p in standings.parts] == [report.HEADLINE]
    assert pages.title == "Pages: totality"
    assert [g.caption for g in pages.grids] == ["P/validation/01_pdf · totality · 18x275", "P/validation/01_pdf · totality · 27x920"]
    assert [f.page for f in pages.grids[0].figures] == ["18x275/d01-x01-y01", "18x275/d02-x01-y01", "18x275/d10-x01-y01"]
    assert all(f.file.suffix == ".pdf" for g in pages.grids for f in g.figures) and not plan.drawn()
    whole = report.planned("P/validation", [])
    assert whole.name == "P/validation" and whole.out == trees / "reports" / "P" / "validation"    # a run's: its folder
    folder(trees / "results", "03_few", "few", 1_000_000, draw=("totality", "few"))                  # few: drawn nowhere
    plan = report.planned("P/validation/03_few", [])
    assert [s.title for s in plan.sections] == ["Standings", "Pages: totality"]
    assert plan.left == ["Pages: few: no source has few drawn"]
    assert "  left out: Pages: few: no source has few drawn" in report.listing(plan)




def test_a_recipe_picks_pages_side_by_side_and_its_sources_can_be_replaced(trees):
    recipe(trees, "weekly", """[report]
title = "Weekly"
from  = ["P/validation/01_pdf"]

[[report.section]]
title  = "Side by side"
from   = ["P/validation"]
pages  = ["d1*"]
cells  = ["18x275"]
layout = "sources"

[[report.section]]
title = "Its own"
pages = ["d01-*"]
""")
    plan = report.planned("P/weekly.toml", [])
    side, own = plan.sections
    assert [g.caption for g in side.grids] == ["totality · 18x275/d10-x01-y01"]
    assert [f.label for f in side.grids[0].figures] == ["pdf", "events"]
    assert {f.source.address for g in own.grids for f in g.figures} == {"P/validation/01_pdf"}
    replaced = report.planned("P/weekly.toml", ["P/validation/02_events"])
    assert {f.source.address for g in replaced.sections[1].grids for f in g.figures} == {"P/validation/02_events"}
    assert [f.label for f in replaced.sections[0].grids[0].figures] == ["pdf", "events"]       # its own from stays
    assert plan.title == "Weekly" and plan.name == "P/weekly.toml"
    assert plan.out == trees / "reports" / "P" / "validation"                    # where its sources meet in results/


def test_a_recipe_is_checked(trees):
    recipe(trees, "typo", '[report]\ntitle = "x"\n\n[[report.section]]\ntitle = "a"\npagez = ["*"]\n')
    with pytest.raises(HepError, match="pagez") as error:
        report.planned("P/typo.toml", ["P/validation/01_pdf"])
    assert "pages" in str(error.value.hint)
    recipe(trees, "two", '[report]\n\n[[report.section]]\ntitle = "a"\npages = ["*"]\nstats = ["top5"]\n')
    with pytest.raises(HepError, match="one of pages"):
        report.planned("P/two.toml", ["P/validation/01_pdf"])
    recipe(trees, "stat", '[report]\n\n[[report.section]]\ntitle = "a"\nstats = ["chi2_ndf:rankin"]\n')
    with pytest.raises(HepError, match="no section 'chi2_ndf:rankin'"):
        report.planned("P/stat.toml", ["P/validation/01_pdf"])
    recipe(trees, "look", '[report]\n\n[[report.section]]\ntitle = "a"\npages = ["*"]\nplot = { normalize = "area" }\n')
    with pytest.raises(HepError, match="normalize"):
        report.planned("P/look.toml", ["P/validation/01_pdf"])
    recipe(trees, "old", '[report]\n\n[[section]]\ntitle = "a"\npages = ["*"]\n')            # P2's form
    with pytest.raises(HepError, match=r"a recipe has \[report\] alone, not \[section\]"):
        report.planned("P/old.toml", ["P/validation/01_pdf"])
    with pytest.raises(HepError, match="no recipe P/none.toml"):
        report.planned("P/none.toml", ["P/validation/01_pdf"])
    with pytest.raises(HepError, match="no result folder P/weekly"):              # no .toml: a source, always
        report.planned("P/weekly", [])


def test_what_is_not_drawn_is_refused_with_the_command_that_draws_it(trees):
    recipe(trees, "few", '[report]\n\n[[report.section]]\ntitle = "a"\nset = "few"\npages = ["*"]\n\n'
                         '[[report.section]]\ntitle = "b"\nset = "few"\nstats = ["top5"]\n')
    with pytest.raises(HepError, match="has no set few drawn") as error:
        report.planned("P/few.toml", ["P/validation/01_pdf"])
    assert "heimdall plot P/validation/01_pdf --sets few" in str(error.value.hint)
    recipe(trees, "events", '[report]\n\n[[report.section]]\ntitle = "a"\npages = ["d01-*"]\nlayout = "sources"\nlabel = "events"\n')
    with pytest.raises(HepError, match="two sources are labelled 10M"):
        report.planned("P/events.toml", ["P/validation"])


def test_a_configuration_run_again_is_labelled_by_its_serial(trees):
    folder(trees / "results", "03_pdf", "pdf", 1_000_000)
    found = report.sources(["P/validation"], "here")
    assert report.labels(found, "folder") == {"P/validation/01_pdf": "01_pdf", "P/validation/02_events": "02_events",
                                              "P/validation/03_pdf": "03_pdf"}
    assert report.labels(found[1:], "folder") == {"P/validation/02_events": "events", "P/validation/03_pdf": "pdf"}
    assert list(report.labels(found[1:], "events").values()) == ["10M", "1M"]


def test_reports_are_built_where_results_has_their_sources_unless_told(trees):
    reports = trees / "reports"
    assert report.planned("P/validation/01_pdf", []).out == reports / "P" / "validation" / "01_pdf"
    assert report.planned("P/validation/0*", []).out == reports / "P" / "validation"
    folder(trees / "results", "01_pdf", "pdf", 1_000_000, run="other")
    assert report.planned("P/validation/01_pdf", ["P/other/01_pdf"]).out == reports / "P"          # two runs': P's
    folder(trees / "results", "01_pdf", "pdf", 1_000_000, project="Q")
    with pytest.raises(HepError, match=r"several projects \(P, Q\)") as error:
        report.planned("P/validation/01_pdf", ["Q/validation/01_pdf"])
    assert "-o DIR" in str(error.value.hint)
    elsewhere = trees / "elsewhere"
    assert report.planned("P/validation/01_pdf", ["Q/validation/01_pdf"], elsewhere).out == elsewhere
    recipe(trees, "out", '[report]\noutput = "P/weekly"\nfrom = ["P/validation/01_pdf", "Q/validation/01_pdf"]\n')
    assert report.planned("P/out.toml", []).out == reports / "P" / "weekly"
    lifted = trees / "lifted"
    shutil.copytree(trees / "results" / "P" / "validation" / "01_pdf", lifted)
    with pytest.raises(HepError, match="is not under results/"):
        report.planned(str(lifted), [])


def test_a_folder_reads_its_own_report_toml(trees):
    where = trees / "results" / "P" / "validation" / "01_pdf"
    (where / report.RECIPE).write_text('[report]\ntitle = "{run}: {title}"\n\n[[report.section]]\ntitle = "Spectra"\n'
                                       'pages = ["d01-*"]\n', encoding="utf-8")
    plan = report.planned("P/validation/01_pdf", [])
    assert [s.title for s in plan.sections] == ["Spectra"] and plan.recipe == where / report.RECIPE
    assert plan.title == "validation: pdf" and plan.out == trees / "reports" / "P" / "validation" / "01_pdf"
    assert report.planned(str(where / report.RECIPE), []).sources[0].address == "P/validation/01_pdf"   # named itself
    both = report.planned("P/validation", [])                    # several: the default, not one folder's recipe
    assert [s.title for s in both.sections] == ["Standings", "Pages: totality"]
    recipe(trees, "weekly", '[report]\ntitle = "Weekly {configuration}"\n\n[[report.section]]\ntitle = "All"\npages = ["*"]\n')
    over = report.planned("P/weekly.toml", ["P/validation/01_pdf"])            # a recipe over it: the recipe's
    assert [s.title for s in over.sections] == ["All"] and over.title == "Weekly pdf"
    assert report.planned("P/weekly.toml", ["P/validation"]).title == "Weekly pdf, events"


@pytest.fixture
def study(trees):
    """A run TOML of the fixture's (Demo/validation) with a [report] naming a template, in tmp_path's configs/."""
    demo = trees / "configs" / "Demo"
    shutil.copytree(Path(os.environ["HEP_WORK"]) / "configs" / "Demo", demo)
    (demo / "weekly.toml").write_text('[report]\ntitle = "Weekly"\nsubtitle = "for the group"\nfrom = ["P/validation/01_pdf"]\n'
                                      'output = "Demo/weekly"\n\n[[report.section]]\ntitle = "Standings"\nstats = ["top5"]\n',
                                      encoding="utf-8")
    text = (demo / "validation.toml").read_text(encoding="utf-8")
    (demo / "study.toml").write_text(text + '\n[report]\ntemplate = "weekly"\ntitle = "{project} · {configuration}"\n\n'
                                     '[[report.section]]\ntitle = "Mine"\npages = ["d01-*"]\n', encoding="utf-8")
    return demo


def test_a_run_tomls_report_lays_its_own_over_its_template(study):
    plan = report.planned("Demo/study.toml", ["P/validation/01_pdf"])
    assert [s.title for s in plan.sections] == ["Standings", "Mine"]                        # the template's first
    assert plan.title == "P · pdf" and plan.subtitle == "for the group"                  # its keys over the template's
    assert plan.out.parts[-3:] == ("P", "validation", "01_pdf")              # the template's output: a recipe's own
    plain = report.planned("Demo/validation.toml", ["P/validation/01_pdf"])         # no [report]: the default
    assert [s.title for s in plain.sections] == ["Standings", "Pages: totality"]
    with pytest.raises(HepError, match="name the folders"):
        report.planned("Demo/study.toml", [])


@pytest.mark.parametrize("table, message", [
    ('[report]\nfrom = ["P/validation/01_pdf"]\n', "a run TOML's \\[report\\] takes no from"),
    ('[report]\noutput = "x"\n', "takes no output"),
    ('[report]\ntemplate = "nowhere"\n', "no report template 'nowhere'"),
    ('[report]\ntemplate = "study"\n', "a report's template is a recipe"),
    ('[report]\ntitel = "x"\n', "unknown key 'titel'"),
])
def test_a_run_tomls_report_is_checked_when_it_is_read(study, table, message):
    from runner import config
    text = (study / "validation.toml").read_text(encoding="utf-8")
    (study / "bad.toml").write_text(text + "\n" + table, encoding="utf-8")
    with pytest.raises(HepError, match=message):
        config.load("Demo/bad")


def test_a_template_naming_itself_is_refused(study):
    from runner import config
    (study / "loop.toml").write_text('[report]\ntemplate = "loop2"\n', encoding="utf-8")
    (study / "loop2.toml").write_text('[report]\ntemplate = "loop"\n', encoding="utf-8")
    text = (study / "validation.toml").read_text(encoding="utf-8")
    (study / "round.toml").write_text(text + '\n[report]\ntemplate = "loop"\n', encoding="utf-8")
    with pytest.raises(HepError, match="go round in a circle: round.toml → loop.toml → loop2.toml → loop.toml"):
        config.load("Demo/round")


def test_the_run_writes_its_report_toml_from_the_config(study, trees):
    from runner import config
    where = trees / "results" / "P" / "validation" / "01_pdf"
    written = report.write_recipe(config.load("Demo/study"), where / "plot.toml")
    text = written.read_text(encoding="utf-8")
    assert written == where / "report.toml" and "Demo/study.toml's [report] and its template Demo/weekly.toml" in text
    assert 'title = "P · pdf"' in text and "from" not in text.split("\n[report]\n", 1)[1] and "output" not in text
    plan = report.planned("P/validation/01_pdf", [])
    assert [s.title for s in plan.sections] == ["Standings", "Mine"] and plan.title == "P · pdf"
    written = report.write_recipe(config.load("Demo/validation"), where / "plot.toml")      # no [report]: the default
    text = written.read_text(encoding="utf-8")
    assert "the default report (Demo/validation.toml has no [report])" in text
    assert report.load_recipe(written)["section"] == report.default_sections({"draw": ["totality"]}, {})
    assert not list(where.glob("*.partial"))


def test_list_writes_nothing_and_init_writes_a_recipe_once(trees, capsys):
    args = argparse.Namespace(names=["P/validation/01_pdf"], list=True, init=None, output=None)
    assert cli.cmd_report(args) == 0
    said = capsys.readouterr().out
    assert said.startswith("report P/validation/01_pdf → ") and "1 Standings: statistics of P/validation/01_pdf" in said
    assert "2 of 2 point(s), 10M events" in said and not (trees / "reports").exists()
    made = argparse.Namespace(names=["P/weekly.toml"], list=False, init="P/validation/01_pdf", output=None)
    assert cli.cmd_report(made) == 0 and (trees / "configs" / "P" / "weekly.toml").is_file()
    with pytest.raises(HepError, match="there already"):
        cli.cmd_report(made)
    with pytest.raises(HepError, match="name it, <P>/<name>.toml"):
        cli.cmd_report(argparse.Namespace(names=["P/weekly"], list=False, init="P/validation/01_pdf", output=None))
    plan = report.planned("P/weekly.toml", [])
    assert [s.title for s in plan.sections] == ["Standings", "totality"] and plan.sources[0].address == "P/validation/01_pdf"
    assert report.recipes("P") == ["P/weekly.toml"]
