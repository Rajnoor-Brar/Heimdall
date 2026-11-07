"""`heimdall diff`: two Runs' records compared (across-axes). The records are written by hand: a snapshot with an errand file
and a card, and a point's identity parts as `run --why` reads them."""

from __future__ import annotations

import argparse
import json
import shutil

import pytest
import tomli_w

from runner import cli, diffcmd
from runner.errors import HeimdallError
from runner.paths import records_root


def make_run(name: str, *, errand: dict | None = None, card: list[str] | None = None, points: dict | None = None,
             sets: list | None = None, assignment: str = "Demo", errand_name: str = "t"):
    folder = records_root() / assignment / errand_name / name
    (folder / "config" / assignment).mkdir(parents=True, exist_ok=True)
    config = f"{assignment}/{errand_name}"
    files = {}
    (folder / "config" / f"{config}.toml").write_text(tomli_w.dumps(errand or {"errand": {"events": 1000}}), encoding="utf-8")
    if card is not None:
        (folder / "config" / assignment / "ep.cmnd").write_text("\n".join(card) + "\n", encoding="utf-8")
        files[f"{assignment}/ep.cmnd"] = "h-" + str(len(card)) + card[0]
    (folder / "config" / "snapshot.toml").write_text(tomli_w.dumps({
        "snapshot": {"config": config, "configuration": "one", "sets": sets or [], "heimdall": "abc", "written": name},
        "files": files}), encoding="utf-8")
    for point, parts in (points or {}).items():
        where = folder / "points" / point
        where.mkdir(parents=True, exist_ok=True)
        (where / "identity.json").write_text(json.dumps({"format": 1, **parts}), encoding="utf-8")
    return folder


def parts(*, events=1000, option="a", exe="sha1", card="x"):
    return {"events": events, "threads": 1, "tools": [{"tag": "pythia", "exe_sha256": exe, "options": option, "card": card}]}


def diff(first, second, **kw):
    return diffcmd.diff(f"Demo/t/{first}", f"Demo/t/{second}", **kw)


@pytest.fixture(autouse=True)
def where(scratch):
    shutil.rmtree(records_root() / "Demo", ignore_errors=True)
    return scratch


def test_the_errand_file_is_compared_key_by_key_and_what_is_equal_is_not_said():
    make_run("01_a", errand={"errand": {"events": 1000, "name": "t"}, "quantities": {"pdf": {"tags": ["a", "b"]}}})
    make_run("02_b", errand={"errand": {"events": 5000, "name": "t"}, "quantities": {"pdf": {"tags": ["a", "c"]}}})
    data = diff("01_a", "02_b")
    assert "errand.events: 1000 → 5000" in data["settings"]
    assert any(line.startswith("quantities.pdf.tags") and ': - "b"' in line for line in data["settings"])
    assert not any("errand.name" in line for line in data["settings"])


def test_the_runs_configuration_and_overrides_are_differences_and_the_revision_is_not():
    make_run("01_a", sets=[])
    make_run("02_b", sets=["events=5"])
    assert diff("01_a", "02_b")["settings"] == ["sets: [] → ['events=5']"]


def test_a_card_that_changed_shows_its_lines_and_a_long_one_the_first_few_until_full():
    old = [f"line {i}" for i in range(40)]
    new = [f"line {i}" if i % 2 else f"edited {i}" for i in range(40)]
    make_run("01_a", card=old)
    make_run("02_b", card=new)
    (item,) = diff("01_a", "02_b")["files"]
    assert item["file"] == "Demo/ep.cmnd" and item["change"] == "differs"
    assert len(item["lines"]) == diffcmd.LINES + 1 and item["lines"][-1].startswith("… and 28 more line(s) (--full)")
    assert len(diff("01_a", "02_b", full=True)["files"][0]["lines"]) == 40
    assert "-line 0" in item["lines"] and "+edited 0" in item["lines"]


def test_a_file_only_one_run_read_is_said():
    make_run("01_a", card=["a"])
    make_run("02_b")
    assert diff("01_a", "02_b")["files"] == [{"file": "Demo/ep.cmnd", "change": "only in the first", "lines": []}]
    assert diff("02_b", "01_a")["files"][0]["change"] == "only in the second"


