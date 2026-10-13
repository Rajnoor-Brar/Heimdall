"""The work dir's lifecycle (audit 3, phase 5.1): records/ apart from logs/ and .cache/ (U21), a point lock
(U66), reserved names (U30), portable records (U29) and `hep migrate --layout`."""

from __future__ import annotations

import argparse
import json
import shutil

import pytest

from runner import cli, execute, house, migrate, record
from runner.errors import HepError
from runner.paths import cache_root, logs_root, records_root


@pytest.fixture
def trees(scratch, monkeypatch):
    for var, name in (("HEP_RECORDS", "records"), ("HEP_LOGS", "logs"), ("HEP_CACHE", "cache"), ("HEP_RESULTS", "results")):
        monkeypatch.setenv(var, str(scratch / name))
    return scratch


def planned(name: str, key: str):
    return cli.build_plans(argparse.Namespace(config=name, set=[], points=None, rerun=False, only=None), key)


def finished(plan) -> None:
    """A point as a completed run leaves it: logs, a product, its records."""
    (plan.out / "logs").mkdir(parents=True, exist_ok=True)
    (plan.out / "cards").mkdir(exist_ok=True)
    plan.res.mkdir(parents=True, exist_ok=True)
    record.provenance_file(plan).parent.mkdir(parents=True, exist_ok=True)
    record.provenance_file(plan).write_text(json.dumps({"seed": 1}), encoding="utf-8")
    record.write_atomic(record.complete_marker(plan), plan.identity + "\n")


def test_deleting_logs_and_cache_reruns_nothing(trees):
    """U21: what a run recorded is in records/, so logs/ and .cache/ may go."""
    p = planned("Demo/jets", "pdf")
    for plan in p.every:
        finished(plan)
    assert record.complete_marker(p.every[0]).is_relative_to(records_root())
    assert p.every[0].out.is_relative_to(logs_root())
    shutil.rmtree(logs_root())
    (cache_root() / "Demo").mkdir(parents=True, exist_ok=True)
    shutil.rmtree(cache_root())
    again = planned("Demo/jets", "pdf")
    assert all(record.is_complete(plan) for plan in again.every)
    assert house.status([again], {})[0].endswith(f"{len(again.every)} complete")


def test_a_point_another_session_runs_is_skipped_naming_it(trees):
    """U66: the second session skips the point the first holds, saying who holds it; nothing is written."""
    p = planned("Demo/jets", "single")
    plan = p.every[0]
    lock = record.PointLock(plan)
    assert lock.acquire()
    try:
        assert record.holder(plan)["pid"] > 0 and house.point_state(plan) == "running"
        heard = []

        class Bus:
            def emit(self, point, tag, event):
                heard.append(event)

        result = execute.run_point(plan, p.run, p.configuration, bus=Bus())
        assert result.held and not result.ok and not result.stopped
        assert heard[-1]["state"] == "skipped" and "running in another session (pid" in heard[-1]["msg"]
        assert not plan.res.exists() and not (plan.out / "cards").exists()    # nothing written twice
        line = next(l for l in house.status([p], {}) if l.strip().startswith(plan.point.name))
        assert "running" in line and "pid" in line
    finally:
        lock.release()
    assert record.holder(plan) is None and house.point_state(plan) == "to run"


def test_a_lock_dies_with_its_process(trees):
    """A lock is the kernel's: when the process that held it ends, however it ends, it is free."""
    import subprocess
    import sys
    p = planned("Demo/jets", "single")
    plan = p.every[0]
    plan.out.mkdir(parents=True, exist_ok=True)
    code = ("import fcntl, os, sys; fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT); "
            "fcntl.flock(fd, fcntl.LOCK_EX); os.write(fd, b'{\"pid\": 1, \"host\": \"x\"}'); os._exit(9)")
    subprocess.run([sys.executable, "-c", code, str(plan.out / record.LOCK_FILE)], check=False)
    assert record.holder(plan) is None
    lock = record.PointLock(plan)
    assert lock.acquire()
    lock.release()


