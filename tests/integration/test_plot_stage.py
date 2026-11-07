"""The plot stage end to end on fake complete points (P3 S2 rows 1 and 4).

Four points (lepton × pdf) whose products are the two legacy mini YODAs; plot_points = lepton, so
two pages per object with two curves each. Reference data are mapped for d01 only.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from runner import labels, plot, quantities, record, sweep, tools

from support import BUILD, apps  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "runner"))
from helpers import beside, parse, raw  # noqa: E402
LEGACY = REPO / "tests" / "reference" / "legacy_run"
BUILT = all((apps() / name).exists() for name in ("Paint.exe", "App_yd2rt.exe"))

pytestmark = pytest.mark.skipif(not BUILT, reason="heimdall build --framework")


@pytest.fixture
def stage(scratch, request):
    backend = getattr(request, "param", "root")
    data = raw(errand__name=f"plotstage_{backend}", errand__cfgs__one__sweeps=["lepton", "pdf"], errand__cfgs__one__plot_points=["lepton"],
               quantities__lepton={"key": {"pythia": "Beams:idB"}, "values": [11, -11], "tags": ["em", "ep"]},
               quantities__pdf__labels=["MSTW 2008 LO", "NNPDF 2.3 LO"],
               plot={"backend": backend, "formats": ["png"], "ratio": True, "min_entries": 10, "range_pad": 1,
                     "data": {"file": str(LEGACY / "ydmrg" / "photo_eic_data.yoda"), "legend": "legacy",
                              "map": {"d01-x01-y01": "/REF/photo_eic/d01-x01-y01"}},
                     "style": {"page": {"dpi": 100}},
                     "figures": {"d04": {"objects": ["d04-*"], "logy": True, "y_gutter": 3.0, "title": "override",
                                         "style": {"legend": {"position": "top-left"}}}}})
    errand = parse(data, scratch)
    configuration = errand.configuration(None)
    return errand, configuration, completed(errand, configuration)



@pytest.fixture(autouse=True)
def keeps_the_working_files():
    """These tests read the plot stage's working files (derived and merged YODAs, mkhtml's), and its skip
    markers: they ask to keep them, as heimdall run --keep cache does (V149)."""
    from runner import paths
    paths.ask_keep(["cache"])

def completed(errand, configuration) -> list:
    """The configuration's points planned, each with a legacy mini YODA as its product, complete."""
    master = quantities.load_master(errand.assignment, errand.master_toml)
    plans = []
    for point in sweep.points(errand, configuration):
        plan = tools.plan_point(errand, configuration, point, master)
        plan.identity = record.identity(plan)
        plans.append(plan)
    for plan in plans:
        shutil.rmtree(plan.res, ignore_errors=True)
        shutil.rmtree(plan.out, ignore_errors=True)
        shutil.rmtree(record.record_dir(plan), ignore_errors=True)
        source = LEGACY / ("mini_27x920_ep_MSTW.yoda" if "MSTW" in plan.point.name else "mini_27x920_ep_NNLO.yoda")
        product = plot.yoda_of(plan)
        product.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, product)
        record.complete_marker(plan).parent.mkdir(parents=True, exist_ok=True)
        record.complete_marker(plan).write_text(plan.identity + "\n", encoding="utf-8")
    for folder in (plans[0].folders.plots, plans[0].folders.statistics, plans[0].folders.pages):
        shutil.rmtree(folder, ignore_errors=True)
    (plans[0].folders.results / "plot.toml").unlink(missing_ok=True)      # V165: what an earlier session left
    (plans[0].folders.results / "report.toml").unlink(missing_ok=True)    # V209: and its report's recipe
    return plans


def test_pages_are_plot_points_by_objects(stage):
    errand, configuration, plans = stage
    pages = plot.pages(errand, configuration, plans)
    assert len(pages) == 2 * 17
    assert {p.cell for p in pages} == {"em", "ep"} and {p.set for p in pages} == {"totality"}      # V164
    first = tomllib.loads(pages[0].config.read_text(encoding="utf-8"))
    assert [c["label"] for c in first["curve"]] == ["MSTW 2008 LO", "NNPDF 2.3 LO"]
    assert first["page"]["min_entries"] == 10 and first["page"]["range_pad"] == 1


def test_data_only_where_the_map_says(stage):
    errand, configuration, plans = stage
    with_data = {p.rel for p in plot.pages(errand, configuration, plans) if "data" in tomllib.loads(p.config.read_text(encoding="utf-8"))}
    assert with_data == {"em/d01-x01-y01", "ep/d01-x01-y01"}


def test_object_overrides_and_rivet_labels(stage):
    errand, configuration, plans = stage
    pages = {p.rel: tomllib.loads(p.config.read_text(encoding="utf-8"))["page"] for p in plot.pages(errand, configuration, plans)}
    assert pages["em/d04-x01-y01"]["logy"] is True and pages["em/d04-x01-y01"]["y_gutter"] == 3.0
    assert pages["em/d04-x01-y01"]["title"] == "override"
    assert pages["em/d02-x01-y01"]["y_gutter"] == 0.5 and pages["em/d02-x01-y01"]["x_gutter"] == "default"
    if (BUILD / "Rivet" / "photo_eic.plot").exists():
        assert pages["em/d01-x01-y01"]["x_label"] == "#it{E}_{#it{T}}^{#it{jet}} [GeV]"
        # with no figure of its own, log y is what the analysis's .plot says (the built copy, which
        # follows modules/: the user may be editing it)
        assert pages["em/d02-x01-y01"]["logy"] is (labels.labels_of("/photo_eic/d02-x01-y01").get("LogY") == "1")


def test_a_page_carries_only_the_style_it_changes(stage):
    errand, configuration, plans = stage
    by = {p.rel: p for p in plot.pages(errand, configuration, plans)}
    assert tomllib.loads(by["em/d04-x01-y01"].config.read_text(encoding="utf-8"))["style"] == {
        "page": {"dpi": 100}, "legend": {"position": "top-left"}}
    assert tomllib.loads(by["em/d02-x01-y01"].config.read_text(encoding="utf-8"))["style"] == {"page": {"dpi": 100}}
    assert by["em/d02-x01-y01"].style["legend"]["position"] == "top-right"     # base.toml's
    assert by["em/d02-x01-y01"].style["page"]["size"] == [4.67, 4.21]


def test_incomplete_points_are_not_drawn(stage):
    errand, configuration, plans = stage
    record.complete_marker(plans[0]).unlink()
    first = tomllib.loads(plot.pages(errand, configuration, plans)[0].config.read_text(encoding="utf-8"))
    assert len(first["curve"]) == 1


def test_draw_writes_every_page(stage):
    errand, configuration, plans = stage
    said = []
    assert plot.draw(errand, configuration, plans, said.append) == 0
    drawn = sorted((plans[0].folders.plots / "totality" / "root").rglob("*.png"))
    assert len(drawn) == 34, said
    assert any("34 of 34" in line for line in said)


def test_the_sweep_is_merged_once_into_the_file_the_pages_read(stage):
    errand, configuration, plans = stage
    pages = plot.pages(errand, configuration, plans)
    merged = plans[0].folders.pages / f"{configuration.label}.root"                # .cache/ (V164)
    assert {c["file"] for p in pages for c in tomllib.loads(p.config.read_text(encoding="utf-8"))["curve"]} == {str(merged)}
    before = merged.stat().st_mtime_ns
    plot.pages(errand, configuration, plans)
    assert merged.stat().st_mtime_ns == before                         # nothing changed: not rebuilt
    uproot = pytest.importorskip("uproot")
    with uproot.open(merged) as f:
        assert {k.split("/")[0] for k in f.keys() if "/" in k} == {p.point.name for p in plans}
        assert "points.json" in {k.split(";")[0] for k in f.keys()} or not record.manifest_file(plans).exists()


