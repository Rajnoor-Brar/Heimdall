"""The scoring engine (framework/stats/score.py): rows in, scores out. The rows are written by hand, so each number is
checked against a hand calculation, and the properties the plan names are tested as properties."""

from __future__ import annotations

import math

import pytest

from runner.errors import HeimdallError
from stats import metrics, score

NAN = float("nan")


def row(point, page="p", cell="c", obj="run/pt/jet", ndf=10, reference=False, **values):
    base = {name: 0.0 for name in ("norm", "shape", "tilt", "worst")}
    base["chi2_ndf"] = 1.0
    return {"cell": cell, "page": page, "object": obj, "point": point, "curve": point, "is_reference": reference,
            "ndf": ndf, **base, **values}


def two_purposes():
    """chi2_ndf (compatibility) and norm (normalisation): two purposes of one metric each."""
    return score.settings_of({"metrics": ["chi2_ndf", "norm"]})


def test_the_default_settings_score_the_five_default_metrics_at_weight_one():
    st = score.settings_of()
    assert set(st.metrics) == {n for n, m in metrics.REGISTRY.items() if m.default}
    assert set(st.metrics.values()) == {1.0}
    assert st.normalise == "thresholds" and st.mean == "rms" and st.aggregate == "rms"


@pytest.mark.parametrize("bad", [{"metrics": ["chi2_nfd"]}, {"mean": "rsm"}, {"normalise": "zscore"},
                                 {"thresholds": {"nrom": [0.1, 0.2]}}, {"metrics": {"norm": 0.0}}, {"aggregate": "borda"}])
def test_a_wrong_name_or_a_scoreless_choice_is_refused_by_name(bad):
    with pytest.raises(HeimdallError):
        score.settings_of(bad)


def test_a_set_s_score_table_is_laid_over_the_run_s():
    st = score.settings_of({"mean": "rms", "veto": 3.0}, {"mean": "median"})
    assert st.mean == "median" and st.veto == 3.0


def test_a_perfect_curve_scores_zero_and_a_point_at_bad_scores_one_per_metric():
    rows = [row("good"), row("bad", chi2_ndf=3.0, norm=0.15)]
    out = {p.point: p for p in score.score(rows, two_purposes()).points}
    assert out["good"].score == 0.0
    assert out["bad"].score == pytest.approx(1.0)                         # both at their `bad` threshold: cost 1 each


def test_the_loss_is_the_rms_over_purposes_of_the_rms_within_each():
    rows = [row("a", chi2_ndf=2.0, norm=0.0)]                              # chi2: (2−1)/(3−1) = 0.5; norm: 0
    (p,) = score.score(rows, two_purposes()).points
    assert p.score == pytest.approx(math.sqrt((0.5**2 + 0.0) / 2))
    assert p.purposes == pytest.approx({"compatibility": 0.5, "normalisation": 0.0})


def test_the_shares_of_the_loss_sum_to_one_and_name_the_purpose_that_costs():
    rows = [row("a", chi2_ndf=3.0, norm=0.02)]                             # chi2 at bad: 1; norm at good: 0
    (p,) = score.score(rows, two_purposes()).points
    assert p.shares["compatibility"] == pytest.approx(1.0) and p.shares["normalisation"] == pytest.approx(0.0)
    assert sum(p.shares.values()) == pytest.approx(1.0)


def test_metrics_of_one_purpose_weigh_one_purpose_not_one_each():
    shape = [n for n, m in metrics.REGISTRY.items() if m.purpose == "shape" and m.default]
    others = [n for n, m in metrics.REGISTRY.items() if m.purpose == "compatibility" and m.default]
    assert shape and others
    values = {n: metrics.REGISTRY[n].thresholds[1] for n in shape}        # every shape metric at bad: cost 1
    one = score.settings_of({"metrics": [*shape[:1], *others]})
    all_ = score.settings_of({"metrics": [*shape, *others]})
    r = [row("a", chi2_ndf=1.0, **values)]
    assert score.score(r, one).points[0].score == pytest.approx(score.score(r, all_).points[0].score)


def test_a_metric_weight_counts_within_its_purpose():
    shape = [n for n, m in metrics.REGISTRY.items() if m.purpose == "shape" and m.default][0]
    bad = metrics.REGISTRY[shape].thresholds[1]
    st = score.settings_of({"metrics": {shape: 3.0, "tilt": 1.0}})
    # tilt is another purpose: weights do not leak across purposes
    (p,) = score.score([row("a", **{shape: bad, "tilt": 0.0})], st).points
    assert p.purposes[metrics.REGISTRY[shape].purpose] == pytest.approx(1.0)


