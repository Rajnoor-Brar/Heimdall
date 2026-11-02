"""runner/report.py (P4–P6; V207, V209–V211): a report's sources and recipe resolved into sections of
figures and statistics, the default recipe, both layouts, the ways in (a folder's report.toml, a recipe, an errand file's
[report] and its template), where each is built, what it draws for itself (resolved here, drawn by the build:
tests/integration/test_report_draw.py), --list and --init. Every tree is tmp_path's: HEIMDALL_RESULTS, HEIMDALL_RECORDS,
HEIMDALL_CONFIGS and HEIMDALL_REPORTS."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from pathlib import Path

import pytest

from runner import cli, report
from runner.errors import HeimdallError

DOCUMENT = """[source]
config = "P/study"
configuration = "{label}"
label = "{label}"
title = "{label}"
errand = "validation"
assignment = "P"
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
{sets}
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
           objects=("d01-x01-y01", "d02-x01-y01", "d10-x01-y01"), draw=("totality",), errand="validation", assignment="P",
           sets=()):
    """A configuration's result folder: its document (`sets`: [plot].sets of its own, point A each), its points'
    YODAs, its totality pages (mpl) and their numbers."""
    where = results / assignment / errand / name
    (where / "points").mkdir(parents=True)
    tables = "".join(f'\n[plot.sets.{s}]\npoints = ["A"]\n' for s in ("totality", *sets)) if sets else ""
    text = DOCUMENT.format(label=label, folder=name, events=events, complete=str(complete).lower(),
                           draw="[" + ", ".join(f'"{s}"' for s in draw) + "]", sets=tables)
    (where / "plot.toml").write_text(text.replace('"validation"', f'"{errand}"').replace('"P"', f'"{assignment}"')
                                     .replace("P/validation/", f"{assignment}/{errand}/"), encoding="utf-8")
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
    for var in ("HEIMDALL_RESULTS", "HEIMDALL_RECORDS", "HEIMDALL_CONFIGS", "HEIMDALL_REPORTS"):
        monkeypatch.setenv(var, str(tmp_path / var.removeprefix("HEIMDALL_").lower()))
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
    with pytest.raises(HeimdallError, match="no result folder P/validation/01_pfd") as error:
        report.sources(["P/validation/01_pfd"], "here")
    assert "01_pdf" in str(error.value.hint)


def test_a_source_says_where_it_came_from(trees):
    first, second = report.sources(["P/validation"], "here")
    facts = first.facts()
    assert facts["configuration"] == "pdf" and facts["heimdall"] == "0123456789ab" and facts["events"] == "10M"
    assert (facts["points"], facts["complete"], facts["incomplete"]) == (2, 2, [])
    assert facts["against"] == "each page's first curve"                     # the document maps no data
    assert second.facts()["incomplete"] == ["B"] and first.label("events") == "10M" and first.label("folder") == "pdf"