def test_figures_are_recipes_for_pages(stage):
    """V80: a defined figure takes over its objects' pages (also those [plot].objects leaves out) with its
    own page keys, and leaves the other pages as they were; one recipe per page."""
    errand, configuration, plans = stage
    cuts = {"class": "overlay", "objects": ["d02-x01-y01", "d03-x01-y01"], "labels": ["$E_T > 5$", "$E_T > 10$"], "ratio": False}
    errand.plot.update({"objects": ["/photo_eic/d01*"]})
    errand.plot["figures"] = {"cuts": cuts}
    before = {p.rel: p.config.read_text(encoding="utf-8") for p in plot.pages(errand, configuration, plans)}
    errand.plot["figures"]["tails"] = {"objects": ["d05-*"], "min_entries": 0, "auto_range": False, "style": {"page": {"dpi": 50}}}
    after = {p.rel: p for p in plot.pages(errand, configuration, plans)}
    assert set(after) == set(before) | {"em/d05-x01-y01", "ep/d05-x01-y01"} and "em/d04-x01-y01" not in after
    assert all(after[name].config.read_text(encoding="utf-8") == text for name, text in before.items())   # the same page TOMLs
    d05 = tomllib.loads(after["em/d05-x01-y01"].config.read_text(encoding="utf-8"))
    assert (d05["page"]["min_entries"], d05["page"]["auto_range"], d05["style"]["page"]["dpi"]) == (0, False, 50)
    errand.plot["figures"]["more"] = {"objects": ["d0[5-6]-*"]}
    with pytest.raises(plot.HeimdallError, match="'tails' and 'more' both make the pages of /photo_eic/d05-x01-y01"):
        plot.pages(errand, configuration, plans)
    errand.plot["figures"] = {"none": {"objects": ["d99-*"]}}
    with pytest.raises(plot.HeimdallError, match="match no object"):
        plot.pages(errand, configuration, plans)


def test_an_overlay_figure_folds_a_band(stage):
    """V80: a figure's band, here an overlay's: one curve per object, the band axis's other values its members."""
    errand, configuration, plans = stage
    errand.plot["figures"] = {"cuts": {"class": "overlay", "objects": ["d02-x01-y01", "d03-x01-y01"], "band": ["pdf"]}}
    page = next(p for p in plot.pages(errand, configuration, plans) if p.rel == "em/cuts")
    curves = tomllib.loads(page.config.read_text(encoding="utf-8"))["curve"]
    assert [c["label"] for c in curves] == ["d02-x01-y01 (pdf envelope)", "d03-x01-y01 (pdf envelope)"]
    assert [len(c["band"]) for c in curves] == [1, 1] and [len(b) for b in page.bands] == [1, 1]
    assert plot.draw(errand, configuration, plans, lambda line: None) == 0


def test_a_derived_figure_is_an_object_of_every_point(stage):
    """V84: /FIGURES/<name> per point, the ratio of two objects, appended to a copy of each point's YODA
    (made again only when the product changes); drawn as an object, its labels its first object's, and
    another figure may overlay it."""
    errand, configuration, plans = stage
    errand.plot["figures"].update({"r15": {"class": "derived", "op": "ratio", "objects": ["d01-x01-y01", "d05-x01-y01"],
                                           "y_label": "d01 / d05", "ratio": False},
                                   "both": {"class": "overlay", "objects": ["r15", "d01-x01-y01"]}})
    by = {p.rel: p for p in plot.pages(errand, configuration, plans)}
    page = tomllib.loads(by["em/r15"].config.read_text(encoding="utf-8"))
    assert page["page"]["y_label"] == "d01 / d05" and page["page"]["x_label"] == tomllib.loads(
        by["em/d01-x01-y01"].config.read_text(encoding="utf-8"))["page"]["x_label"]
    assert [c["object"] for c in page["curve"]][0].endswith("/FIGURES/r15")
    assert by["em/both"].variants == ["/FIGURES/r15", "/photo_eic/d01-x01-y01"] * 2
    copy = plans[0].folders.pages / "derived" / f"{plans[0].point.name}.yoda"
    assert "BEGIN YODA_ESTIMATE1D_V3 /FIGURES/r15" in copy.read_text(encoding="utf-8")
    when = copy.stat().st_mtime_ns
    assert plot.draw(errand, configuration, plans, lambda line: None) == 0
    assert copy.stat().st_mtime_ns == when
    errand.plot["figures"]["bad"] = {"class": "derived", "op": "ratio", "objects": ["d01-x01-y01", "d02-x01-y01"]}
    with pytest.raises(plot.HeimdallError, match="figure 'bad' at .*: ratio of /photo_eic/d01-x01-y01 and /photo_eic/d02-x01-y01"):
        plot.pages(errand, configuration, plans)


def test_a_scan_figure_draws_one_number_per_point(scratch):
    """V85: x a numeric curve axis, y the cross section of each point, a Scatter2D per page cell (here
    per PDF), its points at the x values with ranges halfway to their neighbours; refused for a quantity
    of names, or a page axis."""
    data = raw(errand__name="plotscan", errand__cfgs__one__sweeps=["lepton", "pdf"], errand__cfgs__one__plot_points=["pdf"],
               quantities__lepton={"key": {"pythia": "Beams:idB"}, "values": [11, -11, 22], "tags": ["em", "ep", "g"]},
               plot={"formats": ["png"], "figures": {"xs": {"class": "scan", "x": "lepton", "y": "sigma", "logy": False},
                                                     "b2": {"class": "scan", "x": "lepton", "y": "bin:2",
                                                            "objects": ["d01-x01-y01"], "y_label": "second bin"}}})
    errand = parse(data, scratch)
    configuration = errand.configuration(None)
    plans = completed(errand, configuration)
    by = {p.rel: p for p in plot.pages(errand, configuration, plans)}
    page = by[[n for n in by if n.endswith("/xs")][0]].document
    assert (page["page"]["x_label"], page["page"]["y_label"]) == ("lepton", r"$\sigma$ [pb]") and len(page["curve"]) == 1
    scans = sorted((plans[0].folders.pages / "scan" / "xs").glob("*.yoda"))
    assert len(scans) == 2                                                          # a curve per page cell (PDF)
    import yoda
    points = [(p.x(), p.xErrs(), p.y()) for p in yoda.read(str(scans[0]))["/FIGURES/xs"].points()]
    assert [(x, tuple(e)) for x, e, _ in points] == [(-11.0, (11.0, 11.0)), (11.0, (5.5, 5.5)), (22.0, (5.5, 5.5))]
    assert page["page"]["markers"] is True                                           # a scan is markers (V86)
    assert by[[n for n in by if n.endswith("/b2")][0]].document["page"]["y_label"] == "second bin"
    assert plot.draw(errand, configuration, plans, lambda line: None) == 0
    errand.plot["figures"]["xs"]["x"] = "pdf"
    with pytest.raises(plot.HeimdallError, match="not a curve axis"):
        plot.check_figures(errand, configuration)


def test_a_scatter2d_figure_is_drawn_as_markers(stage):
    """V86: type = "Scatter2D" marks the page; Paint draws its curves as markers, the other pages as before."""
    errand, configuration, plans = stage
    errand.plot["figures"]["pts"] = {"objects": ["d05-*"], "type": "Scatter2D"}
    by = {p.rel: p for p in plot.pages(errand, configuration, plans)}
    assert by["em/d05-x01-y01"].document["page"]["markers"] is True
    assert "markers" not in by["em/d01-x01-y01"].document["page"]
    assert plot.draw(errand, configuration, plans, lambda line: None) == 0


def test_a_2d_object_is_a_heat_map_per_point(stage):
    """V87: a 2D object's pages are heat maps, one per point of the cell, drawn by Paint alone; a
    derived figure projects it; a HeatMap type on a 1D object, or a 2D object in an overlay, is refused."""
    yoda = pytest.importorskip("yoda")
    errand, configuration, plans = stage
    h = yoda.Histo2D(4, 0, 4, 3, 0, 3, "/photo_eic/d90-x01-y01")
    for i in range(60):
        h.fill(i % 4 + 0.5, i % 3 + 0.5, 1.0 + i % 5)
    extra = plans[0].folders.record / "h2.yoda"
    yoda.write([h], str(extra))
    for plan in plans:                                           # each point's YODA gains the 2D object
        product = plot.yoda_of(plan)
        product.write_text(product.read_text(encoding="utf-8") + "\n" + extra.read_text(encoding="utf-8"), encoding="utf-8")
    errand.plot["figures"]["px"] = {"class": "derived", "op": "projection-x", "objects": ["d90-x01-y01"], "ratio": False}
    errand.plot["y_range"] = ["default", 1e9]                    # the 1D pages', not a heat map's
    by = {p.rel: p for p in plot.pages(errand, configuration, plans)}
    maps = sorted(n for n in by if "/d90-x01-y01/" in n)
    assert len(maps) == len(plans) and all(by[n].document["page"]["heatmap"] for n in maps)
    assert all(by[n].document["page"]["y_range"] == ["default", "default"] for n in maps)
    assert by["em/d01-x01-y01"].document["page"]["y_range"] == ["default", 1e9]
    assert by["em/px"].document["page"]["x_label"] is not None
    said = []
    assert plot.draw(errand, configuration, plans, said.append) == 0, said
    assert (plans[0].folders.plots / "totality" / "root" / maps[0]).with_suffix(".png").is_file()
    errand.plot["figures"]["bad"] = {"objects": ["d01-*"], "type": "HeatMap"}
    with pytest.raises(plot.HeimdallError, match="is a HeatMap, and /photo_eic/d01-x01-y01 is a 1D object"):
        plot.pages(errand, configuration, plans)
    errand.plot["figures"]["bad"] = {"class": "overlay", "objects": ["d90-x01-y01", "d01-x01-y01"]}
    with pytest.raises(plot.HeimdallError, match="is a 2D object, which a heat map draws alone"):
        plot.pages(errand, configuration, plans)