def test_a_reserved_name_is_refused(scratch):
    """U30: plots, pre, post and cluster live beside the points; compare beside a run's configurations."""
    from runner import config, sweep
    text = ('[run]\nname = "r"\nproject = "Demo"\nconfiguration = "c"\nevent_count = 1\n\n'
            '[run.cfgs.c]\nsweeps = ["q"]\ntools = ["x"]\n\n[tools.x]\ntool = "exec"\nexecutable = "path:true"\n'
            'consumes = ["q"]\n\n[quantities.q]\nvalues = [1, 2]\ntags = ["plots", "b"]\n')
    path = scratch / "reserved.toml"
    path.write_text(text, encoding="utf-8")
    run = config.load(str(path))
    with pytest.raises(HepError, match="a point is named 'plots'"):
        sweep.points(run, run.configuration("c"))
    clash = (text.replace('[run.cfgs.c]\n', '[run.cfgs.c]\nlabel = "compare"\n').replace('tags = ["plots", "b"]', 'tags = ["a", "b"]')
             + '\n[plot.figures.both]\nclass = "compare"\nobjects = ["/x/*"]\nconfigurations = ["c"]\n')
    path.write_text(clash, encoding="utf-8")
    with pytest.raises(HepError, match="where this run's compare figures go"):
        config.load(str(path))


def test_the_provenance_is_portable(trees):
    """U29: paths in a record are written under their roots ({work}, {apps}), so a moved work dir or
    machine root still reads; hep reproduce turns them back."""
    from runner.paths import unportable
    p = planned("Demo/jets", "single")
    made = record.provenance(p.every[0], p.run, p.configuration, "a", "b", {})
    assert made["config_file"].startswith("{work}/configs/Demo/")
    assert unportable(made["config_file"]) == str(p.run.path)
    pythia = next(t for t in made["tools"] if t["tag"] == "pythia")
    assert pythia["card"].startswith("{") and not any(a.startswith(str(logs_root())) for a in pythia["argv"])


def test_migrate_layout_moves_output_by_lifecycle(scratch):
    """`hep migrate --layout`: records to records/, caches to .cache/<P>/, the rest to logs/."""
    work = scratch / "w"
    point = work / "output" / "Demo" / "jets" / "01_pdf" / "a"
    cache = work / "output" / "Demo" / ".cache"
    files = {point / "provenance.json": "{}", point / ".complete": "x\n", point / "identity.json": "{}",
             point / "cards" / "pythia.cmnd": "c", point / "logs" / "rivet.log": "l",
             point.parent / "points.json": "{}", point.parent / "status.jsonl": "",
             point.parent / "cluster" / "20261013-1200" / "jobs.toml": "",
             point.parent / "plots" / "d01.toml": "", cache / "herwig" / "k" / "point.run": "",
             cache / "checks" / "pythia" / "x.json": "{}"}
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    moves = dict(migrate.layout_moves(work))
    rec, log = work / "records" / "Demo" / "jets" / "01_pdf", work / "logs" / "Demo" / "jets" / "01_pdf"
    assert moves[point / ".complete"] == rec / "a" / ".complete"
    assert moves[point / "provenance.json"] == rec / "a" / "provenance.json"
    assert moves[point.parent / "points.json"] == rec / "points.json"
    assert moves[point.parent / "cluster" / "20261013-1200" / "jobs.toml"] == rec / "cluster" / "20261013-1200" / "jobs.toml"
    assert moves[point / "logs" / "rivet.log"] == log / "a" / "logs" / "rivet.log"
    assert moves[point.parent / "plots" / "d01.toml"] == log / "plots" / "d01.toml"
    assert moves[cache / "herwig" / "k" / "point.run"] == work / ".cache" / "Demo" / "herwig" / "k" / "point.run"
    assert migrate.apply_layout(list(moves.items()), work) == 0
    assert not (work / "output").exists() and (rec / "a" / ".complete").read_text() == "x\n"
    assert (work / ".cache" / "Demo" / "checks" / "pythia" / "x.json").exists()