def test_a_tagged_source_names_its_tag(trees):
    """V223: a source's facts carry its document's [source].tag, and --list and the front pages show it."""
    document = trees / "results" / "P" / "validation" / "01_pdf" / "plot.toml"
    document.write_text(document.read_text(encoding="utf-8").replace('serial = 1\n', 'serial = 1\ntag = "nlo_v2"\n'),
                        encoding="utf-8")
    first, second = report.sources(["P/validation"], "here")
    assert (first.facts()["tag"], second.facts()["tag"]) == ("nlo_v2", "")
    plan = report.planned("P/validation", [])
    listed = report.listing(plan)
    assert any(line.startswith("  source P/validation/01_pdf: pdf [nlo_v2], 2 of 2") for line in listed)
    assert any(line.startswith("  source P/validation/02_events: events, ") for line in listed)
    assert r"\hdSmall\color{hdmuted} tag nlo\_v2" in "\n".join(report._front(plan))


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
    assert plan.left == ["Tools: no source has a record of its points' tools",
                         "Pages: few: no source has few drawn, or a page of it to draw"]          # nor a set few to draw
    assert "  left out: Pages: few: no source has few drawn, or a page of it to draw" in report.listing(plan)




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
    with pytest.raises(HeimdallError, match="pagez") as error:
        report.planned("P/typo.toml", ["P/validation/01_pdf"])
    assert "pages" in str(error.value.hint)
    recipe(trees, "two", '[report]\n\n[[report.section]]\ntitle = "a"\npages = ["*"]\nstats = ["top5"]\n')
    with pytest.raises(HeimdallError, match="one of pages"):
        report.planned("P/two.toml", ["P/validation/01_pdf"])
    recipe(trees, "stat", '[report]\n\n[[report.section]]\ntitle = "a"\nstats = ["chi2_ndf:rankin"]\n')
    with pytest.raises(HeimdallError, match="no section 'chi2_ndf:rankin'"):
        report.planned("P/stat.toml", ["P/validation/01_pdf"])
    recipe(trees, "look", '[report]\n\n[[report.section]]\ntitle = "a"\npages = ["*"]\nplot = { normalize = "area" }\n')
    with pytest.raises(HeimdallError, match="normalize"):
        report.planned("P/look.toml", ["P/validation/01_pdf"])
    recipe(trees, "toolish", '[report]\n\n[[report.section]]\ntitle = "a"\ntools = ["*"]\nplot = { normalise = "area" }\n')
    with pytest.raises(HeimdallError, match="plot is a pages, stats or bars section's"):
        report.planned("P/toolish.toml", ["P/validation/01_pdf"])
    recipe(trees, "old", '[report]\n\n[[section]]\ntitle = "a"\npages = ["*"]\n')            # P2's form
    with pytest.raises(HeimdallError, match=r"a recipe has \[report\] alone, not \[section\]"):
        report.planned("P/old.toml", ["P/validation/01_pdf"])
    with pytest.raises(HeimdallError, match="no recipe P/none.toml"):
        report.planned("P/none.toml", ["P/validation/01_pdf"])
    with pytest.raises(HeimdallError, match="no result folder P/weekly"):              # no .toml: a source, always
        report.planned("P/weekly", [])


def test_what_no_document_can_draw_is_refused_naming_what_it_has(trees):
    recipe(trees, "few", '[report]\n\n[[report.section]]\ntitle = "a"\nset = "few"\npages = ["*"]\n\n'
                         '[[report.section]]\ntitle = "b"\nset = "few"\nstats = ["top5"]\n')
    with pytest.raises(HeimdallError, match="has no set few drawn, and its plot document no set few to draw") as error:
        report.planned("P/few.toml", ["P/validation/01_pdf"])
    assert error.value.hint == "drawn there: totality; its sets: totality; optional = true passes it over"
    recipe(trees, "numbers", '[report]\n\n[[report.section]]\ntitle = "b"\nset = "few"\nstats = ["top5"]\n')
    with pytest.raises(HeimdallError, match="has no set few measured, and its plot document no set few to draw"):
        report.planned("P/numbers.toml", ["P/validation/01_pdf"])
    recipe(trees, "events", '[report]\n\n[[report.section]]\ntitle = "a"\npages = ["d01-*"]\nlayout = "sources"\nlabel = "events"\n')
    with pytest.raises(HeimdallError, match="two sources are labelled 10M"):
        report.planned("P/events.toml", ["P/validation"])


