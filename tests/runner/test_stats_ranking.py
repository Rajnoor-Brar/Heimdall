"""The scoring engine (framework/stats/ranking.py): rows in, scores out. The rows are written by hand, so each number is
checked against a hand calculation, and the properties the plan names are tested as properties."""

from __future__ import annotations

import math

import pytest

from runner.errors import HeimdallError
from stats import metrics, ranking

NAN = float("nan")


def row(point, page="p", cell="c", obj="run/pt/jet", ndf=10, reference=False, **values):
    base = {name: 0.0 for name in ("log_yield_ratio", "log_dev_shrunk", "tilt", "peak_pull2")}
    base["chi2_ndf"] = 1.0
    return {"cell": cell, "page": page, "object": obj, "point": point, "curve": point, "is_reference": reference,
            "ndf": ndf, **base, **values}


def two_categories():
    """chi2_ndf (compatibility) and norm (normalisation): two categories of one metric each."""
    return ranking.settings_of({"metrics": ["chi2_ndf", "log_yield_ratio"]})


def test_the_default_settings_score_the_five_default_metrics_at_weight_one():
    st = ranking.settings_of()
    assert set(st.metrics) == {n for n, m in metrics.REGISTRY.items() if m.default}
    assert set(st.metrics.values()) == {1.0}
    assert st.cost == "thresholds" and st.over_pages == "rms" and st.aggregate == "rms"


@pytest.mark.parametrize("bad", [{"metrics": ["chi2_nfd"]}, {"over_pages": "rsm"}, {"cost": "zscore"},
                                 {"thresholds": {"nrom": [0.1, 0.2]}}, {"metrics": {"log_yield_ratio": 0.0}}, {"aggregate": "borda"}])
def test_a_wrong_name_or_a_scoreless_choice_is_refused_by_name(bad):
    with pytest.raises(HeimdallError):
        ranking.settings_of(bad)


def test_a_set_s_score_table_is_laid_over_the_run_s():
    st = ranking.settings_of(ranking.overlaid({"over_pages": "rms", "veto_loss": 3.0}, {"over_pages": "median"}))
    assert st.over_pages == "median" and st.veto_loss == 3.0


def test_a_perfect_curve_scores_zero_and_a_point_at_bad_scores_one_per_metric():
    rows = [row("good"), row("bad", chi2_ndf=3.0, log_yield_ratio=0.15)]
    out = {p.point: p for p in ranking.rank(rows, two_categories()).points}
    assert out["good"].loss == 0.0
    assert out["bad"].loss == pytest.approx(1.0)                         # both at their `bad` threshold: cost 1 each


def test_the_loss_is_the_rms_over_purposes_of_the_rms_within_each():
    rows = [row("a", chi2_ndf=2.0, log_yield_ratio=0.0)]          # chi2: z = (2−1)/(3−1) = 0.5, c = log2(1.5); norm: 0
    (p,) = ranking.rank(rows, two_categories()).points
    assert p.loss == pytest.approx(math.sqrt((math.log2(1.5) ** 2 + 0.0) / 2))
    assert p.categories == pytest.approx({"compatibility": math.log2(1.5), "normalisation": 0.0})


def test_the_shares_of_the_loss_sum_to_one_and_name_the_purpose_that_costs():
    rows = [row("a", chi2_ndf=3.0, log_yield_ratio=0.02)]                             # chi2 at bad: 1; norm at good: 0
    (p,) = ranking.rank(rows, two_categories()).points
    assert p.shares["compatibility"] == pytest.approx(1.0) and p.shares["normalisation"] == pytest.approx(0.0)
    assert sum(p.shares.values()) == pytest.approx(1.0)


def test_metrics_of_one_purpose_weigh_one_purpose_not_one_each():
    shape = [n for n, m in metrics.REGISTRY.items() if m.category == "accuracy" and m.default]
    others = [n for n, m in metrics.REGISTRY.items() if m.category == "compatibility" and m.default]
    assert shape and others
    values = {n: metrics.REGISTRY[n].thresholds[1] for n in shape}        # every shape metric at bad: cost 1
    one = ranking.settings_of({"metrics": [*shape[:1], *others]})
    all_ = ranking.settings_of({"metrics": [*shape, *others]})
    r = [row("a", chi2_ndf=1.0, **values)]
    assert ranking.rank(r, one).points[0].loss == pytest.approx(ranking.rank(r, all_).points[0].loss)


def test_a_metric_weight_counts_within_its_category():
    first, second = [n for n, m in metrics.REGISTRY.items() if m.category == "accuracy" and m.default]   # 02's pair
    bad, good = metrics.REGISTRY[first].thresholds[1], metrics.REGISTRY[second].thresholds[0]
    st = ranking.settings_of({"metrics": {first: 3.0, second: 1.0, "tilt": 9.0}})
    # costs 1 (weight 3) and 0 (weight 1): the category is √((3·1 + 1·0) / 4); tilt is another category, its weight does not leak
    (p,) = ranking.rank([row("a", **{first: bad, second: good, "tilt": 0.0})], st).points
    assert p.categories["accuracy"] == pytest.approx(math.sqrt(0.75)) and p.categories["trend"] == 0.0


