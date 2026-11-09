"""P5 one-off (canonical-cards): a work dir's points library remade under today's identities. Dry run unless --yes.

    HEIMDALL=<checkout> HEIMDALL_WORK=<work dir> PYTHONPATH=<checkout>/framework python3 remake.py old.json new.json [--yes]

old.json and new.json are keys.py's output: run with the checkout before P4, and with today's. A library entry is proven
when a Run's link to it is a point whose old key (planned from the Run's snapshot) is the entry's .complete. A proven entry
is remade:
* its identity.json (format 2, today's parts) and .complete (today's key) written, each after a `.format1` copy;
* its folders, in records/ and results/, renamed to the new key's 16;
* every link to it relinked, and every Run that links it rekeyed: points.json (format 2) and the plot document
  (`plotdoc.rekey`, format 2), each after a `.format1` copy; the index, points.jsonl, likewise.
Entries one physics now (several old keys, one new): the one most linked is kept in the library (the earliest made on a
tie). Each other stays its Run's own, beside its first link as `<name>.adopted-duplicate` (records and results), and its
links go to the kept entry; `heimdall library prune --duplicates` keeps a duplicate drawn with another seed. Last, the entries
no Run links are removed (`library.prune`) (developer, 2026-11-10). An entry no Run proves is left as it is. Provenance and
seeds are untouched. Refused while a job of the work dir goes.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

from runner import house, library, plotdoc, record
from runner.paths import records_root, results_root, work_root

BACKUP = ".format1"
FORMAT = record.FORMAT


def read_keys(path: str) -> dict[tuple[str, str], dict]:
    return {(r["run"], r["point"]): r for r in map(json.loads, Path(path).read_text(encoding="utf-8").splitlines())
            if "key" in r}


def proven(old: dict, new: dict) -> tuple[dict[tuple[str, str], dict], list[str]]:
    """Each proven entry, (assignment, key16) → {old, new, parts}, and what is left with why."""
    found: dict[tuple[str, str], dict] = {}
    left: list[str] = []
    for (run, point), was in sorted(old.items()):
        now = new.get((run, point))
        link = records_root() / run / "points" / point
        if now is None or not link.is_symlink() or Path(os.readlink(link)).parent.name != library.FOLDER:
            continue
        assignment, name = run.split("/")[0], Path(os.readlink(link)).name
        entry = records_root() / assignment / library.FOLDER / name
        marker = (entry / ".complete").read_text(encoding="utf-8").strip() if (entry / ".complete").is_file() else ""
        if marker != was["key"] or not marker.startswith(name):
            continue
        if library.key_of_recorded(now["parts"]) != now["key"]:
            left.append(f"{assignment}/{name}: new.json's parts do not hash to its key ({run}:{point})")
            continue
        seen = found.setdefault((assignment, name), {"old": marker, "new": now["key"], "parts": now["parts"]})
        if seen["new"] != now["key"]:
            seen["conflict"] = True
    for where, item in list(found.items()):
        if item.pop("conflict", False):
            left.append(f"{where[0]}/{where[1]}: proven by Runs that plan it as different physics now: left")
            del found[where]
    return found, left


def chosen(found: dict, linked: dict[str, dict], made: dict[str, dict]) -> tuple[dict, dict, list[str]]:
    """Per new key: the entry kept and the ones set aside. (kept: (A, key16) → item, aside: (A, key16) → kept's (A, key16),
    what is left)."""
    groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for where, item in found.items():
        if item["old"] != item["new"]:
            groups.setdefault((where[0], item["new"]), []).append(where)
    kept, aside, left = {}, {}, []
    for (assignment, new), members in sorted(groups.items()):
        target = records_root() / assignment / library.FOLDER / new[:16]
        if target.exists() and (assignment, new[:16]) not in members:
            left.append(f"{assignment}/{new[:16]}: exists already, so {', '.join(m[1] for m in members)} left")
            continue

        def rank(where):
            runs = [at for at, _ in linked[assignment].get(where[1], []) if at.is_relative_to(records_root())]
            return (-len(runs), made[assignment].get(found[where]["old"], {}).get("created") or "~")
        first, *rest = sorted(members, key=rank)
        kept[first] = found[first]
        for other in rest:
            aside[other] = first
    return kept, aside, left


def backup(path: Path) -> None:
    copy = path.with_name(path.name + BACKUP)
    if path.is_file() and not copy.exists():
        shutil.copy2(path, copy)


def source_format(text: str) -> str:
    """The plot document's [source].format made today's."""
    out, inside = [], False
    for line in text.splitlines(keepends=True):
        if line.startswith("["):
            inside = line.strip() == "[source]"
        elif inside and re.match(r"^format\s*=\s*\d+\s*$", line):
            line, inside = f"format = {FORMAT}\n", False
        out.append(line)
    return "".join(out)


def remake(yes: bool, old: dict, new: dict) -> list[str]:
    found, left = proven(old, new)
    assignments = sorted({a for a, _ in found})
    linked = {a: library.links(a) for a in assignments}
    made = {a: library.entries(a) for a in assignments}
    kept, aside, more = chosen(found, linked, made)
    left += more
    verb = "" if yes else "would "
    out = [f"{len(found)} entries proven; {len(kept)} rekeyed, {len(aside)} set aside, "
           f"{sum(1 for i in found.values() if i['old'] == i['new'])} already today's"]
    keys: dict[str, str] = {}                            # every old full key → today's, set aside or kept
    runs: set[str] = set()
    for where, item in sorted(kept.items()):
        keys[item["old"]] = item["new"]
        out.append(f"{verb}rekey {where[0]}/{where[1]} → {item['new'][:16]} "
                   f"({len(linked[where[0]].get(where[1], []))} link(s))")
    for where, into in sorted(aside.items()):
        keys[found[where]["old"]] = found[into]["new"]
        at = [link for link, _ in linked[where[0]].get(where[1], []) if link.is_relative_to(records_root())][0]
        seeds = [made[where[0]].get(found[w]["old"], {}).get("seed") for w in (where, into)]
        out.append(f"{verb}set aside {where[0]}/{where[1]} (seed {seeds[0]}) as {at.relative_to(records_root())}"
                   f"{library.DUPLICATE}; its links to {found[into]['new'][:16]} (kept, seed {seeds[1]})")
    for where in list(kept) + list(aside):
        runs |= {run for _, run in linked[where[0]].get(where[1], [])}
    out.append(f"{verb}rekey {len(runs)} Run(s): points.json and plot document")
    out += [f"left {line}" for line in left]
    if not yes:
        return out + [line for a in assignments for line in library.prune(a) if not line.startswith("a dry run")] \
            + ["(prune as it stands now; the set-aside entries leave the library first) a dry run: --yes remakes"]
    if going := house.runs_here(work_root()):
        raise SystemExit(f"a job of this work dir is going (pid {going[0].get('pid')}): remake when it has ended")

    for (assignment, name), item in sorted(kept.items()):              # the entries
        records, results = (root / assignment / library.FOLDER for root in (records_root(), results_root()))
        entry = records / name
        for path in (entry / "identity.json", entry / ".complete"):
            backup(path)
        record.write_atomic(entry / "identity.json",
                            json.dumps({"format": FORMAT, **item["parts"]}, indent=1, sort_keys=True) + "\n")
        record.write_atomic(entry / ".complete", item["new"] + "\n")
        entry.rename(records / item["new"][:16])
        if (results / name).is_dir():
            (results / name).rename(results / item["new"][:16])
    for (assignment, name), into in sorted(aside.items()):             # the ones set aside, beside their first link
        at = [link for link, _ in linked[assignment][name] if link.is_relative_to(records_root())][0]
        run_point = at.relative_to(records_root())
        for root in (records_root(), results_root()):
            entry, beside = root / assignment / library.FOLDER / name, root / run_point
            if entry.is_dir():
                if beside.is_symlink():
                    beside.unlink()
                entry.rename(beside.with_name(beside.name + library.DUPLICATE))
    for (assignment, name) in list(kept) + list(aside):                # every link, to today's folder
        target = keys[found[(assignment, name)]["old"]][:16]
        for link, _ in linked[assignment].get(name, []):
            root = records_root() if link.is_relative_to(records_root()) else results_root()
            if link.is_symlink() or not link.exists():
                library.link_into(link, root / assignment / library.FOLDER / target)
    for assignment in assignments:                                     # the index
        index = library.index_file(assignment)
        backup(index)
        lines = []
        for raw in index.read_text(encoding="utf-8").splitlines():
            try:
                line = json.loads(raw)
            except ValueError:
                lines.append(raw)
                continue
            if line.get("key") in keys:
                was = line["key"]
                line["key"] = keys[was]
                if any(found[w]["old"] == was for w in aside) and line.get("kind") in ("created", "rerun"):
                    line = {"v": line.get("v", 1), "kind": "used", "key": line["key"], "at": line.get("at"), "run": line.get("run")}
            lines.append(json.dumps(line, sort_keys=True))
        record.write_atomic(index, "\n".join(lines) + "\n")
    for run in sorted(runs):                                           # each Run's points.json and plot document
        manifest = records_root() / run / "points.json"
        if manifest.is_file():
            backup(manifest)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            for entry in data.get("points", []):
                if entry.get("identity") in keys:
                    entry["identity"] = keys[entry["identity"]]
                    entry["library"] = entry["identity"][:16]
            data["format"] = FORMAT
            record.write_atomic(manifest, json.dumps(data, indent=1, default=str) + "\n")
        document = plotdoc.path_of(results_root() / run)
        if document.is_file():
            backup(document)
            plotdoc.rekey(results_root() / run, keys)
            record.write_atomic(document, source_format(document.read_text(encoding="utf-8")))
    for assignment in assignments:                                     # what no Run links now
        out += library.prune(assignment, yes=True)
    return out + ["remade"]


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--yes"]
    for line in remake("--yes" in sys.argv[1:], read_keys(args[0]), read_keys(args[1])):
        print(line)
