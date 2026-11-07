"""`heimdall show` (names P2): what a Run, a point and a tool did, read from the record alone."""

from __future__ import annotations

import json

import pytest

from runner import cli
from runner.paths import records_root

from test_runlog import record_with, trees  # noqa: F401  (the fixture)


@pytest.fixture
def record(trees):
    name = record_with(trees)
    base = records_root() / name
    (base / "points.json").write_text(json.dumps({
        "format": 1, "run": "jets", "configuration": "single", "config_file": "configs/jets.toml",
        "constants": {"events": 100, "threads": 2, "seeds": "identity", "parallelism": 1},
        "points": [{"name": "p1", "state": "failed", "identity": "ab" * 32, "seed": 7,
                    "products": {"p1.yoda": "x"}}]}), encoding="utf-8")
    (base / "points" / "p1" / "provenance.json").write_text(json.dumps({
        "identity": "ab" * 32, "seed": 7, "events": 100, "threads": 2, "host": "h", "user": "u",
        "values": {"pdf": {"tag": "MSTW", "value": "MSTW2008lo68cl"}},
        "tools": [{"tag": "pythia", "tool": "pythia", "version": "8.3", "result": {"exit": 3, "seconds": 1.5}}]}), encoding="utf-8")
    (base / "points" / "p1" / "identity.json").write_text(json.dumps({"events": 100, "seeds": "identity"}), encoding="utf-8")
    return name


def test_show_a_run_lists_its_points_and_constants(record, capsys):
    assert cli.main(["show", record]) == 0
    out = capsys.readouterr().out
    assert "errand jets · configuration single" in out and "events 100 · threads 2 · seeds identity" in out
    assert "1 point(s): 1 failed" in out and "p1" in out and "2 attempt(s)" in out


def test_show_a_point_reads_identity_seed_tools_and_says_why_it_has_no_sigma(record, capsys):
    assert cli.main(["show", f"{record}/p1"]) == 0
    out = capsys.readouterr().out
    assert "identity abababababab · seed 7 · events 100 · threads 2" in out and "pdf MSTW" in out
    assert "σ = – (no tool of the latest attempt reported a cross section)" in out
    assert "tool pythia (pythia 8.3): exit 3 in 1.5 s" in out and "products: p1.yoda" in out
    assert "── identity parts" not in out
    assert cli.main(["show", f"{record}/p1", "--parts"]) == 0
    assert '"seeds": "identity"' in capsys.readouterr().out


def test_show_a_point_reports_a_sigma_a_tool_reported(record, capsys):
    path = records_root() / record / "points" / "p1" / "attempts.jsonl"
    row = {"v": 1, "n": 3, "finished": "2026-10-27T10:00:00+00:00", "verdict": "ok", "cause": "", "blamed": "",
           "tools": {"pythia": {"exit": 0, "reported": {"xsec_pb": [12.5, 0.5]}}}}
    path.write_text(path.read_text(encoding="utf-8") + json.dumps(row) + "\n", encoding="utf-8")
    assert cli.main(["show", f"{record}/p1", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["sigma_pb"] == [12.5, 0.5] and data["sigma_note"] == "reported by pythia" and len(data["attempts"]) == 3


def test_show_a_tool_gives_its_provenance_and_the_end_of_its_log(record, capsys):
    assert cli.main(["show", f"{record}/p1/pythia"]) == 0
    out = capsys.readouterr().out
    assert "tool = pythia" in out and "exit 3 in 1.5 s" in out and "now" in out
    assert cli.main(["show", f"{record}/p1/nope"]) == 2
    assert "no tool nope" in capsys.readouterr().err
    assert cli.main(["show", f"{record}/zzz"]) == 2
    assert "no point zzz" in capsys.readouterr().err


def test_show_log_is_heimdall_logs_output(record, capsys):
    assert cli.main(["log", f"{record}/p1/pythia", "--attempt", "1"]) == 0
    logged = capsys.readouterr().out
    assert cli.main(["show", f"{record}/p1/pythia", "--attempt", "1"]) == 0
    assert capsys.readouterr().out == logged == "# tag pythia · attempt 1\nthen\n"
    assert cli.main(["log", f"{record}/p1"]) == 0
    logged = capsys.readouterr().out
    assert cli.main(["show", f"{record}/p1", "--log"]) == 0
    assert capsys.readouterr().out == logged
