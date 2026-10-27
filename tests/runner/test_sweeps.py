"""Sweeps, pages, the P2 checks, seeds and the point-count gate (docs/07_Record.md §8)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from runner import config, record, sweep, tools
from runner.errors import HeimdallError

from helpers import plan, plans_of, raw

REPO = Path(__file__).resolve().parents[2]
COUNTS = tomllib.loads((REPO / "tests" / "reference" / "point_counts.toml").read_text(encoding="utf-8"))


CASES = [(f"Demo/{'jets' if run == 'jets' else 'validation'}", cfg, counts)
         for run, table in COUNTS.items() for cfg, counts in table.items()]


@pytest.mark.parametrize(("name", "cfg", "counts"), CASES, ids=[f"{n.split('/')[1]}/{c}" for n, c, _ in CASES])
def test_point_and_page_counts_equal_the_legacy_table(name, cfg, counts):
    run = config.load(name)
    conf = run.configuration(None if cfg == "default" else cfg)
    points = sweep.points(run, conf)
    assert (len(points), len(sweep.pages(conf, points))) == (counts["points"], counts["pages_v2"])


def test_every_eic_configuration_plans_and_its_seed_blocks_are_disjoint():
    """Within a plan no two points share events (V9, L4). Across configurations the seeds follow the
    generator: the same generator setup (single, pdf's NNPDF23lo point, inproc) gives the same
    seeds, and different setups never overlap."""
    by_basis: dict[str, int] = {}
    blocks = []
    run = config.load("Demo/jets")
    for key in run.configurations:
        _, _, _, plans = plans_of("Demo/jets", key)
        spans = sorted((p.seed, p.seed + p.threads) for p in plans)
        assert all(a_end <= b_start for (_, a_end), (b_start, _) in zip(spans, spans[1:])), key
        for p in plans:
            basis = record.seed_basis(p)
            if len(plans) == len({record.seed_basis(q) for q in plans}):   # no clash moved it
                assert by_basis.setdefault(basis, p.seed) == p.seed, key
            blocks.append((p.seed, p.seed + p.threads, basis))
    shared = {k: v for k, v in by_basis.items() if sum(1 for *_, b in blocks if b == k) > 1}
    assert shared, "single, pdf and inproc share a generator setup"
    unique = sorted({(start, end, basis) for start, end, basis in blocks})
    assert all(a[1] <= b[0] or a[2] == b[2] for a, b in zip(unique, unique[1:]))


def test_entangled_quantities_move_together_and_axes_form_a_grid(scratch):
    data = raw(run__cfgs__one__sweeps=["pdf", ["a", "b"]],
               quantities__a={"values": [1, 2, 3], "tags": ["a1", "a2", "a3"], "key": {"pythia": "A:x"}},
               quantities__b={"values": [4, 5, 6], "tags": ["b1", "b2", "b3"], "key": {"pythia": "B:y"}})
    run = config.parse(data, scratch / "t.toml")
    points = sweep.points(run, run.configuration(None))
    assert len(points) == 2 * 3
    assert [p.name for p in points[:3]] == ["MSTW08lo_a1_b1", "MSTW08lo_a2_b2", "MSTW08lo_a3_b3"]


def test_pages_are_the_plot_points_grid():
    run, conf, points, _ = plans_of("Demo/jets", "energy_pdf")
    pages = sweep.pages(conf, points)
    assert len(pages) == 4 and all(len(members) == 4 for members in pages.values())


def test_the_consumer_table_of_energy_pdf(capsys):
    from runner.cli import print_plan
    run, conf, _, plans = plans_of("Demo/jets", "energy_pdf")
    for p in plans:
        tools.finalise(p, p.seed)
    print_plan(run, conf, plans[:1])
    text = capsys.readouterr().out
    assert "energies     = 5x41           → pythia:['Beams:eA', 'Beams:eB']" in text
    assert "pdf          = MSTW08lo       → pythia:PDF:pSet" in text
    assert "lepton       = ep             → pythia:Beams:idB" in text


def test_c9_an_undeclared_rivet_option_is_refused(scratch):
    data = raw(tools__rivet__options={"NOSUCH": 3})
    with pytest.raises(HeimdallError, match="does not declare the option NOSUCH") as caught:
        plan(data, scratch)
    assert "ETMIN" in caught.value.hint


def test_c9_an_unknown_analysis_is_refused(scratch):
    with pytest.raises(HeimdallError, match="no analysis 'photo_eci'"):
        plan(raw(tools__rivet__analyses=["photo_eci"]), scratch)


def test_c10_a_pdf_set_that_is_not_installed_is_refused(scratch):
    data = raw(static={"pdf": "x"}, quantities__pdf={"values": ["LHAPDF6:NoSuchSet"], "tags": ["x"]})
    with pytest.raises(HeimdallError, match="not installed") as caught:
        plan(data, scratch)
    assert "lhapdf install NoSuchSet" in caught.value.hint


def one_pdf(value):
    return raw(static={"pdf": "x"}, quantities__pdf={"values": [value], "tags": ["x"]})


@pytest.mark.parametrize("value, line", [("LHAPDF6:MSTW2008lo68cl", "PDF:pSet = LHAPDF6:MSTW2008lo68cl"),
                                         ("LHAPDF6:MSTW2008lo68cl/3", "PDF:pSet = LHAPDF6:MSTW2008lo68cl/3"),
                                         (14, "PDF:pSet = 14")])
def test_pythia_gets_the_pdf_value_as_written(scratch, value, line):
    """A prefixed value and one of Pythia's own set numbers are written as given (V40: a number is never prefixed)."""
    _, _, p = plan(one_pdf(value), scratch)
    assert line in p.writes[p.rendered["pythia"].card_combined].splitlines()


def test_a_bare_lhapdf_set_name_is_written_with_its_prefix_for_pythia(scratch):
    """V152: one spelling of a set feeds every generator; Pythia reads a bare name as a file, so it gets the
    prefix, and the card line (so the identity) is the prefixed value's."""
    _, _, bare = plan(one_pdf("MSTW2008lo68cl"), scratch)
    _, _, prefixed = plan(one_pdf("LHAPDF6:MSTW2008lo68cl"), scratch)
    assert "PDF:pSet = LHAPDF6:MSTW2008lo68cl" in bare.writes[bare.rendered["pythia"].card_combined].splitlines()
    assert record.identity(bare) == record.identity(prefixed)


def test_sherpa_and_herwig_take_the_set_s_name():
    from runner.quantities import check_provider
    assert check_provider("lhapdf:bare", "MSTW2008lo68cl", "x") == "MSTW2008lo68cl"
    assert check_provider("lhapdf:bare", "LHAPDF6:MSTW2008lo68cl/3", "x") == "MSTW2008lo68cl/3"
    assert check_provider("lhapdf:set", "LHAPDF6:MSTW2008lo68cl", "x") == "MSTW2008lo68cl"
    with pytest.raises(HeimdallError, match="a set's name, not a member") as caught:
        check_provider("lhapdf:set", "MSTW2008lo68cl/3", "x")
    assert "card" in caught.value.hint
    with pytest.raises(HeimdallError, match="not installed"):
        check_provider("lhapdf:set", "LHAPDF6:NoSuchSet", "x")


def test_an_override_equal_to_the_base_card_does_not_change_the_identity(scratch):
    same = {"values": [3.2, 3.4], "tags": ["pt32", "pt34"], "key": {"pythia": "MultipartonInteractions:pT0Ref"}}
    _, _, without = plan(raw(quantities__pt0ref=same), scratch)
    _, _, redundant = plan(raw(quantities__pt0ref=same, static={"pt0ref": "pt32"}), scratch)
    _, _, real = plan(raw(quantities__pt0ref=same, static={"pt0ref": "pt34"}), scratch)
    ids = [record.identity(p) for p in (without, redundant, real)]
    assert ids[0] == ids[1] != ids[2]
    assert "MultipartonInteractions:pT0Ref = 3.2" in redundant.writes[redundant.rendered["pythia"].card_point]


def test_points_selects_by_tag_index_and_quantity():
    run, conf, points, _ = plans_of("Demo/jets", "energy_pdf")
    assert [p.name for p in sweep.select_points(run, conf, points, "MSTW08lo")][:1] == ["5x41_MSTW08lo"]
    assert len(sweep.select_points(run, conf, points, "energies=18x275")) == 4
    assert [p.index for p in sweep.select_points(run, conf, points, "3,16")] == [3, 16]
    with pytest.raises(HeimdallError, match="matches no point"):
        sweep.select_points(run, conf, points, "nothing")


# ── exclude (V42): values a sweep leaves out, by their 1-based place ───────────────────────────

THREE = {"values": [3.0, 3.2, 3.4], "tags": ["pt30", "pt32", "pt34"], "key": {"pythia": "MultipartonInteractions:pT0Ref"}}


def swept(scratch, **changes):
    run = config.parse(raw(**changes), scratch / "t.toml")
    return sweep.points(run, run.configuration(None))


def test_exclude_leaves_values_out_of_the_sweep(scratch):
    got = swept(scratch, quantities__pt0ref={**THREE, "exclude": [2]}, run__cfgs__one__sweeps=["pdf", "pt0ref"])
    assert [p.name for p in got] == ["MSTW08lo_pt30", "MSTW08lo_pt34", "NNPDF23lo_pt30", "NNPDF23lo_pt34"]
    assert [p.index for p in got] == [1, 2, 3, 4]                     # numbered over what is swept
    assert got[1].choice == {"pdf": 0, "pt0ref": 2}                    # the value keeps its own place


def test_an_entangled_group_loses_the_value_any_of_its_quantities_excludes(scratch):
    alphas = {"values": [0.118, 0.130], "tags": ["as118", "as130"], "key": {"pythia": "SigmaProcess:alphaSvalue"},
              "exclude": [1]}
    got = swept(scratch, quantities__alphas=alphas, run__cfgs__one__sweeps=[["pdf", "alphas"]])
    assert [p.name for p in got] == ["NNPDF23lo_as130"]


def test_a_static_value_may_still_be_an_excluded_one(scratch):
    _, _, p = plan(raw(quantities__pt0ref={**THREE, "exclude": [2]}, static={"pt0ref": "pt32"}), scratch)
    assert p.values["pt0ref"] == 1


def test_exclude_changes_no_remaining_point(scratch):
    _, _, before = plan(raw(quantities__pt0ref=THREE, run__cfgs__one__sweeps=["pt0ref"]), scratch)
    _, _, after = plan(raw(quantities__pt0ref={**THREE, "exclude": [2, 3]}, run__cfgs__one__sweeps=["pt0ref"]), scratch)
    assert (before.point.name, before.identity) == (after.point.name, after.identity)


@pytest.mark.parametrize("exclude, message", [
    ([0], "not a value's place"), ([4], "not a value's place"), ([True], "not a value's place"),
    (["pt32"], "not a value's place"), ([1, 2, 3], "leaves no value"),
])
def test_what_exclude_refuses(scratch, exclude, message):
    with pytest.raises(HeimdallError, match=message):
        swept(scratch, quantities__pt0ref={**THREE, "exclude": exclude}, run__cfgs__one__sweeps=["pt0ref"])


def test_an_entangled_group_with_nothing_left_is_refused(scratch):
    alphas = {"values": [0.118, 0.130], "tags": ["as118", "as130"], "key": {"pythia": "SigmaProcess:alphaSvalue"},
              "exclude": [2]}
    with pytest.raises(HeimdallError, match="no value"):
        swept(scratch, quantities__alphas=alphas, quantities__pdf={**raw()["quantities"]["pdf"], "exclude": [1]},
              run__cfgs__one__sweeps=[["pdf", "alphas"]])


def test_a_set_entry_names_its_folder():
    """[plot].sets (V159): a selector names its folder, a list is set<k>, a table its name; shapes refused."""
    from runner.errors import HeimdallError
    from runner.sweep import set_entries
    got = set_entries([[1, 2], "pdf=NNPDF23lo", "sh3_*", 7, {"name": "lo", "points": ["py8"]}], "w")
    assert [(s.name, s.selectors) for s in got] == [
        ("set1", [1, 2]), ("pdf-NNPDF23lo", ["pdf=NNPDF23lo"]), ("sh3_", ["sh3_*"]), ("#7", [7]), ("lo", ["py8"])]
    assert not any(s.axes for s in got)
    for bad in ([[]], [[0]], [{"name": "x"}], [{"name": "a/b", "points": [1]}], [[True]], ["all", "all"]):
        with pytest.raises(HeimdallError):
            set_entries(bad, "w")


# ── V163: sets of page axes and curve groups, each table an outer product of its quantities' values ──

FOUR = {   # four swept axes, as a study's generator × beam energies × event counts × PDFs (pT0Ref the generator's stand-in)
    "generator": {"values": [3.0, 3.2], "tags": ["py8", "sh3"], "labels": ["Pythia", "Sherpa"],
                  "key": {"pythia": "MultipartonInteractions:pT0Ref"}},
    "energies": {"values": [[20, 10], [60, 15], [275, 18]], "tags": ["10x20", "15x60", "18x275"]},
    "events": {"values": [10_000_000, 100_000_000, 100_000], "tags": ["10M", "100M", "100k"]},
    "pdf": {"values": [f"LHAPDF6:p{i}" for i in range(1, 6)], "tags": [f"pdf{i}" for i in range(1, 6)]},
}
SET1 = {"name": "set1", "pages": {"generator": "all", "energies": ["10x20", "15x60"]},
        "curves": {"events": ["10M", "100M", "100k"], "pdf": "all"}}
SET2 = {"name": "set2", "pages": {"events": "all"},
        "curves": [{"generator": "py8", "pdf": ["pdf1", "pdf2", "pdf5"]}, {"generator": "sh3", "pdf": ["pdf1", "pdf3", "pdf4"]}]}


def four(scratch):
    run = config.parse(raw(quantities=FOUR, run__cfgs__one__sweeps=["generator", "energies", "events", "pdf"]), scratch / "t.toml")
    return run, sweep.points(run, run.configuration(None))


def cells_of(run, points, entry, palette=("#a", "#b", "#c", "#d", "#e", "#f")):
    spec, = sweep.set_entries([entry], "w")
    sweep.check_set(run, spec, points)
    return sweep.set_cells(run, points, spec, list(palette))


def test_a_set_table_is_a_product_of_page_axes_and_of_curve_axes(scratch):
    """set1: a page per generator × chosen energy, in the order written; on each, every event count × pdf,
    the counts in their written order, outermost; labelled by both, the pdf coloured and the count dashed;
    a palette shorter than the colour axis is said."""
    run, points = four(scratch)
    cells, notes = cells_of(run, points, SET1, palette=list("abcde"))
    assert [c.key for c in cells] == ["py8_10x20", "py8_15x60", "sh3_10x20", "sh3_15x60"] and notes == []
    assert cells[0].text == "Pythia, 10x20"
    names = [m.name for m in cells[0].members]
    assert len(names) == 15 and names[:6] == [f"py8_10x20_10M_pdf{i}" for i in range(1, 6)] + ["py8_10x20_100M_pdf1"]
    assert names[-1] == "py8_10x20_100k_pdf5" and cells[0].labelled == [["events"], ["pdf"]]
    assert cells[0].roles == {"colour": "pdf", "line": "events"}
    assert notes == [] and cells_of(run, points, SET1, palette=["#a", "#b"])[1] == [
        "set set1: 36 curve(s) look like another on its page (py8_10x20_10M_pdf1 and py8_10x20_10M_pdf3 on py8_10x20): "
        'give them colours of their own, or the set a longer palette, style = { curves = { palette = ["#rrggbb", …] } }']
    looks = cells[3].looks                          # the same value, the same look, on every page
    assert looks["sh3_15x60_100M_pdf4"] == {"colour": "d", "line": "dashed"} == \
        {k: v for k, v in cells[0].looks["py8_10x20_100M_pdf4"].items()}


def test_a_list_of_curve_tables_is_their_union_in_order(scratch):
    """set2: py8 × {pdf1, pdf2, pdf5}, then sh3 × {pdf1, pdf3, pdf4}: 6 curves, not 2 × 5. energies, which
    neither names and which takes 3 values, pages too, and the stage is told."""
    run, points = four(scratch)
    cells, notes = cells_of(run, points, SET2)
    assert [c.key for c in cells][:4] == ["10M_10x20", "10M_15x60", "10M_18x275", "100M_10x20"] and len(cells) == 9
    assert [m.name for m in cells[0].members] == ["py8_10x20_10M_pdf1", "py8_10x20_10M_pdf2", "py8_10x20_10M_pdf5",
                                                  "sh3_10x20_10M_pdf1", "sh3_10x20_10M_pdf3", "sh3_10x20_10M_pdf4"]
    assert notes == ["set set2: energies is named by neither pages nor curves and takes several values: a page each"]
    fixed = {**SET2, "pages": {"events": "all", "energies": "18x275"}}
    assert [c.key for c in cells_of(run, points, fixed)[0]] == ["10M_18x275", "100M_18x275", "100k_18x275"]


@pytest.mark.parametrize("none", ["none", [], {}])
def test_pages_none_puts_every_curve_on_one_page(scratch, none):
    """V178: pages = "none" (or [] or {}): no page axis, a page per object holding every curve; what the curves
    leave out (energies, events) joins the curves, where without pages it would page, said."""
    run, points = four(scratch)
    cells, notes = cells_of(run, points, {**SET2, "pages": none})
    (cell,) = cells
    assert cell.key == "" and notes == [] and len(cell.members) == 6 * 3 * 3
    assert cell.labelled == [["generator"], ["pdf"], ["energies"], ["events"]]
    assert {m.name for m in cell.members} == {m.name for c in cells_of(run, points, SET2)[0] for m in c.members}
    only = {"pages": none, "curves": {"generator": "all", "pdf": "pdf1", "events": "10M", "energies": "10x20"}}
    (cell,), notes = cells_of(run, points, only)
    assert [m.name for m in cell.members] == ["py8_10x20_10M_pdf1", "sh3_10x20_10M_pdf1"] and notes == []


def test_a_filter_takes_globs_exclusions_and_numbers(scratch):
    run, points = four(scratch)
    entry = {"pages": {"generator": "py8", "energies": "10x20"}, "curves": {"events": 100_000, "pdf": ["!pdf2", "!pdf4"]}}
    (cell,), _ = cells_of(run, points, entry)
    assert [m.name for m in cell.members] == [f"py8_10x20_100k_pdf{i}" for i in (1, 3, 5)]
    assert cell.labelled == [["pdf"]] and cell.roles == {}       # one axis varies: the palette in turn
    globbed = {"pages": {"energies": "1*x*0", "generator": "py8"}, "curves": {"events": "10*", "pdf": "pdf1"}}
    cells, _ = cells_of(run, points, globbed)
    assert [c.key for c in cells] == ["10x20_py8", "15x60_py8"]
    assert [m.name for m in cells[0].members] == ["py8_10x20_10M_pdf1", "py8_10x20_100M_pdf1", "py8_10x20_100k_pdf1"]


def test_a_reference_is_moved_first_and_a_look_is_chosen(scratch):
    run, points = four(scratch)
    entry = {**SET2, "pages": {"events": "10M", "energies": "10x20"}, "reference": {"generator": "sh3", "pdf": "pdf3"},
             "look": {"colour": "generator"}}
    (cell,), notes = cells_of(run, points, entry)
    assert cell.members[0].name == "sh3_10x20_10M_pdf3"
    assert cell.looks["sh3_10x20_10M_pdf3"] == {"colour": "#b"} and cell.looks["py8_10x20_10M_pdf5"] == {"colour": "#a"}
    assert notes == ["set set2: 4 curve(s) look like another on its page (py8_10x20_10M_pdf1 and py8_10x20_10M_pdf2 on 10M_10x20): "
                     'give them colours of their own, or the set a longer palette, style = { curves = { palette = ["#rrggbb", …] } }']
    assert cells_of(run, points, {**entry, "look": "palette"})[0][0].looks == {}
    missed = {**entry, "reference": {"generator": "sh3", "pdf": "pdf2"}, "look": "palette"}   # each there, not together
    assert cells_of(run, points, missed)[1] == ["set set2: reference matches no curve on 1 of 1 page cell(s): "
                                                 "their first curve is the reference"]


def test_a_curves_value_may_carry_its_own_look(scratch):
    """{ tag, colour (or color), line, width }: the look of the curves that filter draws with it, over the set's
    look; the same value in another filter keeps the set's. { tags (or all = true), colours, lines, widths }:
    several values' looks in their order, one each."""
    run, points = four(scratch)
    entry = {"pages": {"events": "10M", "energies": "10x20"},
             "curves": [{"generator": "py8", "pdf": [{"tag": "pdf1", "color": "#d62728", "line": "dashed"}, "pdf2"]},
                        {"generator": "sh3", "pdf": ["pdf1", {"tag": "pdf*", "width": 2}]}]}
    (cell,), _ = cells_of(run, points, entry)
    assert [m.name for m in cell.members] == ["py8_10x20_10M_pdf1", "py8_10x20_10M_pdf2"] + \
        [f"sh3_10x20_10M_pdf{i}" for i in range(1, 6)]
    assert cell.roles == {"colour": "pdf", "line": "generator"}
    assert cell.looks["py8_10x20_10M_pdf1"] == {"colour": "#d62728", "line": "dashed"}
    assert cell.looks["py8_10x20_10M_pdf2"] == {"colour": "#b", "line": "solid"}
    assert cell.looks["sh3_10x20_10M_pdf1"] == {"colour": "#a", "line": "dashed", "width": 2}
    listed = {"pages": {"generator": "sh3", "events": "10M", "energies": "10x20"},
              "curves": {"pdf": {"all": True, "colors": ["#1", "#2", "#3", "#4", "#5"], "lines": ["dotted"] * 5}}}
    (cell,), _ = cells_of(run, points, listed)
    assert [cell.looks[m.name] for m in cell.members] == [{"colour": f"#{i}", "line": "dotted"} for i in range(1, 6)]
    picked = {**listed, "curves": {"pdf": {"tags": ["pdf4", "pdf2"], "colours": ["#4", "#2"]}}}
    (cell,), _ = cells_of(run, points, picked)
    assert {m.name: cell.looks[m.name]["colour"] for m in cell.members} == {"sh3_10x20_10M_pdf4": "#4", "sh3_10x20_10M_pdf2": "#2"}
    for bad, message in ((({"pages": {"pdf": [{"tag": "pdf1", "colour": "#000000"}]}}), "a curves filter's"),
                         ({"curves": {"pdf": {"all": True, "colours": ["#1", "#2"]}}}, r"pdf: 2 colours for 5 values"),
                         ({"curves": {"pdf": {"all": True, "shades": ["#1"]}}}, "values with their looks are"),
                         ({"curves": {"pdf": [{"tag": "pdf1"}]}}, "is { tag"),
                         ({"curves": {"pdf": [{"tag": "pdf1", "line": "wavy"}]}}, "style line = 'wavy' is not one")):
        with pytest.raises(HeimdallError, match=message):
            cells_of(run, points, bad)


@pytest.mark.parametrize("entry, message", [
    ({"pages": {"generatr": "all"}}, "'generatr', which is not a quantity"),
    ({"curves": {"events": ["10M", "1M"]}}, r"events = '1M', which is no value of it"),
    ({"pages": {"pdf": "all"}, "curves": {"pdf": "pdf1"}}, "names pdf in both pages and curves"),
    ({"curves": {"pdf": "all", "events": "all"}, "look": {"line": "pdf"}}, "there are 4 line styles"),
    ({"curves": {"pdf": "all"}, "look": {"colour": "events"}}, "not one of the set's curve axes"),
    ({"curves": {"pdf": "all"}, "colour": "pdf"}, "a set takes no 'colour'"),
    ({"curves": {"pdf": "all"}, "ratio": "yes"}, "'ratio' must be"),
    ({"name": "x"}, "a set names its points"),
    ({"curves": {"pdf": []}}, "names at least one value"),
    ({"pages": "nothing", "curves": {"pdf": "all"}}, 'or "none"'),
])
def test_what_a_set_table_refuses(scratch, entry, message):
    run, points = four(scratch)
    with pytest.raises(HeimdallError, match=message):
        cells_of(run, points, entry)


def test_a_value_no_point_has_is_refused_at_plan_time(scratch):
    run = config.parse(raw(quantities=FOUR, run__cfgs__one__sweeps=["generator", "pdf"]), scratch / "t.toml")
    points = sweep.points(run, run.configuration(None))
    spec, = sweep.set_entries([{"curves": {"events": "10M"}}], "w")
    with pytest.raises(HeimdallError, match="no point of the configuration sets"):
        sweep.check_set(run, spec, points)
    spec, = sweep.set_entries([{"curves": {"pdf": ["pdf1", "pdf9"]}}], "w")
    with pytest.raises(HeimdallError, match="no value of it") as refused:
        sweep.check_set(run, spec, points)
    assert "pdf: pdf1, pdf2, pdf3, pdf4, pdf5" in refused.value.hint



# ── V167: the totality set, named sets ───────────────────────────────────────────────────────────

def test_totality_curves_the_axis_closest_to_five(scratch):
    """The user's rule: the curves along the axis of 4–7 values closest to 5 (else the closest to 5, the earlier
    on a tie), the pages along every other axis with several values; plot_points, when set, win."""
    run, points = four(scratch)                                         # generator 2, energies 3, events 3, pdf 5
    conf = run.configuration(None)
    assert sweep.totality(conf, points) == {"pages": {"generator": "all", "energies": "all", "events": "all"},
                                            "curves": {"pdf": "all"}}
    two = config.parse(raw(quantities=FOUR, run__cfgs__one__sweeps=["generator", "energies"]), scratch / "t2.toml")
    assert sweep.totality(two.configuration(None), sweep.points(two, two.configuration(None))) == \
        {"pages": {"generator": "all"}, "curves": {"energies": "all"}}          # 3 is closer to 5 than 2
    paged = config.parse(raw(quantities=FOUR, run__cfgs__one__sweeps=["generator", "pdf"],
                             run__cfgs__one__plot_points=["pdf"]), scratch / "t3.toml")
    assert sweep.totality(paged.configuration(None), sweep.points(paged, paged.configuration(None))) == \
        {"pages": {"pdf": "all"}, "curves": {"generator": "all"}}
    alone = config.parse(raw(run__cfgs__one__sweeps=[]), scratch / "t4.toml")
    assert sweep.totality(alone.configuration(None), sweep.points(alone, alone.configuration(None))) == {"points": ["all"]}
    cells, notes = cells_of(run, points, {"name": "totality", **sweep.totality(conf, points)})
    assert len(cells) == 2 * 3 * 3 and all(len(c.members) == 5 for c in cells) and notes == []


def test_sets_may_be_named_tables(scratch):
    """[plot.sets.<name>] (V167): a set table each, or selectors, named by their key; the list form is named so too."""
    from runner.sweep import named_sets, set_entries
    got = set_entries({"lo": [1, 2], "pdfs": {"curves": {"pdf": "all"}}, "one": "pdf=pdf1"}, "w")
    assert [(s.name, s.selectors, s.axes) for s in got] == [("lo", [1, 2], False), ("pdfs", [], True), ("one", ["pdf=pdf1"], False)]
    assert named_sets([[1, 2], "all", {"name": "x", "curves": {"pdf": "all"}}]) == {
        "set1": {"points": [1, 2]}, "all": {"points": ["all"]}, "x": {"curves": {"pdf": "all"}}}
    with pytest.raises(HeimdallError, match="is named by its key"):
        set_entries({"lo": {"name": "hi", "points": [1]}}, "w")


def test_run_plot_is_a_gate_and_a_pick(scratch):
    """[run].plot (V167): true, false or the sets drawn; a configuration's own over [run]'s."""
    run = config.parse(raw(run__plot=False, run__cfgs__two={"tools": [["pythia", "rivet"]], "plot": ["totality"]}),
                       scratch / "t.toml")
    assert run.configuration("one").draw is False and run.configuration("two").draw == ["totality"]
    assert config.parse(raw(), scratch / "u.toml").configuration(None).draw is True


def test_stats_is_a_section_and_a_gate(scratch):
    """[stats] (V168) is checked when the file is read; [run].stats gates the statistics as [run].plot the pages."""
    run = config.parse(raw(stats={"normalise": "area", "reference": {"pdf": "NNPDF23lo"}}, run__stats=["totality"]),
                       scratch / "t.toml")
    assert run.stats == {"normalise": "area", "reference": {"pdf": "NNPDF23lo"}} and run.configuration(None).measure == ["totality"]
    for bad, message in (({"normalize": "area"}, "unknown key 'normalize'"), ({"reference": "first"}, "must be one of"),
                         ({"reference": {}}, "a filter is a table")):
        with pytest.raises(HeimdallError, match=message):
            config.parse(raw(stats=bad), scratch / "u.toml")