def test_what_a_source_has_not_drawn_is_drawn_for_the_report(trees):
    """P6: a set its document has but did not draw, numbers it did not measure, pages drawn as PNG alone and a
    section's plot keys are drawn for the report by its build, one drawing per source and look, into the report's
    cache; --list says which and why. Until drawn, a grid waits (a figure with no file) and so do its numbers."""
    folder(trees / "results", "03_few", "few", 1_000_000, sets=("few",))
    recipe(trees, "drawn", '[report]\n\n[[report.section]]\ntitle = "a"\nset = "few"\npages = ["*"]\n\n'
                           '[[report.section]]\ntitle = "b"\nset = "few"\nstats = ["top5"]\n\n'
                           '[[report.section]]\ntitle = "c"\npages = ["d01-*"]\nplot = { normalise = "area" }\n\n'
                           '[[report.section]]\ntitle = "d"\nbars = ["*"]\nplot = { normalise = "area" }\n\n'
                           '[[report.section]]\ntitle = "e"\npages = ["d01-*"]\n\n'
                           '[[report.section]]\ntitle = "f"\nset = "none"\npages = ["*"]\noptional = true\n')
    plan = report.planned("P/drawn.toml", ["P/validation/03_few"])
    assert [s.title for s in plan.sections] == ["a", "b", "c", "d", "e"]
    assert plan.left == ["f: no source has none drawn, or a page of it to draw"]
    own, area = plan.drawings
    assert (own.look, own.sets, own.measured) == ({}, {"few": "not drawn there"}, {"few": "not measured there"})
    assert area.look == {"normalise": "area"} and area.sets == area.measured == {"totality": "its section's plot keys"}
    a, b, c, d, e = plan.sections
    assert [(f.page, f.file, f.why) for g in a.grids for f in g.figures] == [("*", None, "not drawn there")]
    assert [p.csv for p in b.parts] == [None] and [(x.csv, x.look) for x in d.bars] == [(None, True)]
    assert c.waiting() and not e.waiting() and len(plan.drawn()) == 4                 # e: copied, as drawn there
    said = report.listing(plan)
    assert "  drawn for the report: P/validation/03_few: pages of few (not drawn there); numbers of few (not measured there)" in said
    assert ('  drawn for the report: P/validation/03_few with normalise = "area" over its [plot]: pages of totality '
            "(its section's plot keys); numbers of totality (its section's plot keys)") in said
    assert "  1 a: 0 figure(s) in 0 grid(s), the pages of P/validation/03_few drawn for the report" in said
    assert report.drawings_root(plan) == Path(os.environ["HEIMDALL_CACHE"]) / "P" / "reports" / "validation" / "03_few" / ".drawn"
    for page in (trees / "results" / "P" / "validation" / "03_few" / "plots").rglob("*.pdf"):
        page.unlink()                                                                  # drawn there as PNG alone
    plan = report.planned("P/validation/03_few", [])
    pages = next(s for s in plan.sections if s.title == "Pages: totality")
    assert [f.why for g in pages.grids for f in g.figures] == ["drawn there as PNG alone"]
    for yoda in (trees / "results" / "P" / "validation" / "03_few" / "points").rglob("*.yoda"):
        yoda.unlink()                                                                  # nothing to draw from: as it is
    plan = report.planned("P/validation/03_few", [])
    pages = next(s for s in plan.sections if s.title == "Pages: totality")
    assert not plan.drawings and {f.file.suffix for g in pages.grids for f in g.figures} == {".png"}


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
    folder(trees / "results", "01_pdf", "pdf", 1_000_000, errand="other")
    assert report.planned("P/validation/01_pdf", ["P/other/01_pdf"]).out == reports / "P"          # two runs': P's
    folder(trees / "results", "01_pdf", "pdf", 1_000_000, assignment="Q")
    with pytest.raises(HeimdallError, match=r"several assignments \(P, Q\)") as error:
        report.planned("P/validation/01_pdf", ["Q/validation/01_pdf"])
    assert "-o DIR" in str(error.value.hint)
    elsewhere = trees / "elsewhere"
    assert report.planned("P/validation/01_pdf", ["Q/validation/01_pdf"], elsewhere).out == elsewhere
    recipe(trees, "out", '[report]\noutput = "P/weekly"\nfrom = ["P/validation/01_pdf", "Q/validation/01_pdf"]\n')
    assert report.planned("P/out.toml", []).out == reports / "P" / "weekly"
    lifted = trees / "lifted"
    shutil.copytree(trees / "results" / "P" / "validation" / "01_pdf", lifted)
    with pytest.raises(HeimdallError, match="is not under results/"):
        report.planned(str(lifted), [])


def test_a_document_or_title_in_the_names_before_i112_is_refused(trees):
    """a plot document's [source].project and .run, and a title's {project} and {run}, are refused, each
    naming heimdall migrate --names."""
    from runner import plotdoc
    document = trees / "results" / "P" / "validation" / "01_pdf" / "plot.toml"
    text = document.read_text(encoding="utf-8")
    assert 'errand = "validation"' in text and plotdoc.load(document)[0].name == "validation"
    for old in ('run = "validation"\nassignment = "P"', 'errand = "validation"\nproject = "P"'):
        document.write_text(text.replace('errand = "validation"\nassignment = "P"', old), encoding="utf-8")
        with pytest.raises(HeimdallError, match=r"\[source\]\.(run|project) is now \[source\]\.(errand|assignment)") as caught:
            plotdoc.load(document)
        assert caught.value.hint == "heimdall migrate --names rewrites it"
    document.write_text(text, encoding="utf-8")
    recipe(trees, "old", '[report]\ntitle = "{project}: {run}"\n\n[[report.section]]\ntitle = "a"\npages = ["*"]\n')
    with pytest.raises(HeimdallError, match=r"\{project\} is now \{assignment\}") as caught:
        report.planned("P/old.toml", ["P/validation/01_pdf"])
    assert "migrate --names" in caught.value.hint


