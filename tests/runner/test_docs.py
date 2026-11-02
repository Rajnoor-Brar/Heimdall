"""The docs held to the code and to docs/rules/writing.md (doc:docs-system): frontmatter, owners, caps, links, examples,
every setting and tool on its page, what is generated, and everything code cites."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from runner import RANKS, config, docs, house, knowledge, plot, schema, tools, v3
from runner.paths import configs_root

REPO = Path(__file__).resolve().parents[2]
PAGES = knowledge.pages()
BY_ID = {p.id: p for p in PAGES}
AUTHORED = [p for p in PAGES if p.meta.get("generated") != "true"]
ROWS = re.compile(r"^- \*\*((?:V|L|F|R)\d+)\*\* (.*)$", re.M)
FRONT_DOORS = [REPO / "AGENTS.md", REPO / "CLAUDE.md", REPO / "README.md", knowledge.docs_root() / "README.md",
               REPO / ".plans" / "ISSUES.md", REPO / "recipes" / "README.md", REPO / "recipes" / "platforms" / "mac" / "README.md"]


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def prose(body: str) -> str:
    """A page without its code: fenced blocks and inline spans hold examples, not links."""
    return re.sub(r"`[^`\n]*`", "", re.sub(r"^```.*?^```", "", body, flags=re.M | re.S))


def anchors(body: str) -> set[str]:
    """GitHub's anchors of a page's headings: a repeated one gets -1, -2 …"""
    seen: dict[str, int] = {}
    out = set()
    for title in re.findall(r"^#{1,6} (.+)$", re.sub(r"^```.*?^```", "", body, flags=re.M | re.S), re.M):
        slug = docs._slug(title)
        out.add(f"{slug}-{seen[slug]}" if seen.get(slug) else slug)
        seen[slug] = seen.get(slug, 0) + 1
    return out


# ── pages ───────────────────────────────────────────────────────────────────────────────────────

def test_the_pages_exist():
    assert {"invariants", "writing", "work", "code", "model", "identity", "commands", "context"} <= set(BY_ID)


def test_nothing_of_the_old_manual_is_left():
    root = knowledge.docs_root()
    assert not list(root.glob("0[0-7]_*.md")) and not (root / "audit_4").exists() and not (root / "framework").exists()
    extra = [str(p.relative_to(root)) for p in root.rglob("*.md")
             if str(p.relative_to(root)) not in ("README.md", "MAP.md", "live/README.md") and not knowledge.frontmatter(text(p))[0]]
    assert not extra, f"pages without frontmatter: {extra}"


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


@pytest.mark.parametrize("path", [p.path for p in PAGES] + FRONT_DOORS, ids=lambda p: str(p.relative_to(REPO)))
def test_every_relative_link_resolves(path):
    for target in re.findall(r"\]\(([^)\s]+)\)", prose(text(path))):
        if re.match(r"[a-z]+://", target) or target.startswith("mailto:"):
            continue
        name, _, anchor = target.partition("#")
        file = (path.parent / name).resolve() if name else path
        assert file.exists(), f"{path.name}: {target}"
        if anchor and file.suffix == ".md":
            assert anchor in anchors(text(file)), f"{path.name}: #{anchor} is not a heading of {file.name}"


@pytest.mark.parametrize("page", [p for p in AUTHORED if "decisions/" in p.rel], ids=lambda p: p.rel)
def test_a_decision_note_is_short(page):
    rows = ROWS.findall(page.body)
    assert rows, page.rel
    long = [i for i, body in rows if len(body) > knowledge.ROW_CAP]
    assert not long, f"{page.rel}: {long}"


@pytest.mark.parametrize("page", [p for p in PAGES if {"driver", "mechanic"} & set(p.readers)], ids=lambda p: p.rel)
def test_a_human_users_page_cites_no_record(page):
    bare = re.sub(r"^- \*\*L\d+\*\*.*$", "", prose(page.body), flags=re.M)      # a tool's own knowledge notes: what code cites
    assert not re.search(r"\b(?:[VLFU]\d{1,3}[a-z]?|I-\d{2,3}|00/B\d+)\b", bare), page.rel
    assert not re.search(r"\b0[0-7] §\d", bare), page.rel


@pytest.mark.parametrize("page", AUTHORED, ids=lambda p: p.rel)
def test_every_toml_block_parses_and_a_whole_errand_loads(page, scratch):
    for block in re.findall(r"^```toml\n(.*?)^```", page.body, re.S | re.M):
        data = tomllib.loads(block)
        errand = data.get("errand", {})
        if v3.is_v3(data) and {"name", "assignment"} <= set(errand) and data.get("cfgs"):
            path = configs_root() / "Demo" / "_example.toml"   # beside the fixture's files it imports and the cards it names
            path.write_text(block, encoding="utf-8")
            try:
                config.load(str(path))
            finally:
                path.unlink()


def test_a_live_doc_affects_pages_that_exist():
    for page in [p for p in PAGES if p.rel.startswith("live/")]:
        assert page.listed("affects"), page.rel
        assert set(page.listed("affects")) <= set(BY_ID), page.rel


def test_the_rank_table_is_the_runners():
    rows = {m: int(r) for r, m in re.findall(r"^\| (\d) \| `(\w+)\.py` \|", BY_ID["runner"].body, re.M)}
    assert rows == RANKS


def test_every_tool_folder_has_its_page():
    missing = [name for name in tools.folders() if f"tools-{name}" not in BY_ID]
    assert not missing, f"no page in stable/tools/: {missing}"


# ── what is generated ───────────────────────────────────────────────────────────────────────────

def test_the_generated_pages_are_current():
    assert not docs.stale(), f"run `heimdall make --framework docs`: {docs.stale()}"


def test_the_editor_schema_is_current():
    written = json.loads(text(schema.path().with_name("run.schema.json")))
    assert written == json.loads(json.dumps(schema.json_schema())), "run `make schema`"


def test_the_map_lists_every_page_and_its_overlay():
    body = knowledge.map_text()
    for page in PAGES:
        assert f"[{page.id}]({page.rel})" in body
    for target, live in knowledge.overlays(PAGES).items():
        assert re.search(rf"\[{target}\].*⟵ live: .*{live[0]}", body), target


def test_every_setting_is_on_its_page():
    """A key's heading, nested under its table: every schema key, style key, stack setting and tool option."""
    every = "".join(docs.settings_page(name) for name in docs.SETTINGS)
    for row in knowledge.settings():
        for key in row["keys"]:
            assert f"# `{key['key'].rsplit('.', 1)[-1]}`\n" in every, f"{row['table']}: {key['key']}"
    assert plot.base_style(), "base.toml is read"


