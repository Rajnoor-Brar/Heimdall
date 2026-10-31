"""The run TOML's own checks (docs/04_Config_Reference.md §13): one bad file per rule, each with where and hint."""

from __future__ import annotations

import pytest

from runner.errors import HeimdallError

from helpers import parse, plan, raw


def fails(data, scratch, match):
    with pytest.raises(HeimdallError, match=match) as caught:
        parse(data, scratch)
    assert caught.value.where
    return caught.value


def test_the_base_config_parses(scratch):
    errand = parse(raw(), scratch)
    assert errand.configuration(None).tools == [["pythia", "rivet"]]
    assert errand.configuration(None).threads == 1


def test_c1_an_unknown_key_suggests_the_right_one(scratch):
    error = fails(raw(errand__cfgs__one__sweps=["pdf"]), scratch, "unknown key 'sweps'")
    assert "sweeps" in error.hint


def test_the_names_before_i112_are_refused_with_what_rewrites_them(scratch):
    """I-112: [run] is [errand], [run].project its assignment; the old forms (a table, a key, --set run.x, an import's
    only = ["run.…"]) are refused, each naming `heimdall migrate --names`."""
    from runner import config
    old = raw()
    old["run"] = {**old.pop("errand"), "project": "Demo"}
    error = fails(old, scratch, r"\[run\] is now \[errand\] \(I-112's names\)")
    assert error.hint == "heimdall migrate --names rewrites it" and error.where.endswith("[run]")
    error = fails(raw(errand__project="Demo"), scratch, r"\[errand\]\.project is now \[errand\]\.assignment")
    assert "heimdall migrate --names" in error.hint
    with pytest.raises(HeimdallError, match=r"--set run\.threads: \[run\] is now \[errand\]") as caught:
        config.apply_sets(raw(), ["run.threads=4"])
    assert caught.value.hint.startswith("--set errand.threads=4")
    path = scratch / "old.toml"
    path.write_text('[run]\nname = "t"\nproject = "Demo"\nconfiguration = "one"\n', encoding="utf-8")
    with pytest.raises(HeimdallError, match=r"\[run\] is now \[errand\]") as caught:
        config.load(str(path))
    assert caught.value.hint == "heimdall migrate --names rewrites it"
    with pytest.raises(HeimdallError, match=r"'run\.cfgs\.one': \[run\] is now \[errand\]"):
        config._parts("run.cfgs.one", "an import's only")


def test_c1_an_unknown_section(scratch):
    error = fails(raw(tool={"x": {}}), scratch, r"unknown section \[tool\]")
    assert "tools" in error.hint


def test_c1_a_wrong_type(scratch):
    fails(raw(errand__event_count="many"), scratch, "must be an integer")


def test_c2_the_default_configuration_must_exist(scratch):
    fails(raw(errand__configuration="nope"), scratch, "not a \\[errand.cfgs.<cfg>\\] table")


def test_configurations_are_run_cfgs_and_run_holds_only_its_own_keys(scratch):
    """V98: [errand.<cfg>] is refused with the form to write; a misspelt [errand] table is no configuration; a
    configuration may be named like a [errand] key, and a [errand] key that is a table is a type error."""
    data = raw(); data["errand"]["pdf"] = data["errand"]["cfgs"].pop("one"); data["errand"]["configuration"] = "pdf"
    with pytest.raises(HeimdallError, match=r"\[errand.pdf\] is a configuration, and configurations are \[errand.cfgs.<cfg>\] now") as error:
        parse(data, scratch)
    assert "[errand.cfgs.pdf]" in error.value.hint and "heimdall migrate" in error.value.hint
    with pytest.raises(HeimdallError, match=r"\[errand.defualts\] is a configuration") as error:
        parse(raw(errand__defualts={"event_count": 5}), scratch)
    assert "[errand.cfgs.defualts]" in error.value.hint
    with pytest.raises(HeimdallError, match="'threads' must be an integer"):
        parse(raw(errand__threads={"tools": [["pythia", "rivet"]]}), scratch)
    errand = parse(raw(errand__configuration="threads", errand__cfgs__threads={"tools": [["pythia", "rivet"]]}), scratch)
    assert "threads" in errand.configurations


def test_c2_a_named_configuration_must_exist(scratch):
    errand = parse(raw(), scratch)
    with pytest.raises(HeimdallError, match="no configuration 'on'") as caught:
        errand.configuration("on")
    assert "one" in caught.value.hint


