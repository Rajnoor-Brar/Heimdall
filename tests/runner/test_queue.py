"""Run queues: a run queued to another waits for it (queued, held), a queue's order, how `heimdall runs` shows them,
dispatch and forget, and sweeps as chains."""

from __future__ import annotations

import os
import time

from runner import house, runs


def entry(run_id: str, **fields) -> dict:
    """A registry entry as a run's worker writes it: this process's pid, so it reads as alive."""
    return {**runs.here(), "id": run_id, "kind": "run", "started": fields.pop("started", 1.0), "config": "/w/configs/P/a.toml",
            "work": "/w", "configurations": ["c"], **fields}


def test_a_waiting_run_is_queued_and_held_when_its_predecessor_was_stopped():
    assert runs.state(entry("20261108-1200-pp-aaaa", queued=True, queued_to="x")) == "queued"
    assert runs.state(entry("20261108-1200-pp-aaaa", queued=True, held=True, queued_to="x")) == "held"
    assert runs.state(entry("20261108-1200-pp-aaaa", queued=False, queued_to="x")) == "running"    # its turn came
    gone = {**entry("20261108-1200-pp-aaaa", queued=True), "pid": 2 ** 22 + 7, "pstart": "1"}
    assert runs.state(gone) == "lost"                                  # its waiting worker died: not queued


def test_a_queue_is_in_its_chain_order_and_a_split_heads_its_own():
    a = entry("q-a", queue="q-a", started=1.0)
    c = entry("q-c", queue="q-a", queued_to="q-b", queued=True, started=2.0)
    b = entry("q-b", queue="q-a", queued_to="q-a", queued=True, started=3.0)        # queued after C was, but before it
    other = entry("q-z", started=0.5)
    assert [e["id"] for e in runs.queue_of([c, other, b, a], "q-a")] == ["q-a", "q-b", "q-c"]
    b_split = {**b, "queue": "q-b", "queued": False, "dispatched_from": "q-a"}
    c_split = {**c, "queue": "q-b"}
    assert [e["id"] for e in runs.queue_of([a, b_split, c_split], "q-a")] == ["q-a"]
    assert [e["id"] for e in runs.queue_of([a, b_split, c_split], "q-b")] == ["q-b", "q-c"]


def test_runs_lists_a_queue_with_its_places_and_what_each_waits_for():
    a = entry("20261108-120000-pp-aaaa", queue="20261108-120000-pp-aaaa", started=1.0)
    b = entry("20261108-120001-pp-bbbb", queue=a["id"], queued_to=a["id"], queued=True, started=2.0)
    c = entry("20261108-120002-pp-cccc", queue=a["id"], queued_to=b["id"], queued=True, held=True, started=3.0)
    lines = house.runs_listing([a, b, c], [], {}, now=time.time())
    blocks = "\n".join(lines).split("\n\n")
    assert len(blocks) == 3
    assert "    running · NULL/NULL · queue …aaaa 1 of 3" in blocks[0]
    assert "    queued · after [1] …aaaa · NULL/NULL · queue …aaaa 2 of 3" in blocks[1]
    assert "    held · after [2] …bbbb · NULL/NULL · queue …aaaa 3 of 3" in blocks[2]
    assert f"pid {os.getpid()} : heimdall runs --dispatch 2 · heimdall runs --forget 2" in blocks[1]
    assert house.live_entries([a, b, c], []) and len(house.live_entries([a, b, c], [])) == 3
    tinted = "\n".join(house.runs_listing([a, b, c], [], {}, now=time.time(), color=True))
    assert "\x1b[34mqueued\x1b[0m" in tinted and "\x1b[33mheld\x1b[0m" in tinted


import subprocess
import threading
from pathlib import Path

import pytest

from runner import cli


@pytest.fixture
def quick(monkeypatch):
    """A waiter that looks every 20 ms."""
    monkeypatch.setattr(runs, "QUEUE_POLL", 0.02)


def waiting(run_id: str, queued_to: str) -> tuple[threading.Thread, dict]:
    """wait_turn in a thread, as a queued worker runs it: what it returns lands in `got`."""
    got: dict = {}
    thread = threading.Thread(target=lambda: got.update(cli.wait_turn(run_id, queued_to, {"config": "/w/configs/P/a.toml"})),
                              daemon=True)
    thread.start()
    deadline = time.time() + 5
    while not (runs.entry(run_id) or {}).get("queued") and time.time() < deadline:
        time.sleep(0.01)
    return thread, got


def settled(thread: threading.Thread) -> None:
    thread.join(5)
    assert not thread.is_alive()


