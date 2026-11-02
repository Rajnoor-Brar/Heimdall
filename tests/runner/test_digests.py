"""A tool's digest and a point's history (V201): every tool's <tag>.log is its digest (its first and
last lines and every line its rules matched, numbered), --logs adds <tag>.full.log; a new attempt moves the last
one's logs and cards into history/<n>/, the 9 newest keeping their digests and the 3 newest their whole logs; a
prepare cache entry keeps the digest of the step that filled it, and an older stamp is still a hit."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

import pytest

from runner import cli, execute, paths, record
from runner.errors import HeimdallError
from runner.events import Bus
from runner.status import Reader, ToolState

RULES = [{"match": r"^Event (?P<done>\d+)", "emit": "progress"}, {"match": r"\bERROR\b", "emit": "error"},
         {"match": r"^chatter", "emit": "ignore"}]


@pytest.fixture
def trees(scratch, monkeypatch):
    for var, name in (("HEIMDALL_RECORDS", "records"), ("HEIMDALL_CACHE", "cache"), ("HEIMDALL_RESULTS", "results")):
        monkeypatch.setenv(var, str(scratch / name))
    return scratch


def test_a_long_output_is_digested_to_its_ends_and_what_its_rules_matched(scratch):
    reader = Reader(ToolState("p", "sherpa"), fd=None, out=None, rules=RULES, bus=None)
    for n in range(1, 10_001):
        reader.output(f"ERROR: at {n}" if n % 1000 == 0 else f"Event {n}" if n % 10 == 0 else
                      "chatter" if n % 7 == 0 else f"line {n}")
    text = reader.write_digest(scratch / "sherpa.log", {"tag": "sherpa", "attempt": 2, "exit": 1}).read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "# tag sherpa · attempt 2 · exit 1 · 10000 line(s) (990 progress)"
    assert lines[1:4] == ["line 1", "line 2", "line 3"] and lines[100] == "Event 100"
    assert lines[101] == "# … 9700 line(s) left out …"
    assert lines[102] == "# the lines its rules matched (10), with their numbers:"
    assert lines[103:113] == [f"{n:>9}  ERROR: at {n}" for n in range(1000, 10_001, 1000)]
    assert lines[113] == "# its last 200 line(s):" and lines[-1] == "ERROR: at 10000" and len(lines) == 314


def test_a_short_output_is_kept_whole(scratch):
    reader = Reader(ToolState("p", "pythia"), fd=None, out=None, rules=RULES, bus=None)
    for line in ("one", "", "ERROR: two", "three"):
        reader.output(line)
    text = reader.write_digest(scratch / "pythia.log", {"tag": "pythia", "exit": 0}).read_text(encoding="utf-8")
    assert text == "# tag pythia · exit 0 · 4 line(s)\none\n\nERROR: two\nthree\n"


def fake(script: str, configuration: str = "single"):
    p = cli.build_plans(argparse.Namespace(config="Demo/jets", set=[], points=None, rerun=False, only=None), configuration)
    plan = p.every[0]
    step = plan.groups[0][0]
    plan.groups = [[replace(step, argv=["/bin/bash", "-c", script], inputs=[], outputs=[], products=[], count_check=None,
                            sidecar=None, sidecar_written=None, status="filters", filters=RULES)]]
    plan.interfaces, plan.prelim = {}, {}
    return p, plan, step.tag


def test_twelve_attempts_leave_nine_digests_and_three_whole_logs(trees):
    p, plan, tag = fake('for i in $(seq 1 400); do echo "line $i"; done; exit 1')
    for _ in range(12):
        execute.run_point(plan, p.errand, p.configuration, bus=Bus(), logs=True)
    history = plan.out / execute.HISTORY
    kept = sorted(int(f.name) for f in history.iterdir())
    assert kept == list(range(3, 12))                                  # attempts 3…11; the 12th's are the point's own
    assert all((history / str(n) / f"{tag}.log").is_file() and (history / str(n) / "cards").is_dir() for n in kept)
    assert [n for n in kept if (history / str(n) / f"{tag}.full.log").is_file()] == [9, 10, 11]
    assert (plan.out / f"{tag}.log").read_text(encoding="utf-8").startswith(f"# tag {tag} · attempt 12 · started ")
    assert len((plan.out / f"{tag}.full.log").read_text(encoding="utf-8").splitlines()) == 400
    assert [a["n"] for a in record.attempts(plan)] == list(range(1, 13))


def test_an_old_records_first_rotation_takes_the_next_free_number(trees):
    _, plan, tag = fake("true")
    plan.out.mkdir(parents=True)
    (plan.out / f"{tag}.log").write_text("from before attempts were kept\n", encoding="utf-8")
    assert execute.rotate(plan, 9, 3) == plan.out / "history" / "1"
    assert (plan.out / "history" / "1" / f"{tag}.log").is_file() and not (plan.out / f"{tag}.log").exists()
    (plan.out / "prelim.log").write_text("x\n", encoding="utf-8")
    assert execute.rotate(plan, 9, 3).name == "2" and execute.rotate(plan, 9, 3) is None    # nothing left to keep


def sherpa_plan():
    p = cli.build_plans(argparse.Namespace(config="Demo/sherpa", set=[], points=None, rerun=False, only=None), "single")
    plan = p.every[0]
    step = next(s for s in plan.rendered.values() if s.prepare_dir is not None)
    return p, plan, step


def test_a_prepare_entry_keeps_its_digest_and_a_stamp_of_the_older_shape_is_still_a_hit(trees):
    p, plan, step = sherpa_plan()
    marker = step.folder.spec["prepare"].get("marker") or "done"
    plan.rendered[step.tag] = step = replace(step, prepare_needed=True,
                                             prepare_argv=["/bin/bash", "-c", f"echo integrating; touch {marker}"])
    plan.out.mkdir(parents=True, exist_ok=True)
    results: dict = {}
    ok, _, _ = execute.run_prepares(plan, stopper=execute.Stopper(), results=results, attempt=1)
    assert ok
    stamp = json.loads((step.prepare_dir / ".prepared").read_text(encoding="utf-8"))
    assert stamp["point"] == plan.point.name and stamp["seconds"] >= 0 and len(stamp["card_sha256"]) == 64
    assert stamp["record"].endswith(str(plan.folders.record.relative_to(plan.folders.record.parents[2])))
    assert (step.prepare_dir / "prepare.log").read_text(encoding="utf-8").splitlines()[1] == "integrating"
    results = {}
    execute.run_prepares(plan, stopper=execute.Stopper(), results=results)
    hit = results[f"{step.tag}:prepare"]
    assert hit.cache == str(step.prepare_dir) and "prepare.log" in hit.message
    (step.prepare_dir / ".prepared").write_text(json.dumps({"argv": ["x"], "finished": "then"}), encoding="utf-8")
    (step.prepare_dir / "prepare.log").unlink()
    results = {}
    execute.run_prepares(plan, stopper=execute.Stopper(), results=results)           # an older stamp: still a hit
    assert results[f"{step.tag}:prepare"].cache == str(step.prepare_dir)


def test_run_log_is_read_from_heimdall_toml_and_checked(scratch, monkeypatch):
    work = scratch / "logwork"
    work.mkdir()
    (work / "heimdall.toml").write_text('[work]\nname = "w"\n[run]\nlog = { head = 5, full = 1 }\n', encoding="utf-8")
    monkeypatch.chdir(work)
    monkeypatch.setenv("HEIMDALL_WORK", str(work))
    assert paths.log_settings() == {**paths.LOG_DEFAULTS, "head": 5, "full": 1}
    (work / "heimdall.toml").write_text('[work]\nname = "w"\n[run]\nlog = { heads = 5 }\n', encoding="utf-8")
    with pytest.raises(HeimdallError, match="no 'heads' to set"):
        paths.log_settings()