@pytest.mark.skipif(not shutil.which("pdflatex"), reason="pdflatex tiles a sheet's PDF")
def test_a_sheet_tiles_drawn_pages(stage):
    """V89: the pages its globs name, in order, tiled as drawn: a PDF by pdflatex, and (V102) its PNG
    rendered from that PDF, at the pages' own PNG size."""
    from PIL import Image
    errand, configuration, plans = stage
    errand.plot["formats"] = ["pdf", "png"]
    errand.plot["figures"]["grid"] = {"class": "sheet", "pages": ["*/d01-x01-y01", "em/d04-x01-y01"], "columns": 2}
    said = []
    assert plot.draw(errand, configuration, plans, said.append) == 0, said
    assert "plot: sheet grid (totality), 3 page(s) in 2 column(s) (root: pdf, png)" in said
    sheets = plans[0].folders.plots / "totality" / "root" / "sheets"
    page = Image.open(plans[0].folders.plots / "totality" / "root" / "em" / "d01-x01-y01.png")
    assert Image.open(sheets / "grid.png").size == (2 * page.width, 2 * page.height)
    assert (sheets / "grid.pdf").read_bytes().startswith(b"%PDF")
    errand.plot["figures"]["grid"]["pages"] = ["nowhere/*"]
    said.clear()
    assert plot.draw(errand, configuration, plans, said.append) == 1
    assert "plot: sheet grid: 'nowhere/*' names no page drawn here" in said


def test_a_compare_figure_draws_configurations_together(stage):
    """V83: the objects' pages across configurations, curves labelled by the configuration first, drawn
    by the plot stage of whichever configuration completes it, into <run>/compare/<name>/."""
    errand, configuration, plans = stage
    two = replace(configuration, key="two", label="Second")
    errand.configurations["two"] = two
    errand.plot["figures"]["stats"] = {"class": "compare", "objects": ["d01-*"], "configurations": ["one", "two"],
                                       "labels": ["1M", "10M"]}
    said = []
    assert plot.draw(errand, configuration, plans, said.append, others=lambda key: []) == 0
    assert "plot: compare stats waits for two: no complete point yet" in said
    others = completed(errand, two)
    said.clear()
    assert plot.draw(errand, two, others, said.append, others=lambda key: plans) == 0, said
    compare = plans[0].folders.compare("stats")[1]
    assert (compare / "root" / "em" / "d01-x01-y01.png").is_file() and (compare / "root" / "index.html").is_file()
    page = tomllib.loads((plans[0].folders.compare("stats")[0] / "em" / "d01-x01-y01.toml").read_text(encoding="utf-8"))
    assert [c["label"] for c in page["curve"]] == ["1M, MSTW 2008 LO", "1M, NNPDF 2.3 LO", "10M, MSTW 2008 LO", "10M, NNPDF 2.3 LO"]
    assert "data" in page
    errand.plot["figures"]["stats"]["configurations"] = ["one", "nope"]
    with pytest.raises(plot.HeimdallError, match="names 'nope', which is not a configuration"):
        plot.check_figures(errand, configuration)


def test_a_compare_figure_reaches_another_run_toml(stage, scratch):
    """V88: "<config>:<cfg>" names a configuration of another run TOML; its points are curves beside this
    run's, labelled by that run, drawn into this run's compare/; its page axes must have this run's tags."""
    import tomli_w
    from runner import config
    errand, configuration, plans = stage
    other = raw(errand__name="plotstage_other", errand__cfgs__one__sweeps=["lepton", "pdf"], errand__cfgs__one__plot_points=["lepton"],
                quantities__lepton={"key": {"pythia": "Beams:idB"}, "values": [11, -11], "tags": ["em", "ep"]},
                quantities__pdf__labels=["MSTW", "NNPDF"])
    path = beside(scratch) / "other.toml"
    path.write_text(tomli_w.dumps(other), encoding="utf-8")
    theirs = config.load(str(path))
    their_plans = completed(theirs, theirs.configuration(None))
    errand.plot["figures"]["chains"] = {"class": "compare", "objects": ["d01-*"], "configurations": ["one", f"{path}:one"]}
    plot.check_figures(errand, configuration)
    asked = []
    said = []
    assert plot.draw(errand, configuration, plans, said.append, others=lambda ref: asked.append(ref) or their_plans) == 0, said
    assert asked == [f"{path}:one"]
    page = tomllib.loads((plans[0].folders.compare("chains")[0] / "em" / "d01-x01-y01.toml").read_text(encoding="utf-8"))
    assert [c["label"] for c in page["curve"]] == ["one, MSTW 2008 LO", "one, NNPDF 2.3 LO",
                                                   "plotstage_other one, MSTW", "plotstage_other one, NNPDF"]
    other["quantities"]["lepton"]["tags"] = ["e-", "e+"]
    path.write_text(tomli_w.dumps(other), encoding="utf-8")
    with pytest.raises(plot.HeimdallError, match="has other values of lepton, a page axis"):
        plot.check_figures(errand, configuration)
    errand.plot["figures"]["chains"]["configurations"] = [f"{path}:one", f"{path}:one2"]
    with pytest.raises(plot.HeimdallError, match="names '.*:one2', which is not a configuration"):
        plot.check_figures(errand, configuration)


@pytest.mark.skipif(not shutil.which("rivet-merge"), reason="gjallarhorn: rivet-merge")
def test_a_merged_figure_merges_the_points_for_itself(stage):
    """V82: per plot_points cell, the pdf points merged (rivet-merge -e) into one curve, on the objects'
    pages under the figure's folder; the other pages keep the points apart; a second draw merges nothing."""
    errand, configuration, plans = stage
    errand.plot["figures"]["avg"] = {"class": "merged", "objects": ["d01-*", "d05-*"], "over": ["pdf"], "title": "both PDFs"}
    by = {p.rel: p for p in plot.pages(errand, configuration, plans)}
    assert {n for n in by if "/avg/" in n} == {"em/avg/d01-x01-y01", "em/avg/d05-x01-y01", "ep/avg/d01-x01-y01", "ep/avg/d05-x01-y01"}
    page = tomllib.loads(by["em/avg/d01-x01-y01"].config.read_text(encoding="utf-8"))
    assert [c["object"].split("/")[0] for c in page["curve"]] == ["em"] and page["page"]["title"] == "both PDFs"
    assert "data" in page and len(tomllib.loads(by["em/d01-x01-y01"].config.read_text(encoding="utf-8"))["curve"]) == 2
    merged = plans[0].folders.pages / "merged" / "avg" / "em.yoda"
    stamp = merged.stat().st_mtime_ns
    assert plot.draw(errand, configuration, plans, lambda line: None) == 0
    assert merged.stat().st_mtime_ns == stamp                                        # nothing changed: not merged again
    assert (plans[0].folders.plots / "totality" / "root" / "em" / "avg" / "d01-x01-y01.png").is_file()


def test_pages_are_paints_and_another_backend_moves_only_the_output(stage):
    errand, configuration, plans = stage
    page = plot.pages(errand, configuration, plans)[0]
    plots = plans[0].folders.plots / "totality"                      # V164: a set's folder, a backend's in it
    assert page.output == plots / "root" / page.rel and page.name == f"totality/{page.rel}"
    assert tomllib.loads(page.config.read_text(encoding="utf-8"))["page"]["output"] == str(page.output)   # Paint's
    assert plot.for_backend(page, "mpl").output == plots / "mpl" / page.rel


@pytest.mark.slow
@pytest.mark.parametrize("stage", ["mpl"], indirect=True)
def test_both_backends_draw_both_trees(stage):
    errand, configuration, plans = stage
    errand.plot["backend"] = ["root", "mpl"]
    said = []
    assert plot.draw(errand, configuration, plans, said.append) == 0, said
    plots = plans[0].folders.plots / "totality"
    for cell in ("em", "ep"):
        assert len(list((plots / "root" / cell).glob("*.png"))) == 17
        assert len(list((plots / "mpl" / cell).glob("d*.png"))) == 17
    assert said[0].startswith("plot: 34 of 34") and any(line.startswith("plot (mpl): 34 of 34") for line in said)