def test_a_folder_reads_its_own_report_toml(trees):
    where = trees / "results" / "P" / "validation" / "01_pdf"
    (where / report.RECIPE).write_text('[report]\ntitle = "{errand}: {title}"\n\n[[report.section]]\ntitle = "Spectra"\n'
                                       'pages = ["d01-*"]\n', encoding="utf-8")
    plan = report.planned("P/validation/01_pdf", [])
    assert [s.title for s in plan.sections] == ["Spectra"] and plan.recipe == where / report.RECIPE
    assert plan.title == "validation: pdf" and plan.out == trees / "reports" / "P" / "validation" / "01_pdf"
    assert report.planned(str(where / report.RECIPE), []).sources[0].address == "P/validation/01_pdf"   # named itself
    both = report.planned("P/validation", [])                    # several: the default, not one folder's recipe
    assert [s.title for s in both.sections] == ["Standings", "Pages: totality"]               # Tools: no records
    recipe(trees, "weekly", '[report]\ntitle = "Weekly {configuration}"\n\n[[report.section]]\ntitle = "All"\npages = ["*"]\n')
    over = report.planned("P/weekly.toml", ["P/validation/01_pdf"])            # a recipe over it: the recipe's
    assert [s.title for s in over.sections] == ["All"] and over.title == "Weekly pdf"
    assert report.planned("P/weekly.toml", ["P/validation"]).title == "Weekly pdf, events"


@pytest.fixture
def study(trees):
    """A run TOML of the fixture's (Demo/validation) with a [report] naming a template, in tmp_path's configs/."""
    demo = trees / "configs" / "Demo"
    shutil.copytree(Path(os.environ["HEIMDALL_WORK"]) / "configs" / "Demo", demo)
    (demo / "weekly.toml").write_text('[report]\ntitle = "Weekly"\nsubtitle = "for the group"\nfrom = ["P/validation/01_pdf"]\n'
                                      'output = "Demo/weekly"\n\n[[report.section]]\ntitle = "Standings"\nstats = ["top5"]\n',
                                      encoding="utf-8")
    text = (demo / "validation.toml").read_text(encoding="utf-8")
    (demo / "study.toml").write_text(text + '\n[report]\ntemplate = "weekly"\ntitle = "{assignment} · {configuration}"\n\n'
                                     '[[report.section]]\ntitle = "Mine"\npages = ["d01-*"]\n', encoding="utf-8")
    return demo


def test_a_run_tomls_report_lays_its_own_over_its_template(study):
    plan = report.planned("Demo/study.toml", ["P/validation/01_pdf"])
    assert [s.title for s in plan.sections] == ["Standings", "Mine"]                        # the template's first
    assert plan.title == "P · pdf" and plan.subtitle == "for the group"                  # its keys over the template's
    assert plan.out.parts[-3:] == ("P", "validation", "01_pdf")              # the template's output: a recipe's own
    plain = report.planned("Demo/validation.toml", ["P/validation/01_pdf"])         # no [report]: the default
    assert [s.title for s in plain.sections] == ["Standings", "Pages: totality"]
    with pytest.raises(HeimdallError, match="name the folders"):
        report.planned("Demo/study.toml", [])


@pytest.mark.parametrize("table, message", [
    ('[report]\nfrom = ["P/validation/01_pdf"]\n', "an errand file's \\[report\\] takes no from"),
    ('[report]\noutput = "x"\n', "takes no output"),
    ('[report]\ntemplate = "nowhere"\n', "no report template 'nowhere'"),
    ('[report]\ntemplate = "study"\n', "a report's template is a recipe"),
    ('[report]\ntitel = "x"\n', "unknown key 'titel'"),
])
def test_a_run_tomls_report_is_checked_when_it_is_read(study, table, message):
    from runner import config
    text = (study / "validation.toml").read_text(encoding="utf-8")
    (study / "bad.toml").write_text(text + "\n" + table, encoding="utf-8")
    with pytest.raises(HeimdallError, match=message):
        config.load("Demo/bad")


