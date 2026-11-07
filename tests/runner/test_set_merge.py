"""A set's `merge` (set-merge): a quantity's values become one curve. The shapes and refusals, and the groups a set's
cells hold: the points are the sweep's, so nothing runs."""

from __future__ import annotations

import pytest

from runner import sweep
from runner.errors import HeimdallError

from helpers import beside, parse, raw

PDFS = {"values": ["LHAPDF6:A", "LHAPDF6:B", "LHAPDF6:C", "LHAPDF6:D"], "tags": ["a", "b", "c", "d"]}
GEN = {"values": ["pythia", "herwig"], "tags": ["py", "hw"]}


@pytest.fixture(autouse=True)
def cards(scratch):
    beside(scratch)


def sweep_of(scratch, **changes):
    data = raw(errand__cfgs__one__sweeps=["gen", "pdf"], quantities__pdf=PDFS, quantities__gen=GEN, **changes)
    errand = parse(data, scratch)
    return errand, sweep.points(errand, errand.configuration(None))


def spec_of(table: dict, name: str = "m"):
    return sweep.set_entries({name: table}, "w")[0]


def cells_of(scratch, table: dict):
    errand, points = sweep_of(scratch)
    spec = spec_of(table)
    sweep.check_set(errand, spec, points)
    cells, notes = sweep.set_cells(errand, points, spec)
    return errand, cells, notes


def names(cell) -> list[str]:
    return [getattr(m, "point", m).name for m in cell.members]


def test_a_merge_entry_is_one_quantity_beside_how_label_tag_band():
    spec = spec_of({"curves": {"gen": "all"}, "merge": [{"pdf": ["a", "b"], "label": "Both", "tag": "ab", "band": "minmax"},
                                                          {"pdf": "all", "how": "median"}]})
    first, second = spec.merge
    assert (first.quantity, first.what, first.how, first.label, first.tag, first.band) == ("pdf", ["a", "b"], "linear", "Both", "ab", "minmax")
    assert second.how == "median" and second.band is False and spec.axes


@pytest.mark.parametrize("bad, match", [
    ({"merge": []}, "merge is an entry"),
    ({"merge": [{"how": "linear"}]}, "names one quantity"),
    ({"merge": [{"pdf": "all", "gen": "all"}]}, "names one quantity, not 2"),
    ({"merge": [{"pdf": "all", "how": "medain"}]}, "no way to join curves called 'medain'"),
    ({"merge": [{"pdf": "all", "band": "wide"}]}, "band is false"),
    ({"merge": [{"pdf": "all", "band": True}]}, "band is false"),
    ({"merge": [{"pdf": "all", "tag": "a b"}]}, "letters, digits"),
    ({"merge": [{"pdf": "all", "label": ""}]}, "label is a string"),
    ({"pages": {"pdf": "all"}, "merge": {"pdf": "all"}}, "pdf in merge and in pages"),
    ({"curves": {"pdf": "all"}, "merge": {"pdf": "all"}}, "pdf in merge and in curves"),
])
def test_a_wrong_merge_is_refused_naming_it(bad, match):
    with pytest.raises(HeimdallError, match=match):
        spec_of(bad)


def test_a_misspelt_how_says_what_it_may_be():
    with pytest.raises(HeimdallError) as caught:
        spec_of({"merge": {"pdf": "all", "how": "combin"}})
    assert "combine" in caught.value.hint


def test_all_of_a_quantity_merges_it_per_combination_of_the_other_axes(scratch):
    _, cells, notes = cells_of(scratch, {"pages": "none", "merge": {"pdf": "all", "tag": "pdfs", "label": "All PDFs"}})
    (cell,) = cells
    assert names(cell) == ["py_pdfs", "hw_pdfs"] and notes == []
    py, hw = cell.members
    assert [m.name for m in py.leaves] == ["py_a", "py_b", "py_c", "py_d"] and hw.values == {"gen": 1}
    assert "pdf" not in py.point.choice and py.point.stage == "merged" and py.label == "All PDFs"


def test_a_list_merges_those_values_and_leaves_the_others_as_they_are(scratch):
    _, cells, _ = cells_of(scratch, {"pages": "none", "curves": {"gen": "py"}, "merge": {"pdf": ["a", "b"], "tag": "ab"}})
    (cell,) = cells
    assert names(cell) == ["py_ab", "py_c", "py_d"]
    assert [m.name for m in cell.members[0].leaves] == ["py_a", "py_b"]
    assert cell.labelled == [["gen", "pdf"]] or cell.labelled == [["pdf"]] or cell.labelled == [["gen"]]


