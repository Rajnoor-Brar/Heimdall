"""The docs as data (rank 1; doc:docs-system): pages and their frontmatter, the map, the drift report, the site.

A page of docs/ opens with flat frontmatter (`id`, `summary`, `for`, `code`; a live doc `affects`), so what readers
need to choose a page is read from the pages, never kept beside them. `docs.py` writes the generated pages from this.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import schema
from .paths import forge_dir, heimdall_root

READERS = ("driver", "mechanic", "dev", "client", "agent")
PAGE_CAP = 12_000                                   # bytes of an authored page
ROW_CAP = 300                                       # characters of a decision note
ORDER = ("rules", "reference", "stable/start", "stable/guide", "stable/tools", "stable/setup",
         "stable/internals", "stable/design", "live")


@dataclass
class Page:
    path: Path
    rel: str                                        # from docs/
    meta: dict[str, str]
    body: str

    @property
    def id(self) -> str:
        return self.meta["id"]

    def listed(self, key: str) -> list[str]:
        return [v for v in re.split(r"[,\s]+", self.meta.get(key, "")) if v]


def frontmatter(text: str) -> tuple[dict[str, str], str]:
    """`key: value` lines between `---` lines; a page without them has no metadata."""
    if not text.startswith("---\n") or "\n---\n" not in text:
        return {}, text
    head, body = text[4:].split("\n---\n", 1)
    return {k.strip(): v.strip() for k, _, v in (line.partition(":") for line in head.splitlines()) if k.strip()}, body


def docs_root() -> Path:
    return heimdall_root() / "docs"


def pages() -> list[Page]:
    """Every page that has frontmatter, in the map's order."""
    root, out = docs_root(), []
    for path in sorted(root.rglob("*.md")):
        meta, body = frontmatter(path.read_text(encoding="utf-8"))
        if meta:
            out.append(Page(path, str(path.relative_to(root)), meta, body))
    return sorted(out, key=lambda p: (_rank(p.rel), p.rel))


def _rank(rel: str) -> int:
    return next((i for i, prefix in enumerate(ORDER) if rel.startswith(prefix + "/")), len(ORDER))


# ── Text for readers who do not read the record ───────────────────────────────────────────────────

_ID = r"(?:[VLFU]\d{1,3}[a-z]?|I-\d{2,3}|00/B\d+)"
_SECTION = r"0[0-7] §\d+(?:\.\d+)*"
_ANY = rf"(?:{_ID}|{_SECTION})"
_IDS = rf"{_ANY}(?:[ \t]*(?:,|;|–|-|and)[ \t]*{_ANY})*"
_PLAIN = [(re.compile(rf"[ \t]*\((?:see[ \t]+)?{_IDS}\)"), ""),              # (V45, V46): gone
          (re.compile(rf"\((?:see[ \t]+)?{_IDS}[;,:][ \t]*"), "("),          # (V31; rivet, …): (rivet, …)
          (re.compile(rf"[;,:][ \t]*(?:see[ \t]+)?{_IDS}\)"), ")")]          # (rivet, V31)


def plain(text: str) -> str:
    """The record's ids and the old manual's section cites taken out of parentheses, code spans as they are."""
    out, at = [], 0
    for span in re.finditer(r"`[^`\n]*`", text):
        out.append(_plain(text[at:span.start()]))
        out.append(span.group(0))
        at = span.end()
    return "".join(out) + _plain(text[at:])


def _plain(chunk: str) -> str:
    for pattern, new in _PLAIN:
        chunk = pattern.sub(new, chunk)
    return chunk


def kind_of(entry: dict) -> str:
    """A key's type in a few words: `string`, `list of strings`, `integer or string`."""
    names = {"int": "integer", "float": "number", "str": "string", "bool": "true or false", "list": "list", "table": "table"}
    plural = {"int": "integers", "float": "numbers", "str": "strings", "bool": "booleans", "list": "lists", "table": "tables"}
    items = entry.get("items")
    def one(kind: str) -> str:
        if kind == "list" and items:
            return "list of " + " or ".join(plural[i] for i in items.split("|"))
        return names[kind]
    return " or ".join(one(k) for k in entry["type"].split("|"))


# ── The map ───────────────────────────────────────────────────────────────────────────────────────

def overlays(found: list[Page]) -> dict[str, list[str]]:
    """Which live docs change which page: page id → live doc ids."""
    out: dict[str, list[str]] = {}
    for page in found:
        if page.rel.startswith("live/"):
            for target in page.listed("affects"):
                out.setdefault(target, []).append(page.id)
    return out


