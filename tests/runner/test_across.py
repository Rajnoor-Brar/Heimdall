"""The runs of a run TOML together (V169) with their tags and ignored quantities (V224): `@tag` an axis
when a run is tagged, the runs' tags in what makes two points the same, `[from].ignore` and its refusals, and
`[plot.across_from]` written into the document's `[from]`. The runs' plot documents are written here by hand, as a
run writes them (`plotdoc.dumps`), so nothing runs and no YODA is read."""

from __future__ import annotations

import argparse
import shutil

import pytest
import tomli_w

from helpers import parse, raw
from runner import cli, plotdoc, sweep
from runner.errors import HeimdallError
from runner.paths import results_root

PDF = [{"tag": "MSTW08lo", "value": "LHAPDF6:MSTW2008lo68cl"}, {"tag": "NNPDF23lo", "value": "LHAPDF6:NNPDF23_lo_as_0130_qed"}]
GENERATOR = [{"tag": "py8", "value": "pythia", "label": "Pythia 8"}, {"tag": "hw7", "value": "herwig", "label": "Herwig 7"}]


def folder_of(name: str):
    """results/Demo/<name>/, empty."""
    where = results_root() / "Demo" / name
    shutil.rmtree(where, ignore_errors=True)
    where.mkdir(parents=True)
    return where


def a_run(where, folder: str, *, tag: str | None = None, generator: list[int] = (0,), swept: bool = False,
          events: int = 1000, configuration: str = "one") -> None:
    """<where>/<folder>/plot.toml: a run's plot document, its points pdf × the generators given (indices of
    GENERATOR), every one complete; generator a swept axis when `swept`, else fixed (in its values alone)."""
    members = {}
    for g in generator:
        for p, row in enumerate(PDF):
            name = f"{GENERATOR[g]['tag']}_{row['tag']}" if swept else row["tag"]
            choice = {"pdf": p, **({"generator": g} if swept else {})}
            members[name] = {"index": len(members) + 1, "identity": f"{folder}-{name}", "complete": True, "events": events,
                             "yoda": f"points/{name}/out.yoda", "choice": choice, "values": {"generator": g, "pdf": p}}
    document = {"source": {"config": "Demo/t", "configuration": configuration, "label": folder, "errand": where.name,
                           "assignment": "Demo", "folder": f"Demo/{where.name}/{folder}", **({"tag": tag} if tag else {})},
                "axes": {"vary": [["generator"], ["pdf"]] if swept else [["pdf"]], "plot_points": [], "combine": [],
                         "fixed": {} if swept else {"generator": f"#{generator[0] + 1}"}},
                "quantities": {"generator": {"points": GENERATOR}, "pdf": {"points": PDF}}, "members": members}
    (where / folder).mkdir(parents=True, exist_ok=True)
    (where / folder / plotdoc.FILE).write_text(plotdoc.dumps(document), encoding="utf-8")


def an_events_run(where, folder, counts: list[int], *, pdf: int = 1, tag: str | None = None, generator: int | None = 0) -> None:
    """<where>/<folder>/plot.toml: a run that sweeps the event count alone: one member for each of `counts`, the generator and
    the pdf (an index of PDF) fixed, nothing in any member's choice; `generator=None`: the Run never names it."""
    members = {}
    for count in counts:
        name = f"n{count}"
        members[name] = {"index": len(members) + 1, "identity": f"{folder}-{name}", "complete": True, "events": count,
                         "yoda": f"points/{name}/out.yoda", "choice": {},
                         "values": {**({"generator": generator} if generator is not None else {}), "pdf": pdf}}
    document = {"source": {"config": "Demo/t", "configuration": "one", "label": folder, "errand": where.name,
                           "assignment": "Demo", "folder": f"Demo/{where.name}/{folder}", **({"tag": tag} if tag else {})},
                "axes": {"vary": [], "plot_points": [], "combine": [], "fixed": {**({"generator": f"#{generator + 1}"} if generator is not None else {}), "pdf": f"#{pdf + 1}"}},
                "quantities": {"generator": {"points": GENERATOR}, "pdf": {"points": PDF}}, "members": members}
    (where / folder).mkdir(parents=True, exist_ok=True)
    (where / folder / plotdoc.FILE).write_text(plotdoc.dumps(document), encoding="utf-8")


