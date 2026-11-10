"""`heimdall rank`: the leaderboard, marginals and baselines read from a statistics.csv with no page drawn, a row a Run for an
Errand; `heimdall stats` retired for `heimdall plot --stats-only`. The tables are written by hand, so each number is
checked against the engine's own."""

from __future__ import annotations

import csv
import json
import math

import pytest

from runner import cli, rankcmd
from runner.errors import HeimdallError
from stats import table


def row(point, loss, page="p1", obj="run/pt/jet", **values):
    base = {name: 0.0 for name in ("log_yield_ratio", "log_dev_shrunk", "tilt", "peak_pull2")}
    return {"cell": "c", "page": page, "object": obj, "point": point, "curve": point, "is_reference": False, "ndf": 10, "bins": 10,
            **base, "chi2_ndf": loss, **values}


def reference(page="p1", obj="run/pt/jet"):
    return {**row("data", 1.0, page, obj), "is_reference": True}


def make_run(root, name, rows, serial=None, axes=None, ranking=None):
    folder = root / name
    out = folder / "statistics" / "totality"
    out.mkdir(parents=True)
    names = ["chi2_ndf", "log_yield_ratio", "log_dev_shrunk", "tilt", "peak_pull2"]
    with open(out / "statistics.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=table.columns_for(names), restval="")
        writer.writeheader()
        writer.writerows([{k: ("" if isinstance(v, float) and v != v else v) for k, v in r.items()} for r in rows])
    (out / "statistics.json").write_text(json.dumps(table.sidecar_of(names, ranking, axes)), encoding="utf-8")
    if serial is not None:
        (folder / "plot.toml").write_text(f'[source]\nserial = {serial}\n', encoding="utf-8")
    return folder


@pytest.fixture
def results(tmp_path, monkeypatch):
    monkeypatch.setenv("HEIMDALL_RESULTS", str(tmp_path))
    return tmp_path


def args(target, **over):
    given = {"target": target, "set_name": None, "across": False, "by": None, "baseline": None, "json": False}
    return type("Args", (), {**given, **over})()


AXES = {"py8_a": {"generator": "py8", "pdf": "a"}, "py8_b": {"generator": "py8", "pdf": "b"},
        "hw7_a": {"generator": "hw7", "pdf": "a"}, "hw7_b": {"generator": "hw7", "pdf": "b"}}


def sweep_rows():
    losses = {"py8_a": 1.0, "py8_b": 2.0, "hw7_a": 4.0, "hw7_b": 5.0}
    return [reference(), *(row(p, v) for p, v in losses.items())]


def test_a_run_prints_its_leaderboard_best_first(results, capsys):
    make_run(results, "A/E/R1", sweep_rows(), serial=3, axes=AXES)
    assert rankcmd.run(args("A/E/R1")) == 0
    out = capsys.readouterr().out
    assert "A/E/R1 (run 3) · totality" in out
    places = [line.split()[1] for line in out.splitlines() if line[:2] in ("1.", "2.", "3.", "4.")]
    assert places == ["py8_a", "py8_b", "hw7_a", "hw7_b"]
    assert "By generator:" in out and "By pdf:" in out
    assert "Baseline" not in out                                  # none was asked


def test_json_carries_the_same_numbers_and_the_baseline(results, capsys):
    make_run(results, "A/E/R1", sweep_rows(), axes=AXES)
    assert rankcmd.run(args("A/E/R1", json=True, baseline="generator=py8")) == 0
    data = json.loads(capsys.readouterr().out)["tables"][0]
    losses = {s["point"]: s["loss"] for s in data["leaderboard"]}
    assert losses["py8_a"] < losses["py8_b"] < losses["hw7_a"] < losses["hw7_b"]
    assert [s["rank"] for s in data["leaderboard"]] == [1, 2, 3, 4] and all(s["vetoed"] is False for s in data["leaderboard"])
    assert not {"standings", "place", "score", "veto", "axis"} & {*data, *data["leaderboard"][0], *data["marginals"][0]}
    marginal = {m["quantity"]: {v["value"]: v for v in m["values"]} for m in data["marginals"]}
    assert marginal["generator"]["py8"]["points"] == 2 and marginal["generator"]["py8"]["loss"] < marginal["generator"]["hw7"]["loss"]
    deltas = {r["point"]: r for r in data["baseline"]["rows"]}
    assert deltas["hw7_a"]["partner"] == "py8_a" and deltas["hw7_a"]["delta"] == pytest.approx(losses["hw7_a"] - losses["py8_a"])
    assert data["baseline"]["filter"] == {"generator": "py8"}


def test_a_filter_is_quantity_value_pairs_or_a_point_name():
    assert rankcmd.parse_filter("generator=py8, pdf=a") == {"generator": "py8", "pdf": "a"}
    assert rankcmd.parse_filter(" py8_a ") == "py8_a"
    with pytest.raises(HeimdallError, match="not quantity=value"):
        rankcmd.parse_filter("generator=py8,pdf")


def test_a_table_without_values_says_so_when_marginals_were_asked(results, capsys):
    make_run(results, "A/E/R1", sweep_rows())
    assert rankcmd.run(args("A/E/R1", by="generator")) == 0
    out = capsys.readouterr().out
    assert "no marginals or baseline" in out and "By generator" not in out


def test_an_errand_prints_a_row_a_run_over_the_pages_they_share(results, capsys):
    one = [reference("p1"), reference("p2", "run/pt/b"), row("x", 1.0, "p1"), row("x", 1.0, "p2", "run/pt/b")]
    two = [reference("p1"), row("x", 9.0, "p1")]                    # only p1: the shared page
    make_run(results, "A/E/R1", one, serial=1)
    make_run(results, "A/E/R2", two, serial=2)
    assert rankcmd.run(args("A/E", json=True)) == 0
    runs = {r["serial"]: r for r in json.loads(capsys.readouterr().out)["runs"]}
    assert set(runs) == {"1", "2"} and runs["1"]["pages"] == runs["2"]["pages"] == 1
    assert runs["1"]["loss"] < runs["2"]["loss"] and runs["2"]["best"] == "x" and runs["1"]["points"] == 1
    assert rankcmd.run(args("A/E")) == 0
    text = capsys.readouterr().out
    assert "each Run's loss over the 1 page(s) its Runs share" in text and "A/E/R1" in text and "A/E/R2" in text


def test_the_set_option_picks_a_set_and_a_missing_one_is_refused(results):
    make_run(results, "A/E/R1", sweep_rows())
    assert [t.set for t in rankcmd.tables_of("A/E/R1", "totality", False)] == ["totality"]
    with pytest.raises(HeimdallError, match="no statistics in A/E/R1 for set nope"):
        rankcmd.tables_of("A/E/R1", "nope", False)
    with pytest.raises(HeimdallError, match="no results folder"):
        rankcmd.tables_of("A/E/R9", None, False)


def test_across_reads_the_errands_own_folder(results, capsys):
    make_run(results, "A/E", sweep_rows(), axes=AXES)
    make_run(results, "A/E/R1", sweep_rows())
    assert [t.run for t in rankcmd.tables_of("A/E", None, True)] == ["A/E"]
    assert [t.run for t in rankcmd.tables_of("A/E", None, False)] == ["A/E/R1"]      # without --across: its Runs
    assert rankcmd.run(args("A/E", across=True)) == 0
    assert "A/E · totality" in capsys.readouterr().out


def test_a_table_scored_with_its_own_settings_keeps_them_and_by_overlays(results):
    make_run(results, "A/E/R1", sweep_rows(), axes=AXES, ranking={"by": ["pdf"], "over_pages": "median"})
    (t,) = rankcmd.tables_of("A/E/R1", None, False)
    st, axes = rankcmd.settings_for(t, None, None)
    assert st.by == ("pdf",) and st.over_pages == "median" and axes == AXES
    assert rankcmd.settings_for(t, "generator,pdf", None)[0].by == ("generator", "pdf")
    assert rankcmd.settings_for(t, None, "generator=hw7")[0].baseline == {"generator": "hw7"}


def test_an_infinite_loss_prints_as_infinity_not_a_crash(results, capsys):
    make_run(results, "A/E/R1", [reference(), row("a", 1.0), row("b", math.inf)], axes={})
    assert rankcmd.run(args("A/E/R1")) == 0
    assert "∞" in capsys.readouterr().out


def test_the_parser_takes_rank_and_plot_stats_only_and_stats_and_score_are_retired():
    p = cli.parser()
    got = p.parse_args(["rank", "A/E", "--set", "totality", "--by", "generator", "--baseline", "pdf=a", "--json", "--across"])
    assert (got.target, got.set_name, got.by, got.baseline, got.json, got.across) == ("A/E", "totality", "generator", "pdf=a", True, True)
    assert p.parse_args(["plot", "A/E/R1", "--stats-only"]).stats_only is True
    old = p.parse_args(["stats", "A/E/R1", "--sets", "totality"])
    with pytest.raises(HeimdallError, match="heimdall plot RUN --stats-only") as caught:
        cli.cmd_stats_retired(old)
    assert "heimdall rank" in str(caught.value)
    old = p.parse_args(["score", "A/E/R1", "--by", "generator", "--json"])
    with pytest.raises(HeimdallError, match="renamed: heimdall score is heimdall rank"):
        cli.cmd_score_retired(old)
    assert cli.main(["score", "A/E/R1"]) != 0


def test_stats_only_will_not_mix_with_plan_or_style_sync():
    got = cli.parser().parse_args(["plot", "A/E/R1", "--stats-only", "--plan"])
    with pytest.raises(HeimdallError, match="--stats-only measures"):
        cli.cmd_plot(got)