def test_a_points_values_are_the_median_over_its_pages_of_each_default_and_shown_metric():
    rows = [row("a", page=f"p{i}", chi2_sigma=v, n_eff=e) for i, (v, e) in enumerate([(1.0, 500.0), (3.0, NAN), (8.0, 900.0)])]
    (p,) = ranking.rank(rows, ranking.settings_of(CHI2)).points
    assert p.values["chi2_sigma"] == 3.0 and p.values["n_eff"] == pytest.approx(700.0)      # NaN skipped
    assert set(p.values) == {n for n, m in metrics.REGISTRY.items() if m.default or m.shown} and math.isnan(p.values["poisson_dev"])


def test_adding_a_curve_leaves_the_others_threshold_scores_unchanged():
    rows = [row("a", chi2_ndf=2.0, log_yield_ratio=0.05), row("b", chi2_ndf=1.2, log_yield_ratio=0.01)]
    before = {p.point: p.loss for p in ranking.rank(rows, two_categories()).points}
    more = rows + [row("c", chi2_ndf=40.0, log_yield_ratio=0.9)]
    after = {p.point: p.loss for p in ranking.rank(more, two_categories()).points}
    assert after["a"] == before["a"] and after["b"] == before["b"]


def test_a_pool_normalisation_changes_when_a_curve_is_added_and_says_so():
    rows = [row("a", chi2_ndf=2.0), row("b", chi2_ndf=4.0), row("c", chi2_ndf=3.0)]
    st = ranking.settings_of({"metrics": ["chi2_ndf"], "cost": "minmax"})
    first = {p.point: p.loss for p in ranking.rank(rows, st).points}
    second = {p.point: p.loss for p in ranking.rank(rows + [row("d", chi2_ndf=40.0)], st).points}
    assert first == {"a": 0.0, "b": 1.0, "c": 0.5}
    assert second["b"] != first["b"]                                     # one wild curve compressed the rest


def test_points_of_different_cells_are_scored_apart():
    rows = [row("a", cell="x", chi2_ndf=1.0), row("a", cell="y", chi2_ndf=3.0)]
    out = {(p.cell, p.point): p.loss for p in ranking.rank(rows, ranking.settings_of({"metrics": ["chi2_ndf"]})).points}
    assert out == {("x", "a"): 0.0, ("y", "a"): pytest.approx(1.0)}


def test_a_page_s_reference_row_is_not_scored():
    rows = [row("ref", reference=True), row("a", chi2_ndf=3.0)]
    out = ranking.rank(rows, ranking.settings_of({"metrics": ["chi2_ndf"]}))
    assert [p.point for p in out.points] == ["a"]


def test_pages_against_data_win_over_pages_against_a_curve():
    rows = [row("ref", page="vs_curve", reference=True), row("a", page="vs_curve", chi2_ndf=3.0),
            row("a", page="vs_data", chi2_ndf=1.0)]
    (p,) = ranking.rank(rows, ranking.settings_of({"metrics": ["chi2_ndf"]})).points
    assert set(p.pages) == {"vs_data"} and p.loss == 0.0


def test_the_worst_page_and_the_veto():
    rows = [row("a", page="good", chi2_ndf=1.0), row("a", page="awful", chi2_ndf=9.0)]
    st = ranking.settings_of({"metrics": ["chi2_ndf"], "veto_loss": 2.0})
    (p,) = ranking.rank(rows, st).points
    assert p.worst_page == "awful" and p.worst_loss == pytest.approx(math.log2(5.0))     # z = (9−1)/2 = 4, c = log2(5)
    assert p.vetoed is True
    assert ranking.rank(rows, ranking.settings_of({"metrics": ["chi2_ndf"], "veto_loss": 5.0})).points[0].vetoed is False
    assert ranking.rank(rows, ranking.settings_of({"metrics": ["chi2_ndf"]})).points[0].vetoed is False


def test_page_weights_by_figure_and_by_glob_and_the_figure_wins():
    rows = [row("a", page="p1", obj="run/pt/jet_pt", chi2_ndf=1.0), row("a", page="p2", obj="run/pt/mass", chi2_ndf=3.0)]
    st = ranking.settings_of({"metrics": ["chi2_ndf"], "weights": {"jet_*": 3.0}})
    assert ranking.rank(rows, st).points[0].loss == pytest.approx(math.sqrt((3 * 0 + 1 * 1) / 4))    # rms: Σw l² / Σw
    by_figure = ranking.rank(rows, st, page_weights={"p1": 1.0, "p2": 1.0}).points[0].loss
    assert by_figure == pytest.approx(math.sqrt(0.5))
    assert ranking.page_weight("run/pt/jet_pt", "p1", st, None) == 3.0
    assert ranking.page_weight("run/pt/mass", "p2", st, None) == 1.0


