"""The docs held to docs/rules/writing.md (doc:docs-system): frontmatter, owners, caps, links, what is generated."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from runner import docs, knowledge

REPO = Path(__file__).resolve().parents[2]
PAGES = knowledge.pages()
AUTHORED = [p for p in PAGES if p.meta.get("generated") != "true"]
ROWS = re.compile(r"^- \*\*((?:V|L|F|R)\d+)\*\* (.*)$", re.M)


def test_the_pages_exist():
    assert {"invariants", "writing", "work", "code"} <= {p.id for p in PAGES}


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.rel)
def test_frontmatter(page):
    for key in ("id", "summary", "for"):
        assert page.meta.get(key), f"{page.rel}: no {key}"
    assert set(page.listed("for")) <= set(knowledge.READERS), page.rel
    assert len(page.meta["summary"]) <= 180, f"{page.rel}: a summary is one line"


def test_ids_are_unique():
    ids = [p.id for p in PAGES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("page", [p for p in PAGES if p.meta.get("code")], ids=lambda p: p.rel)
def test_the_code_a_page_names_exists(page):
    missing = [c for c in page.listed("code") if not (REPO / c).exists()]
    assert not missing, f"{page.rel}: {missing}"


@pytest.mark.parametrize("page", AUTHORED, ids=lambda p: p.rel)
def test_a_page_keeps_to_its_cap(page):
    assert len(page.path.read_bytes()) <= knowledge.PAGE_CAP, f"{page.rel} is more than one subject"


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.rel)
def test_links_resolve(page):
    bare = re.sub(r"`[^`\n]*`", "", re.sub(r"^```.*?^```", "", page.body, flags=re.M | re.S))
    bad = [m for m in re.findall(r"\]\(([^)#\s]+\.md)", bare) if not (page.path.parent / m).exists()]
    assert not bad, f"{page.rel}: {bad}"


@pytest.mark.parametrize("page", [p for p in AUTHORED if "decisions/" in p.rel], ids=lambda p: p.rel)
def test_a_decision_note_is_short(page):
    rows = ROWS.findall(page.body)
    assert rows, page.rel
    long = [i for i, text in rows if len(text) > knowledge.ROW_CAP]
    assert not long, f"{page.rel}: {long}"


@pytest.mark.parametrize("page", [p for p in PAGES if {"driver", "mechanic"} & set(p.listed("for"))], ids=lambda p: p.rel)
def test_a_human_users_page_cites_no_record(page):
    bare = re.sub(r"`[^`\n]*`", "", re.sub(r"^```.*?^```", "", page.body, flags=re.M | re.S))
    assert not re.search(r"\b(?:[VLFU]\d{1,3}[a-z]?|I-\d{2,3}|00/B\d+)\b", bare), page.rel
    assert not re.search(r"\b0[0-7] §\d", bare), page.rel


@pytest.mark.parametrize("page", [p for p in PAGES if p.rel.startswith("stable/guide/")], ids=lambda p: p.rel)
def test_a_guide_pages_toml_parses(page):
    for block in re.findall(r"^```toml\n(.*?)^```", page.body, re.S | re.M):
        tomllib.loads(block)


def test_a_live_doc_affects_pages_that_exist():
    ids = {p.id for p in PAGES}
    for page in [p for p in PAGES if p.rel.startswith("live/")]:
        assert page.listed("affects"), page.rel
        assert set(page.listed("affects")) <= ids, page.rel


def test_the_map_lists_every_page_and_its_overlay():
    text = knowledge.map_text()
    for page in PAGES:
        assert f"[{page.id}]({page.rel})" in text
    for target, live in knowledge.overlays(PAGES).items():
        assert re.search(rf"\[{target}\].*⟵ live: .*{live[0]}", text), target


def test_the_generated_pages_are_current():
    assert not docs.stale(), "run `heimdall make --framework docs`"


def test_every_key_of_a_settings_page_has_its_block():
    text = docs.settings_page("plot")
    for name in docs.schema.keys("plot"):
        assert f"### `{name}`" in text


def test_the_settings_pages_cite_no_old_section():
    for name in docs.SETTINGS:
        assert not re.search(r"\b0[0-7] §\d", docs.settings_page(name)), name


def test_the_site_is_self_contained(scratch):
    out = knowledge.build_site(scratch / "site" / "index.html")
    text = out.read_text(encoding="utf-8")
    assert "/*DATA*/" not in text and "</script>" in text
    assert not re.search(r"""(?:src|href)=["']https?://""", text), "the site loads nothing from outside"


def test_drift_names_a_page_whose_code_changed(monkeypatch):
    page = next(p for p in PAGES if p.id == "identity")
    monkeypatch.setattr(knowledge.subprocess, "run", lambda *a, **k: type("Done", (), {"stdout": "framework/runner/record.py\n"})())
    assert ("identity", ["framework/runner/record.py"]) in knowledge.drift([page])
    live = knowledge.Page(page.path, "live/x.md", {"id": "live-x", "affects": "identity"}, "")
    assert not knowledge.drift([page, live]), "a live doc naming the page answers it"