def test_c3_sweeps_name_declared_quantities(scratch):
    fails(raw(errand__cfgs__one__sweeps=["pfd"]), scratch, "not a \\[quantities")


def test_c3_entangled_groups_have_equal_lengths(scratch):
    data = raw(errand__cfgs__one__sweeps=[["pdf", "other"]], quantities__other={"values": [1, 2, 3]})
    fails(data, scratch, "equal value counts")


def test_c4_plot_points_must_be_swept(scratch):
    fails(raw(errand__cfgs__one__sweeps=["pdf"], errand__cfgs__one__plot_points=["energies"]), scratch, "not swept")


def test_c5_tools_name_tool_tables(scratch):
    error = fails(raw(errand__cfgs__one__tools=[["pythia", "rivt"]]), scratch, "not a \\[tools.<tag>\\] table")
    assert "rivet" in error.hint


def test_c5_groups_nest_one_level(scratch):
    fails(raw(errand__cfgs__one__tools=[[["pythia"]]]), scratch, "nest one level")


def test_c12_climbing_out_is_refused(scratch):
    with pytest.raises(HeimdallError, match="climbs out"):
        plan(raw(tools__pythia__baseconfig="../ep.cmnd"), scratch)


def test_static_values_resolve_by_tag_value_or_index(scratch):
    for selector in ("NNPDF23lo", "LHAPDF6:NNPDF23_lo_as_0130_qed", "#2"):
        _, _, p = plan(raw(static={"pdf": selector}), scratch)
        assert p.values["pdf"] == 1


def test_a_bad_static_value_names_the_choices(scratch):
    with pytest.raises(HeimdallError, match="not a value") as caught:
        plan(raw(static={"pdf": "NNPDF23"}), scratch)
    assert "NNPDF23lo" in caught.value.hint


def test_set_overrides_one_value(scratch):
    from runner.config import apply_sets
    data = raw()
    apply_sets(data, ["errand.cfgs.one.threads=4", "static.pdf=MSTW08lo"])
    errand = parse(data, scratch)
    assert errand.configuration("one").threads == 4 and errand.static == {"pdf": "MSTW08lo"}


# ── V58: the vocabulary's shapes ──────────────────────────────────────────────────────────────

def test_a_vocabulary_quantity_takes_values_of_its_shape(scratch):
    good = raw(quantities__energies={"values": [[275, 18], [920, 27.5]], "tags": ["a", "b"]})
    parse(good, scratch)
    error = fails(raw(quantities__energies={"values": [275, 18]}), scratch, r"value 1 is 275, not a list of 2")
    assert "beam A, beam B" in error.hint
    fails(raw(quantities__beams={"values": [[2212, "e-"]]}), scratch, "not a list of 2")
    fails(raw(quantities__pdf={"values": [True]}), scratch, "not a string or an integer")


def test_a_quantity_the_vocabulary_lacks_is_the_users_own(scratch):
    parse(raw(quantities__pt0ref={"values": ["anything", 3.2], "key": {"pythia": "MultipartonInteractions:pT0Ref"}}), scratch)


def test_every_folder_maps_only_vocabulary_names():
    from runner import quantities
    master = quantities.load_master("Demo", None)
    names = set(quantities.vocabulary())
    for tool, table in master["quantities"].items():
        assert set(table["compatible_quantities"]) <= names, tool
    assert quantities.BUILTIN == ("events", "threads")


def test_a_users_quantity_may_state_its_shape(scratch):
    """V76: shape = "pdg" (the vocabulary's grammar) checks a quantity the vocabulary does not name."""
    good = raw(quantities__lepton={"key": {"pythia": "Beams:idB"}, "values": [11, -11], "shape": "pdg"})
    parse(good, scratch)
    with pytest.raises(HeimdallError, match="value 2 is '-11', not"):
        parse(raw(quantities__lepton={"key": {"pythia": "Beams:idB"}, "values": [11, "-11"], "shape": "pdg"}), scratch)
    with pytest.raises(HeimdallError, match="is not one"):
        parse(raw(quantities__lepton={"key": {"pythia": "Beams:idB"}, "values": [11], "shape": "integer"}), scratch)
    with pytest.raises(HeimdallError, match="the vocabulary's is"):
        parse(raw(quantities__energies={"values": [[275, 18]], "shape": "float"}), scratch)
