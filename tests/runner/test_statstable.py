"""runner/statstable.py (V206): the statistics table out of plot.py. A page's numbers as rows, a set's
statistics.csv written and read back as the same rows, and its bar graphs and summary written."""

from __future__ import annotations

import json
import math
from pathlib import Path

from runner import plot, statstable


def page_with_numbers(folder: Path, name: str, numbers: list[dict]) -> plot.Page:
    """A drawn page as Paint leaves it: its config and, beside it, the numbers it measured (two curves, no data)."""
    config = folder / f"{name}.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("# a page\n", encoding="utf-8")
    config.with_name(config.name + ".stats.json").write_text(json.dumps({"reference": "curves", "curves": numbers}),
                                                             encoding="utf-8")
    curves = [{"label": label, "object": f"{point}/A/{name}"} for label, point in (("NNPDF 2.3", "p1"), ("MSTW 2008", "p2"))]
    return plot.Page(f"totality/{name}", config, folder / "root" / name, object=f"/A/{name}",
                     document={"curve": curves}, set="totality", rel=name)


NUMBERS = [{"reference": True, "bins": 12, "ndf": 0, "area": 2.5, "area_err": 0.1, "ref_area": 2.5, "cmp_area": 2.5,
            "abs_area": 0.0, "ratio_area": 0.0, "ratio_sum": 12.0, "ratio_width": 12.0, "chi2": None},
           {"reference": False, "bins": 12, "ndf": 11, "area": 3.0, "area_err": 0.2, "ref_area": 2.5, "cmp_area": 3.0,
            "abs_area": 0.6, "ratio_area": 2.4, "ratio_sum": 14.4, "ratio_width": 12.0, "chi2": 22.0}]


