"""`[errand].sweep_runs = true` (V38): `heimdall run` executes every configuration not `swept = false`, in the
order of the file, each as a run of its own after a `run NN - <title> -` line. All are planned
before the first starts; a failed run leaves the next to start, a stop starts no more; each run's
journal (--journal) names the next, so `heimdall watch --file` follows on; the watch socket is the process's,
so `heimdall watch` follows on by itself (V72)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner import cli, record
from runner.errors import HeimdallError
from runner.watch import PlainView, follow_file

from helpers import parse, plan, raw

CUSTOM = {"tool": "exec", "executable": "/bin/true"}


def several(**changes):
    """Four configurations a, b, c, d; the sweep runs a, b and d (V79: sweep_runs lists them)."""
    return raw(**{"errand__sweep_runs": ["a", "b", "d"], "errand__configuration": None, "errand__cfgs__one": None, "prelim": None,
                  "quantities": None, "static": None,
                  "tools__check": CUSTOM, "errand__cfgs__a": {"tools": ["check"]}, "errand__cfgs__b": {"tools": ["check"], "title": "Bee"},
                  "errand__cfgs__c": {"tools": ["check"]}, "errand__cfgs__d": {"tools": ["check"]}, **changes})


def test_the_keys_and_their_defaults(scratch):
    errand = parse(raw(), scratch)
    assert errand.sweep_runs is False and errand.runs(None) == ["one"]
    conf = errand.configuration(None)
    assert conf.swept is True and conf.title == "one"
    assert parse(raw(errand__cfgs__one__title="PDFs at 27x920"), scratch).configuration(None).title == "PDFs at 27x920"


@pytest.mark.parametrize("changes, message", [
    ({"errand__sweep_runs": 1}, "must be true or false or a list"),
    ({"errand__cfgs__one__swept": False}, "swept is gone"),                  # V79: sweep_runs lists the members
    ({"errand__configuration": None}, "needs 'configuration'"),
    ({"errand__sweep_runs": ["one", "nope"]}, "names 'nope', which is not a"),
    ({"errand__sweep_runs": ["one", "one"]}, "names a configuration twice"),
    ({"errand__sweep_runs": True, "errand__configuration": "nope"}, "not a \\[errand.cfgs.<cfg>\\] table"),
])
def test_what_is_refused(scratch, changes, message):
    with pytest.raises(HeimdallError, match=message):
        parse(raw(**changes), scratch)


def test_a_sweep_runs_its_listed_configurations_in_its_order(scratch):
    errand = parse(several(), scratch)
    assert errand.runs(None) == ["a", "b", "d"]
    assert errand.runs("c") == ["c"]                               # named: even one left out of the sweep
    assert parse(several(errand__sweep_runs=["d", "a"]), scratch).runs(None) == ["d", "a"]
    assert parse(several(errand__sweep_runs=True), scratch).runs(None) == ["a", "b", "c", "d"]   # true: every one
    with pytest.raises(HeimdallError, match=r"runs every configuration \(sweep_runs\) and names none"):
        errand.configuration(None)
    assert parse(several(errand__sweep_runs=False, errand__configuration="b"), scratch).runs(None) == ["b"]


def test_a_configuration_may_still_be_named_sweep(scratch):
    errand = parse(raw(errand__cfgs__sweep={"tools": [["pythia", "rivet"]]}), scratch)
    assert errand.sweep_runs is False and set(errand.configurations) == {"one", "sweep"}


def test_a_sweep_changes_neither_identity_nor_seeds(scratch):
    _, _, alone = plan(raw(), scratch)
    _, _, swept = plan(raw(errand__sweep_runs=True, errand__cfgs__two={"tools": [["pythia", "rivet"]]}), scratch)
    assert record.identity(alone) == record.identity(swept)
    assert record.seed_basis(alone) == record.seed_basis(swept)


# ── the loop in cli.cmd_run, with each run faked ───────────────────────────────────────────────

def toml(data: dict) -> str:
    """Enough TOML for these tables (strings, numbers, booleans, flat lists, one level of tables)."""
    def value(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return json.dumps(v)
        if isinstance(v, list):
            return "[" + ", ".join(value(x) for x in v) + "]"
        return str(v)

    lines = []

    def table(name, body):
        lines.append(f"[{name}]")
        subtables = []
        for key, v in body.items():
            if isinstance(v, dict):
                subtables.append((f"{name}.{key}", v))
            else:
                lines.append(f"{key} = {value(v)}")
        for sub in subtables:
            table(*sub)

    for name, body in data.items():
        table(name, body)
    return "\n".join(lines) + "\n"


@pytest.fixture
def sweep_file(scratch, monkeypatch):
    monkeypatch.setenv("HEIMDALL_RECORDS", str(scratch / "records"))
    monkeypatch.setenv("HEIMDALL_CACHE", str(scratch / "cache"))
    path = scratch / "sw.toml"
    path.write_text(toml(several()), encoding="utf-8")
    return path


def args_for(path: Path, **changes):
    return SimpleNamespace(**{"config": str(path), "configuration": None, "set": [], "points": None, "plan": False,
                              "only": None, "rerun": False, "plain": True, "journal": True, "logs": False,
                              **changes})


def fake_runs(monkeypatch, codes: dict, calls: list, given: list | None = None):
    def run_one(args, key, stopper, *, number=0, following=None, planned=None, bus=None, **rest):
        calls.append((key, number, following.parent.name if following else None))
        if given is not None:
            given.append(planned)
        outcome = codes.get(key, 0)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome == 6:
            stopper.requested = True
        return outcome

    monkeypatch.setattr(cli, "run_one", run_one)


def test_the_runs_go_in_turn_and_a_failed_one_leaves_the_next(sweep_file, monkeypatch):
    calls = []
    fake_runs(monkeypatch, {"b": 1}, calls)
    assert cli.cmd_run(args_for(sweep_file)) == 1
    assert calls == [("a", 1, "b"), ("b", 2, "d"), ("d", 3, None)]      # each names the next one's journal


def test_a_stop_starts_no_more_runs(sweep_file, monkeypatch):
    calls = []
    fake_runs(monkeypatch, {"b": 6}, calls)
    assert cli.cmd_run(args_for(sweep_file)) == 6
    assert [c[0] for c in calls] == ["a", "b"]


def test_every_run_is_checked_before_the_first_starts(sweep_file, monkeypatch):
    calls = []
    fake_runs(monkeypatch, {}, calls)
    real = cli.build_plans

    def build_plans(args, key):
        if key == "d":
            raise HeimdallError("base config not found")
        return real(args, key)

    monkeypatch.setattr(cli, "build_plans", build_plans)
    with pytest.raises(HeimdallError, match="configuration 'd': base config not found"):
        cli.cmd_run(args_for(sweep_file))
    assert calls == []


def test_a_run_that_cannot_be_planned_at_its_turn_fails_alone(sweep_file, monkeypatch, capsys):
    calls = []
    fake_runs(monkeypatch, {"b": HeimdallError("the TOML changed")}, calls)
    assert cli.cmd_run(args_for(sweep_file)) == 1
    assert [c[0] for c in calls] == ["a", "b", "d"]
    assert "run 02 - Bee -" in capsys.readouterr().out
    journal = sweep_file.parent / "records" / "Demo" / "t" / "b" / "status.jsonl"
    finished = json.loads(journal.read_text(encoding="utf-8").splitlines()[-1])
    assert finished["verdict"] == "not run: the TOML changed" and Path(finished["next"]).parent.name == "d"


def test_one_named_configuration_is_a_plain_run(sweep_file, monkeypatch):
    calls = []
    fake_runs(monkeypatch, {}, calls)
    assert cli.cmd_run(args_for(sweep_file, configuration="c")) == 0
    assert calls == [("c", 0, None)]                                   # no header, no next


def test_points_belong_to_one_configuration(sweep_file, monkeypatch):
    fake_runs(monkeypatch, {}, [])
    with pytest.raises(HeimdallError, match="--points picks points of one configuration"):
        cli.cmd_run(args_for(sweep_file, points="1"))


def test_the_header_line():
    assert cli.header(2, SimpleNamespace(title="Beam energies")) == "run 02 - Beam energies -"


# ── heimdall watch follows on ───────────────────────────────────────────────────────────────────────

def test_watch_follows_one_run_to_the_next(scratch, monkeypatch):
    first, second = scratch / "a" / "status.jsonl", scratch / "b" / "status.jsonl"
    for path in (first, second):
        path.parent.mkdir(parents=True)
    records = {
        first: [
            {"k": "run", "state": "started", "points": 1, "title": "t · a", "header": "run 01 - a -", "t": 100.0},
            {"point": "p", "k": "point", "state": "started", "index": 1, "t": 100.0},
            {"point": "p", "k": "point", "state": "done", "t": 105.0},
            {"k": "run", "state": "finished", "verdict": "1 done", "next": str(second), "t": 106.0},
        ],
        second: [
            {"k": "run", "state": "started", "points": 1, "title": "t · b", "header": "run 02 - b -", "t": 107.0},
            {"point": "q", "k": "point", "state": "started", "index": 1, "t": 107.0},
            {"point": "q", "k": "point", "state": "done", "t": 109.5},
            {"k": "run", "state": "finished", "verdict": "1 done", "t": 110.0},
        ],
    }
    for path, lines in records.items():
        path.write_text("".join(json.dumps({"point": "", "tool": "", **m}) + "\n" for m in lines), encoding="utf-8")
    captured = io.StringIO()
    monkeypatch.setattr("runner.watch.view", lambda plain=False: PlainView(stream=captured))
    assert follow_file(first, plain=True) == 0
    text = captured.getvalue()
    assert text.index("run 01 - a -") < text.index("── point 1/1: p ── ok after 5.0s") < text.index("run 02 - b -")
    assert "── point 1/1: q ── ok after 2.5s" in text


def test_an_unchanged_toml_is_planned_once(sweep_file, monkeypatch):
    """V54: each run starts from the plan made up front, unless the TOML was edited since."""
    calls, given = [], []
    fake_runs(monkeypatch, {}, calls, given)
    assert cli.cmd_run(args_for(sweep_file)) == 0
    assert given and all(isinstance(p, cli.Planned) for p in given)



def test_notify_desktop_sends_one_note_and_never_fails(scratch, monkeypatch):
    """V76: [errand] notify = "desktop" calls notify-send with the verdict; without it, nothing."""
    sent = []
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/usr/bin/notify-send")
    monkeypatch.setattr(cli.subprocess, "Popen", lambda argv, **kw: sent.append(argv))
    errand = parse(raw(errand__notify="desktop"), scratch)
    assert cli.notify(errand, 1) and sent[-1][-1].endswith(": a point failed")
    assert not cli.notify(parse(raw(), scratch), 0) and len(sent) == 1
    with pytest.raises(HeimdallError, match="one of none, desktop"):
        parse(raw(errand__notify="email"), scratch)
