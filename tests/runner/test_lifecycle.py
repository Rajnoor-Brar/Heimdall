"""The work dir's lifecycle (audit 3, phase 5.1; V157): a point's records (records/<run>/points/) apart from its
working folder (records/<run>/logs/) and .cache/ (U21), a point lock (U66), reserved names (U30), portable records
(U29) and `heimdall migrate --layout`."""

from __future__ import annotations

import argparse
import json
import shutil

import pytest

from runner import cli, execute, house, migrate, record
from runner.errors import HeimdallError
from runner.paths import cache_root, records_root, results_root


@pytest.fixture
def trees(scratch, monkeypatch):
    for var, name in (("HEIMDALL_RECORDS", "records"), ("HEIMDALL_CACHE", "cache"), ("HEIMDALL_RESULTS", "results")):
        monkeypatch.setenv(var, str(scratch / name))
    return scratch


def planned(name: str, key: str):
    return cli.build_plans(argparse.Namespace(config=name, set=[], points=None, rerun=False, only=None), key)


def finished(plan) -> None:
    """A point as a completed run leaves it: a log, its cards, a product, its records."""
    (plan.out / "cards").mkdir(parents=True, exist_ok=True)
    (plan.out / "pythia.log").write_text("x\n", encoding="utf-8")
    plan.res.mkdir(parents=True, exist_ok=True)
    record.provenance_file(plan).parent.mkdir(parents=True, exist_ok=True)
    record.provenance_file(plan).write_text(json.dumps({"seed": 1}), encoding="utf-8")
    record.write_atomic(record.complete_marker(plan), plan.identity + "\n")


def test_deleting_logs_and_cache_reruns_nothing(trees):
    """U21, V157: what a run recorded is in records/<run>/points/, so records/<run>/logs/ and .cache/ may go."""
    p = planned("Demo/jets", "pdf")
    for plan in p.every:
        finished(plan)
    first = p.every[0]
    assert record.complete_marker(first) == records_root() / first.folders.record.relative_to(records_root()) / "points" / first.point.name / ".complete"
    assert first.out == first.folders.record / "logs" / first.point.name and first.res == first.folders.results / "points" / first.point.name
    assert first.res.is_relative_to(results_root()) and first.rendered["pythia"].log == first.out / "pythia.log"
    shutil.rmtree(first.folders.logs)
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

        result = execute.run_point(plan, p.errand, p.configuration, bus=Bus())
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
    text = ('[errand]\nname = "r"\nassignment = "Demo"\nconfiguration = "c"\nevent_count = 1\n\n'
            '[errand.cfgs.c]\nsweeps = ["q"]\ntools = ["x"]\n\n[tools.x]\ntool = "exec"\nexecutable = "path:true"\n'
            'consumes = ["q"]\n\n[quantities.q]\nvalues = [1, 2]\ntags = ["plots", "b"]\n')
    path = scratch / "reserved.toml"
    path.write_text(text, encoding="utf-8")
    errand = config.load(str(path))
    with pytest.raises(HeimdallError, match="a point is named 'plots'"):
        sweep.points(errand, errand.configuration("c"))
    clash = (text.replace('[errand.cfgs.c]\n', '[errand.cfgs.c]\nlabel = "compare"\n').replace('tags = ["plots", "b"]', 'tags = ["a", "b"]')
             + '\n[plot.figures.both]\nclass = "compare"\nobjects = ["/x/*"]\nconfigurations = ["c"]\n')
    path.write_text(clash, encoding="utf-8")
    with pytest.raises(HeimdallError, match="where this run's compare figures go"):
        config.load(str(path))


def test_the_provenance_is_portable(trees):
    """U29: paths in a record are written under their roots ({work}, {apps}), so a moved work dir or
    machine root still reads; heimdall reproduce turns them back."""
    from runner.paths import unportable
    p = planned("Demo/jets", "single")
    made = record.provenance(p.every[0], p.errand, p.configuration, "a", "b", {})
    assert made["config_file"].startswith("{work}/configs/Demo/")
    assert unportable(made["config_file"]) == str(p.errand.path)
    pythia = next(t for t in made["tools"] if t["tag"] == "pythia")
    assert pythia["card"].startswith("{") and not any(a.startswith(str(records_root())) for a in pythia["argv"])