def test_the_mean_is_a_setting_median_ignores_one_bad_page():
    rows = [row("a", page=f"p{i}", chi2_ndf=1.0) for i in range(4)] + [row("a", page="bad", chi2_ndf=9.0)]
    rms = ranking.rank(rows, ranking.settings_of({"metrics": ["chi2_ndf"]})).points[0].loss
    med = ranking.rank(rows, ranking.settings_of({"metrics": ["chi2_ndf"], "over_pages": "median"})).points[0].loss
    assert med == 0.0 and rms > 1.0


def test_a_missing_metric_is_skipped_not_scored_as_zero():
    rows = [row("a", chi2_ndf=NAN, log_yield_ratio=0.15)]
    (p,) = ranking.rank(rows, two_categories()).points
    assert list(p.categories) == ["normalisation"] and p.loss == pytest.approx(1.0)


def test_a_point_with_nothing_to_score_has_a_nan_score_and_ranks_last():
    rows = [row("none", chi2_ndf=NAN, log_yield_ratio=NAN), row("ok", chi2_ndf=1.0, log_yield_ratio=0.0)]
    out = ranking.rank(rows, two_categories())
    assert math.isnan({p.point: p for p in out.points}["none"].loss)
    assert [p.point for p in out.of()] == ["ok", "none"]


def test_dominated_is_pareto_over_categories():
    rows = [row("best", chi2_ndf=1.0, log_yield_ratio=0.0), row("worse", chi2_ndf=2.0, log_yield_ratio=0.1),
            row("tradeoff", chi2_ndf=1.0, log_yield_ratio=0.3), row("other", chi2_ndf=3.0, log_yield_ratio=0.0)]
    st = ranking.settings_of({"metrics": ["chi2_ndf", "log_yield_ratio"], "dominated": True})
    out = {p.point: p.dominated for p in ranking.rank(rows, st).points}
    assert out == {"best": False, "worse": True, "tradeoff": True, "other": True}


# ── the null distributions ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("chi2, ndf, p", [(3.841459, 1, 0.05), (5.991465, 2, 0.05), (18.307038, 10, 0.05), (0.0, 5, 1.0),
                                          (6.634897, 1, 0.01)])
def test_the_chi_square_survival_function_matches_the_tables(chi2, ndf, p):
    assert ranking.chi2_p(chi2, ndf) == pytest.approx(p, abs=2e-6)


def test_the_gaussian_nulls():
    assert ranking.null_p("tail_excess_sigma", 1.959964, {}) == pytest.approx(0.05, abs=1e-6)       # two-sided
    assert ranking.null_p("chi2_sigma", 1.644854, {}) == pytest.approx(0.05, abs=1e-6)     # one-sided
    assert ranking.null_p("chi2_ndf", 1.0, {"ndf": 10}) == pytest.approx(ranking.chi2_p(10, 10))
    with pytest.raises(HeimdallError, match="no null"):
        ranking.null_p("log_yield_ratio", 0.1, {})


def test_surprisal_is_minus_the_log_of_the_null_probability():
    rows = [row("a", chi2_ndf=1.8307038, ndf=10)]                         # χ² = 18.307: p = 0.05
    st = ranking.settings_of({"metrics": ["chi2_ndf"], "cost": "surprisal"})
    assert ranking.rank(rows, st).points[0].loss == pytest.approx(-math.log(0.05), rel=1e-4)


def test_surprisal_refuses_a_metric_with_no_null():
    with pytest.raises(HeimdallError, match="no null"):
        ranking.rank([row("a")], ranking.settings_of({"metrics": ["log_yield_ratio"], "cost": "surprisal"}))


# ── the pool normalisations ───────────────────────────────────────────────────────────────────

def test_median_normalisation_makes_the_typical_curve_cost_one():
    rows = [row("a", chi2_ndf=2.0), row("b", chi2_ndf=4.0), row("c", chi2_ndf=8.0)]
    out = {p.point: p.loss for p in ranking.rank(rows, ranking.settings_of({"metrics": ["chi2_ndf"], "cost": "median"})).points}
    assert out == {"a": pytest.approx(0.5), "b": pytest.approx(1.0), "c": pytest.approx(2.0)}


def test_mad_normalisation_orders_by_the_metric_and_stays_positive():
    rows = [row(c, chi2_ndf=v) for c, v in zip("abcde", (1.0, 1.1, 1.2, 1.3, 9.0))]
    out = ranking.rank(rows, ranking.settings_of({"metrics": ["chi2_ndf"], "cost": "mad"}))
    s = {p.point: p.loss for p in out.points}
    assert all(v > 0 for v in s.values()) and s["a"] < s["d"] < s["e"]


def test_a_pool_normalisation_refuses_a_higher_is_better_metric():
    higher = [n for n, m in metrics.REGISTRY.items() if m.polarity == "higher"]
    if not higher:
        pytest.skip("no higher-is-better metric")
    rows = [row("a", **{higher[0]: 0.5})]
    with pytest.raises(HeimdallError, match="pool"):
        ranking.rank(rows, ranking.settings_of({"metrics": [higher[0]], "cost": "minmax"}))


# ── CRITIC ────────────────────────────────────────────────────────────────────────────────────