def map_text(found: list[Page] | None = None) -> str:
    """docs/MAP.md: one line a page, so an agent chooses what to read at the cost of a line each."""
    found = pages() if found is None else found
    over = overlays(found)
    lines = ["# Map", "",
             "Generated: `heimdall make --framework docs`. One line a page: what it holds, who it is for, its size.",
             "`⟵ live:` a live doc changes that page, and wins until crystallised (see `work`).", ""]
    folder = None
    for page in found:
        here = str(Path(page.rel).parent)
        if here != folder:
            lines += ([""] if folder else []) + [f"## {here}", ""]
            folder = here
        size = f"{len(page.path.read_bytes()) / 1000:.0f} KB"
        live = f" ⟵ live: {', '.join(over[page.id])}" if page.id in over else ""
        lines.append(f"- [{page.id}]({page.rel}): {page.meta.get('summary', '')} ({' '.join(page.listed('for'))}; {size}){live}")
    return "\n".join(lines) + "\n"


# ── Drift ─────────────────────────────────────────────────────────────────────────────────────────

def crystal_commit() -> str:
    data = tomllib.loads((docs_root() / "stable" / "CRYSTAL.toml").read_text(encoding="utf-8"))
    return data["commit"]


def drift(found: list[Page] | None = None) -> list[tuple[str, list[str]]]:
    """Stable pages whose `code:` paths changed since the last crystallise, with no live doc naming the page."""
    found = pages() if found is None else found
    root = heimdall_root()
    done = subprocess.run(["git", "-C", str(root), "diff", "--name-only", crystal_commit()],
                          capture_output=True, text=True, encoding="utf-8", check=True)
    changed = done.stdout.split()
    over = overlays(found)
    out = []
    for page in found:
        if not page.rel.startswith("stable/") or page.id in over:
            continue
        hit = [f for f in changed for code in page.listed("code") if f == code or f.startswith(code.rstrip("/") + "/")]
        if hit:
            out.append((page.id, sorted(set(hit))))
    return out


# ── The site ──────────────────────────────────────────────────────────────────────────────────────

def settings() -> list[dict]:
    """Every setting a reader may look up: the schema's tables and the style's keys, as the site shows them."""
    out = []
    for table in schema.TABLES:
        rows = []
        for name, entry in schema.keys(table).items():
            rows.append({"key": name, "type": kind_of(entry),
                         "default": "required" if entry.get("required") else
                                    (schema.toml_value(entry["default"]) if "default" in entry else ""),
                         "accepts": [schema.toml_value(c) for c in entry.get("choices", [])],
                         "min": entry.get("min"),
                         "meaning": plain(entry.get("notes") or entry.get("doc", ""))})
        out.append({"table": table, "keys": rows})
    out.append({"table": "style", "keys": [{"key": k, "type": "", "default": v, "accepts": [], "min": None, "meaning": plain(c)}
                                           for k, v, c in schema.style_entries()]})
    return out


def graph(found: list[Page]) -> dict:
    """Nodes and edges: pages, the code they name, the pages they link, the decisions they hold."""
    by_path = {p.path.resolve(): p for p in found}
    nodes, edges = {}, []
    for page in found:
        nodes[page.id] = {"id": page.id, "kind": "page", "group": page.rel.split("/")[0 if not page.rel.startswith("stable/") else 1],
                          "summary": page.meta.get("summary", ""), "rel": page.rel}
    for page in found:
        for code in page.listed("code"):
            nodes.setdefault(code, {"id": code, "kind": "code", "group": "code", "summary": "", "rel": ""})
            edges.append([page.id, code])
        for link in re.findall(r"\]\(([^)#\s]+\.md)", page.body):
            target = by_path.get((page.path.parent / link).resolve())
            if target:
                edges.append([page.id, target.id])
        bare = re.sub(r"`[^`\n]*`", "", re.sub(r"^```.*?^```", "", page.body, flags=re.M | re.S))
        for ident in sorted(set(re.findall(r"^- \*\*((?:V|L|F|R)\d+)\*\*", bare, re.M))):
            nodes.setdefault(ident, {"id": ident, "kind": "decision", "group": "decision", "summary": "", "rel": page.rel})
            edges.append([page.id, ident])
    return {"nodes": list(nodes.values()), "edges": edges}


def site_html(found: list[Page] | None = None) -> str:
    found = pages() if found is None else found
    over = overlays(found)
    data = {"settings": settings(), "graph": graph(found), "readers": READERS,
            "pages": [{"id": p.id, "rel": p.rel, "summary": p.meta.get("summary", ""), "for": p.listed("for"),
                       "live": over.get(p.id, []), "body": p.body} for p in found]}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    template = (Path(__file__).parent / "knowledge_site.html").read_text(encoding="utf-8")
    return template.replace("/*DATA*/null", blob)


def build_site(out: Path | None = None) -> Path:
    target = out or forge_dir() / "docs" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(site_html(), encoding="utf-8")
    return target