def test_a_swept_analysis_option_is_a_curve_not_a_page(scratch):
    """Each point's YODA holds its own variant (/photo_eic:R=0.4/…): one page per object, one curve
    per point, each read from its own path (found by the Lambda masswindow run)."""
    data = raw(errand__name="plotvariants", errand__cfgs__one__sweeps=["radius"],
               quantities__radius={"target": "rivet/photo_eic", "key": "R", "values": [0.4, 0.7], "tags": ["r04", "r07"]},
               plot={"formats": ["png"], "min_entries": 10})
    errand = parse(data, scratch)
    configuration = errand.configuration(None)
    master = quantities.load_master(errand.assignment, errand.master_toml)
    plans = []
    for point in sweep.points(errand, configuration):
        plan = tools.plan_point(errand, configuration, point, master)
        plan.identity = record.identity(plan)
        plans.append(plan)
    for plan, r in zip(plans, ("0.4", "0.7")):
        shutil.rmtree(plan.res, ignore_errors=True)
        shutil.rmtree(plan.out, ignore_errors=True)
        shutil.rmtree(record.record_dir(plan), ignore_errors=True)
        text = (LEGACY / "mini_27x920_ep_MSTW.yoda").read_text(encoding="utf-8")
        text = text.replace("/photo_eic/", f"/photo_eic:R={r}/")
        product = plot.yoda_of(plan)
        product.parent.mkdir(parents=True, exist_ok=True)
        product.write_text(text, encoding="utf-8")
        record.complete_marker(plan).parent.mkdir(parents=True, exist_ok=True)
        record.complete_marker(plan).write_text(plan.identity + "\n", encoding="utf-8")
    pages = plot.pages(errand, configuration, plans)
    assert len(pages) == 17 and {p.rel for p in pages} == {f"d{n:02d}-x01-y01" for n in range(1, 18)}
    first = tomllib.loads(pages[0].config.read_text(encoding="utf-8"))
    assert [c["object"] for c in first["curve"]] == ["r04/photo_eic__R-0.4/" + pages[0].rel, "r07/photo_eic__R-0.7/" + pages[0].rel]
    assert [c["raw"] for c in first["curve"]] == [c["object"].replace("/", "/RAW/", 1) for c in first["curve"]]
    said = []
    assert plot.draw(errand, configuration, plans, said.append) == 0, said


def test_use_data_false_draws_no_data_and_divides_by_the_first_curve(stage):
    """V44: the [plot.data] table stays but is not drawn; the ratio's reference is each page's first
    curve (the first value of its curve axis)."""
    errand, configuration, plans = stage
    errand.plot["use_data"] = False
    pages = plot.pages(errand, configuration, plans)
    documents = {p.rel: tomllib.loads(p.config.read_text(encoding="utf-8")) for p in pages}
    assert not any("data" in d for d in documents.values())
    d01 = documents["em/d01-x01-y01"]
    assert d01["page"]["ratio"] is True and d01["page"]["ratio_label"] == "Ratio"
    assert d01["curve"][0]["label"] == "MSTW 2008 LO"
    assert plot.draw(errand, configuration, plans, lambda line: None) == 0


def test_a_best_legend_is_drawn(stage):
    """V49: Paint takes the corner with the fewest drawn points under the legend."""
    errand, configuration, plans = stage
    errand.plot["style"] = {**errand.plot.get("style", {}), "legend": {"position": "best"}}
    assert plot.draw(errand, configuration, plans, lambda line: None) == 0


@pytest.mark.parametrize("stage", ["root", "mpl"], indirect=True)
def test_titles_and_overlays(stage):
    """V51: [plot] titles for every page, a child's override; an overlay is several objects of each
    point on one page, labelled by the overlay (and the point, when a page has several)."""
    errand, configuration, plans = stage
    errand.plot.update({"title": "All pages", "title_right": "Pythia 8", "legend_header": "header for all",
                        "figures": {**errand.plot["figures"], "cuts": {"class": "overlay", "objects": ["d02-x01-y01", "d03-x01-y01"], "labels": ["E_{T} > 5", "E_{T} > 10"],
                                          "title": "#eta by cut", "title_left": "k_{T}"}}})
    errand.plot["figures"]["d04"]["legend_header"] = "d04's own"
    by = {p.rel: p for p in plot.pages(errand, configuration, plans)}
    d01, d04, cuts = (tomllib.loads(by[n].config.read_text(encoding="utf-8"))["page"] for n in ("em/d01-x01-y01", "em/d04-x01-y01", "em/cuts"))
    assert (d01["title"], d01["title_right"], d01["legend_header"]) == ("All pages", "Pythia 8", "header for all")
    assert d04["legend_header"] == "d04's own" and d04["title"] == "override"        # the child's own title
    assert (cuts["title"], cuts["title_left"], cuts["title_right"]) == ("#eta by cut", "k_{T}", "Pythia 8")
    labels = [c["label"] for c in tomllib.loads(by["em/cuts"].config.read_text(encoding="utf-8"))["curve"]]
    assert labels == ["E_{T} > 5, MSTW 2008 LO", "E_{T} > 10, MSTW 2008 LO", "E_{T} > 5, NNPDF 2.3 LO", "E_{T} > 10, NNPDF 2.3 LO"]
    assert plot.draw(errand, configuration, plans, lambda line: None) == 0

    if errand.plot["backend"] == "mpl":
        plots = plans[0].folders.plots / "totality" / "mpl"
        assert (plots / "em" / "cuts.png").exists() and (plots / "em" / "d01-x01-y01.png").exists()


# ── V159: pages of chosen points ──────────────────────────────────────────────────────────────

def test_sets_page_chosen_points_whatever_the_plot_axes(stage):
    """A set is a folder of the points it names, in the order named (indices, names, tags, quantity=tag,
    globs, all); its curves are labelled by what differs on it."""
    errand, configuration, plans = stage
    sets = [[3, 1], "MSTW08lo", "all", {"name": "lo", "points": ["pdf=MSTW08lo"]}, "ep_*"]
    made = plot.pages(replace(errand, plot={**errand.plot, "sets": sets}), configuration, plans)
    assert {p.set for p in made} == {"set1", "MSTW08lo", "all", "lo", "ep_"} and {p.cell for p in made} == {""}
    first = next(p for p in made if p.name == "set1/d01-x01-y01")
    assert [c["object"].split("/")[0] for c in first.document["curve"]] == ["ep_MSTW08lo", "em_MSTW08lo"]
    assert [c["label"] for c in first.document["curve"]] == ["ep", "em"]               # the lepton differs, not the PDF
    every = next(p for p in made if p.name == "all/d01-x01-y01")
    assert len(every.document["curve"]) == 4 and every.document["curve"][0]["label"] == "em, MSTW 2008 LO"
    assert {p.name.split("/")[0] for p in made if p.object.endswith("d04-x01-y01")} == {"set1", "MSTW08lo", "all", "lo", "ep_"}


def test_split_cuts_each_cell_into_pages(stage):
    errand, configuration, plans = stage
    made = plot.pages(replace(errand, plot={**errand.plot, "split": 1}), configuration, plans)
    assert {p.cell for p in made} == {"em-1", "em-2", "ep-1", "ep-2"}
    assert all(len(p.document["curve"]) == 1 for p in made if p.object.endswith("d01-x01-y01"))
    whole = plot.pages(replace(errand, plot={**errand.plot, "split": 3, "sets": ["all"]}), configuration, plans)
    assert {(p.set, p.cell) for p in whole} == {("all", "part1"), ("all", "part2")}


def test_a_set_that_names_no_point_is_refused_at_plan_time(stage):
    from runner.errors import HeimdallError
    errand, configuration, _ = stage
    with pytest.raises(HeimdallError, match="a set names 'NNPDF40', which matches no point"):
        plot.check_figures(replace(errand, plot={**errand.plot, "sets": [[1, "NNPDF40"]]}), configuration)
    with pytest.raises(HeimdallError, match="two sets share the folder"):
        plot.check_figures(replace(errand, plot={**errand.plot, "sets": ["all", "all"]}), configuration)


def test_a_merged_figure_takes_no_sets(scratch):
    from runner.errors import HeimdallError
    data = raw(errand__cfgs__one__sweeps=["pdf"],
               plot={"figures": {"avg": {"class": "merged", "objects": ["d01-*"], "over": ["pdf"], "sets": ["all"]}}})
    with pytest.raises(HeimdallError, match="a merged figure pages by plot_points"):
        parse(data, scratch)



# ── V163: sets of page axes and curve groups ───────────────────────────────────────────────────

BY_PDF = {"name": "by_pdf", "pages": {"pdf": "all"}, "curves": {"lepton": ["ep", "em"]}, "objects": ["d01-*", "d04-*"],
          "ratio": False, "title": "set's", "look": {"line": "lepton"}}


