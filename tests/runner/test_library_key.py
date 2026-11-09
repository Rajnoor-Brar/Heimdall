"""The points library's key: the identity, whose cards are final configs naming no point, so one physics under two point
names is one key and one identity."""

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


def test_one_physics_under_two_names_is_one_key_and_one_identity(renamed):
    *_, first = plans_of("Demo/jets", "pdf")
    *_, second = plans_of("Demo/jets_b", "pdf")
    assert [p.point.name for p in second] == [f"10M_{p.point.name}" for p in first]
    assert [library.key(a) for a in first] == [library.key(b) for b in second]
    assert [a.identity for a in first] == [b.identity for b in second]


def test_a_different_physics_is_another_key(scratch):
    *_, plans = plans_of("Demo/jets", "pdf")
    assert len({library.key(p) for p in plans}) == len(plans) == 4


def test_a_changed_card_line_changes_the_key(scratch):
    *_, plans = plans_of("Demo/jets", "pdf")
    plan = plans[0]
    before = library.key(plan)
    step = plan.rendered["pythia"]
    step.identity_parts["card"] = [*step.identity_parts["card"], "Main:numberOfEvents = 7"]
    assert library.key(plan) != before


def test_the_key_is_the_identity(scratch):
    *_, plans = plans_of("Demo/jets", "pdf")
    plan = plans[0]
    assert len(library.key(plan)) == 64 and library.key(plan) == plan.identity == record.identity(plan)
    assert not any(line.startswith("!") for line in plan.rendered["pythia"].identity_parts["card"])