def test_critic_needs_enough_curves_to_correlate():
    rows = [row(f"p{i}", chi2_ndf=1.0 + i, log_yield_ratio=0.01 * i) for i in range(5)]
    with pytest.raises(HeimdallError, match="critic"):
        ranking.rank(rows, ranking.settings_of({"metrics": ["chi2_ndf", "log_yield_ratio"], "weights_by": "critic"}))


def test_critic_downweights_a_metric_that_repeats_another():
    # three metrics, two of which are the same ranking: the independent one weighs more than each of the repeated pair
    shape, tilt, norm = "log_dev_shrunk", "tilt", "log_yield_ratio"
    rows = []
    for i in range(20):
        rows.append(row(f"p{i}", log_dev_shrunk=0.01 * i, tilt=0.01 * i + 0.001, log_yield_ratio=0.01 * ((i * 7) % 20)))
    obs = ranking.observations(rows, ranking.settings_of({"metrics": [shape, tilt, norm]}))
    st = ranking.settings_of({"metrics": [shape, tilt, norm]})
    ranking.costs(obs, st)
    w = ranking.critic_weights(obs, [shape, tilt, norm])
    assert w[norm] > w[shape] and w[norm] > w[tilt]
    assert sum(w.values()) == pytest.approx(3.0)


def test_critic_through_the_score_runs_and_keeps_the_ranking_of_a_clear_case():
    rows = [row(f"p{i}", chi2_ndf=1.0 + 0.1 * i, log_yield_ratio=0.01 * i, log_dev_shrunk=0.01 * i) for i in range(20)]
    st = ranking.settings_of({"metrics": ["chi2_ndf", "log_yield_ratio", "log_dev_shrunk"], "weights_by": "critic"})
    order = [p.point for p in ranking.rank(rows, st).of()]
    assert order[0] == "p0" and order[-1] == "p19"


# ── the other aggregators ─────────────────────────────────────────────────────────────────────

def test_fisher_orders_by_the_probability_and_is_pool_independent():
    rows = [row("fit", chi2_ndf=1.0), row("poor", chi2_ndf=2.0), row("awful", chi2_ndf=5.0)]
    st = ranking.settings_of({"metrics": ["chi2_ndf"], "aggregate": "fisher"})
    out = ranking.rank(rows, st)
    s = {p.point: p.loss for p in out.points}
    assert s["fit"] < s["poor"] < s["awful"]
    assert s["fit"] == pytest.approx(-2 * math.log(ranking.chi2_p(10, 10)))
    again = {p.point: p.loss for p in ranking.rank(rows[:2], st).points}
    assert again["fit"] == s["fit"]
    assert any("fisher" in n for n in out.notes)


def test_topsis_is_pool_dependent_and_says_so():
    rows = [row("a", chi2_ndf=1.0, log_yield_ratio=0.0), row("b", chi2_ndf=2.0, log_yield_ratio=0.1), row("c", chi2_ndf=3.0, log_yield_ratio=0.2)]
    st = ranking.settings_of({"metrics": ["chi2_ndf", "log_yield_ratio"], "aggregate": "topsis"})
    out = ranking.rank(rows, st)
    s = {p.point: p.loss for p in out.points}
    assert s["a"] == pytest.approx(0.0) and s["c"] == pytest.approx(1.0) and 0 < s["b"] < 1
    assert any("rank reversal" in n for n in out.notes)
    wider = {p.point: p.loss for p in ranking.rank(rows + [row("d", chi2_ndf=9.0, log_yield_ratio=0.9)], st).points}
    assert wider["b"] != s["b"]


def test_promethee_ranks_by_net_outranking_flow():
    rows = [row("a", chi2_ndf=1.0), row("b", chi2_ndf=2.0), row("c", chi2_ndf=3.0)]
    st = ranking.settings_of({"metrics": ["chi2_ndf"], "aggregate": "promethee"})
    out = ranking.rank(rows, st)
    s = {p.point: p.loss for p in out.points}
    assert s["a"] < s["b"] < s["c"]
    assert any("promethee" in n for n in out.notes)


# ── head to head ──────────────────────────────────────────────────────────────────────────────

def test_head_to_head_gives_the_pairwise_differences_and_counts_no_wins():
    rows = [row("a", chi2_ndf=1.0, log_yield_ratio=0.0), row("b", chi2_ndf=3.0, log_yield_ratio=0.02), row("c", chi2_ndf=2.0, log_yield_ratio=0.15)]
    out = ranking.head_to_head(rows, "p", two_categories())
    assert out["points"] == ["a", "b", "c"]
    pairs = {(p["a"], p["b"]): p for p in out["pairs"]}
    assert set(pairs) == {("a", "b"), ("a", "c"), ("b", "c")}
    assert pairs[("a", "b")]["metrics"]["chi2_ndf"] == pytest.approx(0.0 - 1.0)       # a is better by one on χ²
    assert pairs[("a", "b")]["loss"] < 0
    assert pairs[("b", "c")]["metrics"]["log_yield_ratio"] == pytest.approx(0.0 - 1.0)
    assert not any("wins" in p for p in out["pairs"])