def test_a_set_table_pages_by_its_axes_with_its_own_keys(stage):
    """A set table's pages are <set>/<cell>/<object>, a cell per value of its page axes, its curves in the
    order written; its objects alone, its page keys over [plot]'s, a figure's over the set's; its look."""
    errand, configuration, plans = stage
    made = plot.pages(replace(errand, plot={**errand.plot, "sets": [BY_PDF]}), configuration, plans)
    assert {(p.set, p.cell) for p in made} == {("by_pdf", "MSTW08lo"), ("by_pdf", "NNPDF23lo")}
    assert all(p.object.rsplit("/", 1)[-1].startswith(("d01-", "d04-")) for p in made)
    d01 = next(p for p in made if p.name == "by_pdf/NNPDF23lo/d01-x01-y01")
    assert [c["object"].split("/")[0] for c in d01.document["curve"]] == ["ep_NNPDF23lo", "em_NNPDF23lo"]
    assert [c["label"] for c in d01.document["curve"]] == ["ep", "em"]
    assert [c["style"] for c in d01.document["curve"]] == [{"line": "solid"}, {"line": "dashed"}]
    assert d01.document["page"]["ratio"] is False and d01.document["page"]["title"] == "set's"
    assert "data" in d01.document                                     # [plot].data still maps d01
    d04 = next(p for p in made if p.name.startswith("by_pdf/NNPDF23lo/d04-"))
    assert d04.document["page"]["title"] == "override" and d04.document["page"]["logy"] is True


def test_a_set_table_is_drawn_and_planned(stage, capsys):
    """Drawn into plots/<set>/root/<cell>/, each set's statistics in statistics/<set>/ (V164); `heimdall plot …
    --plan` says each cell's curves, drawing nothing."""
    import csv
    errand, configuration, plans = stage
    sets = [BY_PDF, {"name": "em_only", "curves": {"lepton": "em", "pdf": "all"}, "objects": ["d01-*"]},
            {"name": "unnamed", "curves": {"lepton": "em"}, "objects": ["d01-*"]}]
    shown = replace(errand, plot={**errand.plot, "sets": sets})
    lines = plot.plan_lines(shown, configuration, plans)
    assert lines[0].endswith("4 of 4 point(s) complete")
    assert "set by_pdf ([plot]): 2 page cell(s), 4 curve(s), objects d01-*, d04-*; line by lepton" in lines
    assert "  by_pdf/MSTW08lo: 2 curve(s): ep; em" in lines
    assert "set em_only ([plot]): 1 page cell(s), 2 curve(s), objects d01-*" in lines
    assert "  em_only: 2 curve(s): MSTW 2008 LO; NNPDF 2.3 LO" in lines
    assert "  note: set unnamed: pdf is named by neither pages nor curves and takes several values: a page each" in lines
    assert "  unnamed/NNPDF23lo: 1 curve(s): em" in lines
    said = []
    assert plot.draw(shown, configuration, plans, said.append) == 0
    assert "plot: set unnamed: pdf is named by neither pages nor curves and takes several values: a page each" in said
    plots = plans[0].folders.plots
    assert (plots / "by_pdf" / "root" / "MSTW08lo" / "d01-x01-y01.png").is_file()
    assert (plots / "em_only" / "root" / "d01-x01-y01.png").is_file() and (plots / "index.html").is_file()
    assert not (plots / "totality").exists()                          # a drawing of sets draws them alone
    pages_of = {}
    for name in ("by_pdf", "em_only", "unnamed"):
        rows = list(csv.DictReader(open(plans[0].folders.statistics / name / "statistics.csv", encoding="utf-8")))
        pages_of[name] = {r["page"] for r in rows if r["object"].endswith("d01-x01-y01")}
    assert pages_of == {"by_pdf": {"MSTW08lo/d01-x01-y01", "NNPDF23lo/d01-x01-y01"}, "em_only": {"d01-x01-y01"},
                        "unnamed": {"MSTW08lo/d01-x01-y01", "NNPDF23lo/d01-x01-y01"}}


def test_a_set_table_naming_what_no_point_has_is_refused_at_plan_time(stage):
    from runner.errors import HeimdallError
    errand, configuration, _ = stage
    with pytest.raises(HeimdallError, match="lepton = 'mu', which is no value of it"):
        plot.check_figures(replace(errand, plot={**errand.plot, "sets": [{"curves": {"lepton": "mu"}}]}), configuration)
    with pytest.raises(HeimdallError, match="'pfd', which is not a quantity"):
        plot.check_figures(replace(errand, plot={**errand.plot, "sets": [{"pages": {"pfd": "all"}}]}), configuration)

# ── V160: page statistics ─────────────────────────────────────────────────────────────────────

def test_statistics_are_a_table_and_a_legend_may_show_them(stage):
    """Paint's numbers as it draws each page: statistics.csv, a row per curve; the d01 pages against the
    mapped data, the others against their first curve; legend_statistic in each entry but the reference's."""
    import csv
    errand, configuration, plans = stage
    said = []
    shown = replace(errand, plot={**errand.plot, "legend_statistic": "chi2_ndf"})
    assert plot.draw(shown, configuration, plans, said.append) == 0
    table = plans[0].folders.statistics / "totality" / "statistics.csv"       # V164: a set's own
    assert any(line.startswith("plot: statistics of") and str(table.parent) in line for line in said)
    rows = list(csv.DictReader(open(table, encoding="utf-8")))
    d01 = [r for r in rows if r["page"] == "em/d01-x01-y01"]
    assert [r["point"] for r in d01] == ["em_MSTW08lo", "em_NNPDF23lo"] and all(r["reference"] == "legacy" for r in d01)
    assert all(int(r["ndf"]) > 0 and float(r["chi2"]) > 0 and float(r["ref_area"]) > 0 for r in d01)
    assert all(abs(float(r["rel_abs_area"]) - float(r["abs_area"]) / float(r["ref_area"])) < 1e-9 for r in d01)
    assert all(abs(float(r["area_ratio"]) - float(r["cmp_area"]) / float(r["ref_area"])) < 1e-9 for r in d01)   # V175
    assert all(0 < float(r["ratio_dev"]) < 10 and abs(float(r["ratio_mean"]) - 1) <= float(r["ratio_dev"]) + 1e-12 for r in d01)
    d02 = [r for r in rows if r["page"] == "em/d02-x01-y01"]
    assert [r["is_reference"] for r in d02] == ["True", "False"] and float(d02[0]["chi2"]) == 0
    assert float(d02[0]["area_ratio"]) == float(d02[0]["ratio_mean"]) == 1 and float(d02[0]["ratio_dev"]) == 0   # itself
    assert d01[0]["curve"] == "MSTW 2008 LO"                                   # the table's labels are plain
    bars = table.parent                                                          # V162: the table as bar graphs
    assert (bars / "bars" / "em" / "d01-x01-y01.png").is_file()
    assert not list(bars.glob("summary*.png"))                                   # the summary's PNGs: in summary/
    shown = sorted(p.name for p in (bars / "summary").iterdir())               # a page each, numbered in order (V196)
    assert shown == [f"summary_{n:02d}.png" for n in range(1, len(shown) + 1)] and len(shown) >= 1 + 6   # a section a page at least: the front, the standings, five purposes
    assert any(", 1 set(s), 35 bar graph(s) → " in line for line in said)         # 34 pages, the summary
    page = tomllib.loads((plans[0].folders.pages / "totality" / "em" / "d01-x01-y01.toml").read_text(encoding="utf-8"))
    assert all("#chi^{2}/ndf " in c["label"] for c in page["curve"])
    other = tomllib.loads((plans[0].folders.pages / "totality" / "em" / "d02-x01-y01.toml").read_text(encoding="utf-8"))
    assert "ndf" not in other["curve"][0]["label"] and "#chi^{2}/ndf " in other["curve"][1]["label"]
    plot.draw(replace(errand, plot={**errand.plot, "statistics": False}), configuration, plans, said.append)
    table.unlink()
    plot.draw(replace(errand, plot={**errand.plot, "statistics": False}), configuration, plans, said.append)
    assert not table.exists()


