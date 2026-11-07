"""plot/figures/curves.py and stats/merge.py: curves merged bin by bin (set-merge). The YODA files are written by hand as Estimate1D text, so each
number is a hand calculation; needs YODA's Python (the stack)."""

from __future__ import annotations

import math

import pytest

yoda = pytest.importorskip("yoda")

from pathlib import Path  # noqa: E402

from runner import plugins  # noqa: E402
from runner.errors import HeimdallError  # noqa: E402

merge = plugins.load(Path(__file__).resolve().parents[2] / "framework" / "plot" / "figures" / "curves.py", "curves")

EDGES = [0.0, 1.0, 2.0, 3.0]


def text(values, errs, path="/ana/d01-x01-y01", edges=EDGES) -> str:
    rows = "".join(f"{v:.6e} \t{-e:.6e}\t{e:.6e} \t\n" for v, e in zip(values, errs))
    return (f"BEGIN YODA_ESTIMATE1D_V3 {path}\nPath: {path}\nTitle: ~\nType: Estimate1D\n---\n"
            f"Edges(A1): [{', '.join(f'{e:.6e}' for e in edges)}]\n# value      \ttotalDn      \ttotalUp      \t\n"
            f"ErrorLabels: [\"\"]\n" + "nan          \t---          \t---          \t\n" + rows
            + "nan          \t---          \t---          \t\nEND YODA_ESTIMATE1D_V3\n")


def make(tmp_path, name, values, errs, **kw):
    path = tmp_path / f"{name}.yoda"
    path.write_text(text(values, errs, **kw), encoding="utf-8")
    return path


def bins(path, obj="/ana/d01-x01-y01"):
    ao = yoda.read(str(path))[obj]
    return [(b.val(), b.totalErrAvg()) for b in ao.bins()]


def test_two_identical_curves_merge_to_the_curve_with_its_error_over_root_two(tmp_path):
    a = make(tmp_path, "a", [4.0, 6.0, 8.0], [1.0, 1.0, 2.0])
    b = make(tmp_path, "b", [4.0, 6.0, 8.0], [1.0, 1.0, 2.0])
    merge.merge_yoda([a, b], tmp_path / "m.yoda")
    got = bins(tmp_path / "m.yoda")
    assert [v for v, _ in got] == pytest.approx([4.0, 6.0, 8.0])
    assert [e for _, e in got] == pytest.approx([1 / math.sqrt(2), 1 / math.sqrt(2), 2 / math.sqrt(2)])


def test_linear_is_the_bin_mean_and_its_error_the_quadrature_over_k(tmp_path):
    files = [make(tmp_path, n, v, e) for n, v, e in
             (("a", [2.0, 4.0, 6.0], [3.0, 3.0, 3.0]), ("b", [4.0, 4.0, 8.0], [4.0, 4.0, 4.0]), ("c", [6.0, 4.0, 10.0], [0.0, 0.0, 0.0]))]
    merge.merge_yoda(files, tmp_path / "m.yoda", "linear")
    got = bins(tmp_path / "m.yoda")
    assert [v for v, _ in got] == pytest.approx([4.0, 4.0, 8.0])
    assert got[0][1] == pytest.approx(math.sqrt(9 + 16 + 0) / 3)


def test_geometric_of_two_exponentials_is_the_exponential_of_the_mean_slope(tmp_path):
    centres = [0.5, 1.5, 2.5]
    a = make(tmp_path, "a", [math.exp(-1.0 * x) for x in centres], [0.0] * 3)
    b = make(tmp_path, "b", [math.exp(-3.0 * x) for x in centres], [0.0] * 3)
    merge.merge_yoda([a, b], tmp_path / "m.yoda", "geometric")
    assert [v for v, _ in bins(tmp_path / "m.yoda")] == pytest.approx([math.exp(-2.0 * x) for x in centres])


def test_geometric_refuses_a_zero_bin_naming_it_and_a_floor_allows_it(tmp_path):
    a = make(tmp_path, "a", [1.0, 0.0, 1.0], [0.0] * 3)
    b = make(tmp_path, "b", [1.0, 1.0, 1.0], [0.0] * 3)
    with pytest.raises(HeimdallError, match=r"/ana/d01-x01-y01: .*above zero.*\(bin 2\)"):
        merge.merge_yoda([a, b], tmp_path / "m.yoda", "geometric")
    merge.merge_yoda([a, b], tmp_path / "m.yoda", "geometric", {"floor": 1e-4})
    assert bins(tmp_path / "m.yoda")[1][0] == pytest.approx(math.sqrt(1e-4))


def test_trimmed_with_fewer_than_four_curves_is_refused(tmp_path):
    files = [make(tmp_path, n, [1.0, 2.0, 3.0], [0.1] * 3) for n in "abc"]
    with pytest.raises(HeimdallError, match="trimmed|alpha"):
        merge.merge_yoda(files, tmp_path / "m.yoda", "trimmed")


def test_a_setting_the_mean_does_not_take_is_refused(tmp_path):
    files = [make(tmp_path, n, [1.0, 2.0, 3.0], [0.1] * 3) for n in "ab"]
    with pytest.raises(HeimdallError, match="takes no setting 'alpha'"):
        merge.merge_yoda(files, tmp_path / "m.yoda", "linear", {"alpha": 0.1})


