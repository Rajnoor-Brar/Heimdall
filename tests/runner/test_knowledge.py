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
    for key in ("id", "summary"):
        assert page.meta.get(key), f"{page.rel}: no {key}"
    assert "for" not in page.meta, f"{page.rel}: its folder says who it is for"
    assert set(page.readers) <= set(knowledge.READERS), page.rel
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


@pytest.mark.parametrize("page", [p for p in PAGES if {"driver", "mechanic"} & set(p.readers)], ids=lambda p: p.rel)
def test_a_human_users_page_cites_no_record(page):
    bare = re.sub(r"`[^`\n]*`", "", re.sub(r"^```.*?^```", "", page.body, flags=re.M | re.S))
    bare = re.sub(r"^- \*\*L\d+\*\*.*$", "", bare, flags=re.M)      # a tool's own knowledge notes: what code cites
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


def test_every_setting_is_on_its_page():
    """A key's heading, nested under its table: every schema key, style key, stack setting and tool option."""
    every = "".join(docs.settings_page(name) for name in docs.SETTINGS)
    for row in knowledge.settings():
        for key in row["keys"]:
            assert f"# `{key['key'].rsplit('.', 1)[-1]}`\n" in every, f"{row['table']}: {key['key']}"


def test_a_key_is_a_table_its_keywords_a_list_then_its_prose():
    page = docs.settings_page("plot")
    block = page.split("## `backend`\n", 1)[1].split("\n## ", 1)[0]
    table, keywords, prose = block.strip().split("\n\n", 2)
    assert table.startswith("| Type | Default | Acceptable |") and '`"root"`' in table
    assert keywords.startswith('- `"default"`:')
    assert prose.startswith("A figure") or "Paint" in prose


def test_a_key_nests_under_its_table():
    page = docs.settings_page("plot")
    assert "\n# `[plot]`\n" in page and "\n## `[plot.figures.<name>]`\n" in page and "\n### `class`\n" in page
    style = docs.settings_page("style")
    assert "\n# `page`\n" in style and "\n## `margins`\n" in style and "\n### `left`\n" in style


def test_an_anchor_in_a_key_index_resolves():
    for name in docs.SETTINGS:
        page = docs.settings_page(name)
        seen: dict[str, int] = {}
        anchors = set()
        for title in re.findall(r"^#+ (.*)$", page, re.M):
            slug = docs._slug(title)
            anchors.add(f"{slug}-{seen[slug]}" if seen.get(slug) else slug)
            seen[slug] = seen.get(slug, 0) + 1
        for target in re.findall(r"\]\(#([^)]+)\)", page):
            assert target in anchors, f"{name}: {target}"


def test_keys_lists_every_setting_and_stack_entries_read_the_file():
    text = docs.keys_page()
    for needle in ("plot.y_gutter |", "errand.events |", "style.page.font |", "stack.cores |", "stack.env.CXXFLAGS |", "tools.rivet: its own"):
        if needle.startswith("tools."):
            continue
        assert needle in text, needle
    stack = dict((k, c) for k, _, c in docs.schema.stack_entries())
    assert "ufo_models" in stack and "UFO" in stack["ufo_models"], "the comment above a key is its comment"
    assert "apt_packages" in stack and "libxml2-dev" not in stack


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


def test_explain_answers_every_setting():
    """What `heimdall explain` is asked by a reader who read the key off a settings page: each one answers."""
    from runner import house
    prefix = {"[file]": "file", "[errand]": "errand", "[cfgs.<name>]": "cfgs.x", "[quantities.<q>]": "quantities.x", "[tools.<name>]": "tools.x",
              "[plot]": "plot", "[plot.figures.<name>]": "plot.figures.x", "[plot.data]": "plot.data", "[plot.across_from]": "plot.across_from",
              "[stats]": "stats", "[report]": "report", "[[report.section]]": "report.section", "[cluster]": "cluster",
              "style": "style", "stack": "stack"}
    silent = []
    for row in knowledge.settings():
        at = prefix.get(row["table"]) or row["table"].split(":")[0].strip("[]").split(".")[-1]
        for key in row["keys"]:
            ask = f"{at}.{key['key']}"
            try:
                assert house.explain(ask)
            except Exception as error:
                silent.append(f"{ask}: {str(error)[:60]}")
    assert not silent, "explain has no answer:\n  " + "\n  ".join(silent)


def test_context_is_within_its_budget_and_owns_nothing():
    text = docs.context_page()
    assert len(text.encode("utf-8")) <= knowledge.CONTEXT_CAP
    primer = next(p for p in PAGES if p.id == "model").body
    assert "tools are processes, chained by a TOML" in primer and "tools are processes, chained by a TOML" in text
    assert re.search(r"^```toml\n# configs/Demo/mini.toml", text, re.M), "the guide's whole errand file"


def test_the_template_points_to_the_context():
    assert "heimdall context" in (REPO / "framework/templates/work/CLAUDE.md").read_text(encoding="utf-8")
