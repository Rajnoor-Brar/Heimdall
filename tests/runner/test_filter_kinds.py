"""New kinds in filters.toml (V203, I-106 step L5): `reason` (quoted by a failure), `fact` (kept with the attempt),
`stat` (a counts table) and `integration` (a prepare step's σ ± err and phase); a folder's rules whatever its
status; Sherpa's and Pythia's rules on real transcripts; [diagnose], a failed tool asked again."""

from __future__ import annotations

import argparse
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from runner import cli, execute, record, tools
from runner.events import Bus
from runner.status import Reader, ToolState

TESTS = Path(__file__).resolve().parents[1]
FOLDERS = TESTS.parent / "framework" / "tools"


def rules(folder: str) -> list[dict]:
    return tomllib.loads((FOLDERS / folder / "filters.toml").read_text(encoding="utf-8"))["rule"]


def read(lines, folder: str, tag: str = "sherpa") -> tuple[Reader, list[dict]]:
    events: list[dict] = []
    bus = Bus()
    bus.subscribe(events.append)
    reader = Reader(ToolState("p", tag), fd=None, out=None, rules=rules(folder), bus=bus)
    for line in lines:
        reader.output(line)
    return reader, events


def test_sherpas_integration_gives_its_cross_section_and_phase_and_its_result_is_a_fact():
    reader, events = read(["Starting the calculation at 07:46:25. Lean back and enjoy ... .",
                           "55556.2 pb +- ( 3784.12 pb = 6.81134 % ) 5000 ( 10944 -> 45.6 % )",
                           "full optimization:  ( 1s elapsed / 2m 14s left ) [07:46:26]",
                           "55063.4 pb +- ( 150.425 pb = 0.273185 % ) 487226 ( 1381641 -> 33.9 % )",
                           "2_2__j__j__j__j : 55063.4 pb +- ( 150.425 pb = 0.273185 % )  exp. eff: 0.25428 %",
                           "  Hard process: P+ (Hadron) + P (Photon)"], "sherpa", "sherpa:prepare")
    assert reader.state.phase == "integrating" and reader.state.xsec == (55063.4, 150.425)
    assert [e["value_pb"] for e in events if e["k"] == "xsec"] == [55556.2, 55063.4, 55063.4]
    assert reader.facts == ["2_2__j__j__j__j : 55063.4 pb +- ( 150.425 pb = 0.273185 % )  exp. eff: 0.25428 %",
                            "Hard process: P+ (Hadron) + P (Photon)"]
    assert reader.reported()["facts"] == reader.facts


def test_sherpas_reasons_are_quoted_and_its_frequency_counts_kept():
    reader, events = read(["Error in initialising ISR (P+ -> e+) Ignoring process.", "No hard process found",
                           "Error messages from 'ShiftMassesDIS' exceeded frequency limit: 340/20",
                           "Error: Sherpa ended without its Results: it set up no process (its reason is in the lines above)"],
                          "sherpa")
    assert reader.reasons == ["Error in initialising ISR (P+ -> e+) Ignoring process.", "No hard process found"]
    assert reader.stats == {"ShiftMassesDIS": 340}
    said = {(e["level"], e["msg"]) for e in events if e["k"] == "log"}
    assert ("error", "No hard process found") in said
    assert ("warn", "Error messages from 'ShiftMassesDIS' exceeded frequency limit: 340/20") in said


def test_pythias_error_statistics_are_a_counts_table_and_its_errors_reasons():
    reader, events = read([" *-------  PYTHIA Error and Warning Messages Statistics  ------------------*",
                           " |  times   message                                                     |",
                           " | 486209   Abort from Pythia::next: parton+hadronLevel failed; giving up    |",
                           " | 51243763   Error in BeamRemnants::setKinematics: kinematics construction failed",
                           " |  40738   Warning in HadronWidths::pickMasses: angular momentum not used   |",
                           " PYTHIA Abort from Pythia::init: all processes have vanishing cross sections",
                           " | q g -> q gamma (udscb)                      201    1.234e-06     |"], "pythia", "pythia")
    assert reader.stats == {"Abort from Pythia::next: parton+hadronLevel failed; giving up": 486209,
                            "Error in BeamRemnants::setKinematics: kinematics construction failed": 51243763,
                            "Warning in HadronWidths::pickMasses: angular momentum not used": 40738}
    assert reader.reasons == ["PYTHIA Abort from Pythia::init: all processes have vanishing cross sections"]
    assert reader.facts == ["| q g -> q gamma (udscb)                      201    1.234e-06     |"]
    assert not [e for e in events if e["k"] == "log" and e["level"] == "warn"]          # counted, not said