def test_different_binnings_are_refused_naming_the_object_and_the_edge(tmp_path):
    a = make(tmp_path, "a", [1.0, 2.0, 3.0], [0.1] * 3)
    b = make(tmp_path, "b", [1.0, 2.0, 3.0], [0.1] * 3, edges=[0.0, 1.0, 2.0, 3.5])
    with pytest.raises(HeimdallError, match=r"/ana/d01-x01-y01 is binned differently in .*b.yoda.*first difference at edge 3"):
        merge.merge_yoda([a, b], tmp_path / "m.yoda")


def test_only_the_objects_every_curve_has_are_merged_and_counters_and_raws_are_left(tmp_path):
    a = tmp_path / "a.yoda"
    b = tmp_path / "b.yoda"
    a.write_text(text([1.0, 2.0, 3.0], [0.1] * 3) + text([1.0, 1.0, 1.0], [0.1] * 3, path="/RAW/ana/d01-x01-y01")
                 + text([5.0, 5.0, 5.0], [0.1] * 3, path="/ana/only-a"), encoding="utf-8")
    b.write_text(text([3.0, 2.0, 1.0], [0.1] * 3), encoding="utf-8")
    assert merge.merge_yoda([a, b], tmp_path / "m.yoda") == ["/ana/d01-x01-y01"]
    assert list(yoda.read(str(tmp_path / "m.yoda"))) == ["/ana/d01-x01-y01"]


def test_curves_with_nothing_in_common_are_refused(tmp_path):
    a = make(tmp_path, "a", [1.0, 2.0, 3.0], [0.1] * 3, path="/ana/one")
    b = make(tmp_path, "b", [1.0, 2.0, 3.0], [0.1] * 3, path="/ana/two")
    with pytest.raises(HeimdallError, match="share no 1D object"):
        merge.merge_yoda([a, b], tmp_path / "m.yoda")


def test_a_wasserstein_merge_of_a_shifted_peak_keeps_one_peak_and_the_mean_yield(tmp_path):
    edges = [float(i) for i in range(11)]
    peak = lambda c: [math.exp(-((x + 0.5 - c) ** 2) / 2.0) for x in range(10)]            # noqa: E731
    a = make(tmp_path, "a", peak(3.0), [0.01] * 10, edges=edges)
    b = make(tmp_path, "b", peak(6.0), [0.01] * 10, edges=edges)
    merge.merge_yoda([a, b], tmp_path / "m.yoda", "wasserstein")
    values = [v for v, _ in bins(tmp_path / "m.yoda")]
    top = [i for i in range(1, 9) if values[i] > values[i - 1] and values[i] >= values[i + 1]]
    assert len(top) == 1 and top[0] in (4, 5)
    assert sum(values) == pytest.approx(sum(peak(3.0)) / 2 + sum(peak(6.0)) / 2, rel=1e-6)


def test_the_minmax_band_is_the_lowest_and_highest_member_in_each_bin(tmp_path):
    files = [make(tmp_path, n, v, [0.0] * 3) for n, v in (("a", [1.0, 5.0, 3.0]), ("b", [2.0, 4.0, 9.0]), ("c", [3.0, 6.0, 1.0]))]
    merge.band_yoda(files, tmp_path / "lo.yoda", tmp_path / "hi.yoda", "minmax")
    assert [v for v, _ in bins(tmp_path / "lo.yoda")] == [1.0, 4.0, 1.0]
    assert [v for v, _ in bins(tmp_path / "hi.yoda")] == [3.0, 6.0, 9.0]


def test_the_std_band_is_one_sample_standard_deviation_about_the_mean(tmp_path):
    files = [make(tmp_path, n, [v] * 3, [0.0] * 3) for n, v in (("a", 1.0), ("b", 2.0), ("c", 3.0))]
    merge.band_yoda(files, tmp_path / "lo.yoda", tmp_path / "hi.yoda", "std")
    assert [v for v, _ in bins(tmp_path / "lo.yoda")] == pytest.approx([1.0] * 3)
    assert [v for v, _ in bins(tmp_path / "hi.yoda")] == pytest.approx([3.0] * 3)


def test_a_std_band_of_two_curves_is_refused_and_a_wrong_kind_too(tmp_path):
    files = [make(tmp_path, n, [1.0, 2.0, 3.0], [0.0] * 3) for n in "ab"]
    with pytest.raises(HeimdallError, match="at least 3 curves"):
        merge.band_yoda(files, tmp_path / "lo.yoda", tmp_path / "hi.yoda", "std")
    with pytest.raises(HeimdallError, match="a band is one of"):
        merge.band_yoda(files, tmp_path / "lo.yoda", tmp_path / "hi.yoda", "wide")


def test_one_curve_is_not_a_merge(tmp_path):
    with pytest.raises(HeimdallError, match="at least two"):
        merge.merge_yoda([make(tmp_path, "a", [1.0, 2.0, 3.0], [0.1] * 3)], tmp_path / "m.yoda")