def test_migrate_layout_moves_output_by_lifecycle(scratch):
    """`heimdall migrate --layout`: records to records/, caches to .cache/<P>/, the rest to logs/."""
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
    assert not (work / "output").exists() and (rec / "a" / ".complete").read_text(encoding="utf-8") == "x\n"
    assert (work / ".cache" / "Demo" / "checks" / "pythia" / "x.json").exists()


def test_migrate_layout_moves_logs_into_records_and_points_into_points(scratch):
    """V157: logs/ into records/<run>/logs/ (a point's logs/*.log one level up), page documents and journals
    beside the points, points into points/ of records/ and results/, points.json pointed at them; the
    stages' products, the pages and the submissions stay where they are."""
    work = scratch / "w"
    rel = "Demo/jets/01_pdf"
    rec, log, res = work / "records" / rel, work / "logs" / rel, work / "results" / rel
    files = {rec / "a" / ".complete": "x\n", rec / "a" / "provenance.json": "{}", rec / "pre" / ".complete": "p\n",
             rec / "cluster" / "20261013-1200" / "jobs.toml": "",
             log / "a" / "cards" / "pythia.cmnd": "c", log / "a" / "logs" / "rivet.log": "l", log / "a" / ".lock": "",
             log / "pre" / "logs" / "make.log": "m", log / "plots" / "d01.toml": "", log / "status.jsonl": "",
             work / "logs" / "Demo" / "jets" / "compare" / "both" / "d01.toml": "",
             work / "logs" / "Demo" / ".reproduce" / "abc" / "results" / "x": "", work / "logs" / "plots" / "k" / "files.root": "",
             res / "a" / "jets.yoda": "y", res / "pre" / "made.txt": "", res / "plots" / "root" / "d01.pdf": ""}
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (rec / "points.json").write_text(json.dumps({"points": [{
        "name": "a", "results": str(res / "a"), "output": str(log / "a"), "products": {"jets.yoda": str(res / "a" / "jets.yoda")}}]}),
        encoding="utf-8")
    moves = dict(migrate.logs_moves(work))
    assert moves[rec / "a"] == rec / "points" / "a" and moves[rec / "pre"] == rec / "points" / "pre"
    assert moves[res / "a"] == res / "points" / "a" and res / "pre" not in moves and res / "plots" not in moves
    assert moves[log / "a"] == rec / "logs" / "a" and moves[log / "plots"] == rec / "plots"
    assert moves[log / "status.jsonl"] == rec / "status.jsonl" and rec / "cluster" not in moves
    assert moves[work / "logs" / "Demo" / "jets" / "compare" / "both"] == work / "records" / "Demo" / "jets" / "compare" / "both"
    assert moves[work / "logs" / "Demo" / ".reproduce"] == work / ".cache" / "Demo" / "reproduce"
    assert moves[work / "logs" / "plots"] == work / ".cache" / "overlay"
    assert migrate.apply_logs(list(moves.items()), work) == 0
    assert not (work / "logs").exists()
    assert (rec / "points" / "a" / ".complete").read_text(encoding="utf-8") == "x\n"
    assert (rec / "logs" / "a" / "rivet.log").read_text(encoding="utf-8") == "l" and not (rec / "logs" / "a" / "logs").exists()
    assert (rec / "logs" / "a" / "cards" / "pythia.cmnd").is_file() and (rec / "logs" / "pre" / "make.log").is_file()
    assert (res / "points" / "a" / "jets.yoda").is_file() and (res / "pre" / "made.txt").is_file()
    assert (res / "plots" / "root" / "d01.pdf").is_file() and (rec / "cluster" / "20261013-1200" / "jobs.toml").is_file()
    entry = json.loads((rec / "points.json").read_text(encoding="utf-8"))["points"][0]
    assert entry["results"] == str(res / "points" / "a") and entry["output"] == str(rec / "logs" / "a")
    assert entry["products"] == {"jets.yoda": str(res / "points" / "a" / "jets.yoda")}
    assert migrate.logs_moves(work) == []                                # today's layout: nothing to move


