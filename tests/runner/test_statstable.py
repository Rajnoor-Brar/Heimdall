"""runner/statstable.py (V206): the statistics table out of plot.py. A page's numbers as rows, a set's
statistics.csv written and read back as the same rows, and its bar graphs and summary written."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

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
    rows = [r for p in pages for r in statstable.statistics_of(p)]
    assert statstable.write_statistics(pages, tmp_path / "statistics.csv") == 4
    back = statstable.read(tmp_path / "statistics.csv")
    assert same(back, rows)
    assert back[0]["is_reference"] is True and back[1]["is_reference"] is False
    assert isinstance(back[1]["bins"], int) and isinstance(back[1]["ndf"], int) and math.isnan(back[0]["chi2"])
    assert list(back[0])[:len(statstable.STATISTIC_COLUMNS)] == list(statstable.STATISTIC_COLUMNS)    # the old columns first, in order
    later = ["chi2_sigma", "poisson_dev", "log_yield_ratio", "log_dev_shrunk", "log_dev_l4", "tilt", "pull_autocorr", "peak_pull2",
             "log_ratio_roughness", "n_eff", "peak_bin_ratio", "yield_sign"]
    assert list(back[0])[len(statstable.STATISTIC_COLUMNS):] == later        # then the nine defaults, n_eff shown, the two gates
    assert all(math.isnan(r[k]) for r in back for k in later)                 # no measured bins in these numbers


def test_a_sets_numbers_are_its_csv_bar_graphs_and_summary(tmp_path):
    pages = [page_with_numbers(tmp_path / "pages", name, NUMBERS) for name in ("d01-x01-y01", "d02-x01-y01")]
    numbers = tmp_path / "statistics" / "totality"
    count, images = statstable.write_set(pages, numbers, ["png"], ranking={"metrics": ["chi2_ndf"]})
    assert count == 4 and images == 3                                    # a bar graph a page, and the summary
    assert (numbers / "statistics.csv").is_file() and (numbers / "summary.html").is_file()
    assert sorted(p.name for p in (numbers / "bars").iterdir()) == ["d01-x01-y01.png", "d02-x01-y01.png"]
    assert statstable.write_set([], tmp_path / "empty", ["png"]) == (0, 0) and not (tmp_path / "empty").exists()
    bare = tmp_path / "statistics" / "bare"                              # no measured bins: no default metric has a number
    assert statstable.write_set(pages, bare, ["png"]) == (4, 3) and not (bare / "summary.html").exists()   # its facts page alone


def test_a_commands_head_to_head_flag_reaches_the_sidecar_with_its_source(tmp_path):
    pages = [page_with_numbers(tmp_path / "pages", name, NUMBERS) for name in ("d01-x01-y01", "d02-x01-y01")]
    numbers = tmp_path / "statistics" / "totality"
    with statstable.flagged({"head_to_head": "all"}):                     # `heimdall plot --stats-only --head-to-head all`
        statstable.write_set(pages, numbers, ["png"], ranking={"metrics": ["chi2_ndf"]})
    side = json.loads((numbers / "statistics.json").read_text(encoding="utf-8"))
    assert side["ranking"]["head_to_head"] == "all" and side["ranking_sources"]["head_to_head"] == "--head-to-head"
    assert {"name": "head_to_head", "value": "all", "source": "--head-to-head"}.items() <= next(
        c for c in side["method"]["optin"] if c["name"] == "head_to_head").items()
    assert statstable.FLAGS.get() == {}                                    # the flag is the command's alone


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
    assert [r["log_yield_ratio"] for r in rows][0] == 0.0
    assert rows[1]["log_yield_ratio"] == __import__("pytest").approx(math.log(1.2))
    assert all(math.isfinite(r[k]) for r in rows for k in ("log_dev_shrunk", "tilt", "peak_pull2"))
    assert rows[1]["log_dev_shrunk"] > rows[0]["log_dev_shrunk"]


def test_a_metric_named_beyond_the_defaults_is_a_column_too(tmp_path):
    page = measured_page(tmp_path / "pages", "d01-x01-y01")
    target = tmp_path / "statistics.csv"
    assert statstable.write_statistics([page], target, ["chi2_ndf", "log_yield_ratio", "js_divergence", "consensus_dev"]) == 2
    back = statstable.read(target)
    assert list(back[0])[-3:] == ["log_yield_ratio", "js_divergence", "consensus_dev"]
    assert math.isnan(back[1]["consensus_dev"])                              # a pooled metric needs three curves; the page has two


def test_the_sidecar_says_what_the_columns_are(tmp_path):
    page = measured_page(tmp_path / "pages", "d01-x01-y01")
    target = tmp_path / "statistics.csv"
    statstable.write_statistics([page], target)
    side = json.loads((tmp_path / "statistics.json").read_text(encoding="utf-8"))
    assert side["format"] == 3 == statstable.FORMAT and statstable.format_of(target) == 3
    assert side["columns"] == list(statstable.read(target)[0])
    assert set(side["metrics"]) == {"chi2_ndf", "yield_weighted_abs_dev", "yield_ratio", "mean_bin_ratio", "mean_abs_ratio_dev",
                                    "chi2_sigma", "poisson_dev", "log_yield_ratio", "log_dev_shrunk", "log_dev_l4", "tilt",
                                    "pull_autocorr", "peak_pull2", "log_ratio_roughness", "n_eff", "peak_bin_ratio",
                                    "yield_sign"}   # the old columns that are metrics too, the nine, n_eff, the gates
    norm = side["metrics"]["log_yield_ratio"]
    assert norm["polarity"] == "lower" and norm["phrase"] == "lower is better" and norm["scale"] == "linear"
    assert norm["category"] == "normalisation" and norm["thresholds"] == [0.02, 0.15] and norm["default"] and norm["note"]
    assert norm["gate"] is None and not norm["shown"] and side["metrics"]["yield_sign"]["gate"] == 1.0


def test_a_csv_from_before_format_2_has_no_sidecar_and_reads_as_format_1(tmp_path):
    old = tmp_path / "statistics.csv"
    old.write_text(",".join(statstable.STATISTIC_COLUMNS) + "\n"
                   + "d01,em,/A/d01,NNPDF,p1,Data,False,9,1.0,0.1,2.0,1.0,1.0,0.5,0.5,0.4,0.3,20.0,9,2.2\n", encoding="utf-8")
    assert statstable.format_of(old) == 1 and statstable.sidecar(old) is None
    rows = statstable.read(old)
    assert list(rows[0]) == list(statstable.STATISTIC_COLUMNS) and rows[0]["chi2_ndf"] == 2.2 and rows[0]["ndf"] == 9
    assert statstable.columns_for(["log_yield_ratio", "chi2_ndf", "log_yield_ratio"]) == [*statstable.STATISTIC_COLUMNS, "log_yield_ratio"]


def test_a_set_is_ranked_with_the_errands_ranking_and_its_own_laid_over_it(tmp_path):
    from types import SimpleNamespace
    errand = SimpleNamespace(plot={"sets": {"mine": {"points": ["a=1"], "ranking": {"veto_loss": 2.0}}, "other": {"points": ["a=2"]}}},
                             ranking={"over_pages": "median", "veto_loss": 9.0}, stats={"metrics": ["log_yield_ratio"]})
    assert statstable.ranking_of(errand, "mine") == {"over_pages": "median", "veto_loss": 2.0}
    assert statstable.ranking_of(errand, "other") == {"over_pages": "median", "veto_loss": 9.0}
    assert statstable.ranking_of(errand, "totality") == {"over_pages": "median", "veto_loss": 9.0}      # a set it does not name
    assert statstable.ranking_of(SimpleNamespace(plot={}, ranking={}), "totality") == {}


def test_the_columns_are_the_stats_metrics_and_every_metric_scored_and_the_table_keeps_how_it_was_scored(tmp_path):
    assert statstable.metric_names(None, None) == list(statstable.default_metrics())
    score = {"metrics": ["chi2_ndf", "yield_weighted_abs_dev"], "veto_loss": 3.0}
    assert statstable.metric_names({"metrics": ["log_yield_ratio"]}, score) == ["log_yield_ratio", "chi2_ndf", "yield_weighted_abs_dev",
                                                                                 "peak_bin_ratio", "yield_sign"]   # the gates in use
    assert statstable.metric_names({"metrics": ["log_yield_ratio"]}, {**score, "gates": False})[-1] == "yield_weighted_abs_dev"
    pages = [page_with_numbers(tmp_path / "pages", "d01-x01-y01", NUMBERS)]
    numbers = tmp_path / "statistics" / "totality"
    statstable.write_set(pages, numbers, ["png"], None, ["chi2_ndf", "yield_weighted_abs_dev"], score)
    side = statstable.sidecar(numbers / "statistics.csv")
    assert side["ranking"] == score and "yield_weighted_abs_dev" in side["metrics"]
    plain = tmp_path / "plain"
    statstable.write_set(pages, plain, ["png"])
    assert "ranking" not in statstable.sidecar(plain / "statistics.csv")                  # no settings: the defaults, unsaid


def test_a_points_values_are_read_from_the_run_s_plot_document_and_kept_in_the_sidecar(tmp_path):
    run = tmp_path / "run"
    (run / "statistics" / "totality").mkdir(parents=True)
    (run / "plot.toml").write_text(
        '[quantities.generator]\npoints = [{ tag = "py8", value = "pythia" }, { tag = "sh3", value = "sherpa" }]\n'
        '[quantities.pdf]\npoints = [{ tag = "A", value = "a" }, { tag = "B", value = "b" }]\n'
        '[members.py8_B]\nchoice = { generator = 0, pdf = 1 }\n[members.sh3_A]\nchoice = { generator = 1, pdf = 0 }\n'
        '[members.odd]\nchoice = { pdf = 7 }\n', encoding="utf-8")
    numbers = run / "statistics" / "totality"
    axes = statstable.point_values(numbers)
    assert axes == {"py8_B": {"generator": "py8", "pdf": "B"}, "sh3_A": {"generator": "sh3", "pdf": "A"}}
    assert statstable.point_values(tmp_path / "nowhere" / "x") == {}
    pages = [page_with_numbers(tmp_path / "pages", "d01-x01-y01", NUMBERS)]
    statstable.write_set(pages, numbers, ["png"])
    assert statstable.sidecar(numbers / "statistics.csv")["values"] == axes


def test_the_sidecar_names_the_points_a_merged_curve_is_made_of_only_when_there_are_any():
    from stats import table
    assert "merged" not in table.sidecar_of(["chi2_ndf"])
    assert table.sidecar_of(["chi2_ndf"], merged={"em_pdfs": ["em_a", "em_b"]})["merged"] == {"em_pdfs": ["em_a", "em_b"]}


def test_a_table_of_runs_together_has_a_run_column_after_point_and_no_other_table_has(tmp_path):
    from stats import table
    page = page_with_numbers(tmp_path / "pages", "d01-x01-y01", NUMBERS)
    plain = tmp_path / "plain.csv"
    statstable.write_statistics([page], plain)
    assert "run" not in statstable.read(plain)[0] and "run" not in table.sidecar(plain)["columns"]
    page.runs = {"p1": "03·nlo", "p2": "04·pdfs"}
    across = tmp_path / "across.csv"
    assert statstable.write_statistics([page], across) == 2
    rows = statstable.read(across)
    assert [(r["point"], r["run"]) for r in rows] == [("p1", "03·nlo"), ("p2", "04·pdfs")]
    columns = table.sidecar(across)["columns"]
    assert columns[columns.index("point") + 1] == "run" and list(rows[0]) == columns[:len(rows[0])]


def test_a_format_2_table_reads_with_every_metric_under_its_id_now_and_no_value_changed(tmp_path):
    """A csv and sidecar as format 2 wrote them, with the old ids: the rows carry the new ids, the sidecar says format 3's
    keys, and every number is the one written."""
    target = tmp_path / "statistics.csv"
    old = ["page", "cell", "object", "curve", "point", "reference", "is_reference", "bins", "area", "rel_abs_area",
           "area_ratio", "ratio_dev", "chi2_ndf", "norm", "shape", "worst", "lambda"]
    values = ["p", "c", "/A/b", "x", "x", "data", "False", "9", "2.5", "0.1", "1.2", "0.3", "1.5", "0.02", "0.04", "8.0", "0.7"]
    target.write_text(",".join(old) + "\n" + ",".join(values) + "\n", encoding="utf-8")
    side = {"format": 2, "columns": old,
            "metrics": {"norm": {"purpose": "normalisation", "better": "lower", "thresholds": [0.02, 0.15]},
                        "lambda": {"purpose": "quality", "better": "none", "thresholds": None},
                        "shape": {"purpose": "shape", "better": "lower"}},
            "score": {"metrics": {"norm": 2.0, "shape": 1.0}, "thresholds": {"worst": [5, 20]}, "normalise": "thresholds"},
            "axes": {"x": {"pdf": "A"}}}
    (tmp_path / "statistics.json").write_text(json.dumps(side), encoding="utf-8")
    (row,) = statstable.read(target)
    assert list(row)[9:] == ["yield_weighted_abs_dev", "yield_ratio", "mean_abs_ratio_dev", "chi2_ndf", "log_yield_ratio",
                             "log_dev_shrunk", "peak_pull2", "tail_slope"]
    assert [row[k] for k in list(row)[8:]] == [2.5, 0.1, 1.2, 0.3, 1.5, 0.02, 0.04, 8.0, 0.7]
    read = statstable.sidecar(target)
    assert read["format"] == 3 and statstable.format_of(target) == 2               # the file's own format, as written
    assert read["columns"] == list(row)
    assert read["metrics"]["log_yield_ratio"] == {"category": "normalisation", "polarity": "lower", "thresholds": [0.02, 0.15]}
    assert read["metrics"]["tail_slope"]["polarity"] == "descriptor"
    assert read["metrics"]["log_dev_shrunk"]["category"] == "accuracy"                # the category's key was shape
    assert read["ranking"]["metrics"] == {"log_yield_ratio": 2.0, "log_dev_shrunk": 1.0}
    assert read["ranking"]["thresholds"] == {"peak_pull2": [5, 20]} and read["ranking"]["cost"] == "thresholds"
    assert read["values"] == {"x": {"pdf": "A"}} and "score" not in read and "axes" not in read
    assert json.loads((tmp_path / "statistics.json").read_text(encoding="utf-8")) == side          # never written back


def test_a_normalised_pages_curves_know_it_and_their_yield_sign_is_not_asked(tmp_path):
    """A page drawn with `normalise` on: its curves are normalised, so a negative yield is not a gate's failure there."""
    measured = [[0.0, 1.0, -2.0, 0.1, 1.0, 0.1], [1.0, 2.0, -1.0, 0.1, 1.0, 0.1]]
    numbers = [{**NUMBERS[0], "measured": [[lo, hi, ref, e, ref, e] for lo, hi, _, e, ref, _ in measured]},
               {**NUMBERS[1], "measured": measured}]
    flat = page_with_numbers(tmp_path / "flat", "d01-x01-y01", numbers)
    flat.document["page"] = {}
    normed = page_with_numbers(tmp_path / "normed", "d01-x01-y01", numbers)
    normed.document["page"] = {"normalise": "area"}
    assert statstable.statistics_of(flat)[1]["yield_sign"] == 1.0
    assert math.isnan(statstable.statistics_of(normed)[1]["yield_sign"])


