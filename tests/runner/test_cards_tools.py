"""The appended tools' final configs (pythia, herwig, delphes): what each tool reads, planned from the fixtures.
An expected card is tests/fixtures/expected_cards/<name>, read in review; it changes only with the rule it shows."""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from runner import cards
from runner.errors import HeimdallError

from helpers import plan, plans, raw

EXPECTED = Path(__file__).resolve().parents[1] / "fixtures" / "expected_cards"


def combined(p, tag: str) -> str:
    return p.writes[p.rendered[tag].card_combined]


def test_pythias_final_config_is_the_expected_one(scratch):
    _, _, p = plan(raw(), scratch)
    assert combined(p, "pythia") == (EXPECTED / "pythia_ep.cmnd").read_text(encoding="utf-8")


def test_pythias_final_config_has_no_comments_and_each_key_once(scratch):
    _, _, p = plan(raw(), scratch)
    lines = combined(p, "pythia").splitlines()
    keys = [cards.normal(line.split("=")[0]) for line in lines]
    assert all(" = " in line and "!" not in line for line in lines)
    assert len(keys) == len(set(keys))


def test_a_pythia_base_reordered_with_other_comments_makes_the_same_card(scratch):
    """One physics, one card: the base's settings in another order, other comments and spacing."""
    _, _, p = plan(raw(), scratch)
    base = p.rendered["pythia"].card_base[0]
    settings = [line for line in base.read_text(encoding="utf-8").splitlines()
                if line.strip() and line.lstrip()[0].isalnum()]
    random.Random(3).shuffle(settings)
    other = scratch / "shuffled.cmnd"
    other.write_text("! another header\n\n" + "\n".join(f"{s.split('!')[0].strip().replace(' = ', '=')}   ! a note"
                                                           for s in settings) + "\n", encoding="utf-8")
    _, _, q = plan(raw(tools__pythia__baseconfig=str(other)), scratch)
    assert combined(q, "pythia") == combined(p, "pythia")


def test_pythia_reads_the_final_config_so_a_renamed_base_is_the_same_identity(scratch):
    from runner import record
    _, _, p = plan(raw(), scratch)
    step = p.rendered["pythia"]
    assert step.argv[-1] == str(step.card_combined) and not any(str(b) in step.argv for b in step.card_base)
    other = scratch / "renamed.cmnd"
    other.write_text(step.card_base[0].read_text(encoding="utf-8"), encoding="utf-8")
    _, _, q = plan(raw(tools__pythia__baseconfig=str(other)), scratch)
    assert record.identity(q) == record.identity(p)


def test_a_pythia_key_twice_in_one_base_is_refused_at_plan_naming_both_lines(scratch):
    base = scratch / "twice.cmnd"
    base.write_text("HeavyIon:SigFitNGen = 200\n! a comment\nHeavyIon:SigFitNGen = 0\n", encoding="utf-8")
    with pytest.raises(HeimdallError, match="'HeavyIon:SigFitNGen' is set twice") as caught:
        plan(raw(tools__pythia__baseconfig=str(base)), scratch)
    assert caught.value.where == "twice.cmnd:1 and twice.cmnd:3"


def test_a_tune_leads_and_a_particles_commands_keep_their_order(scratch):
    base = scratch / "tuned.cmnd"
    base.write_text("PDF:pSet = 13\n3122:onMode = off\n3122:onIfMatch = 2212 -211\nTune:pp = 14\n", encoding="utf-8")
    _, _, p = plan(raw(tools__pythia__baseconfig=str(base)), scratch)
    lines = combined(p, "pythia").splitlines()
    assert lines[0] == "Tune:pp = 14"
    assert lines.index("3122:onMode = off") + 1 == lines.index("3122:onIfMatch = 2212 -211")


def test_the_sidecar_says_what_a_point_value_overrode(scratch):
    import json
    base = scratch / "b.cmnd"
    base.write_text("PDF:pSet = 13\n", encoding="utf-8")
    _, _, p = plan(raw(tools__pythia__baseconfig=str(base), tools__pythia__settings={"PDF:pSet": 8}), scratch)
    sidecar = json.loads(p.writes[p.rendered["pythia"].card_combined.with_suffix(".json")])
    assert sidecar["PDF:pSet"] == {"value": "8", "from": "[tools.pythia].settings",
                                   "overrode": [{"value": "13", "from": "b.cmnd:1"}]}


def test_herwigs_final_config_is_the_base_as_written_then_the_points_lines_sorted():
    [p] = plans("Demo/herwig")
    assert combined(p, "herwig") == (EXPECTED / "herwig_dis_ep.in").read_text(encoding="utf-8")


def test_delphes_final_config_is_its_base_without_comments_then_its_seed():
    [p] = plans("Demo/jets", "delphes")
    step = p.rendered["delphes"]
    rules = step.folder.spec["card"]
    base = [line.strip() for _, line in cards.cleaned(step.card_base[0].read_text(encoding="utf-8"), rules)]
    assert combined(p, "delphes").splitlines() == base + [f"set RandomSeed {p.seed}"]
