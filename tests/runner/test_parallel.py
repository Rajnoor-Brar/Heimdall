"""`parallelism = K` (V36): up to K points at once. It never changes a point (identity, seeds); the
scheduler keeps K running and stops starting on a stop; the views keep each point's part, so a
block is printed whole; the event bus (and so the journal) and the prepare caches are safe to share."""

from __future__ import annotations

import io
import json
import threading
import time
from types import SimpleNamespace

import pytest

from runner import config, execute, record
from runner.errors import HeimdallError
from runner.events import Bus, Journal
from runner.execute import PointResult, Stopper
from runner.sweep import Point
from runner.watch import PlainView

from helpers import parse, plan, raw


def test_parallelism_is_read_from_run_and_the_configuration(scratch):
    assert parse(raw(), scratch).configuration(None).parallelism == 1
    assert parse(raw(errand__parallelism=4), scratch).configuration(None).parallelism == 4
    assert parse(raw(errand__parallelism=4, errand__cfgs__one__parallelism=2), scratch).configuration(None).parallelism == 2
    with pytest.raises(HeimdallError, match="at least 1"):
        parse(raw(errand__parallelism=0), scratch)


def test_parallelism_changes_neither_identity_nor_seeds(scratch):
    _, _, one = plan(raw(errand__threads=2), scratch)
    _, _, four = plan(raw(errand__threads=2, errand__parallelism=4), scratch)
    assert record.identity(one) == record.identity(four)
    assert record.seed_basis(one) == record.seed_basis(four)


def fake_plans(n: int):
    return [SimpleNamespace(point=Point(index=i + 1, name=f"p{i + 1}")) for i in range(n)]


def test_the_scheduler_keeps_k_points_running_in_order(monkeypatch):
    live, peak, started = [0], [0], []
    lock = threading.Lock()

    def run_point(plan, errand, configuration, *, bus, stopper, logs, wait=False):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
            started.append(plan.point.name)
        time.sleep(0.05)
        with lock:
            live[0] -= 1
        return PointResult(plan.point.name != "p4", cause="" if plan.point.name != "p4" else "x")

    monkeypatch.setattr(execute, "run_point", run_point)
    monkeypatch.setattr(execute, "stale", lambda plan, rerun: plan.point.name != "p2")
    done, failed, stopped = execute.run_points(fake_plans(8), None, SimpleNamespace(parallelism=3),
                                               stopper=Stopper(), rerun=False)
    assert (done, failed, stopped) == (6, 1, False)                  # p2 was complete, p4 failed
    assert peak[0] == 3
    assert started[:3] == ["p1", "p3", "p4"]                         # in order, the complete one skipped


def test_a_stop_starts_nothing_more(monkeypatch):
    stopper, started = Stopper(), []

    def run_point(plan, errand, configuration, *, bus, stopper, logs, wait=False):
        started.append(plan.point.name)
        time.sleep(0.05)
        stopper.requested = True                                     # Ctrl-C while the first ones run
        return PointResult(False, stopped=True)

    monkeypatch.setattr(execute, "run_point", run_point)
    monkeypatch.setattr(execute, "stale", lambda plan, rerun: True)
    done, failed, stopped = execute.run_points(fake_plans(6), None, SimpleNamespace(parallelism=2),
                                               stopper=stopper, rerun=False)
    assert stopped and (done, failed) == (0, 0)
    assert started == ["p1", "p2"]


def test_points_running_at_once_each_print_one_whole_block():
    out = io.StringIO()
    view, bus = PlainView(stream=out), Bus()
    bus.subscribe(view)
    bus.emit("", "", {"k": "run", "state": "started", "points": 2})
    bus.emit("MSTW08lo", "", {"k": "point", "state": "started", "index": 1})
    bus.emit("NNPDF23lo", "", {"k": "point", "state": "started", "index": 2})
    bus.emit("NNPDF23lo", "", {"k": "note", "msg": "   sherpa:prepare: cached"})   # a note knows its point
    bus.emit("MSTW08lo", "rivet", {"k": "tool", "state": "started"})
    bus.emit("MSTW08lo", "rivet", {"k": "log", "level": "error", "msg": "boom"})
    bus.emit("MSTW08lo", "rivet", {"k": "exit", "code": 1, "seconds": 1.0})
    bus.emit("NNPDF23lo", "", {"k": "point", "state": "done", "res": "results/x/NNPDF23lo"})
    bus.emit("MSTW08lo", "", {"k": "point", "state": "failed", "cause": "rivet", "msg": "rivet exited 1"})
    view.flush()
    lines = out.getvalue().splitlines()
    assert lines[0].startswith("── point 2/2: NNPDF23lo ── ok")
    assert lines[1:5] == ["", "   sherpa:prepare: cached", "   done → results/x/NNPDF23lo", ""]
    assert lines[5].startswith("── point 1/2: MSTW08lo ── FAILED [rivet]")
    assert lines[6:] == ["", "   rivet: exit 1 after 1.0s  (boom)", "   rivet exited 1", ""]