def test_a_key_is_a_table_its_keywords_a_list_then_its_prose():
    block = docs.settings_page("plot").split("## `backend`\n", 1)[1].split("\n## ", 1)[0]
    table, keywords, words = block.strip().split("\n\n", 2)
    assert table.startswith("| Type | Default | Acceptable |") and '`"root"`' in table
    assert keywords.startswith('- `"default"`:')
    assert "Paint" in words


def test_a_key_nests_under_its_table():
    page = docs.settings_page("plot")
    assert "\n# `[plot]`\n" in page and "\n## `[plot.figures.<name>]`\n" in page and "\n### `class`\n" in page
    style = docs.settings_page("style")
    assert "\n# `page`\n" in style and "\n## `margins`\n" in style and "\n### `left`\n" in style


def test_keys_lists_every_setting_and_stack_entries_read_the_file():
    body = docs.keys_page()
    for needle in ("plot.y_gutter |", "errand.events |", "style.page.font |", "stack.cores |", "stack.env.CXXFLAGS |"):
        assert needle in body, needle
    stack = {k: c for k, _, c in schema.stack_entries()}
    assert "UFO" in stack["ufo_models"], "the comment above a key is its comment"
    assert "apt_packages" in stack and "libxml2-dev" not in stack


def test_explain_answers_every_setting():
    """What a reader who read a key off a settings page asks: each one answers."""
    prefix = {"[file]": "file", "[errand]": "errand", "[cfgs.<name>]": "cfgs.x", "[quantities.<q>]": "quantities.x", "[tools.<name>]": "tools.x",
              "[plot]": "plot", "[plot.figures.<name>]": "plot.figures.x", "[plot.data]": "plot.data", "[plot.across_from]": "plot.across_from",
              "[stats]": "stats", "[report]": "report", "[[report.section]]": "report.section", "[cluster]": "cluster",
              "style": "style", "stack": "stack"}
    silent = []
    for row in knowledge.settings():
        at = prefix.get(row["table"]) or row["table"].split(":")[0].strip("[]").split(".")[-1]
        for key in row["keys"]:
            try:
                assert house.explain(f"{at}.{key['key']}")
            except Exception as error:
                silent.append(f"{at}.{key['key']}: {str(error)[:60]}")
    assert not silent, "explain has no answer:\n  " + "\n  ".join(silent)


def test_context_is_within_its_budget_and_owns_nothing():
    body = docs.context_page()
    assert len(body.encode("utf-8")) <= knowledge.CONTEXT_CAP
    assert "tools are processes, chained by a TOML" in BY_ID["model"].body and "tools are processes, chained by a TOML" in body
    assert re.search(r"^```toml\n# configs/Demo/mini.toml", body, re.M), "the guide's whole errand file"