def test_a_statistic_figure_ranks_the_points(stage):
    """A page per cell and object: the page's curves as bins, labelled, sorted by the number (best first)."""
    import csv
    errand, configuration, plans = stage
    figure = {"class": "statistic", "statistic": "chi2_ndf", "objects": ["d01-*"], "sort": True}
    ranked = replace(errand, plot={**errand.plot, "y_range": ["default", 1e9],          # [plot]'s: the 1D pages'
                                   "figures": {**errand.plot["figures"], "rank": figure}})
    said = []
    assert plot.draw(ranked, configuration, plans, said.append) == 0
    assert "plot: statistic rank, 2 page(s)" in said
    page = tomllib.loads((plans[0].folders.pages / "statistic" / "rank" / "totality__em__rank__d01-x01-y01.toml")
                         .read_text(encoding="utf-8"))
    numbers = plans[0].folders.statistics / "totality"
    rows = [r for r in csv.DictReader(open(numbers / "statistics.csv", encoding="utf-8")) if r["page"] == "em/d01-x01-y01"]
    best = sorted(rows, key=lambda r: float(r["chi2_ndf"]))
    assert page["page"]["x_labels"] == [labels.tlatex(r["curve"]) for r in best] and page["page"]["markers"]
    assert page["page"]["y_range"] == ["default", "default"]
    assert (numbers / "figures" / "root" / "em" / "rank" / "d01-x01-y01.png").is_file()      # V164: with the numbers
    assert not any(r["page"].startswith("em/rank") for r in rows)              # the table is the pages' own


# ── V165: the plot document ─────────────────────────────────────────────────────────────────────

def test_a_run_draws_from_its_plot_document(stage):
    """The plot stage writes results/<run>/plot.toml, what the run knows and its [plot], and draws from it alone:
    the same pages as from the plans; and report.toml beside it, the default report for its sets (V209)."""
    from runner import cli, plotdoc
    errand, configuration, plans = stage
    said = []
    assert cli.draw_run(errand, configuration, plans, said.append) == 0, said
    target = plans[0].folders.results / "plot.toml"
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    assert set(data) == {"source", "axes", "quantities", "members", "plot"}
    assert sorted(data["members"]) == sorted(p.point.name for p in plans) and all(m["complete"] for m in data["members"].values())
    assert data["members"]["em_MSTW08lo"]["yoda"].startswith("points/em_MSTW08lo/")
    assert data["axes"]["plot_points"] == ["lepton"] and data["quantities"]["pdf"]["points"] == [   # V172: as a run TOML's
        {"tag": "MSTW08lo", "value": "LHAPDF6:MSTW2008lo68cl", "label": "MSTW 2008 LO"},
        {"tag": "NNPDF23lo", "value": "LHAPDF6:NNPDF23_lo_as_0130_qed", "label": "NNPDF 2.3 LO"}]
    assert data["plot"]["data"]["file"] == errand.plot["data"]["file"] and data["source"]["configuration"] == configuration.key
    assert len(list((plans[0].folders.plots / "totality" / "root").rglob("*.png"))) == 34
    doc, kept, members = plotdoc.load(target)
    assert [m.point.name for m in members] == [p.point.name for p in plans] and kept.plot_points == ["lepton"]
    assert [p.document for p in plot.pages(doc, kept, members)] == [p.document for p in plot.pages(errand, configuration, plans)]
    recipe = tomllib.loads(target.with_name("report.toml").read_text(encoding="utf-8"))
    given, standings, pages = recipe["report"]["section"]                                     # V218: what was run first
    assert [s["title"] for s in (given, standings, pages)] == ["Tools", "Standings", "Pages: totality"]
    assert standings["set"] == pages["set"] == "totality" and given["tools"] == ["*"]          # V210: what they were given
    assert all(s["optional"] for s in (standings, pages, given))


def test_the_document_keeps_its_plot_and_says_when_the_config_differs(stage):
    """What the user chose is written once and kept: a hand edit is drawn, and a run with another [plot] says so."""
    from runner import cli, plotdoc
    errand, configuration, plans = stage
    cli.draw_run(errand, configuration, plans, lambda line: None)
    target = plans[0].folders.results / "plot.toml"
    plotdoc.write_chosen(target, {**plotdoc.load(target)[0].plot, "title": "mine"}, {})
    said = []
    assert cli.draw_run(errand, configuration, plans, said.append) == 0
    assert any("differs from" in line and "--style-sync" in line for line in said), said
    page = tomllib.loads((plans[0].folders.pages / "totality" / "em" / "d02-x01-y01.toml").read_text(encoding="utf-8"))
    assert page["page"]["title"] == "mine" and tomllib.loads(target.read_text(encoding="utf-8"))["plot"]["title"] == "mine"


def test_a_folder_copied_away_draws_from_its_document(stage, scratch):
    """<run>/ alone redraws: its plot.toml and points/, no records/ beside it (complete as the document says)."""
    from runner import cli, plotdoc
    errand, configuration, plans = stage
    cli.draw_run(errand, configuration, plans, lambda line: None)
    away = scratch / "away" / "01"
    shutil.copytree(plans[0].folders.results, away)
    shutil.rmtree(away / "plots")
    doc, kept, members = plotdoc.load(away / "plot.toml")
    assert plot.drawable(members)[0] == members and not members[0].folders.record.exists()
    assert plot.draw(doc, kept, members, lambda line: None) == 0
    assert (away / "plots" / "totality" / "root" / "em" / "d01-x01-y01.png").is_file()
    assert (away / "statistics" / "totality" / "statistics.csv").is_file()


def test_a_document_holds_totality_and_draws_the_sets_it_picks(stage):
    """V167: a run's document holds the totality set (here plot_points' pages, the pdf curves) before the config's
    sets; [plot].draw (from [errand].plot's list) or --sets picks which are drawn."""
    from runner import cli, plotdoc
    errand, configuration, plans = stage
    shown = replace(errand, plot={**errand.plot, "sets": [BY_PDF]})
    assert cli.draw_run(shown, replace(configuration, draw=["by_pdf"]), plans, lambda line: None) == 0
    target = plans[0].folders.results / "plot.toml"
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    assert list(data["plot"]["sets"]) == ["totality", "by_pdf"] and data["plot"]["draw"] == ["by_pdf"]
    assert data["plot"]["sets"]["totality"] == {"pages": {"lepton": "all"}, "curves": {"pdf": "all"}}
    plots = plans[0].folders.plots
    assert (plots / "by_pdf").is_dir() and not (plots / "totality").exists()
    doc, kept, members = plotdoc.load(target)
    doc.plot = {**doc.plot, "draw": ["totality"]}
    assert plot.draw(doc, kept, members, lambda line: None) == 0
    assert len(list((plots / "totality" / "root").rglob("*.png"))) == 34 and (plots / "by_pdf").is_dir()   # left as it was
    doc.plot = {**doc.plot, "draw": ["nope"]}
    with pytest.raises(plot.HeimdallError, match="names 'nope', which is no set"):
        plot.check_figures(doc, kept)


# ── V168: statistics, linked to a drawing or alone ───────────────────────────────────────────────

def test_statistics_alone_draw_no_page(stage):
    """`draw = False`: the pages' numbers only (Paint --ranges-only on documents of their own), into
    statistics/<set>/; no page drawn, the drawing's documents untouched."""
    import csv
    from runner import cli
    errand, configuration, plans = stage
    said = []
    assert cli.draw_run(errand, configuration, plans, said.append, draw=False) == 0, said
    numbers = plans[0].folders.statistics / "totality"
    rows = list(csv.DictReader(open(numbers / "statistics.csv", encoding="utf-8")))
    assert len(rows) == 34 * 2 and (numbers / "summary" / "summary_01.png").is_file()
    assert not plans[0].folders.plots.exists() and any(line.startswith("stats: statistics of 68 curve(s)") for line in said)
    assert (plans[0].folders.pages / "stats" / "totality" / "em" / "d01-x01-y01.toml").is_file()
    assert not (plans[0].folders.pages / "totality").exists()


def test_a_stats_table_measures_otherwise_than_the_pages_draw(stage):
    """[stats] normalise = "area" and reference = "curves": the drawn pages as [plot] says, the numbers of shapes
    against each page's first curve, in a pass of their own."""
    import csv
    from runner import cli
    errand, configuration, plans = stage
    shown = replace(errand, stats={"normalise": "area", "reference": "curves", "objects": ["d01-*", "d02-*"]})
    said = []
    assert cli.draw_run(shown, configuration, plans, said.append) == 0, said
    page = tomllib.loads((plans[0].folders.pages / "totality" / "em" / "d01-x01-y01.toml").read_text(encoding="utf-8"))
    assert page["page"]["normalise"] is False and "data" in page                 # the drawn page: [plot]'s
    rows = list(csv.DictReader(open(plans[0].folders.statistics / "totality" / "statistics.csv", encoding="utf-8")))
    assert {r["object"].rsplit("/", 1)[-1] for r in rows} == {"d01-x01-y01", "d02-x01-y01"}
    d01 = [r for r in rows if r["page"] == "em/d01-x01-y01"]
    assert d01[0]["is_reference"] == "True" and d01[0]["reference"] == "MSTW 2008 LO"
    assert all(abs(float(r["area"]) - 1) < 1e-6 for r in rows if r["area"])
    assert len(list((plans[0].folders.plots / "totality" / "root").rglob("*.png"))) == 34


