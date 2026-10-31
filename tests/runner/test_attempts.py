"""What a point's attempts leave (V200, I-106 step L2): each attempt's line in attempts.jsonl with its verdict, cause
and tools (exit, stall, warnings, errors, what they reported); `heimdall status` naming why a point failed; the
run's constants and each point's state in points.json; a block's warnings; the verdict's counts and failures.
The tools are small shell scripts in a fixture point's place, so nothing here needs the stack's generators."""

from __future__ import annotations

import argparse
import io
import json
import threading
import time
from dataclasses import replace

import pytest

from runner import cli, execute, house, record, runs
from runner.events import Bus
from runner.status import Reader, ToolState
from runner.watch import PlainView

RULES = [{"match": r"\bWarning\b", "emit": "warn"}, {"match": r"\bERROR\b", "emit": "error"}]


@pytest.fixture
def trees(scratch, monkeypatch):
    for var, name in (("HEIMDALL_RECORDS", "records"), ("HEIMDALL_CACHE", "cache"), ("HEIMDALL_RESULTS", "results")):
        monkeypatch.setenv(var, str(scratch / name))
    return scratch


def fake(script: str, *, stall_after: float = 300.0, standard: bool = False, configuration: str = "single"):
    """The configuration's first point, its chain one tool: `script`, run by bash, filtered by RULES."""
    p = cli.build_plans(argparse.Namespace(config="Demo/jets", set=[], points=None, rerun=False, only=None), configuration)
    plan = p.every[0]
    step = plan.groups[0][0]
    plan.groups = [[replace(step, argv=["/bin/bash", "-c", script], inputs=[], outputs=[], products=[], count_check=None,
                            sidecar=None, sidecar_written=None, stall_after=stall_after, timeout=0.0,
                            status="standard" if standard else "filters", filters=RULES)]]
    plan.interfaces, plan.prelim = {}, {}
    return p, plan, step.tag


def run(p, plan, stopper=None):
    events: list[dict] = []
    bus = Bus()
    bus.subscribe(events.append)
    result = execute.run_point(plan, p.errand, p.configuration, bus=bus, stopper=stopper or execute.Stopper())
    return result, events


def test_the_reader_keeps_each_warning_and_error_once_with_its_count_and_first_line():
    reader = Reader(ToolState("p", "sherpa"), fd=None, out=None, rules=RULES, bus=None)
    for line in ("starting", "Warning: a", "ERROR: b", "Warning: a", "between", "Warning: c"):
        reader.output(line)
    assert reader.signals("warn") == {"Warning: a": [2, 2], "Warning: c": [1, 6]}
    assert reader.signals("error") == {"ERROR: b": [1, 3]}
    for n in range(60):                                              # at most SIGNALS distinct, then counted
        reader.output(f"Warning: number {n}")
    kept = reader.signals("warn")
    assert len(kept) == 51 and kept["…"] == [12, None]


def test_the_reader_keeps_what_a_tool_reports_of_itself():
    state = ToolState("p", "pythia")
    reader = Reader(state, fd=None, out=None, rules=[], bus=None)
    reader._emit({"k": "summary", "written": 5000, "outputs": ["a.hepmc"]})
    reader._emit({"k": "summary", "accepted": 4990})
    reader._emit({"k": "xsec", "value_pb": 2.5, "err_pb": 0.1})
    reader._emit({"k": "log", "level": "warning", "msg": "low statistics"})
    assert reader.reported() == {"summary": {"written": 5000, "outputs": ["a.hepmc"], "accepted": 4990},
                                 "xsec_pb": [2.5, 0.1]}
    assert reader.signals("warn") == {"low statistics": [1, None]}           # a status message has no line


def test_a_failed_tool_leaves_an_attempt_with_its_cause_and_a_rerun_appends_the_next(trees):
    p, plan, tag = fake('echo "ERROR: the card is wrong"; echo "Warning: odd"; exit 3')
    result, events = run(p, plan)
    assert not result.ok and result.cause == tag
    (first,) = record.attempts(plan)
    assert first["n"] == 1 and first["verdict"] == "failed" and first["cause"] == "failed" and first["blamed"] == tag
    assert first["identity"] == plan.identity and first["started"] <= first["finished"]
    assert first["tools"][tag]["exit"] == 3 and first["tools"][tag]["errors"] == {"ERROR: the card is wrong": [1, 1]}
    assert first["tools"][tag]["warnings"] == {"Warning: odd": [1, 2]}
    assert record.cause_text(first) == f"{tag} failed (exit code 3)"
    assert events[-1]["k"] == "point" and events[-1]["state"] == "failed"
    run(p, plan)
    assert [a["n"] for a in record.attempts(plan)] == [1, 2]
    state, last = record.state_of(plan)
    assert state == "failed" and last["n"] == 2
    line = next(l for l in house.status([p], {}) if l.strip().startswith(plan.point.name))
    assert " failed " in line and line.endswith(f"{tag} failed (exit code 3)")


