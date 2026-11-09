"""P1 probe (canonical-cards): what the real base cards hold. Read-only on every path it is given.

Usage: python3 inventory.py <work dir>... > notes/inventory.md
Cards: each work dir's configs/, and the distinct copies (by sha256) its Run snapshots keep in
records/<A>/<E>/<R>/config/. Parsed with the folder's own grammar (tools.card_parser, tools._cleaned).
"""
import hashlib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Github/Heimdall/framework"))
from runner import tools  # noqa: E402
import yaml  # noqa: E402

FOLDERS = tools.folders()
EXT = {".cmnd": "pythia", ".tcl": "delphes", ".sin": "whizard", ".mg5": "madgraph"}


def folder_of(path: Path) -> str | None:
    name = path.name
    if name.endswith(".in"):
        return "herwig"
    if name.endswith((".yaml", ".yml")):
        return "sherpa"
    return EXT.get(path.suffix)


def cards(work: Path):
    seen = set()
    roots = [work / "configs"] if (work / "configs").is_dir() else [work]
    for root in roots:
        for p in sorted(root.rglob("*")):
            if p.is_file() and folder_of(p) and "/cards/" not in str(p):
                seen.add(hashlib.sha256(p.read_bytes()).hexdigest())
                yield p, "config"
    records = work / "records"
    copies = defaultdict(list)
    for p in sorted(records.glob("*/*/*/config/**/*")) if records.is_dir() else ():
        if p.is_file() and folder_of(p):
            copies[hashlib.sha256(p.read_bytes()).hexdigest()].append(p)
    for digest, paths in copies.items():
        if digest not in seen:
            yield paths[0], f"snapshot ×{len(paths)}"


class DupLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    keys = [loader.construct_object(k, deep=deep) for k, _ in node.value]
    for key, n in Counter(map(str, keys)).items():
        if n > 1:
            loader.duplicates.append((key, node.start_mark.line + 1))
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


DupLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def directives(text: str, comment: str) -> list[str]:
    return [f"{n}: {line.strip()}" for n, line in enumerate(text.splitlines(), 1)
            if re.match(r"^\s*" + re.escape(comment) + r"\s*heimdall\s*:", line)]


def probe(path: Path, tool: str) -> dict:
    folder = FOLDERS[tool]
    text = path.read_text(encoding="utf-8", errors="replace")
    out = {"lines": len(text.splitlines()), "directives": directives(text, folder.get("card", "comment", "#")),
           "dups": [], "order": [], "settings": 0}
    if tool == "sherpa":
        loader = DupLoader(text)
        loader.duplicates = []
        try:
            data = loader.get_single_data() or {}
        except yaml.YAMLError as e:
            out["order"].append(f"YAML error: {e}")
            return out
        out["dups"] = [f"`{k}` twice (mapping at line {l})" for k, l in loader.duplicates]
        out["settings"] = len(data) if isinstance(data, dict) else 0
        lists = [k for k, v in data.items() if isinstance(v, list)] if isinstance(data, dict) else []
        if lists:
            out["order"].append("lists (order is meaning): " + ", ".join(f"`{k}`" for k in lists))
        return out
    parse = tools.card_parser(folder)
    repeatable = {r.lower() for r in folder.get("card", "repeatable", [])}
    rows = [(n, line, parse(line)) for n, line in tools._cleaned(path, folder)]
    out["settings"] = sum(1 for *_, p in rows if p)
    by_key = defaultdict(list)
    for n, line, p in rows:
        if p:
            by_key[p[0]].append((n, p[1].strip(), p[2]))
    for key, hits in by_key.items():
        if len(hits) > 1 and key.rpartition(":")[2] not in repeatable:
            values = {v for _, v, _ in hits}
            out["dups"].append(f"`{hits[0][2]}` at lines {', '.join(str(n) for n, *_ in hits)}"
                               + (" (same value)" if len(values) == 1 else f" (values {', '.join(sorted(values))})"))
        cases = {k for *_, k in hits}
        if len(cases) > 1:
            out["order"].append(f"case variants of one key: {', '.join(sorted(cases))}")
    if tool == "pythia":
        tunes = [(n, p[2]) for n, _, p in rows if p and p[0].startswith("tune:")]
        for n, key in tunes:
            before = [p[2] for m, _, p in rows if p and m < n and not p[0].startswith("tune:")]
            out["order"].append(f"`{key}` at line {n}" + (f", after {len(before)} settings ({', '.join(before[:4])}{'…' if len(before) > 4 else ''})" if before else ", before every setting"))
        particles = defaultdict(list)
        for n, _, p in rows:
            if p and re.match(r"^-?\d+:", p[0]):
                particles[p[0].split(":")[0]].append(p[2].split(":", 1)[1])
        for pid, cmds in particles.items():
            if len(cmds) > 1:
                out["order"].append(f"particle {pid}: {len(cmds)} commands in order ({', '.join(cmds[:5])}{'…' if len(cmds) > 5 else ''})")
        unparsed = [f"{n}: {line.strip()}" for n, line, p in rows if not p]
        if unparsed:
            out["order"].append("lines the grammar does not read: " + "; ".join(unparsed[:5]))
    else:
        cds = [f"{n}: {line.strip()}" for n, line, _ in rows if re.match(r"^\s*cd\s", line)]
        if cds:
            out["order"].append("`cd`: " + "; ".join(cds))
        blocks = [line.strip() for _, line, _ in rows if re.match(r"^\s*module\s", line)]
        if blocks:
            out["order"].append(f"{len(blocks)} `module` blocks")
        other = Counter(line.split()[0] for _, line, p in rows if not p and line.split())
        if other:
            out["order"].append("commands: " + ", ".join(f"{k} ×{v}" for k, v in other.most_common(8)))
    return out


def main(works: list[str]) -> None:
    print("# Inventory of base cards (P1, canonical-cards)\n")
    print("Made by a scratch probe on 2026-11-09, read-only, with each folder's own grammar (`tools.card_parser`, "
          "`tools._cleaned`; Sherpa with a YAML loader that records duplicate keys). Per work dir: `configs/`, then "
          "each distinct copy a Run snapshot keeps (`records/<A>/<E>/<R>/config/`) that is not in `configs/`. "
          "A real study's work dir is named only as \"work dir 1\", \"work dir 2\".\n")
    for i, work in enumerate(map(Path, works)):
        label = "the test fixtures" if "Heimdall" in str(work) else f"work dir {i}"
        print(f"## {label}\n")
        totals = Counter()
        for path, where in cards(work):
            tool = folder_of(path)
            r = probe(path, tool)
            totals[tool] += 1
            name = path.relative_to(work)
            if label != "the test fixtures":
                name = f"card {totals[tool]}{''.join(path.suffixes[-1:])}"
            flags = r["dups"] or r["order"] or r["directives"]
            print(f"- **{name}** ({tool}, {where}, {r['lines']} lines, {r['settings']} settings)" + ("" if flags else ": nothing order-sensitive, no duplicates"))
            for d in r["dups"]:
                print(f"  - duplicate: {d}")
            for o in r["order"]:
                print(f"  - order: {o}")
            for d in r["directives"]:
                print(f"  - directive: {d}")
        print("\nCards per folder: " + ", ".join(f"{k} {v}" for k, v in sorted(totals.items())) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:])
