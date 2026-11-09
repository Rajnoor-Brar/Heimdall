"""The points library (rank 3, points-library): generation points pooled per Assignment under a key that ignores the
point's name, so two Errands that ask for the same physics run it once.

* **The key** (`parts`, `key`, `key_of_recorded`): the point's identity. Its cards are final configs, which name no
  point (doc:identity), so one physics under two names or two Errands is one identity.
* **The entry** (`plan.folders.library_entry(key)`, `library_product(key)`): records/<A>/library/<key16>/ and
  results/<A>/library/<key16>/. A Run links them as its `points/<name>` (`link`, `link_into`, `unlink_run`).
* **The index** (`note`, `append`, `entries`, `links`, `first`): records/<A>/library/points.jsonl, appended under an flock
  and folded by `entries`.
* **`heimdall library`** (`assignments`, `list_lines`, `verify`, `prune`, `adopt`): reading and reorganising entries. Waiting
  while a job of the work dir runs is the command's (`cli.cmd_library`); this module never imports `house` or `cli`.

It imports `record` (the marker, lock and seed logic every point passes through), and `record` never imports it.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
from pathlib import Path

from .errors import HeimdallError
from .paths import disk_size, human_size, records_root, results_root
from .record import identity_parts, now, write_atomic
from .sweep import tag_of
from .tools import PointPlan


def parts(plan: PointPlan) -> dict:
    """What the points library keys a point by: its identity's parts, which name no point."""
    return identity_parts(plan)


def _hash(parts: dict) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def key(plan: PointPlan) -> str:
    """The points library's key for a point: the sha256 of `parts` (64 hex digits; an entry's folder is its first 16),
    which is its identity (`record.identity`)."""
    return _hash(parts(plan))


def key_of_recorded(parts: dict) -> str:
    """The library key of a point from its recorded `identity.json` (its parts, `format` aside): what `heimdall library adopt`
    files a complete point under. Equal to `key(plan)` of the plan that made it."""
    return _hash(json.loads(json.dumps({k: v for k, v in parts.items() if k != "format"}, default=str)))


# ── the entries, their links and the index ───────────────────────────────────────────────────────────

FOLDER = "library"
INDEX = "points.jsonl"


def link(plan: PointPlan) -> bool:
    """A library point in its Run: records/<A>/<E>/<R>/points/<name> and results/<A>/<E>/<R>/points/<name> become relative
    links (`../../../library/<key16>`, within the Assignment) to the entry's folders, made if need be. So the paths every
    reader uses are the same, and what a run writes there goes into the entry. True when a link was made or changed.
    A link to another entry (the name now means other physics) is replaced; a folder of the Run's own is refused when it
    holds anything (heimdall library adopt moves such a point in), and an empty one is replaced."""
    if not plan.library:
        raise ValueError("the plan is not a library point")
    changed = False
    folders = plan.folders
    for at, entry in ((folders.points / plan.point.name, folders.library_entry(plan.library)),
                      (plan.res, folders.library_product(plan.library))):
        entry.mkdir(parents=True, exist_ok=True)
        changed |= link_into(at, entry)
    return changed


def linked(plan: PointPlan) -> bool:
    """Whether the point's folder in its Run is a link into the library: a Run `heimdall library adopt` moved in, whose config
    may not pool. Its plan is a library point all the same, so it reads complete through the link (the entry's .complete
    holds the key, not the identity), and a run of it writes its own entry under the entry's lock, never through a link
    another Run shares."""
    at = plan.folders.points / plan.point.name
    return at.is_symlink() and Path(os.readlink(at)).parent.name == FOLDER


def link_into(link: Path, entry: Path) -> bool:
    """`link` made a relative link to the folder `entry` (within the Assignment): True when made or changed. A link to another
    folder is replaced, an empty folder of the Run's own is replaced, and one with anything in it is refused."""
    link.parent.mkdir(parents=True, exist_ok=True)
    target = os.path.relpath(entry, link.parent)
    if link.is_symlink():
        if os.readlink(link) == target:
            return False
        link.unlink()
    elif link.exists():
        if link.is_dir() and not any(link.iterdir()):
            link.rmdir()
        else:
            raise HeimdallError(f"{link} is a folder of this Run's own, and the point is to be pooled",
                                hint="heimdall library adopt moves a Run's complete points into the library")
    try:
        link.symlink_to(target)
    except FileExistsError:                    # another session of this Run linked it meanwhile
        if os.readlink(link) != target:
            raise
        return False
    return True