def test_adding_a_curve_leaves_the_others_threshold_scores_unchanged():
    rows = [row("a", chi2_ndf=2.0, norm=0.05), row("b", chi2_ndf=1.2, norm=0.01)]
    before = {p.point: p.score for p in score.score(rows, two_purposes()).points}
    more = rows + [row("c", chi2_ndf=40.0, norm=0.9)]
    after = {p.point: p.score for p in score.score(more, two_purposes()).points}
    assert after["a"] == before["a"] and after["b"] == before["b"]


def test_a_pool_normalisation_changes_when_a_curve_is_added_and_says_so():
    rows = [row("a", chi2_ndf=2.0), row("b", chi2_ndf=4.0), row("c", chi2_ndf=3.0)]
    st = score.settings_of({"metrics": ["chi2_ndf"], "normalise": "minmax"})
    first = {p.point: p.score for p in score.score(rows, st).points}
    second = {p.point: p.score for p in score.score(rows + [row("d", chi2_ndf=40.0)], st).points}
    assert first == {"a": 0.0, "b": 1.0, "c": 0.5}
    assert second["b"] != first["b"]                                     # one wild curve compressed the rest


def test_points_of_different_cells_are_scored_apart():
    rows = [row("a", cell="x", chi2_ndf=1.0), row("a", cell="y", chi2_ndf=3.0)]
    out = {(p.cell, p.point): p.score for p in score.score(rows, score.settings_of({"metrics": ["chi2_ndf"]})).points}
    assert out == {("x", "a"): 0.0, ("y", "a"): pytest.approx(1.0)}


def test_a_page_s_reference_row_is_not_scored():
    rows = [row("ref", reference=True), row("a", chi2_ndf=3.0)]
    out = score.score(rows, score.settings_of({"metrics": ["chi2_ndf"]}))
    assert [p.point for p in out.points] == ["a"]


def test_pages_against_data_win_over_pages_against_a_curve():
    rows = [row("ref", page="vs_curve", reference=True), row("a", page="vs_curve", chi2_ndf=3.0),
            row("a", page="vs_data", chi2_ndf=1.0)]
    (p,) = score.score(rows, score.settings_of({"metrics": ["chi2_ndf"]})).points
    assert set(p.pages) == {"vs_data"} and p.score == 0.0


def test_the_worst_page_and_the_veto():
    rows = [row("a", page="good", chi2_ndf=1.0), row("a", page="awful", chi2_ndf=9.0)]
    st = score.settings_of({"metrics": ["chi2_ndf"], "veto": 2.0})
    (p,) = score.score(rows, st).points
    assert p.worst_page == "awful" and p.worst_loss == pytest.approx(4.0)
    assert p.veto is True
    assert score.score(rows, score.settings_of({"metrics": ["chi2_ndf"], "veto": 5.0})).points[0].veto is False
    assert score.score(rows, score.settings_of({"metrics": ["chi2_ndf"]})).points[0].veto is False


def test_page_weights_by_figure_and_by_glob_and_the_figure_wins():
    rows = [row("a", page="p1", obj="run/pt/jet_pt", chi2_ndf=1.0), row("a", page="p2", obj="run/pt/mass", chi2_ndf=3.0)]
    st = score.settings_of({"metrics": ["chi2_ndf"], "weights": {"jet_*": 3.0}})
    assert score.score(rows, st).points[0].score == pytest.approx(math.sqrt((3 * 0 + 1 * 1) / 4))    # rms: Σw l² / Σw
    by_figure = score.score(rows, st, figure_weights={"p1": 1.0, "p2": 1.0}).points[0].score
    assert by_figure == pytest.approx(math.sqrt(0.5))
    assert score.page_weight("run/pt/jet_pt", "p1", st, None) == 3.0
    assert score.page_weight("run/pt/mass", "p2", st, None) == 1.0


def test_the_mean_is_a_setting_median_ignores_one_bad_page():
    rows = [row("a", page=f"p{i}", chi2_ndf=1.0) for i in range(4)] + [row("a", page="bad", chi2_ndf=9.0)]
    rms = score.score(rows, score.settings_of({"metrics": ["chi2_ndf"]})).points[0].score
    med = score.score(rows, score.settings_of({"metrics": ["chi2_ndf"], "mean": "median"})).points[0].score
    assert med == 0.0 and rms > 1.0


def test_a_missing_metric_is_skipped_not_scored_as_zero():
    rows = [row("a", chi2_ndf=NAN, norm=0.15)]
    (p,) = score.score(rows, two_purposes()).points
    assert list(p.purposes) == ["normalisation"] and p.score == pytest.approx(1.0)