def test_plot_stats_only_measures_a_runs_document(stage, capsys):
    import argparse
    from runner import cli
    errand, configuration, plans = stage
    cli.draw_run(errand, configuration, plans, lambda line: None, draw=False, stats=False)
    assert not plans[0].folders.statistics.exists()
    args = argparse.Namespace(command="plot", config=str(plans[0].folders.results), configuration=None, set=[],
                              draw_sets=None, stats_only=True)
    assert cli.cmd_plot(args) == 0
    assert "stats: statistics of 68 curve(s), 1 set(s)" in capsys.readouterr().out
    assert (plans[0].folders.statistics / "totality" / "statistics.csv").is_file() and not plans[0].folders.plots.exists()


# ── V169: the runs of a run TOML together ───────────────────────────────────────────────────────

def test_the_runs_of_a_run_toml_draw_together(stage):
    """[plot.across]: results/<P>/<name>/plot.toml, the runs' members together with @events, @run and
    @configuration; a set by event count draws each run's points on one page."""
    from runner import cli, plotdoc
    errand, configuration, plans = stage
    two = replace(configuration, key="two", label="Second", event_count=20)
    errand.configurations["two"] = two
    others = completed(errand, two)
    plotdoc.across_path(errand.assignment, errand.name).unlink(missing_ok=True)
    across = {"by_events": {"pages": {"lepton": "all"}, "curves": {"@events": "all", "pdf": "NNPDF23lo"}}}
    shown = replace(errand, plot={**errand.plot, "across": across})
    for conf, members in ((configuration, plans), (two, others)):
        assert cli.draw_run(shown, conf, members, lambda line: None) == 0
    assert "across" not in tomllib.loads((plans[0].folders.results / "plot.toml").read_text(encoding="utf-8"))["plot"]
    target, written = plotdoc.write_across(shown)
    assert written and target == plans[0].folders.results.parent / "plot.toml"
    doc, kept, members = plotdoc.load(target)
    assert doc.quantities["@events"].tags == ["10", "20"] and doc.quantities["@run"].tags == ["Second", "one"]
    assert {m.point.name for m in members} == {f"{f}__{p.point.name}" for f, ps in (("one", plans), ("Second", others)) for p in ps}
    assert plot.draw(doc, kept, members, lambda line: None) == 0
    page = tomllib.loads((members[0].folders.pages / "by_events" / "em" / "d01-x01-y01.toml").read_text(encoding="utf-8"))
    assert [c["label"] for c in page["curve"]] == ["10 events", "20 events"]
    assert (plans[0].folders.results.parent / "plots" / "by_events" / "root" / "em" / "d01-x01-y01.png").is_file()
    assert (plans[0].folders.results.parent / "statistics" / "by_events" / "statistics.csv").is_file()