def test_one_member_stays_a_plain_point(scratch):
    _, cells, _ = cells_of(scratch, {"pages": "none", "curves": {"gen": "py"}, "merge": {"pdf": ["a", "zzz*"][:1]}})
    assert names(cells[0]) == ["py_a", "py_b", "py_c", "py_d"]


def test_entries_apply_in_the_order_written_and_nest(scratch):
    _, cells, _ = cells_of(scratch, {"pages": "none", "merge": [{"pdf": ["a", "b"], "tag": "ab"},
                                                                  {"gen": "all", "tag": "gens"}]})
    (cell,) = cells
    assert names(cell) == ["ab_gens", "c_gens", "d_gens"]
    group = cell.members[0]
    assert [m.name for m in group.members[0].leaves] == ["py_a", "py_b"]       # the inner group first
    assert [m.name for m in group.leaves] == ["py_a", "py_b", "hw_a", "hw_b"]
    assert [m.name for m in cell.members[1].leaves] == ["py_c", "hw_c"]


def test_a_merged_quantity_does_not_page_the_set(scratch):
    _, cells, notes = cells_of(scratch, {"curves": {"gen": "all"}, "merge": {"pdf": "all"}})
    assert [c.key for c in cells] == [""] and not notes


def test_a_pages_axis_still_pages_a_merged_set(scratch):
    _, cells, _ = cells_of(scratch, {"pages": {"gen": "all"}, "merge": {"pdf": "all"}})
    assert [c.key for c in cells] == ["py", "hw"] and [names(c) for c in cells] == [["py_pdf_merged"], ["hw_pdf_merged"]]


@pytest.mark.parametrize("table, match", [
    ({"merge": {"nope": "all"}}, "not a quantity"),
    ({"merge": {"pdf": ["z"]}}, "no value of it"),
    ({"merge": {"pdf": "all", "tag": "a"}}, "one of pdf.s already"),
    ({"merge": [{"pdf": ["a", "b"]}, {"pdf": ["c", "d"]}]}, "share the tag"),
])
def test_a_merge_the_points_cannot_make_is_refused_at_plan_time(scratch, table, match):
    errand, points = sweep_of(scratch)
    with pytest.raises(HeimdallError, match=match):
        sweep.check_set(errand, spec_of({"pages": "none", **table}), points)


def test_a_combined_quantity_cannot_be_merged_again(scratch):
    errand, points = sweep_of(scratch)
    with pytest.raises(HeimdallError, match="combines away"):
        sweep.check_set(errand, spec_of({"merge": {"pdf": "all"}}), points, combined={"pdf"})


def test_two_entries_of_one_quantity_need_a_tag_each_and_may_have_them(scratch):
    errand, points = sweep_of(scratch)
    spec = spec_of({"pages": "none", "curves": {"gen": "py"}, "merge": [{"pdf": ["a", "b"], "tag": "ab"}, {"pdf": ["c", "d"], "tag": "cd"}]})
    sweep.check_set(errand, spec, points)
    cells, _ = sweep.set_cells(errand, points, spec)
    assert names(cells[0]) == ["py_ab", "py_cd"]


def test_plan_lists_each_merged_curve_with_the_points_it_is_made_of(scratch):
    from runner import plot
    errand, points = sweep_of(scratch)
    errand.plot = {"sets": {"m": {"pages": "none", "curves": {"gen": "all"}, "merge": {"pdf": ["a", "b"], "label": "A and B", "tag": "ab"}}}}
    configuration = errand.configuration(None)
    here = plot.run_folders(errand, configuration)
    members = []
    for p in points:
        yoda = scratch / f"{p.name}.yoda"
        yoda.write_text("", encoding="utf-8")
        members.append(plot.Member(p, {**p.choice}, here, yoda, {}, {}, p.name, p.name))
    text = "\n".join(plot.plan_lines(errand, configuration, members))
    assert "set m ([plot]): 1 page cell(s), 6 curve(s)" in text
    assert "A and B (merges py_a, py_b; linear)" in text and "A and B (merges hw_a, hw_b; linear)" in text
    assert text.count("merges") == 2 and "py_c" not in text.split("merges")[0]
