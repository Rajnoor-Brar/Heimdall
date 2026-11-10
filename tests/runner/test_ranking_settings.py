"""[score] and the new [stats] keys: checked when the file is read, names against the registries, a set's own `score`
and a figure's `weight`; `heimdall explain score` lists the metrics and means."""

from __future__ import annotations

import pytest

from helpers import raw
from runner import config, house, schema
from runner.errors import HeimdallError
from runner.sweep import set_entries


def test_score_is_a_section_with_its_keys(scratch):
    score = {"metrics": {"chi2_ndf": 1, "log_yield_ratio": 2, "js_divergence": 0.5}, "normalise": "thresholds", "thresholds": {"log_yield_ratio": [0.01, 0.1]},
             "weights": {"d01-*": 2}, "mean": "rms", "veto": 3.0, "dominated": True, "aggregate": "rms", "weights_by": "equal",
             "by": ["pdf"], "baseline": {"pdf": "NNPDF23lo"}}
    errand = config.parse(raw(score=score), scratch / "t.toml")
    assert errand.score == score
    assert config.parse(raw(), scratch / "u.toml").score == {}
    assert config.parse(raw(score={"metrics": ["log_yield_ratio", "tilt"]}), scratch / "v.toml").score == {"metrics": ["log_yield_ratio", "tilt"]}


@pytest.mark.parametrize("bad,message", [
    ({"metrics": ["chi2_nfd"]}, "no metric 'chi2_nfd'"),
    ({"metrics": {"nope": 1}}, "no metric 'nope'"),
    ({"metrics": {"log_yield_ratio": -1}}, "a number of zero or more"),
    ({"thresholds": {"log_yield_ratio": [0.1]}}, r"\[good, bad\]"),
    ({"thresholds": {"log_yield_ratio": [0.1, 0.1]}}, r"\[good, bad\]"),
    ({"thresholds": {"zzz": [0.1, 0.2]}}, "no metric 'zzz'"),
    ({"weights": {"d01-*": "heavy"}}, "a number of zero or more"),
    ({"mean": "rmss"}, "no mean 'rmss'"),
    ({"normalise": "zscore"}, "must be one of"),
    ({"veto": -1.0}, "at least"),
    ({"aggregate": "sum"}, "must be one of"),
    ({"surprise": 1}, "unknown key 'surprise'"),
])
def test_a_bad_score_is_refused_with_a_hint(scratch, bad, message):
    with pytest.raises(HeimdallError, match=message):
        config.parse(raw(score=bad), scratch / "t.toml")


def test_a_mistyped_metric_gets_a_hint(scratch):
    with pytest.raises(HeimdallError) as caught:
        config.parse(raw(score={"metrics": ["chi2_nfd"]}), scratch / "t.toml")
    assert "chi2_ndf" in str(caught.value)
    with pytest.raises(HeimdallError) as caught:
        config.parse(raw(score={"mean": "trimed"}), scratch / "t.toml")
    assert "trimmed" in str(caught.value)


def test_stats_takes_metrics_and_centres_and_checks_the_names(scratch):
    errand = config.parse(raw(stats={"metrics": ["chi2_ndf", "log_yield_ratio", "js_divergence"], "centres": "barycentre"}), scratch / "t.toml")
    assert errand.stats == {"metrics": ["chi2_ndf", "log_yield_ratio", "js_divergence"], "centres": "barycentre"}
    with pytest.raises(HeimdallError, match="no metric 'jss'"):
        config.parse(raw(stats={"metrics": ["jss"]}), scratch / "u.toml")
    with pytest.raises(HeimdallError, match="must be one of"):
        config.parse(raw(stats={"centres": "median"}), scratch / "v.toml")


def test_a_set_may_carry_its_own_score_and_a_figure_its_weight():
    got = set_entries([{"name": "lo", "points": ["py8"], "score": {"mean": "median", "veto": 2.0}}], "w")
    assert got[0].score == {"mean": "median", "veto": 2.0}
    with pytest.raises(HeimdallError, match="unknown key"):
        set_entries([{"name": "lo", "points": ["py8"], "score": {"bogus": 1}}], "w")
    assert "weight" in schema.FIGURE_OWN and schema.keys("figure")["weight"]["min"] == 0


