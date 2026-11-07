"""[score] and the new [stats] keys: checked when the file is read, names against the registries, a set's own `score`
and a figure's `weight`; `heimdall explain score` lists the metrics and means."""

from __future__ import annotations

import pytest

from helpers import raw
from runner import config, house, schema
from runner.errors import HeimdallError
from runner.sweep import set_entries


def test_score_is_a_section_with_its_keys(scratch):
    score = {"metrics": {"chi2_ndf": 1, "norm": 2, "js": 0.5}, "normalise": "thresholds", "thresholds": {"norm": [0.01, 0.1]},
             "weights": {"d01-*": 2}, "mean": "rms", "veto": 3.0, "dominated": True, "aggregate": "rms", "weights_by": "equal",
             "by": ["pdf"], "baseline": {"pdf": "NNPDF23lo"}}
    errand = config.parse(raw(score=score), scratch / "t.toml")
    assert errand.score == score
    assert config.parse(raw(), scratch / "u.toml").score == {}
    assert config.parse(raw(score={"metrics": ["norm", "tilt"]}), scratch / "v.toml").score == {"metrics": ["norm", "tilt"]}


@pytest.mark.parametrize("bad,message", [
    ({"metrics": ["chi2_nfd"]}, "no metric 'chi2_nfd'"),
    ({"metrics": {"nope": 1}}, "no metric 'nope'"),
    ({"metrics": {"norm": -1}}, "a number of zero or more"),
    ({"thresholds": {"norm": [0.1]}}, r"\[good, bad\]"),
    ({"thresholds": {"norm": [0.1, 0.1]}}, r"\[good, bad\]"),
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
    errand = config.parse(raw(stats={"metrics": ["chi2_ndf", "norm", "js"], "centres": "barycentre"}), scratch / "t.toml")
    assert errand.stats == {"metrics": ["chi2_ndf", "norm", "js"], "centres": "barycentre"}
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
