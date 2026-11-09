"""The card model (runner/cards.py): a card parsed into entries, sources merged by priority, the final
config written in the folder's order, and the sidecar. Hand-made cards and [card] tables, no tool run."""
import random

import pytest

from runner import cards
from runner.errors import HeimdallError

PYTHIA = {"order": "free", "comment": "!", "drop": r"^\s*[^A-Za-z0-9\s]", "trailing": r"\s+!.*$",
          "leading": ["Tune:ee", "Tune:pp"], "group": r"^(-?\d+):",
          "repeatable": ["onIfAny", "onIfMatch", "all", "new"]}
SET = {"order": "sequential", "comment": "#", "line": "set {key} {value}"}

BASE = """! a base card
Beams:eCM = 13000.   ! the energy
SoftQCD:nonDiffractive = on

3122:mayDecay = on
3122:onMode = off
3122:onIfMatch = 2212 -211
Tune:pp = 14
PDF:pSet = 13
"""


def base(text=BASE, rules=PYTHIA, name="base.cmnd"):
    return cards.parse(text, rules, name)


def point(*pairs, rules=PYTHIA, origin="[tools.pythia].settings"):
    return cards.Source(tuple(cards.setting(k, v, origin, rules) for k, v in pairs), sort=True)


def final(sources, rules=PYTHIA):
    return cards.write(cards.merge(sources, rules), rules)


# ── parse ──────────────────────────────────────────────────────────────────────────────────────

def test_parse_drops_comments_and_blank_lines_and_keeps_where_each_line_is():
    entries = base().entries
    assert [e.key for e in entries] == ["Beams:eCM", "SoftQCD:nonDiffractive", "3122:mayDecay", "3122:onMode",
                                        "3122:onIfMatch", "Tune:pp", "PDF:pSet"]
    assert entries[0].value == "13000." and entries[0].origin == "base.cmnd:2"


def test_parse_reads_a_set_grammar_and_keeps_a_command_as_a_line_without_a_key():
    entries = cards.parse("cd /Herwig/Generators\nset EventGenerator:EventHandler:LuminosityFunction:Energy 318\n", SET, "b.in").entries
    assert entries[0].key == "" and entries[0].line == "cd /Herwig/Generators"
    assert entries[1].key == "EventGenerator:EventHandler:LuminosityFunction:Energy" and entries[1].value == "318"


def test_directives_are_read_before_the_comments_go():
    rules = {**SET, "directives": r"^\s*#\s*heimdall:\s*(\w+)\s*=\s*(.*)$"}
    text = "# heimdall: beam_structure = pdf_builtin, epa\nsqrts = 318 GeV\n"
    assert cards.directives(text, rules, "ep.sin") == {"beam_structure": ("pdf_builtin, epa", "ep.sin:1")}
    assert [e.line for e in cards.parse(text, rules, "ep.sin").entries] == ["sqrts = 318 GeV"]


def test_a_directive_given_twice_is_refused():
    rules = {"directives": r"^#\s*heimdall:\s*(\w+)\s*=\s*(.*)$"}
    with pytest.raises(HeimdallError, match="twice"):
        cards.directives("# heimdall: a = 1\n# heimdall: a = 2\n", rules, "x.sin")


# ── merge ──────────────────────────────────────────────────────────────────────────────────────

def test_a_setting_twice_in_one_card_is_refused_naming_both_lines():
    with pytest.raises(HeimdallError, match="'heavyion:sigfitngen' is set twice") as caught:
        cards.merge([base("HeavyIon:SigFitNGen = 200\nHeavyIon:mode = 1\nheavyion:sigfitngen = 0\n")], PYTHIA)
    assert "base.cmnd:1 and base.cmnd:3" in caught.value.where


def test_a_later_source_wins_and_the_loser_is_kept():
    merged = cards.merge([base(), point(("PDF:pSet", "8"))], PYTHIA)
    pdf = [e for e in merged.entries if e.normal == "pdf:pset"]
    assert [e.value for e in pdf] == ["8"]
    assert [(e.value, e.origin) for e in merged.overrode["pdf:pset"]] == [("13", "base.cmnd:9")]


def test_a_later_base_beats_an_earlier_one():
    merged = cards.merge([base("PDF:pSet = 13\n", name="a.cmnd"), base("PDF:pSet = 7\n", name="b.cmnd")], PYTHIA)
    assert [(e.value, e.origin) for e in merged.entries] == [("7", "b.cmnd:1")]


def test_a_repeatable_command_is_kept_every_time():
    merged = cards.merge([base("23:onMode = off\n23:onIfMatch = 11 -11\n23:onIfMatch = 13 -13\n")], PYTHIA)
    assert [e.value for e in merged.entries] == ["off", "11 -11", "13 -13"]