def test_a_folders_rules_read_its_output_whatever_its_status(scratch):
    p = cli.build_plans(argparse.Namespace(config="Demo/jets", set=[], points=None, rerun=False, only=None), "single")
    pythia = p.every[0].rendered["pythia"]
    assert pythia.status == "standard" and pythia.filters == rules("pythia")
    assert {"exits", "card", "quote"} <= set(tools.folders()["pythia"].spec["diagnose"])


@pytest.fixture
def trees(scratch, monkeypatch):
    for var, name in (("HEIMDALL_RECORDS", "records"), ("HEIMDALL_CACHE", "cache"), ("HEIMDALL_RESULTS", "results")):
        monkeypatch.setenv(var, str(scratch / name))
    return scratch


def test_a_failure_quotes_its_reason_and_diagnose_asks_the_tool_again(trees):
    p = cli.build_plans(argparse.Namespace(config="Demo/jets", set=[], points=None, rerun=False, only=None), "single")
    plan = p.every[0]
    step = plan.groups[0][0]
    folder = replace(step.folder, spec={**step.folder.spec, "diagnose": {
        "exits": [3], "card": ["Print:quiet = off"], "ext": "cmnd", "quote": "PYTHIA (?:Error|Abort)"}})
    script = ('for a in "$@"; do case "$a" in *diagnose.cmnd) echo "loud now";'
              ' echo " PYTHIA Abort from Pythia::init: all processes have vanishing cross sections"; exit 1;; esac; done;'
              ' echo "Print:quiet = on"; echo " PYTHIA Error in quietness: nothing said"; exit 3')
    plan.groups = [[replace(step, folder=folder, argv=["/bin/bash", "-c", script, "pythia"], inputs=[], outputs=[],
                            products=[], count_check=None, sidecar=None, sidecar_written=None, status="filters",
                            filters=rules("pythia"))]]
    plan.interfaces, plan.prelim = {}, {}
    result = execute.run_point(plan, p.errand, p.configuration, bus=Bus())
    assert not result.ok
    assert result.message == (f"{step.tag} exited with exit code 3: PYTHIA Error in quietness: nothing said; asked again: "
                              "PYTHIA Abort from Pythia::init: all processes have vanishing cross sections")
    said = (plan.out / f"{step.tag}.diagnose.log").read_text(encoding="utf-8").splitlines()
    assert said[0].startswith(f"# tag {step.tag} (asked again: [diagnose]) · exit 1") and "loud now" in said
    assert not (plan.out / "diagnose").exists()                            # its scratch output is gone
    (attempt,) = record.attempts(plan)
    assert attempt["message"] == result.message


def test_diagnose_runs_its_program_in_place_of_the_executable(trees):
    p = cli.build_plans(argparse.Namespace(config="Demo/jets", set=[], points=None, rerun=False, only=None), "single")
    plan = p.every[0]
    step = plan.rendered["pythia"]
    script = 'for last; do :; done; echo "said: $(basename {exe}) $# $(cat "$last")"'
    folder = replace(step.folder, spec={**step.folder.spec, "diagnose": {
        "exits": [3], "card": ["x = 1"], "ext": "cmnd", "quote": "^said", "program": ["/bin/bash", "-c", script, "it"]}})
    step = replace(step, folder=folder, argv=["/no/such/exe", "out.hepmc", "card.cmnd"], outputs=[])
    plan.out.mkdir(parents=True, exist_ok=True)
    assert execute.diagnose(plan, step, 3) == f"said: {step.exe.name} 3 x = 1"      # its arguments, then the card
    assert execute.diagnose(plan, step, 1) == ""                                     # an exit it does not name
