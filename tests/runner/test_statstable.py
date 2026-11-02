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
    assert list(back[0]) == list(statstable.STATISTIC_COLUMNS)


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