def same(a: list[dict], b: list[dict]) -> bool:
    def norm(rows):
        return [{k: ("nan" if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()} for r in rows]
    return norm(a) == norm(b)


def test_a_statistics_csv_reads_back_as_the_rows_it_was_written_from(tmp_path):
    pages = [page_with_numbers(tmp_path / "pages", name, NUMBERS) for name in ("d01-x01-y01", "d02-x01-y01")]
    rows = [r for p in pages for r in plot.statistics_of(p)]
    assert statstable.write_statistics(pages, tmp_path / "statistics.csv") == 4
    back = statstable.read(tmp_path / "statistics.csv")
    assert same(back, rows)
    assert back[0]["is_reference"] is True and back[1]["is_reference"] is False
    assert isinstance(back[1]["bins"], int) and isinstance(back[1]["ndf"], int) and math.isnan(back[0]["chi2"])
    assert list(back[0])[:len(statstable.STATISTIC_COLUMNS)] == list(statstable.STATISTIC_COLUMNS)    # the old columns first, in order
    assert list(back[0])[len(statstable.STATISTIC_COLUMNS):] == ["norm", "shape", "tilt", "worst"]   # then the new defaults
    assert all(math.isnan(r[k]) for r in back for k in ("norm", "shape", "tilt", "worst"))      # no measured bins in these numbers


def test_plot_still_names_what_moved():
    assert plot.statistics_of is statstable.statistics_of and plot.heading_of is statstable.heading_of
    assert plot.write_statistics is statstable.write_statistics and plot.STATISTIC_COLUMNS == statstable.STATISTIC_COLUMNS


def test_a_sets_numbers_are_its_csv_bar_graphs_and_summary(tmp_path):
    pages = [page_with_numbers(tmp_path / "pages", name, NUMBERS) for name in ("d01-x01-y01", "d02-x01-y01")]
    numbers = tmp_path / "statistics" / "totality"
    count, images = statstable.write_set(pages, numbers, ["png"])
    assert count == 4 and images == 3                                    # a bar graph a page, and the summary
    assert (numbers / "statistics.csv").is_file() and (numbers / "summary.html").is_file()
    assert sorted(p.name for p in (numbers / "bars").iterdir()) == ["d01-x01-y01.png", "d02-x01-y01.png"]
    assert statstable.write_set([], tmp_path / "empty", ["png"]) == (0, 0) and not (tmp_path / "empty").exists()


def measured_page(folder: Path, name: str, y_scale: float = 1.2) -> plot.Page:
    """A page whose stats.json carries `measured` bins: 10 bins, a falling reference, the second curve y_scale times it."""
    ref = [100.0 * math.exp(-0.3 * i) for i in range(10)]
    row = lambda y, i: [float(i), float(i + 1), y, 0.02 * y, ref[i], 0.02 * ref[i]]
    page = page_with_numbers(folder, name, NUMBERS)
    path = page.config.with_name(page.config.name + ".stats.json")
    made = json.loads(path.read_text(encoding="utf-8"))
    made["curves"][0]["measured"] = [row(ref[i], i) for i in range(10)]
    made["curves"][1]["measured"] = [row(y_scale * ref[i], i) for i in range(10)]
    path.write_text(json.dumps(made), encoding="utf-8")
    return page


def test_the_default_metrics_are_columns_computed_from_the_measured_bins(tmp_path):
    page = measured_page(tmp_path / "pages", "d01-x01-y01")
    rows = statstable.statistics_of(page)
    assert [r["norm"] for r in rows][0] == 0.0
    assert rows[1]["norm"] == __import__("pytest").approx(math.log(1.2))
    assert all(math.isfinite(r[k]) for r in rows for k in ("shape", "tilt", "worst"))
    assert rows[1]["shape"] > rows[0]["shape"]


def test_a_metric_named_beyond_the_defaults_is_a_column_too(tmp_path):
    page = measured_page(tmp_path / "pages", "d01-x01-y01")
    target = tmp_path / "statistics.csv"
    assert statstable.write_statistics([page], target, ["chi2_ndf", "norm", "js", "consensus"]) == 2
    back = statstable.read(target)
    assert list(back[0])[-3:] == ["norm", "js", "consensus"]
    assert math.isnan(back[1]["consensus"])                              # a pooled metric needs three curves; the page has two


def test_the_sidecar_says_what_the_columns_are(tmp_path):
    page = measured_page(tmp_path / "pages", "d01-x01-y01")
    target = tmp_path / "statistics.csv"
    statstable.write_statistics([page], target)
    side = json.loads((tmp_path / "statistics.json").read_text(encoding="utf-8"))
    assert side["format"] == 2 == statstable.FORMAT and statstable.format_of(target) == 2
    assert side["columns"] == list(statstable.read(target)[0])
    assert set(side["metrics"]) == {"chi2_ndf", "norm", "shape", "tilt", "worst", "rel_abs_area", "area_ratio", "ratio_mean", "ratio_dev"}   # the old columns that are metrics too
    norm = side["metrics"]["norm"]
    assert norm["purpose"] == "normalisation" and norm["thresholds"] == [0.02, 0.15] and norm["default"] and norm["note"]


def test_a_csv_from_before_format_2_has_no_sidecar_and_reads_as_format_1(tmp_path):
    old = tmp_path / "statistics.csv"
    old.write_text(",".join(statstable.STATISTIC_COLUMNS) + "\n"
                   + "d01,em,/A/d01,NNPDF,p1,Data,False,9,1.0,0.1,2.0,1.0,1.0,0.5,0.5,0.4,0.3,20.0,9,2.2\n", encoding="utf-8")
    assert statstable.format_of(old) == 1 and statstable.sidecar(old) is None
    rows = statstable.read(old)
    assert list(rows[0]) == list(statstable.STATISTIC_COLUMNS) and rows[0]["chi2_ndf"] == 2.2 and rows[0]["ndf"] == 9
    assert statstable.columns_for(["norm", "chi2_ndf", "norm"]) == [*statstable.STATISTIC_COLUMNS, "norm"]


def test_a_set_is_scored_with_the_errands_score_and_its_own_laid_over_it(tmp_path):
    from types import SimpleNamespace
    errand = SimpleNamespace(plot={"sets": {"mine": {"points": ["a=1"], "score": {"veto": 2.0}}, "other": {"points": ["a=2"]}}},
                             score={"mean": "median", "veto": 9.0}, stats={"metrics": ["norm"]})
    assert statstable.score_of(errand, "mine") == {"mean": "median", "veto": 2.0}
    assert statstable.score_of(errand, "other") == {"mean": "median", "veto": 9.0}
    assert statstable.score_of(errand, "totality") == {"mean": "median", "veto": 9.0}      # a set it does not name
    assert statstable.score_of(SimpleNamespace(plot={}, score={}), "totality") == {}


def test_the_columns_are_the_stats_metrics_and_every_metric_scored_and_the_table_keeps_how_it_was_scored(tmp_path):
    assert statstable.metric_names(None, None) == list(statstable.default_metrics())
    score = {"metrics": ["chi2_ndf", "rel_abs_area"], "veto": 3.0}
    assert statstable.metric_names({"metrics": ["norm"]}, score) == ["norm", "chi2_ndf", "rel_abs_area"]
    pages = [page_with_numbers(tmp_path / "pages", "d01-x01-y01", NUMBERS)]
    numbers = tmp_path / "statistics" / "totality"
    statstable.write_set(pages, numbers, ["png"], None, ["chi2_ndf", "rel_abs_area"], score)
    side = statstable.sidecar(numbers / "statistics.csv")
    assert side["score"] == score and "rel_abs_area" in side["metrics"]
    plain = tmp_path / "plain"
    statstable.write_set(pages, plain, ["png"])
    assert "score" not in statstable.sidecar(plain / "statistics.csv")                  # no settings: the defaults, unsaid


def test_a_points_axes_are_read_from_the_run_s_plot_document_and_kept_in_the_sidecar(tmp_path):
    run = tmp_path / "run"
    (run / "statistics" / "totality").mkdir(parents=True)
    (run / "plot.toml").write_text(
        '[quantities.generator]\npoints = [{ tag = "py8", value = "pythia" }, { tag = "sh3", value = "sherpa" }]\n'
        '[quantities.pdf]\npoints = [{ tag = "A", value = "a" }, { tag = "B", value = "b" }]\n'
        '[members.py8_B]\nchoice = { generator = 0, pdf = 1 }\n[members.sh3_A]\nchoice = { generator = 1, pdf = 0 }\n'
        '[members.odd]\nchoice = { pdf = 7 }\n', encoding="utf-8")
    numbers = run / "statistics" / "totality"
    axes = statstable.point_axes(numbers)
    assert axes == {"py8_B": {"generator": "py8", "pdf": "B"}, "sh3_A": {"generator": "sh3", "pdf": "A"}}
    assert statstable.point_axes(tmp_path / "nowhere" / "x") == {}
    pages = [page_with_numbers(tmp_path / "pages", "d01-x01-y01", NUMBERS)]
    statstable.write_set(pages, numbers, ["png"])
    assert statstable.sidecar(numbers / "statistics.csv")["axes"] == axes