def test_a_free_card_refuses_a_line_that_is_not_a_setting():
    with pytest.raises(HeimdallError, match="not a setting"):
        cards.merge([cards.parse("Main:timesAllowErrors 10\n", {**PYTHIA, "drop": r"^\s*!"}, "x.cmnd")], PYTHIA)


def test_a_sequential_card_replaces_nothing_and_sorts_only_a_sorted_source():
    sources = [cards.parse("set B 1\ncd /X\nset A 2\n", SET, "b.in"),
               point(("Z", "1"), ("A", "3"), rules=SET),
               cards.Source((cards.Entry("", "", "the runner", "saverun point EventGenerator"),))]
    assert final(sources, SET) == ["set B 1", "cd /X", "set A 2", "set A 3", "set Z 1", "saverun point EventGenerator"]


# ── write ──────────────────────────────────────────────────────────────────────────────────────

def test_the_free_writer_leads_with_tunes_sorts_the_rest_then_each_particle_in_written_order():
    assert final([base(), point(("Beams:idA", "11"))]) == [
        "Tune:pp = 14", "Beams:eCM = 13000.", "Beams:idA = 11", "PDF:pSet = 13", "SoftQCD:nonDiffractive = on",
        "3122:mayDecay = on", "3122:onMode = off", "3122:onIfMatch = 2212 -211"]


def test_particles_sort_by_number_and_a_point_command_follows_the_base_ones():
    text = "23:onMode = off\n113:mayDecay = off\n5:mayDecay = on\n"
    assert final([base(text), point(("23:onIfAny", "11"))]) == [
        "5:mayDecay = on", "23:onMode = off", "23:onIfAny = 11", "113:mayDecay = off"]


def test_a_shuffled_free_card_with_other_comments_and_layout_writes_the_same_config():
    lines = [line for line in BASE.splitlines() if line.strip() and not line.startswith("!")]
    settings = [l for l in lines if not l.startswith("3122")]
    particle = [l for l in lines if l.startswith("3122")]
    random.Random(7).shuffle(settings)
    other = "\n".join(["! another comment", *(f"   {l.replace(' = ', '=')}   ! note" for l in settings), "", *particle])
    assert final([base(other)]) == final([base()])


def test_a_shuffled_sequential_card_is_another_config():
    text = "cd /Herwig/MatrixElements/\ninsert SubProcess:MatrixElements[0] MEDISNC\n"
    swapped = "\n".join(reversed(text.splitlines()))
    assert final([cards.parse(text, SET, "b.in")], SET) != final([cards.parse(swapped, SET, "b.in")], SET)


def test_reordering_a_particles_commands_is_another_config():
    a = "3122:onMode = off\n3122:onIfMatch = 2212 -211\n"
    b = "3122:onIfMatch = 2212 -211\n3122:onMode = off\n"
    assert final([base(a)]) != final([base(b)])


def test_an_unknown_order_is_refused():
    with pytest.raises(HeimdallError, match="order"):
        cards.merge([], {"order": "sorted"})


# ── sidecar ────────────────────────────────────────────────────────────────────────────────────

def test_the_sidecar_says_each_value_where_it_comes_from_and_what_it_overrode():
    merged = cards.merge([base("PDF:pSet = 13\n23:onIfAny = 11\n23:onIfAny = 13\n"), point(("PDF:pSet", "8"))], PYTHIA)
    assert cards.sidecar(merged) == {
        "23:onIfAny": {"value": "11", "from": "base.cmnd:2"},
        "23:onIfAny #2": {"value": "13", "from": "base.cmnd:3"},
        "PDF:pSet": {"value": "8", "from": "[tools.pythia].settings", "overrode": [{"value": "13", "from": "base.cmnd:1"}]}}


# ── trees (YAML) ──────────────────────────────────────────────────────────────────────────────

def test_a_tree_refuses_a_key_twice_in_one_mapping():
    with pytest.raises(HeimdallError, match="'EVENTS' is set twice") as caught:
        cards.load_tree("EVENTS: 1\nBEAMS: [11, 2212]\nEVENTS: 2\n", "ep.yaml")
    assert caught.value.where == "ep.yaml:1 and ep.yaml:3"


def test_a_tree_dumps_sorted_mappings_and_keeps_list_order():
    a = cards.load_tree("# c\nPDF_SET: [NNPDF31, CT18]\nBEAMS: [11, 2212]\nME: {b: 1, a: 2}\n", "a.yaml")
    b = cards.load_tree("ME: {a: 2, b: 1}\nBEAMS: [11, 2212]\n\nPDF_SET: [NNPDF31, CT18]\n", "b.yaml")
    assert cards.dump_tree(a) == cards.dump_tree(b)
    assert cards.dump_tree(a).index("BEAMS") < cards.dump_tree(a).index("ME") < cards.dump_tree(a).index("PDF_SET")
    assert cards.dump_tree(cards.load_tree("L: [2, 1]\n", "c.yaml")) != cards.dump_tree(cards.load_tree("L: [1, 2]\n", "c.yaml"))