def test_head_to_head_on_a_page_that_is_not_there_names_the_pages():
    with pytest.raises(HeimdallError, match="no page"):
        ranking.head_to_head([row("a")], "nope")


# ── marginals and baselines ───────────────────────────────────────────────────────────────────

def sweep_rows(losses: dict, drop=()):
    """A point per (generator, pdf), its d01 page's χ²/ndf set so that the page costs losses[(g, p)] and its d02 page twice that:
    a cost c is z = 2^c − 1 on the hinge (1, 3), so χ²/ndf = 1 + 2·(2^c − 1)."""
    rows, axes = [], {}
    for (g, p), loss in losses.items():
        if (g, p) in drop:
            continue
        name = f"{g}_{p}"
        rows.append(row(name, page="c/d01-x01-y01", cell="c", obj="run/pt/d01-x01-y01", chi2_ndf=1.0 + 2.0 * (2 ** loss - 1)))
        rows.append(row(name, page="c/d02-x01-y01", cell="c", obj="run/pt/d02-x01-y01", chi2_ndf=1.0 + 2.0 * (2 ** (2 * loss) - 1)))
        axes[name] = {"generator": g, "pdf": p}
    return rows, axes


BALANCED = {("py8", "A"): 0.5, ("py8", "B"): 1.0, ("sh3", "A"): 1.5, ("sh3", "B"): 2.0}
ONE = ranking.settings_of({"metrics": ["chi2_ndf"]})


def test_a_marginal_is_the_mean_score_over_the_points_having_each_value():
    rows, axes = sweep_rows(BALANCED)
    out = ranking.rank(rows, ONE)
    by = {m.quantity: m for m in ranking.marginals(out, axes)}
    assert set(by) == {"generator", "pdf"}
    s = {p.point: p.loss for p in out.points}
    py8 = next(r for r in by["generator"].rows if r[0] == "py8")
    assert py8[1] == pytest.approx(math.sqrt((s["py8_A"] ** 2 + s["py8_B"] ** 2) / 2)) and py8[2] == 2
    assert [r[0] for r in by["generator"].rows] == ["py8", "sh3"]                 # best first
    assert by["generator"].confounded == [] and by["pdf"].confounded == []
    assert set(py8[3]) == {"compatibility"}


def test_a_marginal_says_which_values_confound_it():
    rows, axes = sweep_rows(BALANCED, drop=[("sh3", "B")])                       # B only with py8
    by = {m.quantity: m for m in ranking.marginals(ranking.rank(rows, ONE), axes)}
    assert by["generator"].confounded == ["pdf = B only with generator = py8"]
    assert by["pdf"].confounded == ["generator = sh3 only with pdf = A"]


def test_an_axis_that_is_not_varied_is_refused_and_by_chooses_the_axes():
    rows, axes = sweep_rows(BALANCED)
    out = ranking.rank(rows, ONE)
    only = ranking.settings_of({"metrics": ["chi2_ndf"], "by": "pdf"})
    assert [m.quantity for m in ranking.marginals(out, axes, only)] == ["pdf"]
    with pytest.raises(HeimdallError, match="not a quantity"):
        ranking.marginals(out, axes, ranking.settings_of({"metrics": ["chi2_ndf"], "by": ["beams"]}))
    fixed = {k: {**v, "generator": "py8"} for k, v in axes.items()}
    assert [m.quantity for m in ranking.marginals(out, fixed)] == ["pdf"]               # a fixed axis is not varied


def test_a_point_with_no_axes_never_enters_a_marginal():
    rows, axes = sweep_rows(BALANCED)
    rows += [row("merged", page="c/d01-x01-y01", cell="c", obj="run/pt/d01-x01-y01", chi2_ndf=99.0)]
    by = {m.quantity: m for m in ranking.marginals(ranking.rank(rows, ONE), axes)}
    assert sum(r[2] for r in by["generator"].rows) == 4


def test_a_baseline_is_taken_against_the_point_equal_on_every_other_axis():
    rows, axes = sweep_rows(BALANCED)
    out = ranking.rank(rows, ONE)
    result = ranking.baseline(out, axes, {"generator": "py8"})
    s = {p.point: p.loss for p in out.points}
    by = {r.point: r for r in result.rows}
    assert by["sh3_A"].partner == "py8_A" and by["sh3_A"].delta == pytest.approx(s["sh3_A"] - s["py8_A"])
    assert by["sh3_B"].partner == "py8_B" and by["py8_B"].delta == 0 and by["py8_B"].is_baseline
    assert by["sh3_A"].objects["d01-x01-y01"] == pytest.approx((1.5 - 0.5))      # the page loss less its partner's
    assert by["sh3_A"].objects["d02-x01-y01"] == pytest.approx(2 * (1.5 - 0.5))
    assert result.unmatched == []