def test_a_points_parts_are_compared_tool_by_tool_and_equal_points_are_counted_not_listed():
    make_run("01_a", points={"p1": parts(), "p2": parts(), "p3": parts()})
    make_run("02_b", points={"p1": parts(option="b", exe="sha2"), "p2": parts(), "p4": parts()})
    data = diff("01_a", "02_b")
    assert set(data["points"]) == {"p1"} and data["same_points"] == 1
    lines = data["points"]["p1"]
    assert 'tools.pythia.exe_sha256: "sha1" → "sha2"' in lines and 'tools.pythia.options: "a" → "b"' in lines
    assert data["only"] == {"first": ["p3"], "second": ["p4"]}


def test_points_keeps_the_ones_named_by_name_or_glob():
    make_run("01_a", points={"py_a": parts(), "py_b": parts(), "hw_a": parts()})
    make_run("02_b", points={"py_a": parts(events=1), "py_b": parts(events=2), "hw_a": parts(events=3)})
    assert set(diff("01_a", "02_b", picked=["py_*"])["points"]) == {"py_a", "py_b"}
    assert set(diff("01_a", "02_b", picked=["hw_a"])["points"]) == {"hw_a"}


def test_a_long_point_diff_is_cut_and_whole_with_full():
    make_run("01_a", points={"p": {"events": 1, **{f"k{i}": i for i in range(30)}}})
    make_run("02_b", points={"p": {"events": 1, **{f"k{i}": i + 1 for i in range(30)}}})
    cut = diff("01_a", "02_b")["points"]["p"]
    assert len(cut) == diffcmd.LINES + 1 and "… and 18 more (--full)" in cut[-1]
    assert len(diff("01_a", "02_b", full=True)["points"]["p"]) == 30


def test_a_point_with_no_recorded_identity_in_one_run_says_so_and_one_in_neither_is_not_listed():
    make_run("01_a", points={"p": parts()})
    folder = make_run("02_b")
    (folder / "points" / "p").mkdir(parents=True)
    (folder / "points" / "p" / "identity.json").write_text("not json", encoding="utf-8")
    assert diff("01_a", "02_b")["points"] == {"p": ["its identity was not recorded"]}


def test_the_second_run_may_be_named_by_its_folder_alone_and_two_errands_are_refused():
    make_run("01_a")
    make_run("02_b")
    make_run("01_a", errand_name="other")
    assert diffcmd.diff("Demo/t/01_a", "02_b")["second"] == "Demo/t/02_b"
    with pytest.raises(HeimdallError, match="different Errands"):
        diffcmd.diff("Demo/t/01_a", "Demo/other/01_a")
    with pytest.raises(HeimdallError, match="same as itself"):
        diffcmd.diff("Demo/t/01_a", "01_a")


def test_a_run_without_a_snapshot_is_refused_naming_it():
    make_run("01_a")
    (records_root() / "Demo" / "t" / "02_b").mkdir(parents=True)
    with pytest.raises(HeimdallError, match="02_b has no snapshot"):
        diff("01_a", "02_b")


def test_the_lines_say_what_differs_and_the_cli_prints_them_or_json(capsys):
    make_run("01_a", errand={"errand": {"events": 1}}, points={"p": parts()})
    make_run("02_b", errand={"errand": {"events": 2}}, points={"p": parts(events=9)})
    args = cli.parser().parse_args(["diff", "Demo/t/01_a", "02_b", "--points", "p", "--json"])
    assert args.command == "diff" and args.points == "p" and args.json and not args.full
    assert cli.cmd_diff(args) == 0
    assert json.loads(capsys.readouterr().out)["points"]["p"] == ["events: 1000 → 9"]
    assert cli.cmd_diff(cli.parser().parse_args(["diff", "Demo/t/01_a", "02_b"])) == 0
    text = capsys.readouterr().out
    assert "Demo/t/01_a  →  Demo/t/02_b" in text and "errand.events: 1 → 2" in text and "points that differ (1 of 1 both have):" in text