def together(where, **wanted):
    """<where>/plot.toml, the runs together, its [from] `wanted` (none: as a run writes it), loaded."""
    document = {"source": {"config": "Demo/t", "errand": where.name, "assignment": "Demo", "level": "name"},
                "from": {"runs": ["*"], "prefer": "last", **wanted}, "plot": {}}
    (where / plotdoc.FILE).write_text(plotdoc.ACROSS_HEADER + plotdoc.dumps(document), encoding="utf-8")
    return plotdoc.load(where / plotdoc.FILE)


def cells(doc, members, table: dict) -> dict[str, list[str]]:
    """A set's page cells as set_cells makes them: cell → its curves' point names."""
    spec = sweep.set_entries({"s": table}, "[plot.across]")[0]
    return {c.key: [m.point.name for m in c.members] for c in sweep.set_cells(doc, members, spec)[0]}


def test_untagged_runs_are_as_they_were(scratch):
    """No run tagged: no @tag, each member's choice its own and @events, the same point of two runs the later's."""
    where = folder_of("untagged")
    a_run(where, "01_one")
    a_run(where, "02_one")
    doc, _, members = together(where)
    assert set(doc.quantities) == {"generator", "pdf", "@run", "@events", "@configuration"}
    assert [m.point.name for m in members] == ["02_one__MSTW08lo", "02_one__NNPDF23lo"]
    assert all(set(m.point.choice) == {"pdf", "@events"} for m in members)
    assert set(members[0].values) == {"generator", "pdf", "@run", "@events", "@configuration"}
    assert doc.source["shadowed"] == {"01_one__MSTW08lo": "02_one__MSTW08lo", "01_one__NNPDF23lo": "02_one__NNPDF23lo"}
    assert doc.configuration.sweeps == [["pdf"], ["@events"]]
    assert cells(doc, members, {"curves": {"pdf": "all"}}) == {"": ["02_one__MSTW08lo", "02_one__NNPDF23lo"]}


def test_runs_of_different_tags_are_kept_apart_a_page_each(scratch):
    """@tag: each run's tag, an untagged run's "" (labelled and named untagged); an axis, so a set that does not name
    it pages by it; points of different tags never shadow each other."""
    where = folder_of("tags")
    a_run(where, "01_one", tag="lo")
    a_run(where, "02_one", tag="nlo")
    a_run(where, "03_one")
    doc, _, members = together(where)
    tag = doc.quantities["@tag"]
    assert (tag.values, tag.tags, tag.labels) == (["lo", "nlo", ""], ["lo", "nlo", "untagged"], ["lo", "nlo", "untagged"])
    assert len(members) == 6 and doc.source["shadowed"] == {}
    assert members[0].point.choice == {"pdf": 0, "@events": 0, "@tag": 0} and members[4].values["@tag"] == 2
    assert cells(doc, members, {"curves": {"pdf": "all"}}) == {
        "lo": ["01_one__MSTW08lo", "01_one__NNPDF23lo"], "nlo": ["02_one__MSTW08lo", "02_one__NNPDF23lo"],
        "untagged": ["03_one__MSTW08lo", "03_one__NNPDF23lo"]}
    assert cells(doc, members, {"pages": {"pdf": "all"}, "curves": {"@tag": ["nlo", "untagged"]}}) == {
        "MSTW08lo": ["02_one__MSTW08lo", "03_one__MSTW08lo"], "NNPDF23lo": ["02_one__NNPDF23lo", "03_one__NNPDF23lo"]}


def test_reruns_under_one_tag_shadow_each_other(scratch):
    """Two runs of one tag: the later's points; a third under another tag stays."""
    where = folder_of("reruns")
    a_run(where, "01_one", tag="nlo")
    a_run(where, "02_one", tag="nlo")
    a_run(where, "03_one", tag="lo")
    doc, _, members = together(where)
    assert [m.point.name for m in members] == ["02_one__MSTW08lo", "02_one__NNPDF23lo", "03_one__MSTW08lo", "03_one__NNPDF23lo"]
    assert doc.source["shadowed"] == {"01_one__MSTW08lo": "02_one__MSTW08lo", "01_one__NNPDF23lo": "02_one__NNPDF23lo"}
    assert len(together(where, prefer="all")[2]) == 6