def unlink_run(plans: list[PointPlan]) -> None:
    """A `library = "only"` run's end: its links into the library are removed, and the points/ folders of its records and
    results with them once they are empty. The entries are never touched; the Run's logs and run.jsonl stay."""
    for plan in plans:
        if not plan.library:
            continue
        for at in (plan.folders.points / plan.point.name, plan.res):
            if at.is_symlink():
                at.unlink()
    for folder in {plan.folders.points for plan in plans if plan.library} | {plan.res.parent for plan in plans if plan.library}:
        try:
            folder.rmdir()
        except OSError:
            pass


def first(plan: PointPlan) -> str:
    """The Run that first made a library point, <A>/<E>/<R>; "" when the index does not say."""
    return (entries(plan.folders.assignment).get(plan.library) or {}).get("first_run") or ""


def index_file(assignment: str) -> Path:
    return records_root() / assignment / FOLDER / INDEX


def note(plan: PointPlan, errand, kind: str) -> None:
    """One line appended to the Assignment's library index, under an flock: `created` (key, every quantity's tag at the point,
    events, threads, seed, the Run that made it), `used` (a Run that links it) or `rerun` (an entry made again). A reader
    folds the lines (`entries`)."""
    path = index_file(plan.folders.assignment)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {"v": 1, "kind": kind, "key": plan.library, "at": now(),
            "run": str(plan.folders.record.relative_to(records_root()))}
    if kind in ("created", "rerun"):
        line.update({"coordinates": {n: tag_of(errand.quantities[n], i) for n, i in plan.values.items() if n in errand.quantities},
                     "events": plan.events, "threads": plan.threads, "seed": plan.seed})
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, (json.dumps(line, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        os.close(fd)                                   # the lock goes with the descriptor


def append(assignment: str, line: dict) -> None:
    """A line appended to an Assignment's library index as it is (`created` of an adopted point, `pruned`), under the flock."""
    path = index_file(assignment)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, (json.dumps({"v": 1, "at": now(), **line}, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def links(assignment: str) -> dict[str, list[tuple[Path, str]]]:
    """Every link into an Assignment's library, from its Runs' `points/` folders in records/ and results/: entry folder name
    (key16) → [(the link, its Run <A>/<E>/<R>)]. A link that dangles is in it all the same (`verify` says so)."""
    found: dict[str, list[tuple[Path, str]]] = {}
    for root in (records_root(), results_root()):
        base = root / assignment
        for errand in sorted(base.iterdir()) if base.is_dir() else ():
            if errand.name == FOLDER or not errand.is_dir():
                continue
            for run in sorted(errand.iterdir()):
                folder = run / "points"
                for link in sorted(folder.iterdir()) if folder.is_dir() else ():
                    if link.is_symlink() and Path(os.readlink(link)).parent.name == FOLDER:
                        found.setdefault(Path(os.readlink(link)).name, []).append((link, f"{assignment}/{errand.name}/{run.name}"))
    return found


def entries(assignment: str) -> dict[str, dict]:
    """The library's index folded: key → {key, coordinates, events, threads, seed, created, first_run, runs (in the order
    they came), reruns}. A line that is not JSON (a write cut short) is passed over."""
    try:
        text = index_file(assignment).read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict[str, dict] = {}
    for raw in text.splitlines():
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        key = line.get("key") if isinstance(line, dict) else None
        if not key:
            continue
        if line.get("kind") == "pruned":
            out.pop(key, None)
            continue
        entry = out.setdefault(key, {"key": key, "runs": [], "reruns": 0})
        if line.get("kind") in ("created", "rerun"):
            for field in ("coordinates", "events", "threads", "seed"):
                if field in line:
                    entry[field] = line[field]
        if line.get("kind") == "created":
            entry["created"], entry["first_run"] = line.get("at"), line.get("run")
        if line.get("kind") == "rerun":
            entry["reruns"] += 1
        if line.get("run") and line["run"] not in entry["runs"]:
            entry["runs"].append(line["run"])
    return out


# ── what `heimdall library` does ─────────────────────────────────────────────────────────────────────

def assignments(scope: str = "") -> list[str]:
    """The Assignments that have a points library (records/<A>/library/), or `scope`'s alone."""
    if scope:
        return [scope] if (records_root() / scope / "library").is_dir() else []
    return sorted(p.parent.name for p in records_root().glob("*/library") if p.is_dir()) if records_root().is_dir() else []


def _entry_folders(assignment: str) -> list[Path]:
    base = records_root() / assignment / "library"
    return sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []


def _complete_key(entry: Path) -> str | None:
    marker = entry / ".complete"
    return marker.read_text(encoding="utf-8").strip() if marker.is_file() else None


def list_lines(scope: str = "") -> list[str]:
    """`heimdall library list [A]`: each Assignment's entries, with the quantities' tags at the point, events and seed, whether
    the entry is complete, the Run that first made it and the Runs that link it now."""
    out: list[str] = []
    for assignment in assignments(scope):
        folded, linked = entries(assignment), links(assignment)
        folders = _entry_folders(assignment)
        out.append(f"{assignment}: {len(folders)} library point(s)")
        for entry in folders:
            key = _complete_key(entry)
            info = next((v for k, v in folded.items() if k.startswith(entry.name)), {})
            coords = " ".join(f"{k}={v}" for k, v in (info.get("coordinates") or {}).items())
            runs = sorted({run for _, run in linked.get(entry.name, [])})
            out.append(f"  {entry.name}  {coords or '–'}  {info.get('events', '–')} events  seed {info.get('seed', '–')}  "
                       f"{'complete' if key else 'incomplete'}")
            out.append(f"      made by {info.get('first_run') or '–'}; linked by {len(runs)} Run(s)" + (f": {', '.join(runs[:6])}" + (" …" if len(runs) > 6 else "") if runs else ""))
    return out or ["no points library" + (f" under {scope}" if scope else "")]


def verify(scope: str = "") -> tuple[list[str], int]:
    """`heimdall library verify [A]`: each entry complete for its key (its .complete begins with the folder's name and is the
    key its identity.json gives), its products there, each link resolving, and the index and the folders agreeing. Reports
    and fixes nothing. (the lines, the number of problems)"""
    problems: list[str] = []
    checked = 0
    for assignment in assignments(scope):
        folded, linked = entries(assignment), links(assignment)
        names = set()
        for entry in _entry_folders(assignment):
            names.add(entry.name)
            checked += 1
            key = _complete_key(entry)
            if key is None:
                problems.append(f"{assignment}/library/{entry.name}: not complete (no .complete)")
            elif not key.startswith(entry.name):
                problems.append(f"{assignment}/library/{entry.name}: its .complete holds {key[:16]}, not this entry's key")
            else:
                try:
                    parts = json.loads((entry / "identity.json").read_text(encoding="utf-8"))
                    if key_of_recorded(parts) != key:
                        problems.append(f"{assignment}/library/{entry.name}: its identity.json gives another key than its .complete")
                except (OSError, ValueError):
                    problems.append(f"{assignment}/library/{entry.name}: identity.json is missing or unreadable")
                if not (results_root() / assignment / "library" / entry.name).is_dir():
                    problems.append(f"{assignment}/library/{entry.name}: complete, but its products folder is missing")
            if not any(k.startswith(entry.name) for k in folded):
                problems.append(f"{assignment}/library/{entry.name}: not in the index")
        for key in folded:
            if key[:16] not in names:
                problems.append(f"{assignment}/library/points.jsonl: names {key[:16]}, whose folder is gone")
        for found in linked.values():
            for at, _ in found:
                if not at.exists():
                    problems.append(f"{at}: dangles ({os.readlink(at)})")
    if not assignments(scope):
        return ["no points library" + (f" under {scope}" if scope else "")], 0
    return problems + [f"{len(problems)} problem(s) in {checked} entr{'y' if checked == 1 else 'ies'}" if problems
                       else f"{checked} entr{'y' if checked == 1 else 'ies'} checked: complete for their keys, every link resolves"], len(problems)


def _independent(duplicate: Path) -> str | None:
    """Why an adopted duplicate (records/…/points/<name>.adopted-duplicate) is no copy of the entry its name links: its seed
    differs from the entry's (a random or manual seed the key leaves out), so it holds other events; None when the seeds
    are the same (identity seeds: the same events), and when either cannot be read it is kept too."""
    link = duplicate.with_name(duplicate.name.removesuffix(DUPLICATE))
    try:
        mine = json.loads((duplicate / "provenance.json").read_text(encoding="utf-8")).get("seed")
        theirs = json.loads((link / "provenance.json").read_text(encoding="utf-8")).get("seed")
    except (OSError, ValueError):
        return "its seed or its entry's cannot be read"
    return None if mine == theirs else f"seed {mine}, its entry's {theirs}"


def prune(scope: str = "", yes: bool = False, duplicates: bool = False) -> list[str]:
    """`heimdall library prune [A] [--duplicates] [--yes]`: the entries no Run links (and not one a session holds), listed;
    with `yes` removed, records and products, and the index told. `duplicates`: also the `<name>.adopted-duplicate` folders
    `adopt` left, but for one drawn with another seed than its entry (`_independent`): other events, which are kept. Without
    `yes` nothing is touched."""
    out: list[str] = []
    for assignment in assignments(scope):
        linked, folded = links(assignment), entries(assignment)
        for entry in _entry_folders(assignment):
            if linked.get(entry.name):
                continue
            lock = entry / ".lock"
            held = False
            if lock.is_file():
                fd = os.open(lock, os.O_RDONLY)
                try:
                    fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    held = True
                finally:
                    os.close(fd)
            if held:
                out.append(f"{assignment}/library/{entry.name}: unlinked, but a session holds it: kept")
                continue
            size = disk_size(entry) + disk_size(results_root() / assignment / FOLDER / entry.name)
            out.append(f"{'removed' if yes else 'would remove'} {assignment}/library/{entry.name}  ({human_size(size)}; no Run links it)")
            if yes:
                shutil.rmtree(entry)
                shutil.rmtree(results_root() / assignment / FOLDER / entry.name, ignore_errors=True)
                full = next((k for k in folded if k.startswith(entry.name)), entry.name)
                append(assignment, {"kind": "pruned", "key": full})
        if duplicates:
            kept = {}                                      # a duplicate drawn with another seed: its records' path → why
            for folder in sorted((records_root() / assignment).glob(f"*/*/points/*{DUPLICATE}")) if (records_root() / assignment).is_dir() else ():
                if (why := _independent(folder)) is not None:
                    kept[folder.relative_to(records_root())] = why
            for root in (records_root(), results_root()):
                for folder in sorted((root / assignment).glob(f"*/*/points/*{DUPLICATE}")) if (root / assignment).is_dir() else ():
                    if (why := kept.get(folder.relative_to(root))) is not None:
                        out.append(f"kept {folder}  ({why}: other events than its entry's, not a copy)")
                        continue
                    out.append(f"{'removed' if yes else 'would remove'} {folder}  ({human_size(disk_size(folder))}; a copy `adopt` kept)")
                    if yes:
                        shutil.rmtree(folder)
    if not out:
        out = ["nothing to prune: every library point is linked" + ("" if not duplicates else ", and no adopted duplicate is left")]
    elif not yes:
        out.append("a dry run: --yes removes them")
    return out


# ── adopt ─────────────────────────────────────────────────────────────────────────────────────────────

DUPLICATE = ".adopted-duplicate"


def adopt(run: str, apply: bool = False, documents=None) -> list[str]:
    """`heimdall library adopt <A>/<E>/<R> [--yes]`: a Run's complete generation points (those its points.json lists, whose
    `.complete` is the hash of their recorded `identity.json`) moved into the Assignment's points library under their keys, and
    linked back as a Run that used the library has them: a reorganisation, nothing is run. A point whose key is already complete
    in the library is linked to that entry, and its own folders are kept beside the link as `<name>.adopted-duplicate`
    (`heimdall library prune --duplicates` removes them). Without `apply` it says what it would do. The Run's points.json gets
    `library` and the key as `identity` for each adopted point; `documents(products folder, {old identity: key})`, when given,
    does the same for the Run's plot document (`plotdoc.rekey`, which this rank cannot import), so its drawing finds them
    complete."""
    parts_ = [p for p in run.strip("/").split("/") if p]
    if len(parts_) != 3:
        raise HeimdallError(f"'{run}' is not a Run", hint="a Run is <A>/<E>/<R> (heimdall runs names them)")
    assignment = parts_[0]
    here, products = records_root() / Path(*parts_), results_root() / Path(*parts_)
    manifest_path = here / "points.json"
    if not manifest_path.is_file():
        raise HeimdallError(f"no points.json in {run}: adopt reads which points it ran", where=str(manifest_path))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    library_records, library_results = records_root() / assignment / FOLDER, results_root() / assignment / FOLDER
    out: list[str] = []
    changed = False
    rekeyed: dict[str, str] = {}                 # the identity each adopted point ran with → its key
    verb = "" if apply else "would "
    for entry in manifest.get("points", []):
        name = entry.get("name", "")
        folder, results = here / "points" / name, products / "points" / name
        if folder.is_symlink():
            out.append(f"{name}: already in the library")
            continue
        try:
            parts = json.loads((folder / "identity.json").read_text(encoding="utf-8"))
            marker = (folder / ".complete").read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            out.append(f"{name}: left (no recorded identity or not complete)")
            continue
        if _hash({k: v for k, v in parts.items() if k != "format"}) != marker:
            out.append(f"{name}: left (its .complete is not the hash of its identity.json)")
            continue
        if not results.is_dir():
            out.append(f"{name}: left (no products folder {results})")
            continue
        key = key_of_recorded(parts)
        entry_rec, entry_res = library_records / key[:16], library_results / key[:16]
        shared = (entry_rec / ".complete").is_file() and (entry_rec / ".complete").read_text(encoding="utf-8").strip() == key
        if not shared and (entry_rec.exists() or entry_res.exists()):
            out.append(f"{name}: left (the library has an unfinished entry {key[:16]}: prune it, or finish it)")
            continue
        out.append(f"{verb}{'link ' + name + ' to the library entry ' + key[:16] + ' (its own folders kept as ' + name + DUPLICATE + ')' if shared else 'move ' + name + ' into the library as ' + key[:16]}")
        if not apply:
            continue
        if shared:
            folder.rename(folder.with_name(name + DUPLICATE))
            results.rename(results.with_name(name + DUPLICATE))
        else:
            entry_rec.parent.mkdir(parents=True, exist_ok=True)
            entry_res.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(folder), str(entry_rec))
            shutil.move(str(results), str(entry_res))
            write_atomic(entry_rec / ".complete", key + "\n")
        link_into(folder, entry_rec)
        link_into(results, entry_res)
        prov = {}
        try:
            prov = json.loads((entry_rec / "provenance.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        line = {"key": key, "run": run.strip("/"), "kind": "used" if shared else "created"}
        if not shared:
            line.update({"coordinates": {q: v.get("tag") for q, v in entry.get("values", {}).items()},
                         "events": prov.get("events"), "threads": prov.get("threads"), "seed": prov.get("seed")})
        append(assignment, line)
        if marker != key:                            # a point recorded before its identity was its key
            rekeyed[marker] = key
        entry["library"], entry["identity"] = key[:16], key
        changed = True
    if apply and changed:
        write_atomic(manifest_path, json.dumps(manifest, indent=1, default=str) + "\n")
        if documents is not None:
            done = documents(products, rekeyed)
            out.append(f"its plot document names the library keys of {done} member(s)" if done
                       else "its plot document needs no rewrite: it names the keys already" if not rekeyed else "no plot document to rewrite")
    if not apply:
        out.append("a dry run: --yes makes these moves")
    return out