def test_a_baseline_by_point_name_and_a_point_without_a_partner_is_listed_not_dropped():
    rows, axes = sweep_rows(BALANCED, drop=[("py8", "B")])
    out = ranking.rank(rows, ONE)
    result = ranking.baseline(out, axes, {"generator": "py8"})
    assert [(p, why.split(" but")[0]) for _, p, why in result.unmatched] == [("sh3_B", "no point equal to it")]
    one = ranking.baseline(out, axes, "py8_A")                                      # a name: that point's every axis
    assert {r.partner for r in one.rows} == {"py8_A"} and len(one.rows) == 3
    with pytest.raises(HeimdallError, match="no point 'nope'"):
        ranking.baseline(out, axes, "nope")
    with pytest.raises(HeimdallError, match="not a quantity"):
        ranking.baseline(out, axes, {"beams": "ep"})
    with pytest.raises(HeimdallError, match="no baseline"):
        ranking.baseline(out, axes)


def test_three_points_on_two_pages_lose_what_the_hinge_and_the_rms_give_by_hand():
    """chi2_ndf hinged on (1, 3), log_yield_ratio on (0.02, 0.15), each excess z compressed to c = log2(1 + z); a page's loss is
    the RMS over its two categories, a point's the RMS over its two pages. a: z (0.5, 0) and (0, 0.5), so c = log2 1.5 on one
    category of each page: each page log2(1.5)/√2, and so the point. b: z (1, 1) and (0, 0): c 1 and 0, pages 1 and 0, so √0.5.
    c: z (1.5, 0) and (0.25, 0.25): page 1 log2(2.5)/√2, page 2 log2(1.25), so √((log2(2.5)²/2 + log2(1.25)²) / 2)."""
    values = {("a", "p1"): (2.0, 0.02), ("a", "p2"): (1.0, 0.085), ("b", "p1"): (3.0, 0.15), ("b", "p2"): (1.0, 0.02),
              ("c", "p1"): (4.0, 0.02), ("c", "p2"): (1.5, 0.0525)}
    rows = [row(point, page=page, chi2_ndf=chi2, log_yield_ratio=norm) for (point, page), (chi2, norm) in values.items()]
    got = {p.point: p.loss for p in ranking.rank(rows, two_categories()).points}
    assert got["a"] == pytest.approx(math.log2(1.5) / math.sqrt(2), abs=1e-12)                  # 0.41363
    assert got["b"] == pytest.approx(0.7071067811865476, abs=1e-12)
    assert got["c"] == pytest.approx(math.sqrt((math.log2(2.5) ** 2 / 2 + math.log2(1.25) ** 2) / 2), abs=1e-12)   # 0.69907


# ── the gates and the order ─────────────────────────────────────────────────────────────────────

def gated(point, loss_chi2=1.0, pages=1, failed=0, failure="peak_bin_ratio", cell="c"):
    """A point on `pages` pages, its chi2_ndf on each; `failed` of them fail the gate `failure`."""
    out = []
    for i in range(pages):
        bad = i < failed
        out.append(row(point, page=f"p{i}", cell=cell, chi2_ndf=loss_chi2, peak_bin_ratio=4.0 if bad and failure == "peak_bin_ratio" else 0.0,
                       yield_sign=1.0 if bad and failure == "yield_sign" else 0.0))
    return out


CHI2 = {"metrics": ["chi2_ndf"]}


def test_a_vetoed_point_ranks_after_every_passing_point_whatever_the_losses():
    import random
    rng = random.Random(20261110)
    for _ in range(200):
        rows = []
        for i in range(rng.randint(2, 7)):
            rows += gated(f"pt{i}", loss_chi2=rng.choice([1.0, rng.uniform(1, 40)]), pages=3, failed=rng.choice([0, 0, 1, 2, 3]),
                          failure=rng.choice(["peak_bin_ratio", "yield_sign"]))
        order = ranking.rank(rows, ranking.settings_of(CHI2)).points
        flags = [p.vetoed for p in order]
        assert flags == sorted(flags)
        assert all((p.rank is None) == p.vetoed for p in order)


def test_among_the_vetoed_fewer_failed_pages_first_then_the_smaller_loss():
    rows = (gated("three", 1.0, 3, 3) + gated("one", 30.0, 3, 1) + gated("two_bad", 20.0, 3, 2) + gated("two_good", 2.0, 3, 2)
            + gated("ok", 40.0, 3, 0) + [row("empty", page="p0", chi2_ndf=NAN, peak_bin_ratio=0.0, yield_sign=0.0)])
    out = ranking.rank(rows, ranking.settings_of(CHI2))
    assert [p.point for p in out.points] == ["ok", "empty", "one", "two_good", "two_bad", "three"]
    assert [p.rank for p in out.points] == [1, None, None, None, None, None]
    one = out.points[2]
    assert one.failed_pages == 1 and one.gate_reason == "a bin 10^4 × reference on 1 of 3 pages"


def test_ties_at_three_figures_share_a_rank_and_the_next_skips():
    rows = [row("d", chi2_ndf=4.0), row("b", chi2_ndf=2.0), row("c", chi2_ndf=2.0001), row("a", chi2_ndf=1.5)]
    out = ranking.rank(rows, ranking.settings_of(CHI2))
    assert [(p.point, p.rank) for p in out.points] == [("a", 1), ("b", 2), ("c", 2), ("d", 4)]