def test_an_ignored_quantity_is_no_axis(scratch):
    """Two tagged runs that differ only in their generator (swept, one value each): without ignore a page per
    generator; ignored, one page per pdf with a curve per tag, the generator kept in each member's values."""
    where = folder_of("ignored")
    a_run(where, "01_one", tag="py", generator=[0], swept=True)
    a_run(where, "02_one", tag="hw", generator=[1], swept=True)
    table = {"pages": {"pdf": "all"}, "curves": {"@tag": "all"}}
    doc, _, members = together(where)
    assert sorted(cells(doc, members, table)) == ["MSTW08lo_hw7", "MSTW08lo_py8", "NNPDF23lo_hw7", "NNPDF23lo_py8"]
    doc, _, members = together(where, ignore=["generator"])
    assert cells(doc, members, table) == {"MSTW08lo": ["01_one__py8_MSTW08lo", "02_one__hw7_MSTW08lo"],
                                          "NNPDF23lo": ["01_one__py8_NNPDF23lo", "02_one__hw7_NNPDF23lo"]}
    assert all("generator" not in m.point.choice for m in members) and [m.values["generator"] for m in members] == [0, 0, 1, 1]
    assert ["generator"] not in doc.configuration.sweeps


def test_an_ignored_quantity_leaves_what_makes_two_points_the_same(scratch):
    """Untagged runs of two generators (fixed): apart as they were; with the generator ignored the later stands for
    both, and @events ignored lets runs of other event counts stand for each other too."""
    where = folder_of("merged")
    a_run(where, "01_one", generator=[0])
    a_run(where, "02_one", generator=[1], events=2000)
    assert len(together(where)[2]) == 4
    assert len(together(where, ignore=["generator"])[2]) == 4                 # their event counts still differ
    doc, _, members = together(where, ignore=["generator", "@events"])
    assert [m.point.name for m in members] == ["02_one__MSTW08lo", "02_one__NNPDF23lo"]
    assert all(set(m.point.choice) == {"pdf"} for m in members) and members[0].values["@events"] == 1


def test_an_ignored_quantity_holding_several_values_in_a_run_is_refused(scratch):
    where = folder_of("several")
    a_run(where, "01_one", tag="py", generator=[0])
    a_run(where, "02_one", tag="both", generator=[0, 1], swept=True)
    with pytest.raises(HeimdallError, match="ignore names generator, which takes 2 values in the Run 02_one: py8, hw7") as error:
        together(where, ignore=["generator"])
    assert "[from].ignore" in str(error.value.where)


def test_an_unknown_name_in_ignore_and_a_bad_from_are_refused(scratch):
    where = folder_of("unknown")
    a_run(where, "01_one")
    with pytest.raises(HeimdallError, match="ignore names 'generater', which is no quantity of the Runs") as error:
        together(where, ignore=["generater"])
    assert "did you mean 'generator'" in error.value.hint
    with pytest.raises(HeimdallError, match="which is no quantity"):
        together(where, ignore=["@run"])
    with pytest.raises(HeimdallError, match="prefer must be one of last, all"):
        together(where, prefer="first")
    with pytest.raises(HeimdallError, match="unknown key 'ignored'") as error:
        together(where, ignored=["pdf"])
    assert "did you mean 'ignore'" in error.value.hint


