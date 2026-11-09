"""A point's identity does not depend on how its inputs are written: the order of the [quantities.*] tables and of a
configuration's `vary`, a card's comments, blank lines and the order of its commuting lines. One physics, one identity,
so a rewritten config or card reruns nothing: the identity hashes each tool's final config (doc:identity)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from runner import library, paths

from test_lifecycle import planned, trees  # noqa: F401  (the fixture)


def _block(text: str, name: str) -> str:
    return re.search(rf"^\[quantities\.{name}\]\n.*?(?=^\[)", text, flags=re.M | re.S).group(0)


@pytest.fixture
def reordered(trees):
    configs = Path(paths.configs_root()) / "Demo"
    text = (configs / "jets.toml").read_text(encoding="utf-8")
    energies, pdf = _block(text, "energies"), _block(text, "pdf")
    swapped = text.replace(energies, "\0").replace(pdf, energies).replace("\0", pdf)        # the two tables trade places
    vary = text.replace('vary        = ["energies", "pdf"]', 'vary        = ["pdf", "energies"]')
    variants = {"swapped": swapped, "vary": vary}
    for name, body in variants.items():
        assert body != text
        (configs / f"order_{name}.toml").write_text(re.sub(r'^name\s*=\s*"jets"', f'name = "order_{name}"', body,
                                                          count=1, flags=re.M), encoding="utf-8")
    yield list(variants)
    for name in variants:
        (configs / f"order_{name}.toml").unlink(missing_ok=True)


def _by_physics(name: str) -> dict:
    """Each point of energy_pdf keyed by its values' tags: (its name, identity, library key)."""
    p = planned(name, "energy_pdf")
    return {tuple(sorted(plan.point.choice.items())): (plan.point.name, plan.identity, library.key(plan)) for plan in p.every}




def test_swapping_the_quantity_tables_changes_no_identity(reordered):
    base, other = _by_physics("Demo/jets"), _by_physics("Demo/order_swapped")
    assert {k: v[1:] for k, v in other.items()} == {k: v[1:] for k, v in base.items()}


def test_reordering_a_configs_quantities_changes_no_identity(reordered):
    base = _by_physics("Demo/jets")
    for variant in reordered:
        other = _by_physics(f"Demo/order_{variant}")
        assert set(other) == set(base), variant
        assert {k: v[2] for k, v in other.items()} == {k: v[2] for k, v in base.items()}, f"{variant}: library keys"
        assert {k: v[1] for k, v in other.items()} == {k: v[1] for k, v in base.items()}, f"{variant}: identities"


def _card_edited(edit) -> dict:
    """energy_pdf's points by physics, after `edit(lines)` has rewritten the scratch work's Demo/ep.cmnd."""
    card = Path(paths.configs_root()) / "Demo" / "ep.cmnd"
    before = card.read_text(encoding="utf-8")
    card.write_text("\n".join(edit(before.splitlines())) + "\n", encoding="utf-8")
    try:
        return _by_physics("Demo/jets")
    finally:
        card.write_text(before, encoding="utf-8")


def _settings(lines: list[str]) -> list[int]:
    return [i for i, line in enumerate(lines) if line.strip() and not line.lstrip().startswith(("!", "#"))]




def test_comments_and_blank_lines_in_a_card_change_no_identity(trees):
    base = _by_physics("Demo/jets")
    edited = _card_edited(lambda lines: ["! a note", ""] + [line + "   " for line in lines] + ["", "# the end"])
    assert {k: v[1] for k, v in edited.items()} == {k: v[1] for k, v in base.items()}




def test_swapping_two_lines_of_a_card_changes_no_identity(trees):
    base = _by_physics("Demo/jets")

    def swap(lines):
        first, second = _settings(lines)[:2]
        lines[first], lines[second] = lines[second], lines[first]
        return lines
    edited = _card_edited(swap)
    assert {k: v[1] for k, v in edited.items()} == {k: v[1] for k, v in base.items()}