def test_moving_the_machine_root_and_the_work_dir_changes_no_fingerprint(trees, monkeypatch):
    """V137: a fingerprint names its programs and cards under {apps}, {work} and the other roots, so a
    work dir copied elsewhere, with its machine root (its apps) somewhere else too, plans to the same
    identity at every point of every configuration."""
    import os
    from support import WORK
    from runner import config, paths
    names = ["Demo/jets", "Demo/validation", "Decay/decay"]

    def identities() -> dict:
        out = {}
        for name in names:
            for key in config.load(name).configurations:
                for plan in planned(name, key).every:
                    out[(name, key, plan.point.name)] = plan.identity
        return out

    here = identities()
    moved = trees / "elsewhere"
    shutil.copytree(WORK, moved / "work", symlinks=True)
    (moved / "machine").mkdir()
    (moved / "machine" / "apps").symlink_to(paths.apps_dir().resolve())
    monkeypatch.setenv("HEIMDALL_WORK", str(moved / "work"))
    monkeypatch.setenv("HEIMDALL_MACHINE", str(moved / "machine"))
    monkeypatch.setenv("HEIMDALL_APPS", str(moved / "machine" / "apps"))
    paths.reset()
    try:
        there = identities()
        parts = json.dumps(record.identity_parts(planned("Demo/jets", "single").every[0]))
    finally:
        paths.reset()
    assert there == here
    assert str(moved) not in parts and str(WORK) not in parts and os.path.expanduser("~/Himinbjorg") not in parts


def test_migrate_layout_moves_pages_into_their_set_and_numbers_out_of_plots(scratch):
    """V164: plots/<backend>/ into plots/totality/<backend>/, the merged sweep and the page documents into
    .cache/<P>/plots/<name>/<cfg>/, statistics.csv and its bar graphs into statistics/totality/; a compare
    figure's documents into .cache/ and its table into its statistics/. Renames; then nothing is left to move."""
    work = scratch / "w"
    rel = "Demo/jets/01_pdf"
    rec, res = work / "records" / rel, work / "results" / rel
    cache = work / ".cache" / "Demo" / "plots" / "jets" / "01_pdf"
    compare = work / "results" / "Demo" / "jets" / "compare" / "both"
    files = {res / "plots" / "root" / "em" / "d01.png": "p", res / "plots" / "root" / "index.html": "i",
             res / "plots" / "root" / "pdf.root": "r", res / "plots" / "mpl" / "em" / "d01.png": "m",
             res / "plots" / "root" / "sheets" / "grid.pdf": "s", res / "plots" / "statistics.csv": "c",
             res / "plots" / "statistics" / "em" / "d01.png": "b", res / "plots" / "statistics" / "summary.png": "S",
             rec / "plots" / "em" / "d01.toml": "t", rec / "plots" / "merged.sha256": "h", rec / "points.json": "{}",
             work / "records" / "Demo" / "jets" / "compare" / "both" / "em" / "d01.toml": "",
             compare / "root" / "em" / "d01.png": "", compare / "statistics.csv": "",
             compare / "statistics" / "em" / "d01.png": ""}
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert migrate.old_plots(work)
    moves = dict(migrate.sets_moves(work))
    totality = res / "plots" / "totality"
    assert moves[res / "plots" / "root" / "em"] == totality / "root" / "em"
    assert moves[res / "plots" / "root" / "pdf.root"] == cache / "pdf.root"
    assert moves[res / "plots" / "root" / "sheets"] == totality / "root" / "sheets"
    assert moves[res / "plots" / "statistics.csv"] == res / "statistics" / "totality" / "statistics.csv"
    assert moves[res / "plots" / "statistics" / "em"] == res / "statistics" / "totality" / "bars" / "em"
    assert moves[res / "plots" / "statistics" / "summary.png"] == res / "statistics" / "totality" / "summary.png"
    assert moves[rec / "plots"] == cache
    assert moves[compare / "statistics.csv"] == compare / "statistics" / "statistics.csv"
    assert moves[compare / "statistics" / "em"] == compare / "statistics" / "bars" / "em"
    assert compare / "root" not in moves                                 # a compare figure's pages stay
    assert migrate.apply_sets(list(moves.items()), work) == 0
    assert (totality / "root" / "em" / "d01.png").read_text(encoding="utf-8") == "p"
    assert (totality / "mpl" / "em" / "d01.png").is_file() and (cache / "em" / "d01.toml").is_file()
    assert (cache / "merged.sha256").is_file() and (cache / "pdf.root").is_file() and (rec / "points.json").is_file()
    assert not (res / "plots" / "root").exists() and not (rec / "plots").exists()
    assert not migrate.old_plots(work) and migrate.sets_moves(work) == []