def test_plot_across_from_is_checked_and_written_into_from(scratch):
    """[plot.across_from]: checked when the file is read, as [from] is; written over the defaults into the document's
    [from] when a run writes it, and by --style-sync; without the table [from] is the defaults, and a sync keeps it.
    A single run's document never holds it."""
    import tomllib
    across = {"by_tag": {"curves": {"@tag": "all"}}}
    with pytest.raises(HeimdallError, match="prefer must be one of last, all"):
        parse(raw(plot={"across": across, "across_from": {"prefer": "first"}}), scratch)
    with pytest.raises(HeimdallError, match="unknown key 'ignored'"):
        parse(raw(plot={"across": across, "across_from": {"ignored": ["pdf"]}}), scratch)
    where = folder_of("t")
    a_run(where, "01_one", tag="lo")
    plain = parse(raw(plot={"across": across}), scratch)
    target, written = plotdoc.write_across(plain)
    assert written and tomllib.loads(target.read_text(encoding="utf-8"))["from"] == {"runs": ["*"], "prefer": "last"}
    assert "across_from" not in plotdoc.across_chosen(plain)[0]
    target.unlink()
    given = {"runs": ["0*"], "ignore": ["generator"]}
    errand = parse(raw(plot={"across": across, "across_from": given}), scratch)
    assert "across_from" not in plotdoc.chosen_of(errand, errand.configuration("one"), [])[0]
    target, _ = plotdoc.write_across(errand)
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    assert data["from"] == {"runs": ["0*"], "prefer": "last", "ignore": ["generator"]} and "across_from" not in data["plot"]

    config = scratch / "synced.toml"
    args = argparse.Namespace(style_sync=str(config), set=[], plan=False, replot=False)
    config.write_text(tomli_w.dumps(raw(errand__cfgs__one__sweeps=["pdf"], plot={"across": across})), encoding="utf-8")
    assert cli.style_sync_across(args) == 0                    # no table: [from] kept
    assert tomllib.loads(target.read_text(encoding="utf-8"))["from"]["ignore"] == ["generator"]
    config.write_text(tomli_w.dumps(raw(errand__cfgs__one__sweeps=["pdf"], plot={"across": across, "across_from": {"prefer": "all"}})),
                      encoding="utf-8")
    assert cli.style_sync_across(args) == 0
    text = target.read_text(encoding="utf-8")
    assert tomllib.loads(text)["from"] == {"runs": ["*"], "prefer": "all"} and text.startswith(plotdoc.ACROSS_HEADER)


def test_a_run_tagged_untagged_and_an_untagged_run_are_told_apart(scratch):
    """An untagged run among tagged ones is "untagged"; a run really tagged so keeps its name, and the blank one's
    name and label are both "untagged_", so their curves never share a label."""
    where = folder_of("blank")
    a_run(where, "01_one", tag="untagged")
    a_run(where, "02_one")
    doc, _, _ = together(where)
    assert doc.quantities["@tag"].tags == ["untagged", "untagged_"]
    assert doc.quantities["@tag"].labels == ["untagged", "untagged_"]


def test_the_records_tag_is_the_truth_across_runs(scratch):
    """A tag given since the run's plot stage last wrote its document (heimdall run --tag with no plot stage) is
    drawn: the record's, when the record is there; else the document's [source].tag."""
    from runner import record
    from runner.paths import records_root
    where = folder_of("stale")
    a_run(where, "01_one", tag="old")
    a_run(where, "02_one", tag="lo")
    doc, _, _ = together(where)
    assert doc.quantities["@tag"].tags == ["old", "lo"]
    kept = records_root() / "Demo" / "stale" / "01_one"
    shutil.rmtree(kept.parent, ignore_errors=True)
    kept.mkdir(parents=True)
    record.write_run_tag(kept, "new")
    doc, _, _ = together(where)
    assert doc.quantities["@tag"].tags == ["new", "lo"]
    shutil.rmtree(kept.parent)


def test_a_sync_mends_a_from_in_error(scratch):
    """--style-sync reads the document as it is, so a [from] that no longer loads is replaced, not in its way."""
    import tomllib
    where = folder_of("t")
    a_run(where, "01_one", tag="lo")
    across = {"by_tag": {"curves": {"@tag": "all"}}}
    target, _ = plotdoc.write_across(parse(raw(plot={"across": across}), scratch))
    text = target.read_text(encoding="utf-8").replace('prefer = "last"', 'prefer = "first"')
    target.write_text(text, encoding="utf-8")
    with pytest.raises(HeimdallError, match="prefer"):
        plotdoc.load(target)
    config = scratch / "mended.toml"
    config.write_text(tomli_w.dumps(raw(errand__cfgs__one__sweeps=["pdf"], plot={"across": across, "across_from": {"prefer": "all"}})),
                      encoding="utf-8")
    args = argparse.Namespace(style_sync=str(config), set=[], plan=False, replot=False)
    assert cli.style_sync_across(args) == 0
    assert tomllib.loads(target.read_text(encoding="utf-8"))["from"]["prefer"] == "all"
    plotdoc.load(target)