def test_gates_off_vetoes_none_and_the_record_says_where_that_came_from():
    rows = gated("bad", 1.0, 2, 2) + gated("ok", 3.0, 2, 0)
    on = ranking.rank(rows, ranking.settings_of(CHI2))
    assert [p.point for p in on.points] == ["ok", "bad"] and on.points[1].vetoed
    off = ranking.rank(rows, ranking.settings_of({**CHI2, "gates": False}))
    assert [p.point for p in off.points] == ["bad", "ok"] and not any(p.vetoed for p in off.points)
    assert "gates: off ([ranking]). no gate metric is applied" in off.method.lines("gates")


def test_a_named_gate_list_leaves_the_other_gate_unapplied():
    rows = gated("negative", 1.0, 2, 2, failure="yield_sign")
    st = ranking.settings_of({**CHI2, "gates": ["peak_bin_ratio"]})
    (p,) = ranking.rank(rows, st).points
    assert not p.vetoed and p.rank == 1
    (q,) = ranking.rank(rows, ranking.settings_of(CHI2)).points
    assert q.vetoed and q.gate_reason == "a yield of zero or less on 2 of 2 pages"
    with pytest.raises(HeimdallError, match="not a gate metric"):
        ranking.settings_of({**CHI2, "gates": ["chi2_ndf"]})


def test_veto_loss_is_a_gate_on_the_page_loss():
    rows = [row("a", page="good", chi2_ndf=1.0), row("a", page="awful", chi2_ndf=9.0), row("b", page="good", chi2_ndf=5.0),
            row("b", page="awful", chi2_ndf=5.0)]
    out = ranking.rank(rows, ranking.settings_of({**CHI2, "veto_loss": 2.0}))      # a's awful page: z 4, c log2 5 = 2.32 > 2
    assert [p.point for p in out.points] == ["b", "a"]                              # b's pages: z 2, c log2 3 = 1.58: it passes
    assert out.points[1].gate_reason == "a page loss of up to 2.32 on 1 of 2 pages"


def test_a_table_without_the_gate_columns_vetoes_none_and_says_not_evaluated():
    out = ranking.rank([row("a"), row("b", chi2_ndf=3.0)], ranking.settings_of(CHI2))
    assert not any(p.vetoed for p in out.points)
    lines = out.method.lines("gates")
    assert any(l.startswith("gate peak_bin_ratio: 3 (table). not evaluated: no `peak_bin_ratio` column") for l in lines)
    assert any("not evaluated: no `yield_sign` column" in l for l in lines)


def test_the_record_holds_every_stage_and_the_sources_follow_the_flags():
    st = ranking.settings_of({"cost": "thresholds"}, {"by": ["pdf"]}, None)
    assert st.sources["cost"] == "[ranking]" and st.sources["by"] == "--by" and st.sources["over_pages"] == "default"
    assert ranking.settings_of({"cost": "mad"}, sources={"cost": "set lo"}).sources["cost"] == "set lo"
    assert ranking.settings_of(flags={"head_to_head": "all"}).sources["head_to_head"] == "--head-to-head"
    record = ranking.rank([row("a")], ranking.settings_of(CHI2)).method.as_dict()
    assert list(record) == list(ranking.Method.STAGES) and record["marginals"] == []                             # 4.2
    assert all(record[stage] for stage in ("gates", "metrics", "cost", "category", "page_loss", "pages", "order", "optin"))


def test_cells_are_one_order_when_their_pages_match_else_an_order_a_cell():
    same = [row("a", cell="x", chi2_ndf=3.0), row("b", cell="y", chi2_ndf=1.0)]
    out = ranking.rank(same, ranking.settings_of(CHI2))
    assert out.flat and [(p.point, p.rank) for p in out.points] == [("b", 1), ("a", 2)]
    apart = [row("a", cell="x", chi2_ndf=3.0), row("b", cell="y", obj="run/pt/other", chi2_ndf=1.0)]
    out = ranking.rank(apart, ranking.settings_of(CHI2))
    assert not out.flat and [(p.point, p.rank) for p in out.points] == [("a", 1), ("b", 1)]
    assert out.method.lines("order")[-1].startswith("cells: banded (table).")


# ── compression and the record of how a loss is made ────────────────────────────────────────────

def test_raising_one_metric_past_good_never_lowers_the_loss():
    import random
    rng = random.Random(311)
    names = ["chi2_ndf", "log_yield_ratio", "log_dev_shrunk", "tilt", "peak_pull2"]
    st = ranking.settings_of({"metrics": names})
    for _ in range(200):
        values = {n: rng.uniform(0, 3) if n == "tilt" else rng.uniform(0, 0.4) if n != "chi2_ndf" else rng.uniform(0.5, 30) for n in names}
        before = ranking.rank([row("a", **values)], st).points[0].loss
        name = rng.choice(names)
        after = ranking.rank([row("a", **{**values, name: values[name] * rng.uniform(1, 50) + 1e-3})], st).points[0].loss
        assert after >= before - 1e-12, (name, values)


