"""Provenance across two repos (docs/framework/01_Target.md §5.6): a point records Heimdall's git state
and its work dir's, which `hep reproduce` compares with today's."""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

from helpers import plan, raw
from runner import paths, record
from support import REPO, WORK

needs_git = pytest.mark.skipif(not shutil.which("git") or not (REPO / ".git").exists(), reason="git, and Heimdall a checkout")


def head(folder) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=folder, capture_output=True, text=True).stdout.strip()


def provenance_of(scratch):
    run, conf, point = plan(raw(), scratch)
    return record.provenance(point, run, conf, "2026-10-10T00:00:00", "2026-10-10T00:00:01", {})


def test_a_folder_that_is_not_a_repo_has_no_git_state(scratch):
    assert record.git_state(scratch) == {}


@needs_git
def test_a_point_records_both_roots_and_heimdalls_revision(scratch):
    made = provenance_of(scratch)
    assert made["git"]["heimdall"]["revision"] == head(REPO)
    assert made["git"]["work"] == {}                                   # the scratch work is not a repo
    assert made["hep"] == str(REPO)
    assert made["work"] == {"name": "fixture", "root": str(WORK)}
    assert made["stack"] == os.environ.get("HEP_STACK", "")


@needs_git
def test_a_work_dir_in_git_records_its_revision(scratch, monkeypatch):
    work = scratch / "study"
    shutil.copytree(WORK, work)                                       # build/ too: planning reads photo_eic.info
    (work / ".gitignore").write_text("build/\n", encoding="utf-8")
    for var, value in (("GIT_AUTHOR_NAME", "t"), ("GIT_COMMITTER_NAME", "t"),
                       ("GIT_AUTHOR_EMAIL", "t@t.invalid"), ("GIT_COMMITTER_EMAIL", "t@t.invalid")):
        monkeypatch.setenv(var, value)
    for argv in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "w"]):
        subprocess.run(["git", *argv], cwd=work, check=True, capture_output=True)
    monkeypatch.setenv("HEP_WORK", str(work))
    paths.reset()
    try:
        made = provenance_of(scratch)
    finally:
        paths.reset()
    assert made["git"]["work"] == {"revision": head(work), "dirty": False}
    assert made["work"]["root"] == str(work)


@needs_git
def test_reproduce_is_told_when_a_revision_moved():
    today = record.git_state(REPO)
    assert record.revision_changes({"heimdall": {"revision": today["revision"], "dirty": False}}) == []
    moved = record.revision_changes({"heimdall": {"revision": "0" * 40, "dirty": True}, "work": {}})
    assert moved[0] == f"heimdall was at {'0' * 12} when it ran, and is at {today['revision'][:12]} now"
    assert moved[1].startswith("heimdall had uncommitted changes when it ran")
    assert record.revision_changes({"revision": "x", "dirty": False}) == []     # High-Energy's form: one repo, not compared