def test_a_queued_run_starts_when_its_predecessor_ends_done_or_failed(quick):
    for verdict in (0, 1):
        before, me = runs.new_id(), runs.new_id()
        runs.begin(before, {})                                     # running: this process
        thread, got = waiting(me, before)
        assert runs.state(runs.entry(me)) == "queued" and runs.entry(me)["queue"] == before
        time.sleep(0.1)
        assert thread.is_alive()                                   # it waits while the one before runs
        runs.finish(before, verdict)
        settled(thread)
        assert got["queued"] is False and got["queue"] == before and got["queued_to"] == before and "began" in got


def test_a_stopped_predecessor_holds_it_until_it_is_dispatched_and_then_it_heads_its_own_queue(quick):
    before, me = runs.new_id(), runs.new_id()
    runs.begin(before, {})
    thread, got = waiting(me, before)
    runs.finish(before, 6)                                         # stopped
    deadline = time.time() + 5
    while not runs.entry(me).get("held") and time.time() < deadline:
        time.sleep(0.01)
    assert runs.state(runs.entry(me)) == "held" and thread.is_alive()
    assert runs.ask_queue(me, "dispatch")
    settled(thread)
    assert (got["queue"], got["queued_to"], got["dispatched_from"], got["held"]) == (me, None, before, False)


def test_a_waiter_follows_a_resume_and_a_forgotten_predecessor(quick):
    first, second, me = runs.new_id(), runs.new_id(), runs.new_id()
    runs.begin(first, {})
    runs.begin(second, {"queue": first, "queued_to": first, "queued": True})
    thread, got = waiting(me, second)
    assert runs.entry(me)["queue"] == first                        # the queue is its predecessor's
    runs.finish(first, 6, state="paused")
    resumed = runs.new_id()
    runs.begin(resumed, {"queue": first})
    runs.update(first, resumed_by=resumed)                         # not its predecessor: second still waits for first
    runs.finish(second, 2, "forgotten", left_queue=True, queued=False)     # second leaves: me now waits for first
    deadline = time.time() + 5
    while runs.entry(me).get("queued_to") != resumed and time.time() < deadline:
        time.sleep(0.01)
    assert runs.entry(me)["queued_to"] == resumed and thread.is_alive()   # first resumed: it waits for the resumed run
    runs.finish(resumed, 0)
    settled(thread)
    assert got["queued_to"] == resumed


def test_forget_ends_a_queued_run_unrun(quick):
    before, me = runs.new_id(), runs.new_id()
    runs.begin(before, {})
    thread, got = waiting(me, before)
    runs.ask_queue(me, "forget")
    settled(thread)
    assert got == {"verdict": "forgotten", "code": 2}
    ended = runs.entry(me)
    assert ended["left_queue"] and ended["verdict"] == "forgotten" and ended["queued_to"] == before


def test_queued_to_checks_the_run_now_and_starts_a_waiting_worker(monkeypatch, capsys):
    before = runs.new_id()
    runs.begin(before, {})
    spawned = []

    def spawn(argv: list[str], run_id: str, log: Path) -> subprocess.Popen:
        spawned.append(argv)
        runs.begin(run_id, {"queued": True, "queued_to": before, "queue": before})
        return subprocess.Popen(["sleep", "1"])

    monkeypatch.setattr(runs, "spawn", spawn)
    assert cli.main(["run", "Demo/jets", "single", "--queued-to", before[-4:], "--detach"]) == 0
    assert spawned[-1][-2:] == ["--queued-to", before] and "--detach" not in spawned[-1]
    out = capsys.readouterr().out
    assert f"{before}\n" in out and ", after [" in out and str(runs.folder()) in out
    runs.finish(before, 0)
    assert cli.main(["run", "Demo/jets", "single", "--queued-to", before]) == 2
    assert "has ended (done)" in capsys.readouterr().err


def test_again_does_not_queue_a_relaunch():
    assert runs.again({"argv": ["run", "P/b", "--queued-to", "x", "--worker", "y"]}) == ["run", "P/b", "--detach"]


def test_dispatch_and_forget_ask_the_waiter_and_refuse_what_is_not_queued(capsys):
    before, me = runs.new_id(), runs.new_id()
    runs.begin(before, {})
    runs.begin(me, {"queue": before, "queued_to": before, "queued": True})
    assert cli.main(["runs", "--dispatch", me]) == 0
    assert runs.queue_asked(me) == "dispatch" and "starts now" in capsys.readouterr().out
    assert cli.main(["runs", "--forget", me]) == 0
    assert runs.queue_asked(me) == "forget" and f"waits for {before}" in capsys.readouterr().out
    assert cli.main(["runs", "--dispatch", before]) == 2
    assert "is running, not queued" in capsys.readouterr().err