def test_a_point_with_nothing_to_score_has_a_nan_score_and_ranks_last():
    rows = [row("none", chi2_ndf=NAN, norm=NAN), row("ok", chi2_ndf=1.0, norm=0.0)]
    out = score.score(rows, two_purposes())
    assert math.isnan(out.points[0].score)
    assert [p.point for p in out.ranked()] == ["ok", "none"]


def test_dominated_is_pareto_over_purposes():
    rows = [row("best", chi2_ndf=1.0, norm=0.0), row("worse", chi2_ndf=2.0, norm=0.1),
            row("tradeoff", chi2_ndf=1.0, norm=0.3), row("other", chi2_ndf=3.0, norm=0.0)]
    st = score.settings_of({"metrics": ["chi2_ndf", "norm"], "dominated": True})
    out = {p.point: p.dominated for p in score.score(rows, st).points}
    assert out == {"best": False, "worse": True, "tradeoff": True, "other": True}


# ── the null distributions ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("chi2, ndf, p", [(3.841459, 1, 0.05), (5.991465, 2, 0.05), (18.307038, 10, 0.05), (0.0, 5, 1.0),
                                          (6.634897, 1, 0.01)])
def test_the_chi_square_survival_function_matches_the_tables(chi2, ndf, p):
    assert score.chi2_p(chi2, ndf) == pytest.approx(p, abs=2e-6)


def test_the_gaussian_nulls():
    assert score.null_p("tail", 1.959964, {}) == pytest.approx(0.05, abs=1e-6)       # two-sided
    assert score.null_p("chi2_z", 1.644854, {}) == pytest.approx(0.05, abs=1e-6)     # one-sided
    assert score.null_p("chi2_ndf", 1.0, {"ndf": 10}) == pytest.approx(score.chi2_p(10, 10))
    with pytest.raises(HeimdallError, match="no null"):
        score.null_p("norm", 0.1, {})


def test_surprisal_is_minus_the_log_of_the_null_probability():
    rows = [row("a", chi2_ndf=1.8307038, ndf=10)]                         # χ² = 18.307: p = 0.05
    st = score.settings_of({"metrics": ["chi2_ndf"], "normalise": "surprisal"})
    assert score.score(rows, st).points[0].score == pytest.approx(-math.log(0.05), rel=1e-4)


def test_surprisal_refuses_a_metric_with_no_null():
    with pytest.raises(HeimdallError, match="no null"):
        score.score([row("a")], score.settings_of({"metrics": ["norm"], "normalise": "surprisal"}))


# ── the pool normalisations ───────────────────────────────────────────────────────────────────

def test_median_normalisation_makes_the_typical_curve_cost_one():
    rows = [row("a", chi2_ndf=2.0), row("b", chi2_ndf=4.0), row("c", chi2_ndf=8.0)]
    out = {p.point: p.score for p in score.score(rows, score.settings_of({"metrics": ["chi2_ndf"], "normalise": "median"})).points}
    assert out == {"a": pytest.approx(0.5), "b": pytest.approx(1.0), "c": pytest.approx(2.0)}


def test_mad_normalisation_orders_by_the_metric_and_stays_positive():
    rows = [row(c, chi2_ndf=v) for c, v in zip("abcde", (1.0, 1.1, 1.2, 1.3, 9.0))]
    out = score.score(rows, score.settings_of({"metrics": ["chi2_ndf"], "normalise": "mad"}))
    s = {p.point: p.score for p in out.points}
    assert all(v > 0 for v in s.values()) and s["a"] < s["d"] < s["e"]


def test_a_pool_normalisation_refuses_a_higher_is_better_metric():
    higher = [n for n, m in metrics.REGISTRY.items() if m.better == "higher"]
    if not higher:
        pytest.skip("no higher-is-better metric")
    rows = [row("a", **{higher[0]: 0.5})]
    with pytest.raises(HeimdallError, match="pool"):
        score.score(rows, score.settings_of({"metrics": [higher[0]], "normalise": "minmax"}))


# ── CRITIC ────────────────────────────────────────────────────────────────────────────────────

def test_critic_needs_enough_curves_to_correlate():
    rows = [row(f"p{i}", chi2_ndf=1.0 + i, norm=0.01 * i) for i in range(5)]
    with pytest.raises(HeimdallError, match="critic"):
        score.score(rows, score.settings_of({"metrics": ["chi2_ndf", "norm"], "weights_by": "critic"}))