def test_a_template_naming_itself_is_refused(study):
    from runner import config
    (study / "loop.toml").write_text('[report]\ntemplate = "loop2"\n', encoding="utf-8")
    (study / "loop2.toml").write_text('[report]\ntemplate = "loop"\n', encoding="utf-8")
    text = (study / "validation.toml").read_text(encoding="utf-8")
    (study / "round.toml").write_text(text + '\n[report]\ntemplate = "loop"\n', encoding="utf-8")
    with pytest.raises(HeimdallError, match="go round in a circle: round.toml → loop.toml → loop2.toml → loop.toml"):
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
    with pytest.raises(HeimdallError, match="there already"):
        cli.cmd_report(made)
    with pytest.raises(HeimdallError, match="name it, <A>/<E>.toml"):
        cli.cmd_report(argparse.Namespace(names=["P/weekly"], list=False, init="P/validation/01_pdf", output=None))
    plan = report.planned("P/weekly.toml", [])
    assert [s.title for s in plan.sections] == ["Standings", "totality"] and plan.sources[0].address == "P/validation/01_pdf"
    assert report.recipes("P") == ["P/weekly.toml"]
    assert "# accent   = \"#2a78d6\"" in (trees / "configs" / "P" / "weekly.toml").read_text(encoding="utf-8")


PYTHIA = """! from {base}
Beams:eCM = 13000.
PDF:pSet = {pdf}
! point {point}
Random:seed = {seed}
"""

SHERPA = """# point {point}
BEAMS: [2212, 2212]
PROCESSES:
- 93 93 -> 93 93:
    Order: {{QCD: {order}, EW: 0}}
PDF_SET: {pdf}
"""


def recorded(trees, name: str = "01_pdf", context: bool = True, points=("A", "B")) -> Path:
    """A configuration's records: each point complete, its cards and its context.toml as a run leaves them."""
    record = trees / "records" / "P" / "validation" / name
    for k, (point, identity, pdf) in enumerate(zip(("A", "B"), ("one", "two"), ("NNPDF", "CT18"))):
        (record / "points" / point).mkdir(parents=True, exist_ok=True)
        (record / "points" / point / ".complete").write_text(identity + "\n", encoding="utf-8")
        if point not in points:
            continue
        logs = record / "logs" / point
        (logs / "cards").mkdir(parents=True)
        (logs / "cards" / "pythia.cmnd").write_text(PYTHIA.format(base="/w/configs/P/base.cmnd", pdf=pdf, point=point, seed=k + 1),
                                                    encoding="utf-8")
        (logs / "cards" / "pythia.point.cmnd").write_text(f"PDF:pSet = {pdf}\n", encoding="utf-8")
        (logs / "cards" / "sherpa.yaml").write_text(SHERPA.format(point=point, order=2 + k, pdf=pdf), encoding="utf-8")
        if context:
            (logs / "context.toml").write_text(
                '[tools.pythia]\ntool = "pythia"\ncard = "/elsewhere/cards/pythia.cmnd"\ncard_parts = ["/w/base.cmnd"]\n\n'
                '[tools.sherpa]\ntool = "sherpa"\ncard = "/elsewhere/cards/sherpa.yaml"\n\n'
                f'[tools.rivet]\ntool = "rivet"\nanalyses = ["MC_JETS"]\nplugin_path = "/w/build/Rivet"\nrunner = "{point}"\n\n'
                '[tools.yd2rt]\ntool = "yd2rt"\n', encoding="utf-8")
    return record


