"""The points library's key (points-library P2): the identity without the card comments, so one physics under two
point names is one key, while the identity itself is unchanged."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from runner import library, paths, record

from helpers import plans_of


@pytest.fixture
def renamed(scratch):
    """Demo/jets_b: Demo/jets with its errand and its pdf points renamed (`10M_` before each tag); gone after the test, the
    scratch work being the session's (the identity golden file plans every config in it)."""
    configs = Path(paths.configs_root()) / "Demo"
    text = re.sub(r'^name\s*=\s*"jets"', 'name = "jets_b"', (configs / "jets.toml").read_text(encoding="utf-8"), count=1, flags=re.M)
    for tag in ("MSTW08lo", "NNPDF23lo", "NNPDF23nlo", "PDF4LHC21"):
        text = text.replace(f'tag = "{tag}"', f'tag = "10M_{tag}"').replace(f'fixed  = "{tag}"', f'fixed  = "10M_{tag}"')
    (configs / "jets_b.toml").write_text(text, encoding="utf-8")
    yield
    (configs / "jets_b.toml").unlink(missing_ok=True)


def test_one_physics_under_two_names_is_one_key_and_two_identities(renamed):
    *_, first = plans_of("Demo/jets", "pdf")
    *_, second = plans_of("Demo/jets_b", "pdf")
    assert [p.point.name for p in second] == [f"10M_{p.point.name}" for p in first]
    assert [library.key(a) for a in first] == [library.key(b) for b in second]
    assert all(a.identity != b.identity for a, b in zip(first, second))


def test_a_different_physics_is_another_key(scratch):
    *_, plans = plans_of("Demo/jets", "pdf")
    assert len({library.key(p) for p in plans}) == len(plans) == 4


def test_a_changed_card_line_changes_the_key_but_a_comment_does_not(scratch):
    *_, plans = plans_of("Demo/jets", "pdf")
    plan = plans[0]
    before = library.key(plan)
    step = plan.rendered["pythia"]
    card = list(step.identity_parts["card"])
    step.identity_parts["card"] = [*card, "! a remark"]
    assert library.key(plan) == before                       # a comment line: dropped, as seed_basis drops it
    step.identity_parts["card"] = [*card, "Main:numberOfEvents = 7"]
    assert library.key(plan) != before


def test_the_key_is_not_the_identity_and_the_identity_is_untouched(scratch):
    *_, plans = plans_of("Demo/jets", "pdf")
    plan = plans[0]
    assert len(library.key(plan)) == 64 and library.key(plan) != plan.identity
    assert record.identity(plan) == plan.identity
