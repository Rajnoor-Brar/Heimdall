"""A work dir's sources and its git repository (audit 3, phase 5.2 and 5.3): decks/ apart from reports/
(U22), datasets.toml (U23), `hep setup --refresh` (U28), and a work dir made in a git repository (U67)."""

from __future__ import annotations

import hashlib
import json
import subprocess

import pytest

from runner import deck, migrate, record, setup
from runner.errors import HepError


@pytest.fixture
def quiet():
    lines: list[str] = []
    return lines.append, lines


@pytest.fixture
def git_identity(monkeypatch):
    for var, value in (("GIT_AUTHOR_NAME", "t"), ("GIT_AUTHOR_EMAIL", "t@t"), ("GIT_COMMITTER_NAME", "t"),
                       ("GIT_COMMITTER_EMAIL", "t@t")):
        monkeypatch.setenv(var, value)


def git(where, *args) -> str:
    return subprocess.run(["git", *args], cwd=where, capture_output=True, text=True).stdout.strip()


def fresh_repo(where):
    """A hosting site's new repository, cloned: README.md, LICENSE and a .gitignore, committed."""
    where.mkdir(parents=True)
    git(where, "init", "-q")
    (where / "README.md").write_text("# My study\n\nWhat it is about.\n", encoding="utf-8")
    (where / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (where / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    git(where, "add", "-A")
    git(where, "commit", "-q", "-m", "Initial commit")
    return where


def test_a_fresh_git_init_needs_no_adopt(scratch, quiet):
    target = scratch / "w"
    target.mkdir()
    git(target, "init", "-q")
    setup.setup(target, project="P", out=quiet[0])
    assert (target / "hep.toml").is_file() and (target / ".git").is_dir()
    assert git(target, "rev-parse", "--verify", "-q", "HEAD") == ""                 # .git untouched: no commit


def test_a_hosting_sites_repo_keeps_its_files_and_commits_only_what_was_added(scratch, quiet, git_identity):
    target = fresh_repo(scratch / "study")
    (target / "README.md").write_text("# My study\n\nWhat it is about, and more.\n", encoding="utf-8")
    git(target, "add", "README.md")                                                 # staged by the user
    added = setup.setup(target, project="P", git="yes", out=quiet[0])
    assert (target / "README.md").read_text(encoding="utf-8") == "# My study\n\nWhat it is about, and more.\n"
    assert (target / "LICENSE").read_text(encoding="utf-8") == "MIT\n"
    assert setup.GUIDE in added and "A Heimdall work dir" in (target / setup.GUIDE).read_text(encoding="utf-8")
    ignore = (target / ".gitignore").read_text(encoding="utf-8")
    assert ignore.startswith("*.pyc\n") and setup.BLOCK in ignore and "records/" in ignore and "logs/" in ignore
    assert git(target, "log", "--format=%s").splitlines()[0].startswith("hep setup: the work dir study")
    assert len(git(target, "log", "--format=%s").splitlines()) == 2
    committed = git(target, "show", "--name-only", "--format=", "HEAD").split()
    assert "hep.toml" in committed and ".gitignore" in committed and "README.md" not in committed
    assert "M  README.md" in git(target, "status", "--short")                     # still staged
    assert any(line.startswith("merged .gitignore:") for line in quiet[1])
    assert any(line.startswith("kept README.md") for line in quiet[1])


def test_inside_a_larger_repo_no_nested_git(scratch, quiet, git_identity):
    outer = fresh_repo(scratch / "big")
    setup.setup(outer / "analysis", git="yes", out=quiet[0])
    assert not (outer / "analysis" / ".git").exists()
    assert "analysis/hep.toml" in git(outer, "show", "--name-only", "--format=", "HEAD").split()
    state = record.git_state(outer / "analysis")
    assert state["subfolder"] == "analysis" and state["revision"] == git(outer, "rev-parse", "HEAD")
    setup.setup(outer / "own", git="new", out=quiet[0])
    assert (outer / "own" / ".git").is_dir()


def test_an_unborn_repository_is_recorded_as_one(scratch):
    target = scratch / "u"
    target.mkdir()
    git(target, "init", "-q")
    assert record.git_state(target) == {"revision": "", "dirty": False, "unborn": True}
    assert record.git_state(scratch / "nowhere-at-all") == {}


def test_next_steps_say_git_add_when_not_committed(scratch, quiet):
    target = fresh_repo(scratch / "r")
    added = setup.setup(target, project="P", out=quiet[0])
    lines = setup.next_steps(target, added, "P", None)
    assert "  hep check P/p" in lines and any(l.startswith("  git add -- ") for l in lines)


def test_datasets_are_fetched_from_the_manifest_and_checked(scratch, quiet):
    source = scratch / "remote.yoda"
    source.write_text("BEGIN YODA\n", encoding="utf-8")
    good = hashlib.sha256(source.read_bytes()).hexdigest()
    target = scratch / "w"
    setup.setup(target, out=quiet[0])
    (target / "datasets.toml").write_text(f'[files."zeus/2012.yoda"]\nurl = "{source.as_uri()}"\nsha256 = "{good}"\n',
                                          encoding="utf-8")
    setup.setup(target, out=quiet[0])                                             # hep setup . in a clone
    assert (target / "datasets" / "zeus" / "2012.yoda").read_text() == "BEGIN YODA\n"
    assert "/zeus/2012.yoda" in (target / "datasets" / ".gitignore").read_text()
    assert any(l.startswith("fetched datasets/zeus/2012.yoda") for l in quiet[1])
    (target / "datasets.toml").write_text(f'[files."b.yoda"]\nurl = "{source.as_uri()}"\nsha256 = "{"0" * 64}"\n',
                                          encoding="utf-8")
    with pytest.raises(HepError, match="arrived with another sha256"):
        setup.fetch_datasets(target)
    assert not (target / "datasets" / "b.yoda").exists()


def test_refresh_brings_the_framework_files_up_to_date_and_leaves_the_users(scratch, quiet):
    target = scratch / "w"
    setup.setup(target, out=quiet[0])
    (target / "Makefile").write_text("old\n", encoding="utf-8")
    (target / "configs" / "mine.txt").write_text("mine\n", encoding="utf-8")
    with pytest.raises(HepError, match="differ from today's template"):
        setup.refresh(target, out=quiet[0])
    assert setup.refresh(target, yes=True, out=quiet[0]) == 1
    assert "include" in (target / "Makefile").read_text(encoding="utf-8")
    assert (target / "configs" / "mine.txt").read_text(encoding="utf-8") == "mine\n"
    assert setup.refresh(target, yes=True, out=quiet[0]) == 0                      # today's: nothing to do


def test_a_deck_is_written_in_decks_and_built_in_reports(scratch, monkeypatch):
    monkeypatch.setenv("HEP_DECKS", str(scratch / "decks"))
    monkeypatch.setenv("HEP_REPORTS", str(scratch / "reports"))
    src = scratch / "decks" / "talk"
    src.mkdir(parents=True)
    (src / "eta_one.png").write_bytes(b"\x89PNG")
    made = deck.load("talk")
    assert made.src == src.resolve() and made.dir == (scratch / "reports" / "talk").resolve()
    old = scratch / "reports" / "old"                                              # written before decks/
    old.mkdir(parents=True)
    (old / "deck.toml").write_text("[deck]\n", encoding="utf-8")
    (old / "eta_one.png").write_bytes(b"\x89PNG")
    (old / "deck.pdf").write_bytes(b"%PDF")
    assert deck.load("old").src == deck.load("old").dir == old.resolve()
    work = scratch
    moves = dict(migrate.deck_moves(work))
    assert moves == {old / "deck.toml": work / "decks" / "old" / "deck.toml",
                     old / "eta_one.png": work / "decks" / "old" / "eta_one.png"}       # the build's stay