def test_a_tools_card_is_its_baseline_and_what_varied_point_by_point(trees):
    recorded(trees)
    (source,) = report.sources(["P/validation/01_pdf"], "here")
    pythia, rivet, sherpa = report.configured(source, ["*"], [], "here")                      # yd2rt: given nothing
    assert (pythia.tag, pythia.ext) == ("pythia", ".cmnd")
    assert pythia.baseline == ["! from /w/configs/P/base.cmnd", "Beams:eCM = 13000."]      # read by name from cards/
    assert pythia.varied == [("A", "PDF A", ["PDF:pSet = NNPDF", "Random:seed = 1"]),          # comments left out
                             ("B", "PDF B", ["PDF:pSet = CT18", "Random:seed = 2"])]
    assert pythia.table() == (["PDF:pSet", "Random:seed"], [{"PDF:pSet": "NNPDF", "Random:seed": "1"},
                                                             {"PDF:pSet": "CT18", "Random:seed": "2"}])
    assert rivet.ext == "" and rivet.options == {"analyses": ["MC_JETS"], "plugin_path": "/w/build/Rivet"}
    assert rivet.table() == (["runner"], [{"runner": '"A"'}, {"runner": '"B"'}])          # an option that varied
    assert sherpa.baseline == ["BEAMS: [2212, 2212]", "PROCESSES:", "- 93 93 -> 93 93:"]
    assert sherpa.table() is None                                                          # a nested line varied
    assert sherpa.varied[0][2] == ["    Order: {QCD: 2, EW: 0}", "PDF_SET: NNPDF"]
    (hidden,) = report.configured(source, ["pythia"], ["Random:*"], "here")
    assert hidden.table() == (["PDF:pSet"], [{"PDF:pSet": "NNPDF"}, {"PDF:pSet": "CT18"}])
    (nothing,) = report.configured(source, ["yd2rt"], [], "here")                               # named: shown, and said
    assert nothing.notes == ["given no card and no options"]
    with pytest.raises(HeimdallError, match="have no tool 'pythai'") as error:
        report.configured(source, ["pythai"], [], "here")
    assert "pythia" in str(error.value.hint)


def test_a_point_without_a_record_is_said_and_an_older_record_read_from_its_cards(trees):
    recorded(trees, points=("A",))
    (source,) = report.sources(["P/validation/01_pdf"], "here")
    (pythia,) = report.configured(source, ["pythia"], [], "here")
    assert [p for p, _, _ in pythia.varied] == ["A"] and pythia.notes == ["1 complete point(s) with no record, not shown: B"]
    folder(trees / "results", "03_old", "old", 1_000_000)
    recorded(trees, "03_old", context=False)
    (old,) = report.sources(["P/validation/03_old"], "here")
    assert [g.tag for g in report.configured(old, ["*"], [], "here")] == ["pythia", "sherpa"]     # cards/<tag>.*, no .point.
    with pytest.raises(HeimdallError, match="no record of its points' tools"):
        report.configured(report.sources(["P/validation/02_events"], "here")[0], ["*"], [], "here")


def test_the_default_report_begins_with_its_tools_and_tools_chooses_them(trees):
    recorded(trees)
    plan = report.planned("P/validation/01_pdf", [])
    assert [s.title for s in plan.sections] == ["Tools", "Standings", "Pages: totality"]           # what was run first
    assert [g.tag for g in plan.sections[0].given] == ["pythia", "rivet", "sherpa"]
    assert "  1 Tools: tools of P/validation/01_pdf: pythia (2 point(s), 2 card line(s) alike, 2 varied key(s)), rivet (2 " \
           "point(s), 2 option(s) alike, 1 varied key(s)), sherpa (2 point(s), 3 card line(s) alike, a list of what varied)" \
           in report.listing(plan)
    where = trees / "results" / "P" / "validation" / "01_pdf"
    (where / report.RECIPE).write_text('[report]\ntools = []\n', encoding="utf-8")       # sections the default's
    assert [s.title for s in report.planned("P/validation/01_pdf", []).sections] == ["Standings", "Pages: totality"]
    (where / report.RECIPE).write_text('[report]\ntools = ["sh*"]\n', encoding="utf-8")
    assert [g.tag for g in report.planned("P/validation/01_pdf", []).sections[0].given] == ["sherpa"]
    recipe(trees, "bad", '[report]\n\n[[report.section]]\ntitle = "a"\npages = ["*"]\nhide = ["x"]\n')
    with pytest.raises(HeimdallError, match="hide is a tools section's"):
        report.planned("P/bad.toml", ["P/validation/01_pdf"])