def test_adding_a_point_changes_no_other_points_loss_over_random_tables():
    import random
    rng = random.Random(312)
    st = ranking.settings_of({"metrics": ["chi2_ndf", "log_yield_ratio", "tilt"]})
    for _ in range(50):
        rows = [row(f"p{i}", page=f"g{j}", chi2_ndf=rng.uniform(0.5, 20), log_yield_ratio=rng.uniform(0, 0.5), tilt=rng.uniform(0, 4))
                for i in range(4) for j in range(3)]
        before = {p.point: p.loss for p in ranking.rank(rows, st).points}
        more = rows + [row("new", page=f"g{j}", chi2_ndf=rng.uniform(0.5, 100), log_yield_ratio=1.0, tilt=9.0) for j in range(3)]
        after = {p.point: p.loss for p in ranking.rank(more, st).points}
        assert all(after[k] == before[k] for k in before)


ROWS_R19 = [row("a", chi2_ndf=1.2, log_yield_ratio=0.03), row("b", chi2_ndf=2.5, log_yield_ratio=0.2),
            row("c", chi2_ndf=6.0, log_yield_ratio=0.01), row("d", chi2_ndf=1.0, log_yield_ratio=0.09)]


@pytest.mark.parametrize("cost,metrics_on,expected", [               # each as the engine gave it before compression came
    ("median", ["chi2_ndf", "log_yield_ratio"], {"a": 0.5791135766815168, "b": 2.5433503087374962}),
    ("mad", ["chi2_ndf", "log_yield_ratio"], {"a": 0.4576540454378009, "c": 2.667813189863337}),
    ("minmax", ["chi2_ndf", "log_yield_ratio"], {"a": 0.07962516062769448, "b": 0.73824115301167}),
    ("surprisal", ["chi2_ndf"], {"d": 0.8198600776149134, "c": 19.435604408046576}),
])
def test_an_opt_in_cost_is_not_compressed_and_its_numbers_do_not_move(cost, metrics_on, expected):
    out = ranking.rank(ROWS_R19, ranking.settings_of({"metrics": metrics_on, "cost": cost}))
    got = {p.point: p.loss for p in out.points}
    assert {k: got[k] for k in expected} == pytest.approx(expected, rel=1e-12)
    (line,) = out.method.lines("cost")
    assert line.startswith(f"cost: {cost} ([ranking]).") and "not compressed" in line
    assert ("pool-dependent" in line) == (cost != "surprisal")


def test_the_record_names_each_metric_its_thresholds_weight_and_what_is_computed_but_not_scored():
    rows = [row("a", tail_slope=0.3, n_eff=5000.0, peak_bin_ratio=0.0, yield_sign=0.0)]
    st = ranking.settings_of({"metrics": {"chi2_ndf": 2, "log_yield_ratio": 1, "chi2_sigma": 1},
                              "thresholds": {"log_yield_ratio": [0.01, 0.1]}})
    lines = ranking.rank(rows, st).method.lines("metrics")
    assert "chi2_ndf: lower, linear scale (registry). category compatibility" in lines
    assert any(l.startswith("thresholds of chi2_ndf: 1, 3 (registry).") for l in lines)
    assert "thresholds of log_yield_ratio: 0.01, 0.1 ([ranking])." in lines
    assert "weight of chi2_ndf: 2 ([ranking])." in lines
    assert any(l.startswith("chi2_sigma: not in this table (table).") for l in lines)
    assert any(l.startswith("tail_slope: computed, not scored (registry). a descriptor") for l in lines)
    assert any(l.startswith("n_eff: computed, not scored (registry). shown") for l in lines)
    assert not any(l.startswith(("peak_bin_ratio", "yield_sign")) for l in lines)          # gates are the Gates stage's
    record = ranking.rank(rows, st).method
    assert record.lines("cost")[0].startswith("cost: thresholds (default).") and "log₂(1 + z)" in record.lines("cost")[0]
    assert [c.name for c in record.optin] == ["aggregate", "dominated", "weights_by", "baseline", "head_to_head"]
    assert "categories with a cost: compatibility, normalisation (table)." in record.lines("page_loss")


def test_the_pages_stage_names_each_weight_and_its_source_and_the_pages_left_out():
    rows = [row("a", page="p1", obj="run/pt/jet_pt"), row("a", page="p2", obj="run/pt/mass"), row("a", page="p3", obj="run/pt/eta"),
            row("data", page="vs_curve", reference=True), row("a", page="vs_curve")]
    st = ranking.settings_of({**CHI2, "weights": {"jet_*": 2.0}})
    lines = ranking.rank(rows, st, page_weights={"p2": 4.0}).method.lines("pages")
    assert "page p1: 2 ([ranking]). the glob 'jet_*'" in lines and "page p2: 4 (figure)." in lines
    assert any(l.startswith("every other page: 1 (default). 1 page(s)") for l in lines)
    assert any(l.startswith("pages left out: 1 (table). against their first curve") for l in lines)