def test_critic_downweights_a_metric_that_repeats_another():
    # three metrics, two of which are the same ranking: the independent one weighs more than each of the repeated pair
    shape, tilt, norm = "shape", "tilt", "norm"
    rows = []
    for i in range(20):
        rows.append(row(f"p{i}", shape=0.01 * i, tilt=0.01 * i + 0.001, norm=0.01 * ((i * 7) % 20)))
    obs = score.observations(rows, score.settings_of({"metrics": [shape, tilt, norm]}))
    st = score.settings_of({"metrics": [shape, tilt, norm]})
    score.costs(obs, st)
    w = score.critic_weights(obs, [shape, tilt, norm])
    assert w[norm] > w[shape] and w[norm] > w[tilt]
    assert sum(w.values()) == pytest.approx(3.0)


def test_critic_through_the_score_runs_and_keeps_the_ranking_of_a_clear_case():
    rows = [row(f"p{i}", chi2_ndf=1.0 + 0.1 * i, norm=0.01 * i, shape=0.01 * i) for i in range(20)]
    st = score.settings_of({"metrics": ["chi2_ndf", "norm", "shape"], "weights_by": "critic"})
    order = [p.point for p in score.score(rows, st).ranked()]
    assert order[0] == "p0" and order[-1] == "p19"


# ── the other aggregators ─────────────────────────────────────────────────────────────────────

def test_fisher_orders_by_the_probability_and_is_pool_independent():
    rows = [row("fit", chi2_ndf=1.0), row("poor", chi2_ndf=2.0), row("awful", chi2_ndf=5.0)]
    st = score.settings_of({"metrics": ["chi2_ndf"], "aggregate": "fisher"})
    out = score.score(rows, st)
    s = {p.point: p.score for p in out.points}
    assert s["fit"] < s["poor"] < s["awful"]
    assert s["fit"] == pytest.approx(-2 * math.log(score.chi2_p(10, 10)))
    again = {p.point: p.score for p in score.score(rows[:2], st).points}
    assert again["fit"] == s["fit"]
    assert any("fisher" in n for n in out.notes)


def test_topsis_is_pool_dependent_and_says_so():
    rows = [row("a", chi2_ndf=1.0, norm=0.0), row("b", chi2_ndf=2.0, norm=0.1), row("c", chi2_ndf=3.0, norm=0.2)]
    st = score.settings_of({"metrics": ["chi2_ndf", "norm"], "aggregate": "topsis"})
    out = score.score(rows, st)
    s = {p.point: p.score for p in out.points}
    assert s["a"] == pytest.approx(0.0) and s["c"] == pytest.approx(1.0) and 0 < s["b"] < 1
    assert any("rank reversal" in n for n in out.notes)
    wider = {p.point: p.score for p in score.score(rows + [row("d", chi2_ndf=9.0, norm=0.9)], st).points}
    assert wider["b"] != s["b"]


def test_promethee_ranks_by_net_outranking_flow():
    rows = [row("a", chi2_ndf=1.0), row("b", chi2_ndf=2.0), row("c", chi2_ndf=3.0)]
    st = score.settings_of({"metrics": ["chi2_ndf"], "aggregate": "promethee"})
    out = score.score(rows, st)
    s = {p.point: p.score for p in out.points}
    assert s["a"] < s["b"] < s["c"]
    assert any("promethee" in n for n in out.notes)


# ── head to head ──────────────────────────────────────────────────────────────────────────────

def test_head_to_head_gives_the_pairwise_differences_and_counts_no_wins():
    rows = [row("a", chi2_ndf=1.0, norm=0.0), row("b", chi2_ndf=3.0, norm=0.02), row("c", chi2_ndf=2.0, norm=0.15)]
    out = score.head_to_head(rows, "p", two_purposes())
    assert out["points"] == ["a", "b", "c"]
    pairs = {(p["a"], p["b"]): p for p in out["pairs"]}
    assert set(pairs) == {("a", "b"), ("a", "c"), ("b", "c")}
    assert pairs[("a", "b")]["metrics"]["chi2_ndf"] == pytest.approx(0.0 - 1.0)       # a is better by one on χ²
    assert pairs[("a", "b")]["loss"] < 0
    assert pairs[("b", "c")]["metrics"]["norm"] == pytest.approx(0.0 - 1.0)
    assert not any("wins" in p for p in out["pairs"])


def test_head_to_head_on_a_page_that_is_not_there_names_the_pages():
    with pytest.raises(HeimdallError, match="no page"):
        score.head_to_head([row("a")], "nope")