def test_a_report_says_each_runs_ignored_value(scratch):
    """A set's sub-header names what [from].ignore left out, each run's one value: the label, then its runs."""
    from runner import report
    where = folder_of("ignored")
    a_run(where, "01_one", tag="py", generator=[0], swept=True)
    a_run(where, "02_one", tag="py2", generator=[0], swept=True)
    a_run(where, "03_one", tag="hw", generator=[1], swept=True)
    doc, _, members = together(where, ignore=["generator"])
    assert doc.source["ignored"] == {"01_one": {"generator": "py8"}, "02_one": {"generator": "py8"},
                                     "03_one": {"generator": "hw7"}}
    head = report.set_head(report.Source("Demo/ignored", where, doc, members), "totality")
    assert ("Ignored", ["generator: Pythia 8 (01_one, 02_one) · Herwig 7 (03_one)"]) in head.facts


def test_a_pdf_sweep_and_an_events_sweep_meet_on_a_pdf_by_events_page(scratch):
    """One Run sweeps the pdf at a fixed 10k events, another the event count at a fixed pdf (NNPDF23lo): across gives every
    member every quantity, the fixed one as its value, so a set pages and curves by both; the point the Runs have twice
    (NNPDF23lo at 10k) is the later Run's, both with prefer = "all"."""
    where = folder_of("meet")
    a_run(where, "01_pdfs", events=10000)
    an_events_run(where, "02_events", [1000, 10000], pdf=1)
    doc, _, members = together(where)
    assert [m.point.name for m in members] == ["01_pdfs__MSTW08lo", "02_events__n1000", "02_events__n10000"]
    assert doc.source["shadowed"] == {"01_pdfs__NNPDF23lo": "02_events__n10000"}
    assert all(m.values["pdf"] in (0, 1) and "@events" in m.values for m in members)
    assert cells(doc, members, {"pages": {"@events": "all"}, "curves": {"pdf": "all"}}) == {
        "1k": ["02_events__n1000"], "10k": ["01_pdfs__MSTW08lo", "02_events__n10000"]}
    both = together(where, prefer="all")
    assert cells(both[0], both[2], {"pages": {"@events": "all"}, "curves": {"pdf": "all"}})["10k"] == [
        "01_pdfs__MSTW08lo", "01_pdfs__NNPDF23lo", "02_events__n10000"]


def test_a_quantity_a_run_never_names_is_unset_there_not_guessed(scratch):
    """The second Run says nothing of the generator (not in its members' values): across gives its members the value
    `unset` ("not set"), so they page apart from the Run that fixed it and are not taken for the same points."""
    where = folder_of("unset")
    a_run(where, "01_pdfs", events=10000)
    an_events_run(where, "02_events", [10000], pdf=1, generator=None)
    doc, _, members = together(where)
    generator = doc.quantities["generator"]
    assert generator.tags[-1] == "unset" and generator.labels[-1] == "not set"
    by_name = {m.point.name: generator.tags[m.values["generator"]] for m in members}
    assert by_name == {"01_pdfs__MSTW08lo": "py8", "01_pdfs__NNPDF23lo": "py8", "02_events__n10000": "unset"}
    assert doc.source["shadowed"] == {}                                    # not the same point as the pdf Run's NNPDF23lo
    assert cells(doc, members, {"pages": {"generator": "all"}, "curves": {"pdf": "all"}}) == {
        "py8": ["01_pdfs__MSTW08lo", "01_pdfs__NNPDF23lo"], "unset": ["02_events__n10000"]}


def test_a_quantity_every_run_names_has_no_unset_value(scratch):
    where = folder_of("allnamed")
    a_run(where, "01_pdfs", events=10000)
    an_events_run(where, "02_events", [10000], pdf=1)
    assert "unset" not in together(where)[0].quantities["generator"].tags