def test_a_stalled_tool_leaves_where_it_stopped(trees):
    p, plan, tag = fake('echo "Starting the calculation at 20:29:41"; sleep 30', stall_after=1.0)
    result, _ = run(p, plan)
    (attempt,) = record.attempts(plan)
    assert attempt["cause"] == "stalled" and attempt["blamed"] == tag
    stall = attempt["tools"][tag]["stall"]
    assert stall["silent"] == 1 and stall["last_line"] == "Starting the calculation at 20:29:41" and stall["since"]
    assert record.cause_text(attempt) == f"{tag} stalled (silent 1 s)"
    assert "was silent for 1 s" in attempt["message"]


def test_a_stopped_point_says_so(trees):
    p, plan, tag = fake("sleep 30")
    stopper = execute.Stopper()
    threading.Timer(0.6, lambda: setattr(stopper, "requested", True)).start()
    result, _ = run(p, plan, stopper)
    assert result.stopped
    (attempt,) = record.attempts(plan)
    assert attempt["verdict"] == "stopped" and attempt["cause"] == "stopped"
    assert record.state_of(plan)[0] == "stopped" and record.cause_text(attempt) == "stopped"


def test_a_point_that_went_well_keeps_what_its_tools_reported(trees):
    p, plan, tag = fake('printf \'{"k":"summary","written":10}\\n{"k":"xsec","value_pb":1.5,"err_pb":0.1}\\n\' >&"$HEIMDALL_STATUS_FD";'
                        ' echo "Warning: careful"; echo "Warning: careful"', standard=True)
    result, events = run(p, plan)
    assert result.ok
    (attempt,) = record.attempts(plan)
    assert attempt["verdict"] == "ok" and attempt["cause"] == "" and attempt["cards"] == record.card_hashes(plan)
    kept = attempt["tools"][tag]
    assert kept["reported"] == {"summary": {"written": 10}, "xsec_pb": [1.5, 0.1]}
    assert kept["warnings"] == {"Warning: careful": [2, 1]}
    provenance = json.loads(record.provenance_file(plan).read_text(encoding="utf-8"))
    tool = next(t for t in provenance["tools"] if t["tag"] == tag)
    assert tool["result"]["warnings"] == {"Warning: careful": [2, 1]} and tool["result"]["reported"]["xsec_pb"] == [1.5, 0.1]
    assert record.state_of(plan)[0] == "complete"


def test_points_json_holds_each_points_state_and_the_runs_constants(trees):
    p, plan, tag = fake("exit 1")
    run(p, plan)
    data = record.points_manifest(p.every, p.errand, p.configuration)
    entry = next(e for e in data["points"] if e["name"] == plan.point.name)
    assert entry["state"] == "failed" and entry["cause"] == f"{tag} failed (exit code 1)"
    constants = data["constants"]
    assert constants["events"] == p.configuration.event_count and constants["threads"] == p.configuration.threads
    assert constants["seeds"] == "identity" and constants["chain"] == p.configuration.tools
    rivet = next(t for tag, t in constants["tools"].items() if t["tool"] == "rivet")          # sharded: rivet.<n>
    assert "pythia" in constants["tools"] and rivet["analyses"] == ["photo_eic"]
    assert constants["points"] == {"failed": 1} and "heimdall" in constants["git"] and constants["host"]
    assert all(len(sha) == 64 for sha in constants["base_cards"].values())
    shown = house.status([p], {})
    assert shown[1].startswith(f"   {p.configuration.event_count:,} events · ") and shown[2].startswith("   tools: pythia")


def test_a_block_lists_its_warnings_and_the_verdict_counts_them():
    out = io.StringIO()
    view, tally, bus = PlainView(stream=out), runs.Tally(), Bus()
    bus.subscribe(view)
    bus.subscribe(tally)
    bus.emit("", "", {"k": "run", "state": "started", "points": 2, "title": "t"})
    for point in ("a", "b"):
        bus.emit(point, "", {"k": "point", "state": "started", "index": 1})
    bus.emit("a", "sherpa", {"k": "tool", "state": "started"})
    for msg in ("Error in initialising ISR (e+ -> j). Ignoring process.", "Error in initialising ISR (e+ -> j). Ignoring process."):
        bus.emit("a", "sherpa", {"k": "log", "level": "error", "msg": msg})
    bus.emit("a", "rivet", {"k": "log", "level": "warn", "msg": "no histogram filled (0 of 13) in zeus.yoda"})
    bus.emit("a", "", {"k": "point", "state": "done", "res": "r/a"})
    bus.emit("b", "", {"k": "point", "state": "failed", "cause": "sherpa", "msg": "sherpa:prepare was silent for 5200 s"})
    view.flush()
    text = out.getvalue()
    assert "   errors: 2 (sherpa 2): Error in initialising ISR (e+ -> j). Ignoring process. (×2)" in text
    assert "   warnings: 1 (rivet 1): no histogram filled (0 of 13) in zeus.yoda" in text
    assert tally.warned() == 1 and tally.failures() == ["   b  [sherpa] sherpa:prepare was silent for 5200 s"]