def test_explain_score_lists_the_keys_the_metrics_by_purpose_and_the_means():
    lines = "\n".join(house.explain("score"))
    for word in ("[score]", "thresholds", "metrics, statistical compatibility", "metrics, local defects", "chi2_ndf", "(default)", "wasserstein", "trimmed"):
        assert word in lines, word


def test_explain_one_metric_or_mean_in_full():
    tilt = "\n".join(house.explain("score.tilt"))
    assert "good 0.03, bad 0.25" in tilt and "because" in tilt and "by default" in tilt
    trimmed = "\n".join(house.explain("score.trimmed"))
    assert "guard" in trimmed and "approximate" in trimmed and "alpha" in trimmed
    assert "[score].mean" in "\n".join(house.explain("score.mean"))


# ── an old metric id: refused in a user's file, read in a record ──────────────────────────────

OLD_IN_PLACE = [
    ({"stats": {"metrics": ["chi2_ndf", "norm"]}}, "[stats].metrics", "norm", "log_yield_ratio"),
    ({"score": {"metrics": ["shape"]}}, "[score].metrics", "shape", "log_dev_shrunk"),
    ({"score": {"metrics": {"worst": 2}}}, "[score].metrics", "worst", "peak_pull2"),
    ({"score": {"thresholds": {"rho1": [0.3, 0.9]}}}, "[score].thresholds", "rho1", "pull_autocorr"),
    ({"plot": {"sets": [{"name": "a", "score": {"metrics": ["L4"]}}]}}, "[plot].sets[1].score.metrics", "L4", "log_dev_l4"),
    ({"plot": {"sets": {"a": {"score": {"thresholds": {"cvar": [1, 2]}}}}}}, "[plot].sets.a.score.thresholds", "cvar", "peak_deviance"),
    ({"plot": {"legend_statistic": "ratio_dev"}}, "[plot].legend_statistic", "ratio_dev", "mean_abs_ratio_dev"),
    ({"plot": {"figures": {"f": {"class": "statistic", "statistic": "area_ratio"}}}}, "[plot.figures.f].statistic", "area_ratio",
     "yield_ratio"),
    ({"plot": {"sets": [{"name": "a", "legend_statistic": "ratio_mean"}]}}, "[plot].sets[1].legend_statistic", "ratio_mean",
     "mean_bin_ratio"),
    ({"report": {"section": [{"title": "a", "plot": {"legend_statistic": "rel_abs_area"}}]}}, "[report].section[1].plot.legend_statistic",
     "rel_abs_area", "yield_weighted_abs_dev"),
    ({"report": {"section": [{"title": "a", "stats": ["standings", "chi2_z:ranking"]}]}}, "[report].section[1].stats", "chi2_z",
     "chi2_sigma"),
]


@pytest.mark.parametrize("given,place,old,new", OLD_IN_PLACE)
def test_an_old_metric_id_in_a_users_file_is_refused_naming_its_id_now(given, place, old, new):
    with pytest.raises(HeimdallError, match=f"renamed: {old} is {new}") as caught:
        config.renamed(given, "configs/T/t.toml", recorded=False)
    assert caught.value.where == f"configs/T/t.toml: {place}" and "heimdall migrate" in caught.value.hint


@pytest.mark.parametrize("given,place,old,new", OLD_IN_PLACE)
def test_an_old_metric_id_in_a_record_is_read_as_its_id_now_and_noted_once(given, place, old, new, monkeypatch):
    monkeypatch.setattr(config, "OLD_NAMES", [])
    import json
    read = config.renamed(given, "records/…/config/T/t.toml", recorded=True)
    read = config.renamed(given, "records/…/config/T/t.toml", recorded=True)
    assert old not in json.dumps(read).replace(f'"{new}"', "") and new in json.dumps(read)
    assert config.OLD_NAMES == [f"`{old}` → `{new}`"]
    assert given != read                                                         # a copy: the file's tables are left alone


def test_a_file_with_no_old_name_is_returned_as_it_is():
    given = {"score": {"metrics": ["log_dev_shrunk"]}, "plot": {"legend_statistic": "chi2_ndf", "sets": ["pdf=A"]}}
    assert config.renamed(given, "t.toml", recorded=False) is given