def test_the_prompt_offers_dispatch_stop_and_forget_for_a_queued_run_and_watch_waits_its_turn(capsys):
    before, me = runs.new_id(), runs.new_id()
    runs.begin(before, {})
    runs.begin(me, {"queue": before, "queued_to": before, "queued": True})
    entry_, state, number = cli.entry_of(me)
    assert state.word == "queued" and cli.offered(entry_, state, number) == ["d", "s", "f", "q"]
    assert cli.act_on(me, {}, plain=True, key_reader=lambda: "d", line_reader=lambda prompt: "dispatch") == 0
    assert runs.queue_asked(me) == "dispatch"
    assert cli.running_at(number, "stopped") == os.getpid()
    with pytest.raises(cli.HeimdallError, match="nothing is watched until its turn"):
        cli.running_at(number, "watched")


def sweep_of(monkeypatch, keys: list[str]) -> None:
    """Demo/jets with a sweep of `keys` (as [errand].sweep_runs would give)."""
    from runner import config
    monkeypatch.setattr(config.Errand, "runs", lambda self, name: list(keys))


def chained_spawn(monkeypatch, *, held_at: int | None = None, slow_at: int | None = None,
                  slow: list | None = None) -> list[tuple[list[str], str]]:
    """runs.spawn faked: each worker's entry begins as its real one would (the head running, the rest queued to the one
    named by --queued-to); `held_at`: that one (1-based) is held, its worker waiting on; `slow_at`: that one's worker
    never begins. Those two sleep, their processes put in `slow`."""
    spawned: list[tuple[list[str], str]] = []
    slow = [] if slow is None else slow

    def spawn(argv: list[str], run_id: str, log: Path) -> subprocess.Popen:
        spawned.append((argv, run_id))
        if slow_at == len(spawned):
            slow.append(subprocess.Popen(["sleep", "30"]))
            return slow[-1]
        to = argv[argv.index("--queued-to") + 1] if "--queued-to" in argv else None
        fields = {"queue": (runs.entry(to) or {}).get("queue", to), "queued_to": to, "queued": True} if to else {}
        if held_at == len(spawned):
            fields["held"] = True
        runs.begin(run_id, fields)
        if held_at == len(spawned):                                # a held waiter waits on, as a real one does
            slow.append(subprocess.Popen(["sleep", "30"]))
            return slow[-1]
        return subprocess.Popen(["sleep", "0.2"])

    monkeypatch.setattr(runs, "spawn", spawn)
    return spawned


def test_a_detached_sweep_is_a_chain_one_worker_a_configuration(monkeypatch, capsys):
    sweep_of(monkeypatch, ["single", "pdf", "energies"])
    spawned = chained_spawn(monkeypatch)
    assert cli.main(["run", "Demo/jets", "--detach"]) == 0
    assert [a[a.index("--sweep-member") + 1] for a, _ in spawned] == ["single", "pdf", "energies"]
    assert all("--detach" not in a for a, _ in spawned)
    ids = [i for _, i in spawned]
    assert "--queued-to" not in spawned[0][0]
    assert [a[a.index("--queued-to") + 1] for a, _ in spawned[1:]] == ids[:2]          # each queued to the one before
    assert [e["id"] for e in runs.queue_of(runs.entries(), ids[0])] == ids
    out = capsys.readouterr().out
    assert "a sweep of 3 runs" in out and f"1. single: {ids[0]}" in out and "3. energies" in out


def test_a_sweep_refuses_points_and_a_config_error_anywhere_starts_nothing(monkeypatch, capsys):
    sweep_of(monkeypatch, ["single", "nowhere"])
    spawned = chained_spawn(monkeypatch)
    assert cli.main(["run", "Demo/jets", "--detach"]) == 2
    assert not spawned and "nowhere" in capsys.readouterr().err
    sweep_of(monkeypatch, ["single", "pdf"])
    assert cli.main(["run", "Demo/jets", "--detach", "--points", "1"]) == 2
    assert not spawned and "this sweep runs several" in capsys.readouterr().err


def test_a_sweep_queued_to_a_run_heads_on_it(monkeypatch, capsys):
    before = runs.new_id()
    runs.begin(before, {})
    sweep_of(monkeypatch, ["single", "pdf"])
    spawned = chained_spawn(monkeypatch)
    assert cli.main(["run", "Demo/jets", "--queued-to", before]) == 0
    assert [a[a.index("--queued-to") + 1] for a, _ in spawned] == [before, spawned[0][1]]
    assert [e["id"] for e in runs.queue_of(runs.entries(), before)] == [before, *(i for _, i in spawned)]