def test_the_template_points_to_the_context():
    assert "heimdall context" in text(REPO / "framework/templates/work/CLAUDE.md")


def test_the_site_is_self_contained(scratch):
    body = text(knowledge.build_site(scratch / "site" / "index.html"))
    assert "/*DATA*/" not in body and "</script>" in body
    assert not re.search(r"""(?:src|href)=["']https?://""", body), "the site loads nothing from outside"


def test_drift_names_a_page_whose_code_changed(monkeypatch):
    page = BY_ID["identity"]
    monkeypatch.setattr(knowledge.subprocess, "run", lambda *a, **k: type("Done", (), {"stdout": "framework/runner/record.py\n"})())
    assert ("identity", ["framework/runner/record.py"]) in knowledge.drift([page])
    live = knowledge.Page(page.path, "live/x.md", {"id": "live-x", "affects": "identity"}, "")
    assert not knowledge.drift([page, live]), "a live doc naming the page answers it"


# ── the agents' instructions ────────────────────────────────────────────────────────────────────

def test_agents_md_is_behaviour_only():
    """No features, no state: it may name only docs/ and .plans/, and stays short, so it cannot go stale."""
    body = text(REPO / "AGENTS.md")
    assert len(body.encode("utf-8")) <= 4000
    paths = re.findall(r"(?<![\w.])(?:[\w.-]+/)+[\w.-]*", body)
    assert all(p.startswith(("docs/", ".plans/")) for p in paths), paths
    assert not re.search(r"\b(?:Pythia|Rivet|Himinbjorg|gjallarhorn|heimdall [a-z]+|V\d+)\b", body)


def test_claude_md_only_imports():
    assert text(REPO / "CLAUDE.md").split() == ["@AGENTS.md", "@docs/rules/invariants.md"]


# ── what the code cites ─────────────────────────────────────────────────────────────────────────

CODE = [p for top in ("framework", "src", "tests", "recipes", "env", ".github") for p in (REPO / top).rglob("*")
        if p.is_file() and p.suffix in (".py", ".hh", ".cc", ".toml", ".sh", ".mk", ".yml", ".def", ".txt")
        and "tests/reference" not in str(p) and "tests/fixtures" not in str(p) and p.name != "test_docs.py"]   # frozen, with I-91
CODE += [REPO / "Makefile", REPO / "gjallarhorn.sh", REPO / "launch.sh", REPO / "framework" / "bin" / "heimdall", REPO / "framework" / "bin" / "run"]


def code_text() -> list[tuple[Path, str]]:
    out = []
    for path in CODE:
        try:
            out.append((path, text(path)))
        except (UnicodeDecodeError, OSError):
            continue
    return out


def test_every_doc_the_code_cites_exists():
    bad = [f"{path.relative_to(REPO)}: doc:{m}" for path, body in code_text() for m in re.findall(r"\bdoc:([a-z][\w-]*)", body)
           if m not in BY_ID and m != "id"]
    assert not bad, "\n  ".join(bad)


def test_no_code_cites_a_page_by_its_old_place():
    old = re.compile(r"docs/(?:0\d_|audit_|conda/|framework/|reporter/|07_)|\.plans/|\b0[0-7] §\d|\bI-\d{2,3}\b|00/B\d+")
    bad = [f"{path.relative_to(REPO)}: {old.search(body).group(0)}" for path, body in code_text() if old.search(body)]
    assert not bad, "\n  ".join(bad)


def test_every_page_path_a_string_names_exists():
    bad = [f"{path.relative_to(REPO)}: {m}" for path, body in code_text()
           for m in re.findall(r"docs/[\w/.-]+\.md", body) if not (REPO / m).exists()]
    assert not bad, "\n  ".join(bad)


def test_every_cited_note_exists():
    """A label in code leads to its note: grep finds it in one hop."""
    known = set()
    for page in PAGES:
        known |= set(re.findall(r"\*\*((?:V|L|F|R|C)\d+)\*\*", page.body))
    cited = re.compile(r"(?<![\w/-])((?:V|L|C)\d{1,3})(?![\w.])")
    bad = []
    for path, body in code_text():
        if path.suffix not in (".py", ".hh", ".cc", ".sh", ".mk", ".toml", ".def"):
            continue
        for m in cited.finditer(body):
            line = body[body.rfind("\n", 0, m.start()) + 1: body.find("\n", m.end())]
            if m.group(1) not in known and re.search(r"(#|//|\"\"\"|'''|^\s*\S*\s*\"|hint|where)", line):
                bad.append(f"{path.relative_to(REPO)}: {m.group(1)}: {line.strip()[:90]}")
    assert not bad, "notes that do not exist:\n  " + "\n  ".join(bad)