GENERATORS = """[source]
config = "P/study"
configuration = "generator_pdf"
errand = "zeus"
assignment = "P"
folder = "P/zeus/01_generator_pdf"

[axes]
vary = ["generator", "pdf"]
plot_points = ["generator"]
combine = []
fixed = { generator = "#1", beams = "#1", pdf = "#1" }

[quantities.generator]
points = [
  { tag = "py8", value = "pythia", label = "Pythia 8.318" },
  { tag = "sh3", value = "sherpa", label = "Sherpa 3.0.5" },
]

[quantities.beams]
points = [{ tag = "ep", value = [-11, 2212], label = "$e^{+}p$" }]

[quantities.pdf]
points = [
  { tag = "NNPDF23", value = "NNPDF23_nlo", label = "NNPDF 2.3" },
  { tag = "NNPDF23_lo", value = "NNPDF23_lo", label = "NNPDF 2.3 LO" },
  { tag = "CT18", value = "CT18NLO", label = "CT18" },
]

[plot]
backend = ["mpl"]

[plot.sets.few]
pages = []
curves = [{ generator = "py8", pdf = ["NNPDF23_lo", "CT18"] }, { generator = "sh3", pdf = "NNPDF23" }]

[plot.sets.pythia]
pages = { generator = "py8" }
curves = { pdf = "all" }

[members.py8_NNPDF23]
index = 0
choice = { generator = 0, pdf = 0 }
values = { generator = 0, pdf = 0 }
yoda = "points/py8_NNPDF23/run.yoda"
identity = "one"
complete = true
events = 1000
"""


def test_a_sets_sub_header_names_its_axes_and_what_is_fixed_and_a_cell_its_labels(trees):
    """a set's pages and curves along its axes, as their labels, and the quantities held fixed; a page cell
    read as its tags' labels, the longest tag first."""
    where = trees / "results" / "P" / "zeus" / "01_generator_pdf"
    where.mkdir(parents=True)
    (where / "plot.toml").write_text(GENERATORS, encoding="utf-8")
    (source,) = report.sources(["P/zeus/01_generator_pdf"], "here")
    fixed = ("Fixed", ["beams: $e^{+}p$"])
    assert report.set_head(source, "few").facts == [
        ("Pages", ["a page per object, every curve on it"]),
        ("Curves", ["generator: Pythia 8.318 · pdf: NNPDF 2.3 LO, CT18", "generator: Sherpa 3.0.5 · pdf: NNPDF 2.3"]), fixed]
    assert report.set_head(source, "pythia").facts == [("Pages", ["generator: Pythia 8.318"]),
                                                       ("Curves", ["pdf: NNPDF 2.3, NNPDF 2.3 LO, CT18"]), fixed]
    assert report.set_head(source, "totality").facts == [("Pages", ["generator: Pythia 8.318, Sherpa 3.0.5"]),
                                                         ("Curves", ["pdf: NNPDF 2.3, NNPDF 2.3 LO, CT18"]), fixed]
    assert report.set_head(source, "pythia", {"sets": {"pythia": {"pages": {"generator": "py8"}, "curves": {"pdf": "!CT18"}}}}) \
        .facts[1] == ("Curves", ["pdf: all but CT18"])                       # a section's plot keys over the document's
    assert report.cell_label(source.doc, "py8") == "Pythia 8.318"
    assert report.cell_label(source.doc, "NNPDF23_lo_py8") == "NNPDF 2.3 LO, Pythia 8.318"
    assert report.cell_label(source.doc, "18x275") == "18x275"
    plan = report.planned("P/validation/01_pdf", [])
    first, second = plan.sections[1].grids
    assert first.head.set == "totality" and first.head.address == "P/validation/01_pdf" and second.head is None
    assert first.head.facts == [("Pages", ["a page per object, every curve on it"]), ("Curves", ["pdf: PDF A, PDF B"])]
    assert (first.cell, second.cell) == ("18x275", "27x920")


def test_a_recipes_look_is_kept_and_checked(trees):
    """[report]'s look keys on the plan; a bad one refused."""
    assert report.planned("P/validation/01_pdf", []).look == report.Look()
    recipe(trees, "look", '[report]\nfont = "serif"\nsize = 10.5\naccent = "#d62728"\ncolumns = 3\ncontents = false\n')
    assert report.planned("P/look.toml", ["P/validation/01_pdf"]).look == report.Look("serif", 10.5, "#d62728", False, 3)
    for line, message in (('accent = "red"', "accent is a colour as #rrggbb"), ("size = 13", "size is at most 12"),
                          ("columns = 0", "columns"), ('font = "mono"', "mono"), ("size = 7", "size")):
        recipe(trees, "bad", f"[report]\n{line}\n")
        with pytest.raises(HeimdallError, match=message):
            report.planned("P/bad.toml", ["P/validation/01_pdf"])