def test_an_attached_sweep_follows_each_run_in_turn_and_stops_at_a_held_one(monkeypatch, capsys):
    sweep_of(monkeypatch, ["single", "pdf", "energies"])
    monkeypatch.setattr(cli, "live", lambda args: True)
    followed = []

    def follow_worker(proc, run_id, log, what, plain):
        followed.append(what)
        proc.wait()
        runs.finish(run_id, 0)
        return "ended", 0

    monkeypatch.setattr(cli, "follow_worker", follow_worker)
    chained_spawn(monkeypatch)                                     # a queued one's worker ends: its turn is over
    assert cli.main(["run", "Demo/jets"]) == 0
    assert [w.rsplit(" · ", 1)[1] for w in followed] == ["single", "pdf", "energies"]
    followed.clear()
    slow: list[subprocess.Popen] = []
    chained_spawn(monkeypatch, held_at=2, slow=slow)
    try:
        assert cli.main(["run", "Demo/jets"]) == 6
        assert len(followed) == 1 and "queue held: pdf" in capsys.readouterr().out
    finally:
        for proc in slow:
            proc.kill()


def test_a_queued_run_starts_when_its_predecessor_is_lost(quick):
    before, me = runs.new_id(), runs.new_id()
    runs.begin(before, {"pid": 2 ** 22 + 7, "pstart": "1"})        # its process gone (killed), its entry never finished
    thread, got = waiting(me, before)
    settled(thread)
    assert got["queued"] is False and got["queued_to"] == before and "began" in got


def test_a_sweep_worker_that_never_begins_is_ended_and_the_queue_forgotten(monkeypatch, capsys, quick):
    """Audit 2026-11-08 O-1: a worker slow to begin was left alive, to run later as a run no one asked for."""
    monkeypatch.setattr(runs, "BEGIN_WAIT", 0.3)
    sweep_of(monkeypatch, ["single", "pdf", "energies"])
    slow: list[subprocess.Popen] = []
    spawned = chained_spawn(monkeypatch, slow_at=3, slow=slow)
    assert cli.main(["run", "Demo/jets", "--detach"]) == 1
    assert slow[0].poll() is not None                                 # ended, not left to begin later
    ids = [i for _, i in spawned]
    assert runs.entry(ids[2]) is None and runs.queue_asked(ids[1]) == "forget"
    err = capsys.readouterr().err
    assert "had not begun after 0.3 s" in err and "heimdall stop --pid" in err and ids[0] in err


def test_a_queued_worker_that_never_begins_is_ended(monkeypatch, capsys, quick):
    monkeypatch.setattr(runs, "BEGIN_WAIT", 0.3)
    before = runs.new_id()
    runs.begin(before, {})
    sweep_of(monkeypatch, ["single"])
    slow: list[subprocess.Popen] = []
    chained_spawn(monkeypatch, slow_at=1, slow=slow)
    assert cli.main(["run", "Demo/jets", "single", "--queued-to", before]) == 1
    assert slow[0].poll() is not None and "had not begun" in capsys.readouterr().err


def test_the_queue_decides_on_the_state_word_and_not_on_how_it_is_written(quick, monkeypatch):
    """The waiter starts, holds and gives the turn as it does when the text is the usual one, whatever the text says."""
    monkeypatch.setattr(runs.RunState, "text", property(lambda self: "worded some other way"))
    before, me = runs.new_id(), runs.new_id()
    runs.begin(before, {})
    thread, got = waiting(me, before)
    time.sleep(0.1)
    assert thread.is_alive()                                       # it waits while the one before runs
    runs.finish(before, 1)
    settled(thread)
    assert got["queued"] is False and got["queued_to"] == before and "began" in got

    stopped, held_one = runs.new_id(), runs.new_id()
    runs.begin(stopped, {})
    thread, got = waiting(held_one, stopped)
    runs.finish(stopped, 6)
    deadline = time.time() + 5
    while not runs.entry(held_one).get("held") and time.time() < deadline:
        time.sleep(0.01)
    assert runs.entry(held_one)["held"] is True and thread.is_alive()       # a stopped predecessor holds it
    assert runs.ask_queue(held_one, "forget")
    settled(thread)

    paused, behind = runs.new_id(), runs.new_id()
    runs.begin(paused, {})
    thread, got = waiting(behind, paused)
    runs.finish(paused, 6, state="paused")
    time.sleep(0.1)
    assert thread.is_alive() and not runs.entry(behind).get("held")         # a pause is waited for
    runs.update(paused, forgotten=1.0)
    deadline = time.time() + 5
    while not runs.entry(behind).get("held") and time.time() < deadline:
        time.sleep(0.01)
    assert runs.entry(behind)["held"] is True                               # a forgotten one holds
    assert runs.ask_queue(behind, "forget")
    settled(thread)