def test_the_journal_takes_lines_from_many_threads(scratch):
    journal, bus = Journal(scratch / "status.jsonl"), Bus()
    bus.subscribe(journal)

    def write(n: int):
        for i in range(500):
            bus.emit(f"p{n}", "pythia", {"k": "progress", "done": i, "pad": "x" * 200})

    threads = [threading.Thread(target=write, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    journal.close()
    lines = (scratch / "status.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4000 and all(json.loads(line)["k"] == "progress" for line in lines)


def test_a_prepare_entry_is_filled_by_one_point_at_a_time(scratch):
    entry, inside, peak = scratch / "cache" / "abc", [0], [0]
    lock = threading.Lock()

    def fill():
        with execute._prepare_lock(entry):
            with lock:
                inside[0] += 1
                peak[0] = max(peak[0], inside[0])
            time.sleep(0.05)
            with lock:
                inside[0] -= 1

    threads = [threading.Thread(target=fill) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak[0] == 1
    assert (scratch / "cache" / "abc.lock").exists() and not entry.exists()   # the lock sits beside the entry


def test_auto_parallelism_is_the_cores_over_a_points_cores(scratch, monkeypatch):
    """V75: "auto" is os.cpu_count() // the costliest point's cores, at least 1."""
    import os
    from runner import cli
    monkeypatch.setattr(os, "cpu_count", lambda: 24)
    _, conf, p = plan(raw(errand__threads=6, errand__parallelism="auto"), scratch)
    assert conf.parallelism_auto and execute.auto_parallelism([p]) == 24 // execute.cores(p)
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    assert execute.auto_parallelism([p]) == 1
    with pytest.raises(HeimdallError, match="one of auto"):
        parse(raw(errand__parallelism="many"), scratch)


def test_the_budget_holds_a_point_until_its_cores_are_free():
    budget = execute.Budget(24)
    assert budget.take(12) and budget.take(12) and not budget.take(1)
    budget.give(12)
    assert budget.take(12)
    alone = execute.Budget(4)
    assert alone.take(12)                                          # bigger than the budget: it runs alone
    assert not alone.take(1)


def test_a_pipelined_run_says_when_every_point_has_started(monkeypatch):
    """V75: the gate opens once the last point has started, not when it ends; the budget is shared."""
    events, gate = [], threading.Event()

    def run_point(plan, errand, configuration, *, bus, stopper, logs, wait=False):
        events.append(("start", plan.point.name, gate.is_set()))
        time.sleep(0.05)
        return PointResult(True)

    monkeypatch.setattr(execute, "run_point", run_point)
    monkeypatch.setattr(execute, "stale", lambda plan, rerun: True)
    monkeypatch.setattr(execute, "cores", lambda plan: 2)
    budget = execute.Budget(4)
    done, failed, stopped = execute.run_points(fake_plans(3), None, SimpleNamespace(parallelism=3), stopper=Stopper(),
                                               rerun=False, budget=budget, started_all=gate.set)
    assert (done, failed, stopped) == (3, 0, False) and gate.is_set() and budget.used == 0
    assert [e[2] for e in events[:2]] == [False, False]             # shut while p3 waited for its cores
    assert len(events) == 3                                          # (it opens as p3 is handed its thread)


def test_overlapping_runs_keep_their_points_apart():
    """V75: in a pipelined sweep two runs have points of the same name at once; each heading names its run."""
    out = io.StringIO()
    view, bus = PlainView(stream=out), Bus()
    bus.subscribe(view)
    for run in ("a", "b"):
        bus.emit("", "", {"k": "run", "state": "started", "points": 2, "run": run})
        bus.emit("MSTW08lo", "", {"k": "point", "state": "started", "index": 1, "run": run})
    bus.emit("MSTW08lo", "", {"k": "point", "state": "done", "res": "results/b/MSTW08lo", "run": "b"})
    bus.emit("MSTW08lo", "", {"k": "point", "state": "done", "res": "results/a/MSTW08lo", "run": "a"})
    view.end()
    lines = out.getvalue().splitlines()
    assert lines[0].startswith("── point 1/2 (b): MSTW08lo ── ok") and lines[2] == "   done → results/b/MSTW08lo"
    assert lines[4].startswith("── point 1/2 (a): MSTW08lo ── ok") and lines[6] == "   done → results/a/MSTW08lo"


def _watched_points(monkeypatch, seconds: float = 0.25):
    """run_point faked: each point holds for `seconds`; `live`, `peak` and the order they began in are kept."""
    state = {"live": 0, "peak": 0, "log": []}
    lock = threading.Lock()

    def run_point(plan, errand, configuration, *, bus, stopper, logs, wait=False):
        with lock:
            state["live"] += 1
            state["peak"] = max(state["peak"], state["live"])
            state["log"].append((plan.point.name, state["live"]))
        time.sleep(seconds)
        with lock:
            state["live"] -= 1
        return PointResult(True)

    monkeypatch.setattr(execute, "run_point", run_point)
    monkeypatch.setattr(execute, "stale", lambda plan, rerun: True)
    return state


def test_a_live_cap_raised_mid_run_starts_more_points_at_once(monkeypatch):
    """Parallelism 1; after the first point starts the cap is raised to 3: three run at once, in order."""
    state = _watched_points(monkeypatch)
    stopper = Stopper()
    threading.Timer(0.1, stopper.set_parallelism, args=(3,)).start()
    done, failed, halted = execute.run_points(fake_plans(6), None, SimpleNamespace(parallelism=1), bus=Bus(), stopper=stopper, rerun=False)
    assert (done, failed, halted) == (6, 0, False)
    assert state["peak"] == 3 and [name for name, _ in state["log"]] == [f"p{i}" for i in range(1, 7)]
    assert state["log"][0] == ("p1", 1)                      # it began alone


def test_a_live_cap_lowered_starts_none_until_fewer_run_and_stops_no_running_point(monkeypatch):
    state = _watched_points(monkeypatch)
    stopper = Stopper()
    threading.Timer(0.1, stopper.set_parallelism, args=(1,)).start()
    done, failed, halted = execute.run_points(fake_plans(6), None, SimpleNamespace(parallelism=3), bus=Bus(), stopper=stopper, rerun=False)
    assert (done, failed, halted) == (6, 0, False)           # the three running at the change ended: none stopped
    assert [live for _, live in state["log"]] == [1, 2, 3, 1, 1, 1]       # a fourth began alone, after all three ended


def test_the_live_cap_is_the_stoppers_over_every_configuration_and_ceilinged(monkeypatch):
    stopper = Stopper()
    assert stopper.cap(4) == 4 and stopper.cap(0) == 1
    seen = []
    stopper.on_parallelism.append(seen.append)
    assert stopper.set_parallelism(2) is None and stopper.cap(4) == 2 and stopper.cap(1) == 2
    assert stopper.set_parallelism(10 ** 6) == 2 and stopper.parallelism == Stopper.CEILING
    assert seen == [2, Stopper.CEILING]
    assert stopper.set_parallelism(0) == Stopper.CEILING and stopper.parallelism == 1


def test_a_budget_resized_lets_points_start_or_holds_them_without_touching_running_ones():
    budget = execute.Budget(4)
    assert budget.take(2) and budget.take(2) and not budget.take(1)
    budget.resize(6)
    assert budget.take(2) and not budget.take(1)
    budget.resize(2)                                          # lowered: what runs keeps its cores, nothing new starts
    assert budget.used == 6 and not budget.take(1)
    budget.give(6)
    assert budget.take(2) and budget.total == 2
    budget.resize(0)
    assert budget.total == 1
