"""The registries (framework/stats): every metric and mean has what the scoring and the report need, and is tested by name."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from stats import means, metrics

TESTS = Path(__file__).parent
DEFAULTS = {"chi2_ndf", "norm", "shape", "tilt", "worst"}


def is_tested(name: str, *files: str) -> bool:
    text = "\n".join((TESTS / f).read_text(encoding="utf-8") for f in files)
    return bool(re.search(rf"[\"\'\.]{re.escape(name)}[\"\'\(\s,\)\[]", text))


@pytest.mark.parametrize("name", sorted(metrics.REGISTRY))
def test_every_metric_has_a_purpose_a_direction_a_note_and_a_test(name):
    m = metrics.REGISTRY[name]
    assert m.name == name
    assert m.purpose in metrics.PURPOSES
    assert m.better in ("lower", "higher", "one", "none")
    assert m.note.strip(), "say what it measures and what it is blind to"
    assert is_tested(name, "test_stats_metrics.py"), f"no test names {name}"


@pytest.mark.parametrize("name", sorted(metrics.REGISTRY))
def test_a_scored_metric_has_ordered_thresholds_and_the_reason_for_them(name):
    m = metrics.REGISTRY[name]
    if m.better == "none":
        assert m.thresholds is None                                       # a descriptor: it has no better or worse
        return
    assert m.thresholds is not None and m.why.strip(), f"{name}: thresholds and why"
    good, bad = m.thresholds
    assert (good > bad) if m.better == "higher" else (good < bad)


def test_exactly_the_five_are_on_by_default():
    assert {n for n, m in metrics.REGISTRY.items() if m.default} == DEFAULTS


def test_every_purpose_has_a_metric_and_the_defaults_cover_all_but_two():
    used = {m.purpose for m in metrics.REGISTRY.values()}
    assert used == set(metrics.PURPOSES)
    on = {m.purpose for m in metrics.REGISTRY.values() if m.default}
    assert set(metrics.PURPOSES) - on == {"similarity", "quality"}


def test_a_metric_that_needs_no_reference_says_so_and_a_pooled_one_is_flagged():
    for m in metrics.REGISTRY.values():
        if m.purpose == "quality":
            assert not m.needs_reference, m.name
        if m.pool:
            assert "pool-dependent" in m.note, m.name


@pytest.mark.parametrize("name", sorted(means.REGISTRY))
def test_every_mean_has_a_guard_a_note_an_error_rule_and_a_test(name):
    m = means.REGISTRY[name]
    assert m.name == name and m.guard.strip() and m.note.strip() and callable(m.error)
    assert is_tested(name, "test_stats_means.py"), f"no test names {name}"