def test_a_figures_weight_reaches_the_loss_and_the_sidecar_holds_the_same_record_as_rank(tmp_path):
    """d01's curve has χ²/ndf 22/11 = 2 (z 0.5, cost log2 1.5) and weight 3 from its figure; d02's 44/11 = 4 (z 1.5, cost
    log2 2.5) and weight 1. One category, so a page's loss is its cost, and the point's the ω-weighted RMS:
    √((3 · log2(1.5)² + log2(2.5)²) / 4)."""
    from runner import rankcmd
    from stats import ranking
    worse = [dict(NUMBERS[0]), {**NUMBERS[1], "chi2": 44.0}]
    pages = [page_with_numbers(tmp_path / "pages", "d01-x01-y01", NUMBERS), page_with_numbers(tmp_path / "pages", "d02-x01-y01", worse)]
    pages[0].weight = 3.0
    numbers = tmp_path / "statistics" / "totality"
    table = {"metrics": ["chi2_ndf"], "weights": {"d01-*": 5.0}}
    statstable.write_set(pages, numbers, ["png"], ranking=table, over={"over_pages": "rms"}, set_name="totality")
    side = json.loads((numbers / "statistics.json").read_text(encoding="utf-8"))
    assert side["page_weights"] == {"d01-x01-y01": 3.0}
    assert side["ranking_sources"] == {"metrics": "[ranking]", "weights": "[ranking]", "over_pages": "set totality"}
    report = rankcmd.report_of(rankcmd.Table("A/E/R", "", "totality", numbers / "statistics.csv"))
    (p2,) = [s for s in report["leaderboard"] if s["point"] == "p2"]
    assert p2["loss"] == pytest.approx(math.sqrt((3 * math.log2(1.5) ** 2 + math.log2(2.5) ** 2) / 4))
    assert json.loads(json.dumps(report["method"])) == side["method"]                  # one record, wherever it is read
    pages_stage = ranking.Method(**{k: tuple(ranking.Choice(**c) for c in v) for k, v in side["method"].items()}).lines("pages")
    assert "page d01-x01-y01: 3 (figure). over [ranking].weights' 'd01-*' = 5" in pages_stage     # the figure's weight won
    assert "over_pages: rms (set totality). the mean of a point's page losses, page weights counting" in pages_stage