def test_a_cards_lines_are_highlighted():
    """keys, = and :, numbers, words and comments marked for Verbatim's commandchars; \\, { and } escaped."""
    assert report.highlight("Beams:eCM = 318. ! the energy") == r"\hdK{Beams:eCM} \hdP{=} \hdN{318.} {\hdC ! the energy}"
    assert report.highlight("HadronLevel:all = off") == r"\hdK{HadronLevel:all} \hdP{=} \hdB{off}"
    assert report.highlight("    Order: {QCD: 2}") == r"    \hdK{Order}\hdP{:} \hdLB{}QCD: 2\hdRB{}"
    assert report.highlight("- 93 93 -> 93 93:") == "- 93 93 -> 93 93:"
    assert report.highlight("set /Herwig/Gen:NumberOfEvents 1000") == r"\hdB{set} /Herwig/Gen:NumberOfEvents \hdN{1000}"
    assert report.highlight(r"# a \path {x}") == r"{\hdC # a \hdBS{}path \hdLB{}x\hdRB{}}"
    assert report.highlight('PDF:pSet = "a ! b" # yaml') == r'\hdK{PDF:pSet} \hdP{=} "a ! b" {\hdC # yaml}'


def test_typeset_takes_any_colour_and_keeps_a_short_table_whole():
    """a cell's ink or fill as Matplotlib names it ("white"); a table of a few rows asks for room for all of
    them on its page, a long one for its head and a few rows."""
    typeset, paper = report._typeset(), report.statstable.bars().paper
    assert [typeset._hex(c) for c in ("white", "#2a78d6", (1.0, 0.5, 0.0))] == ["FFFFFF", "2A78D6", "FF8000"]
    short = paper.Table("t", "a table", ["a"], [paper.Row(f"r{k}", [paper.Cell("1")]) for k in range(5)])
    long = paper.Table("t", "a table", ["a"], [paper.Row(f"r{k}", [paper.Cell("1")]) for k in range(40)])
    assert typeset.keep(short) == 24 + 3 * typeset.ROW + 5 * typeset.ROW
    assert typeset.keep(long) == 24 + 3 * typeset.ROW + typeset.HEAD_ROWS * typeset.ROW


def test_index_titles_show_labels_as_text():
    """index.html's titles and a set's facts: a label's $…$ as Unicode, as the statistics' own pages read it."""
    assert report.shown_text("Inclusive $k_T$ jets") == "Inclusive kT jets"
    assert report.shown_text("$e^{+}p$ at $\\sqrt{s}$ = 318 GeV") == "e+p at √s = 318 GeV"
    assert report.shown_text("a & b") == "a & b"


def test_what_was_run_comes_first_and_how_the_numbers_are_made_after_it(trees):
    """a recipe's tools sections first, in its order, then How the numbers are made, then its results in its
    order; context = "last" puts them after; method = false leaves the method out."""
    recorded(trees)
    body = ('\n[[report.section]]\ntitle = "Spectra"\npages = ["d01-*"]\n\n[[report.section]]\ntitle = "Numbers"\n'
            'stats = ["chi2_ndf"]\n\n[[report.section]]\ntitle = "Cards"\ntools = ["pythia"]\n\n'
            '[[report.section]]\ntitle = "Options"\ntools = ["rivet"]\n')
    recipe(trees, "order", '[report]\nfrom = ["P/validation/01_pdf"]\n' + body)
    plan = report.planned("P/order.toml", [])
    assert [s.title for s in plan.sections] == ["Cards", "Options", "Spectra", "Numbers"] and plan.method
    listed = report.listing(plan)
    assert "  How the numbers are made (unnumbered): each statistic's formula and meaning, after what was run, " \
           "before the results" in listed and listed[-1].startswith("  How the numbers are made")
    recipe(trees, "last", '[report]\nfrom = ["P/validation/01_pdf"]\ncontext = "last"\nmethod = false\n' + body)
    plan = report.planned("P/last.toml", [])
    assert [s.title for s in plan.sections] == ["Spectra", "Numbers", "Cards", "Options"] and not plan.method
    assert not any("How the numbers are made" in line for line in report.listing(plan))
    recipe(trees, "bad", '[report]\ncontext = "middle"\n')
    with pytest.raises(HeimdallError, match="middle"):
        report.planned("P/bad.toml", ["P/validation/01_pdf"])