def test_the_runs_together_by_their_tags(stage):
    """V224: a run tagged, @tag pages a set that does not name it and labels the curves of one that does; the tag
    cleared, the page documents are byte for byte those of the runs never tagged."""
    import hashlib
    from runner import cli, plotdoc
    errand, configuration, plans = stage
    two = replace(configuration, key="two", label="Second", event_count=20)
    errand.configurations["two"] = two
    others = completed(errand, two)
    plotdoc.across_path(errand.assignment, errand.name).unlink(missing_ok=True)
    shown = replace(errand, plot={**errand.plot, "across": {"plain": {"curves": {"pdf": "all"}}}})
    for conf, members in ((configuration, plans), (two, others)):
        assert cli.draw_run(shown, conf, members, lambda line: None) == 0
    target, _ = plotdoc.write_across(shown)
    second = others[0].folders.results / plotdoc.FILE

    def drawn() -> dict[str, str]:
        doc, kept, members = plotdoc.load(target)
        assert plot.draw(doc, kept, members, lambda line: None) == 0
        pages = members[0].folders.pages
        return {str(p.relative_to(pages)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(pages.rglob("*.toml"))}

    never = drawn()
    assert "plain/em_10/d01-x01-y01.toml" in never
    plotdoc.write_tag(second, "nlo")
    tagged = drawn()
    assert "plain/em_10_untagged/d01-x01-y01.toml" in tagged and "plain/em_20_nlo/d01-x01-y01.toml" in tagged
    by_tag = {"by_tag": {"pages": {"lepton": "all"}, "curves": {"@tag": "all", "@events": "all", "pdf": "NNPDF23lo"}}}
    plotdoc.write_chosen(target, {**plotdoc.load(target)[0].plot, "sets": by_tag}, {})
    doc, kept, members = plotdoc.load(target)
    assert plot.draw(doc, kept, members, lambda line: None) == 0
    page = tomllib.loads((members[0].folders.pages / "by_tag" / "em" / "d01-x01-y01.toml").read_text(encoding="utf-8"))
    assert [c["label"] for c in page["curve"]] == ["nlo, 20 events", "untagged, 10 events"]      # in folder order
    plotdoc.write_tag(second, None)
    plotdoc.write_chosen(target, {**doc.plot, "sets": shown.plot["across"]}, {})
    assert drawn() == never                                  # nothing left of the tagged pages either


def test_plot_looks_give_a_value_its_look_by_tag(stage, scratch):
    """[plot.looks.<quantity>] (V171): a value's look on every page, by tag; a tag no point has is unused; a set's
    automatic look leaves the axis alone; a bad look is refused when the file is read."""
    from runner.errors import HeimdallError
    errand, configuration, plans = stage
    looks = {"pdf": {"MSTW08lo": "#111111", "NNPDF23lo": {"colour": "#222222", "line": "dashed"}, "gone": "#333333"}}
    made = plot.pages(replace(errand, plot={**errand.plot, "looks": looks}), configuration, plans)
    page = next(p for p in made if p.rel == "em/d02-x01-y01")
    assert [c["style"] for c in page.document["curve"]] == [{"colour": "#111111"}, {"colour": "#222222", "line": "dashed"}]
    two = {"name": "both", "curves": {"lepton": "all", "pdf": "all"}}
    made = plot.pages(replace(errand, plot={**errand.plot, "looks": looks, "sets": [two]}), configuration, plans)
    page = next(p for p in made if p.rel == "d02-x01-y01")
    assert {c["style"]["colour"] for c in page.document["curve"]} == {"#111111", "#222222"}       # no automatic colour
    with pytest.raises(HeimdallError, match="style line = 'wavy' is not one"):
        parse(raw(plot={"looks": {"pdf": {"MSTW08lo": {"line": "wavy"}}}}), scratch)



def test_the_summary_is_scored_by_purpose(stage):
    """V174, V196: statistics/<set>/summary.pdf, every page A4 portrait: the standings (score, worst page, veto, a column a
    purpose), then a section per purpose with a metric on: its ranking, then each metric's ranking, page cells against
    curves and table (a row per point, a column per object in natural order, then the mean; the reference "ref"); each item
    names its notes. A table wider than the page is cut into column blocks, the mean on the last. V197: a table in curve
    order groups its rows under their cells' bands; the facts, contents and notes up front. V199: summary.html beside it.
    A head to head only for the pages `[score].head_to_head` names."""
    import re
    from runner import plugins
    from stats import metrics, score
    errand, configuration, plans = stage
    names = ["chi2_ndf", "norm", "shape", "tilt", "worst", "rel_abs_area", "area_ratio", "ratio_mean", "ratio_dev"]
    scored = {"metrics": names, "veto": 5.0, "head_to_head": "em/d01-x01-y01"}
    shown = replace(errand, score=scored, plot={**errand.plot, "formats": ["pdf", "png"]})
    assert plot.draw(shown, configuration, plans, lambda line: None) == 0
    numbers = plans[0].folders.statistics / "totality"
    pdf = (numbers / "summary.pdf").read_bytes()
    count = len(re.findall(rb"/Type\s*/Page\b(?!s)", pdf))
    boxes = re.findall(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", pdf)
    assert len(boxes) == count and {(float(w), float(h)) for w, h in boxes} == {(595.44, 841.68)}   # A4, every page
    assert len(list((numbers / "summary").glob("summary_*.png"))) == count
    assert "<h2>Head to head</h2>" in (numbers / "summary.html").read_text(encoding="utf-8")   # V199: the same, a page
    side = json.loads((numbers / "statistics.json").read_text(encoding="utf-8"))
    assert side["score"] == scored and set(names) <= set(side["columns"])        # the table says how it was scored
    bars = plugins.load(plot.heimdall_root() / "framework" / "plot" / "figures" / "bars.py", "bars")
    st = score.settings_of(scored)
    rows = [r for page in plot.pages(shown, configuration, plans) for r in (plot.statistics_of(page, names) or [])]
    assert any(math.isfinite(r["worst"]) for r in rows)                          # Paint measured the bins they come from
    document = bars.summary_model(rows, plot.heading_of(numbers), st)
    assert len(bars.paper.pages(document)) == count
    assert document.heading.endswith(" · totality")
    assert document.facts[0].startswith("4 point(s) in 2 page cell(s), on 17 object(s)")       # V197: up front
    sections = {s.key: s for s in document.sections}
    assert list(sections) == ["standings", "purpose-compatibility", "purpose-normalisation", "purpose-shape",
                              "purpose-trend", "purpose-defects", "head-to-head"]
    items = {item.key: item for s in document.sections for item in s.items}
    assert [i.key for i in sections["purpose-compatibility"].items] == [
        "purpose-compatibility-ranking", "chi2_ndf-ranking", "chi2_ndf-crossed", "chi2_ndf"]
    crossed = items["chi2_ndf-crossed"]                                         # V198: page cells against curves
    assert crossed.headers == ["MSTW 2008 LO", "NNPDF 2.3 LO", "rms"] and [r.label for r in crossed.rows] == [
        "em", "ep", "rms"]

    def notes(item):
        return " ".join(document.notes[k] for k in item.notes)
    for key in names:
        assert metrics.describe(key, st.thresholds.get(key)) in notes(items[key])
    assert "Compared bins" in notes(items["chi2_ndf"])

    table = items["chi2_ndf"]
    assert table.headers[:3] == ["d01", "d02", "d03"] and table.headers[-1] == "rms" and len(table.headers) == 18
    assert [r.label for r in table.rows] == ["em", "MSTW 2008 LO", "NNPDF 2.3 LO", "ep", "MSTW 2008 LO",
                                             "NNPDF 2.3 LO"]                    # V197: each cell's band, its curves
    assert [r.band for r in table.rows] == [True, False, False, True, False, False]
    assert any(c.text == "ref" for r in table.rows for c in r.cells)
    for key in names:                                   # every block fits the page; the mean on the last
        shape = bars.paper._table_shape(items[key])
        assert [j for block in shape.blocks for j in block] == list(range(18)) and shape.blocks[-1][-1] == 17
        assert all(shape.label_width + sum(shape.widths[j] for j in block) <= bars.paper.WIDTH + 1e-9
                   for block in shape.blocks)

    scores = score.score(rows, st)                                              # the standings are the engine's
    assert [p.n_pages for p in scores.points] == [1, 1, 1, 1]                   # only d01 has data: one page each
    standings = items["standings"]
    assert [r.label for r in standings.rows if r.band] == ["em", "ep"] and standings.headers[:4] == [
        "score", "worst page", "worst", "veto"]
    for cell in ("em", "ep"):
        mine = sorted((p for p in scores.points if p.cell == cell), key=lambda p: p.score)
        first = next(r for r in standings.rows[standings.rows.index(next(r for r in standings.rows if r.band and r.label == cell)) + 1:]
                     if not r.band)
        assert first.cells[0].text == bars._shown(mine[0].score) and first.label.startswith("1. ")
    for key in names:
        ranking = items[f"{key}-ranking"]
        ratio = key in ("area_ratio", "ratio_mean")
        have = {r["point"] for r in rows if not r["is_reference"] and math.isfinite(r[key])}
        assert len(ranking.values) == len(have) >= 2                            # a point with no number is left out
        assert ranking.values == sorted(ranking.values, key=lambda m: abs(math.log10(m)) if ratio else m)
        assert all(re.search(r"  \(\d+\)$", n) for n in ranking.names)         # the pages it was compared on, in brackets
        assert "the root mean square" in notes(ranking)
        assert ranking.base == (1.0 if ratio else 0.0)
    (match,) = sections["head-to-head"].items                                   # the one page asked: em's d01
    assert match.headers == ["MSTW 2008 LO", "NNPDF 2.3 LO", "loss"] and match.title.endswith("em/d01-x01-y01")
    assert float(match.rows[0].cells[1].text) == pytest.approx(-float(match.rows[1].cells[0].text))


@pytest.mark.parametrize("where", ["out-right", "out-left", "out-top", "out-bottom"])
@pytest.mark.filterwarnings("ignore:This process .* is multi-threaded:DeprecationWarning")   # an earlier test's fsspec
def test_a_legend_outside_the_frame_and_a_gap_above_the_ratio(stage, where):                  # thread; mpl forks per page
    """V185: legend.position out-right, out-left, out-top, out-bottom, and ratio.gap (points between the frames):
    Paint and mpl draw them (Paint's frame makes room, mpl's page grows)."""
    from runner.errors import HeimdallError
    errand, configuration, plans = stage
    styled = replace(errand, plot={**errand.plot, "backend": ["root", "mpl"],
                                   "style": {"page": {"dpi": 100}, "legend": {"position": where}, "ratio": {"gap": 6.0}}})
    plot.validate(styled)
    assert plot.draw(styled, configuration, plans, lambda line: None) == 0
    pages = plans[0].folders.plots / "totality"
    for backend in ("root", "mpl"):
        assert (pages / backend / "em" / "d01-x01-y01.png").is_file()
    with pytest.raises(HeimdallError, match="must be one of"):
        plot.check_style({"legend": {"position": "out-middle"}}, "[plot.style]")


# ── set-merge: a set's `merge` draws a curve of its own ────────────────────────────────────────

def test_a_merge_entry_draws_one_curve_from_the_pdfs_with_a_band(stage):
    errand, configuration, plans = stage
    errand.plot = {**errand.plot, "sets": {"both": {"pages": {"lepton": "all"}, "merge": {"pdf": "all", "label": "Both PDFs",
                                                                                          "tag": "pdfs", "band": "minmax"}}}}
    pages = [p for p in plot.pages(errand, configuration, plans) if p.set == "both"]
    assert len(pages) == 2 * 17 and {p.cell for p in pages} == {"em", "ep"}
    document = tomllib.loads(next(p for p in pages if p.rel == "em/d02-x01-y01").config.read_text(encoding="utf-8"))
    (curve,) = document["curve"]
    assert curve["label"] == "Both PDFs" and curve["object"].startswith("em_pdfs/")
    assert [b["object"].split("/")[0] for b in curve["band"]] == ["em_pdfs__lo", "em_pdfs__hi"]
    sets = plans[0].folders.pages / "sets"
    assert (sets / "em_pdfs.yoda").is_file() and (sets / "em_pdfs__lo.yoda").is_file() and (sets / "em_pdfs.sha256").is_file()


def test_a_merged_curve_is_the_linear_mean_of_its_members_and_rebuilt_only_when_they_change(stage):
    errand, configuration, plans = stage
    errand.plot = {**errand.plot, "sets": {"both": {"pages": {"lepton": "all"}, "merge": {"pdf": "all", "tag": "pdfs"}}}}
    plot.pages(errand, configuration, plans)
    target = plans[0].folders.pages / "sets" / "em_pdfs.yoda"
    first = target.stat().st_mtime_ns
    import yoda
    merged = yoda.read(str(target))["/photo_eic/d02-x01-y01"].bins()[3].val()
    mine = [yoda.read(str(plot.yoda_of(p)))["/photo_eic/d02-x01-y01"].bins()[3].val() for p in plans if p.point.name.startswith("em_")]
    assert merged == pytest.approx(sum(mine) / len(mine))
    plot.pages(errand, configuration, plans)
    assert target.stat().st_mtime_ns == first


def test_a_set_with_a_merged_curve_and_its_band_draws_through_paint(stage):
    errand, configuration, plans = stage
    errand.plot = {**errand.plot, "sets": {"both": {"pages": {"lepton": "all"}, "merge": {"pdf": "all", "label": "Both PDFs",
                                                                                          "tag": "pdfs", "band": "minmax"}}}}
    errand.plot["draw"] = ["both"]
    said: list[str] = []
    assert plot.draw(errand, configuration, plans, said.append, stats=False) == 0, said
    drawn = sorted((plans[0].folders.plots / "both" / "root").rglob("*.png"))
    assert len(drawn) == 2 * 17 and all(p.stat().st_size > 1000 for p in drawn)


def test_how_combine_pools_the_members_statistics_as_the_merged_figure_does(stage):
    errand, configuration, plans = stage
    errand.plot = {**errand.plot, "sets": {"both": {"pages": {"lepton": "all"}, "merge": {"pdf": "all", "how": "combine", "tag": "pooled"}}}}
    pages = [p for p in plot.pages(errand, configuration, plans) if p.set == "both"]
    assert len(pages) == 2 * 17
    assert (plans[0].folders.pages / "sets" / "em_pooled.yoda").is_file()
