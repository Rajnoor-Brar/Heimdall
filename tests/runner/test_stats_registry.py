"""The registries (framework/stats): every metric and mean has what the scoring and the report need, and is tested by name."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from stats import means, metrics

TESTS = Path(__file__).parent
DEFAULTS = {"chi2_ndf", "log_yield_ratio", "log_dev_shrunk", "tilt", "peak_pull2"}


def is_tested(name: str, *files: str) -> bool:
    text = "\n".join((TESTS / f).read_text(encoding="utf-8") for f in files)
    return bool(re.search(rf"[\"\'\.]{re.escape(name)}[\"\'\(\s,\)\[]", text))


@pytest.mark.parametrize("name", sorted(metrics.REGISTRY))
def test_every_metric_has_a_purpose_a_polarity_a_scale_a_note_and_a_test(name):
    m = metrics.REGISTRY[name]
    assert m.name == name
    assert m.category in metrics.CATEGORIES
    assert m.polarity in ("lower", "higher", "one", "descriptor")
    assert m.scale in ("linear", "log")
    assert m.note.strip(), "say what it measures and what it is blind to"
    assert is_tested(name, "test_stats_metrics.py"), f"no test names {name}"


@pytest.mark.parametrize("name", sorted(metrics.REGISTRY))
def test_a_scored_metric_has_ordered_thresholds_and_the_reason_for_them(name):
    m = metrics.REGISTRY[name]
    if m.polarity == "descriptor":
        assert m.thresholds is None                                       # a descriptor: it has no better or worse
        return
    if m.gate is not None and m.thresholds is None:                       # a gate only: its level is its test
        assert m.gate > 0 and m.note.strip()
        return
    assert m.thresholds is not None and m.why.strip(), f"{name}: thresholds and why"
    good, bad = m.thresholds
    assert (good > bad) if m.polarity == "higher" else (good < bad)


def test_exactly_the_five_are_on_by_default():
    assert {n for n, m in metrics.REGISTRY.items() if m.default} == DEFAULTS


def test_every_category_has_a_metric_and_the_defaults_cover_all_but_three():
    used = {m.category for m in metrics.REGISTRY.values()}
    assert used == set(metrics.CATEGORIES)
    assert {n for n, m in metrics.REGISTRY.items() if m.gate is not None} == {"peak_bin_ratio", "yield_sign"}
    on = {m.category for m in metrics.REGISTRY.values() if m.default}
    assert set(metrics.CATEGORIES) - on == {"similarity", "integrity", "quality"}
    assert list(metrics.CATEGORIES) == ["compatibility", "normalisation", "accuracy", "similarity", "trend", "defects",
                                        "integrity", "quality"]


def test_a_metric_that_needs_no_reference_says_so_and_a_pooled_one_is_flagged():
    for m in metrics.REGISTRY.values():
        if m.category == "quality":
            assert not m.needs_reference, m.name
        if m.pool:
            assert "pool-dependent" in m.note, m.name


@pytest.mark.parametrize("name", sorted(means.REGISTRY))
def test_every_mean_has_a_guard_a_note_an_error_rule_and_a_test(name):
    m = means.REGISTRY[name]
    assert m.name == name and m.guard.strip() and m.note.strip() and callable(m.error)
    assert is_tested(name, "test_stats_means.py"), f"no test names {name}"


def test_every_purpose_says_what_it_asks_and_every_metric_has_a_title():
    assert set(metrics.QUESTIONS) == set(metrics.CATEGORIES)
    assert all(text.strip().endswith((".", "?")) for text in metrics.QUESTIONS.values())
    assert set(metrics.TITLES) == set(metrics.REGISTRY)
    assert set(metrics.FORMULAS) <= set(metrics.REGISTRY)


@pytest.mark.parametrize("name", sorted(metrics.REGISTRY))
def test_a_metric_describes_itself_with_its_thresholds_and_a_setting_overrides_them(name):
    m = metrics.REGISTRY[name]
    text = metrics.describe(name)
    assert text.startswith(f"{metrics.title_of(name)}: {m.note}")
    assert ("Scored from" in text) == (m.thresholds is not None)
    if m.thresholds:
        assert metrics.describe(name, (0.5, 2.0)).endswith("Scored from 0.5 (cost 0) to 2 (cost 1).")


def test_every_polarity_has_a_glyph_an_ascii_form_and_a_phrase():
    for table in (metrics.GLYPH, metrics.ASCII, metrics.PHRASE):
        assert set(table) == set(metrics.POLARITIES)
    assert metrics.REGISTRY["n_eff"].scale == "log"
    assert {n for n, m in metrics.REGISTRY.items() if m.scale == "log"} == {"n_eff"}


def test_an_old_id_is_an_alias_of_one_metric_and_never_a_metric_itself():
    assert len(metrics.ALIASES) == 24
    for old, new in metrics.ALIASES.items():
        assert old not in metrics.REGISTRY, old
        assert new in metrics.REGISTRY, (old, new)
        assert metrics.resolve(old) == new
    assert metrics.resolve("tilt") == "tilt"
    assert metrics.ALIASES["wmape_yield"] == "yield_weighted_abs_dev" and metrics.ALIASES["wmape_axis"] == "mean_abs_ratio_dev"


def test_no_two_metrics_share_a_function():
    fns = [m.fn for m in metrics.REGISTRY.values()]
    assert len(fns) == len(set(fns))


def test_an_old_id_evaluates_and_describes_as_its_new_one():
    import numpy as np
    from stats import bins
    lo = np.arange(10, dtype=float)
    ref = np.full(10, 10.0)
    curve = bins.Curve(lo, lo + 1, ref * np.linspace(0.9, 1.2, 10), ref * 0.05, ref, ref * 0.05)
    assert metrics.evaluate("shape", curve) == metrics.evaluate("log_dev_shrunk", curve)
    assert metrics.describe("worst") == metrics.describe("peak_pull2")
