"""Identity, seeds, skip-unchanged and provenance (rank 3).

docs/06_Internals.md §8 and §12.

* The identity of a point hashes everything that decides its result: each tool's binary, cards
  (before seeds), argv, extracted config, analyses and files, plus threads and events. It is
  computed before the seeds are written into the cards, and the seeds are then derived from it.
* Seeds (`seed_type`, V39): the threads of a point use base … base+threads−1, and the base is
  - "identity" (the default): lo + int(basis[:12], 16) mod (hi − lo + 1 − threads), [lo, hi] the point's seed range (V54). The basis is the
    generator's own identity (the `produces_events` steps: their cards, binaries and replica
    values), so the same generator setup gives the same events in any configuration: the chain's
    point and an integrated program's (P4 S1). Without a seeded step it is the point's identity.
    Blocks are checked for overlap across the whole plan, and a clash moves up by `threads` (L4),
    so two points of one plan never share events (V9);
  - "manual": exactly the value of a quantity targeting <tool>/seed, else `manual_seed`. Points
    with one generator setup whose blocks overlap without being the same are refused: they would
    repeat some of each other's events;
  - "random": drawn from the OS when the point runs (disjoint as above); a complete point keeps the
    seed its provenance.json records.
* A point is complete when records/…/<point>/.complete holds its identity. It is written last,
  after the count checks, so a half-written point is never skipped.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import platform
import secrets
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .errors import HepError
from .paths import find_work, hep_root, portable, work_meta
from .tools import DEFAULT_SEED_RANGE, PointPlan, version_of



def identity(plan: PointPlan) -> str:
    text = json.dumps(identity_parts(plan), sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def identity_parts(plan: PointPlan) -> dict:
    """What the identity hashes, as a table: written beside .complete as identity.json (V57), so a later
    plan can say what changed (`--why`)."""
    parts = {
        "threads": plan.threads,
        "events": plan.events,
        "tools": [plan.rendered[tag].identity_parts for tag in sorted(plan.rendered)],
        "groups": [[s.tag for s in group] for group in plan.groups],
        "prelim": {k: v for k, v in plan.prelim.items() if v},   # an empty list is none (v3 infers, V130)
        "seeds": seed_rule(plan),        # the seed rule: changing it must rerun what it decided
    }
    if plan.upstream:                    # post: it changes when any point does
        parts["upstream"] = plan.upstream
    if plan.products:                    # generate_cards' products: what the context file gives (04 §9.4)
        parts["products"] = plan.products
    return parts


def identity_record(plan: PointPlan) -> Path:
    return record_dir(plan) / "identity.json"


def write_identity(plan: PointPlan) -> None:
    """The parts of a completed point's identity (V57): a record, beside .complete."""
    normal = json.loads(json.dumps(identity_parts(plan), sort_keys=True, default=str))
    write_atomic(identity_record(plan), json.dumps(normal, indent=1, sort_keys=True) + "\n")


def why(plan: PointPlan, limit: int = 24) -> list[str]:
    """`--why` (V57): what differs between the identity a point last completed with and this plan's."""
    if is_complete(plan):
        return []
    record = identity_record(plan)
    if not record.is_file():
        return ["it has not completed with a recorded identity (never run, or before V57)"
                if not complete_marker(plan).exists() else "its last identity was not recorded (it ran before V57)"]
    try:
        old = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["its identity record is unreadable"]
    new = json.loads(json.dumps(identity_parts(plan), sort_keys=True, default=str))
    if old == new:
        return ["nothing changed since it last ran: it did not complete (failed or stopped)"]
    lines = _diff(_by_tag(old), _by_tag(new), "")
    return lines[:limit] + ([f"… and {len(lines) - limit} more"] if len(lines) > limit else [])


def _by_tag(parts: dict) -> dict:
    out = dict(parts)
    if isinstance(out.get("tools"), list):
        out["tools"] = {t.get("tag", str(i)): t for i, t in enumerate(out["tools"])}
    return out


def _short(value) -> str:
    text = json.dumps(value, default=str)
    return text if len(text) <= 70 else text[:67] + "…"


def _diff(old, new, at: str) -> list[str]:
    if isinstance(old, dict) and isinstance(new, dict):
        out = []
        for key in sorted(set(old) | set(new), key=str):
            where = f"{at}.{key}" if at else str(key)
            if key not in old:
                out.append(f"{where}: added {_short(new[key])}")
            elif key not in new:
                out.append(f"{where}: removed (was {_short(old[key])})")
            elif old[key] != new[key]:
                out += _diff(old[key], new[key], where)
        return out
    if isinstance(old, list) and isinstance(new, list) and all(isinstance(v, str) for v in old + new):
        gone, came = [v for v in old if v not in new], [v for v in new if v not in old]
        if gone or came:
            return [f"{at}: - {_short(v)}" for v in gone] + [f"{at}: + {_short(v)}" for v in came]
        return [f"{at}: the same lines, in another order"]
    return [f"{at}: {_short(old)} → {_short(new)}"]


def seed_rule(plan: PointPlan):
    """What the identity says about the seeds: "generator" (the default: the seeds follow from the
    rest, so this is what every identity said before V39), ["manual", seed] or "random"."""
    if plan.seed_type == "manual":
        return ["manual", manual_seed_of(plan)]
    return "random" if plan.seed_type == "random" else "generator"


def manual_seed_of(plan: PointPlan) -> int:
    """seed_type = "manual": the value of the quantity targeting <tool>/seed, else manual_seed."""
    values = list(dict.fromkeys(v for step in plan.rendered.values() for v in step.identity_parts.get("replica", [])))
    where = f"point {plan.point.name}"
    if len(values) > 1:
        raise HepError(f"two seed quantities give this point the seeds {values}", where=where,
                       hint="a point has one seed: target <tool>/seed from one quantity")
    seed = values[0] if values else plan.manual_seed
    if seed is None:
        raise HepError("seed_type is manual but this point has no seed", where=where,
                       hint="set manual_seed in [run] or [run.cfgs.<cfg>], or sweep a quantity targeting <tool>/seed")
    lo, hi = plan.seed_range
    if isinstance(seed, bool) or not isinstance(seed, int) or not lo <= seed <= hi - plan.threads:
        raise HepError(f"the seed {seed!r} is not an integer from {lo:,} to {hi - plan.threads:,}", where=where,
                       hint=f"with threads = {plan.threads} the point uses seed … seed + {plan.threads - 1}; the range is "
                            "its generators' [card] seed_range")
    return seed


def seed_of(identity_hex: str, threads: int, seed_range: tuple[int, int] = DEFAULT_SEED_RANGE) -> int:
    lo, hi = seed_range
    return lo + int(identity_hex[:12], 16) % (hi - lo + 1 - threads)


def seed_basis(plan: PointPlan, replica: bool = True) -> str:
    """What the seeds follow: the identity of the event generators (`produces_events`), without their
    argv (which names this point's FIFOs) or card comments, whether they run or are only exported to
    an integrated program. A detector simulation downstream does not move the generator's seeds.
    Without `replica`, the generator setup alone (what a manual seed is checked against)."""
    seeded = []
    for _, step in sorted(plan.rendered.items()):
        if not step.folder.get("tool", "produces_events"):      # the generators, not Delphes
            continue
        parts = {k: v for k, v in step.identity_parts.items() if k != "argv" and (replica or k != "replica")}
        comment = step.folder.get("card", "comment", "")
        if comment and "card" in parts:                  # the header comment names the point
            parts["card"] = [line for line in parts["card"] if not line.startswith(comment)]
        seeded.append(parts)
    if not seeded:
        return plan.identity
    text = json.dumps({"threads": plan.threads, "events": plan.events, "generators": seeded}, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def assign_seeds(plans: list[PointPlan], rerun: frozenset[str] = frozenset()) -> None:
    """A seed block per point (V39): given ("manual"), kept from a complete point's provenance or
    drawn ("random"; `rerun` names the points about to run again, which draw anew), else from the
    generator's identity; the last two disjoint across the plan."""
    taken: list[tuple[int, int]] = []

    def clear(base: int, threads: int) -> bool:
        return not any(base < end and start < base + threads for start, end in taken)

    by_setup: dict[str, list[PointPlan]] = {}
    for plan in [p for p in plans if p.seed_type == "manual"]:
        plan.seed = manual_seed_of(plan)
        for other in by_setup.setdefault(seed_basis(plan, replica=False), []):
            if other.seed != plan.seed and plan.seed < other.seed + other.threads and other.seed < plan.seed + plan.threads:
                raise HepError(f"points {other.point.name} (seed {other.seed}) and {plan.point.name} (seed {plan.seed}) "
                               f"have one generator setup and overlapping seed blocks at threads = {plan.threads}",
                               where=f"point {plan.point.name}",
                               hint=f"they would repeat some of each other's events: space the seeds by ≥ {plan.threads}")
        by_setup[seed_basis(plan, replica=False)].append(plan)
    for plan in [p for p in plans if p.seed_type == "random"]:
        plan.seed, plan.seed_kept = (0 if plan.point.name in rerun else _recorded_seed(plan)), True
        if plan.seed:
            taken.append((plan.seed, plan.seed + plan.threads))
    for plan in [p for p in plans if p.seed_type == "random" and not p.seed]:
        plan.seed_kept = False
        lo, hi = plan.seed_range
        while not clear(base := lo + secrets.randbelow(hi - lo + 1 - plan.threads), plan.threads):
            pass
        taken.append((base, base + plan.threads))
        plan.seed = base
    for plan in sorted([p for p in plans if p.seed_type == "identity"], key=lambda p: p.identity):
        lo, hi = plan.seed_range
        base = seed_of(seed_basis(plan), plan.threads, plan.seed_range)
        while not clear(base, plan.threads):
            base = lo + (base - lo + plan.threads) % (hi - lo + 1 - plan.threads)
        taken.append((base, base + plan.threads))
        plan.seed = base


def _recorded_seed(plan: PointPlan) -> int:
    """A complete point's seed, from its provenance.json (0 when it is not complete, or unreadable)."""
    if not is_complete(plan):
        return 0
    try:
        return int(json.loads(provenance_file(plan).read_text(encoding="utf-8"))["seed"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0


def records_of(folder: Path) -> Path:
    """The records of a folder of logs/ (a point's, a stage's, a configuration's): the same place under
    records/ (U21), so deleting logs/ or .cache/ reruns nothing."""
    from .paths import logs_root, records_root
    return records_root() / folder.relative_to(logs_root())


def record_dir(plan: PointPlan) -> Path:
    return records_of(plan.out)


def provenance_file(plan: PointPlan) -> Path:
    return record_dir(plan) / "provenance.json"


def manifest_file(plans: list) -> Path:
    """A configuration's points.json: in its records, beside its points' folders."""
    return records_of(plans[0].out.parent) / "points.json"


def complete_marker(plan: PointPlan) -> Path:
    return record_dir(plan) / ".complete"     # recorded: beside the provenance, never with the logs


def is_complete(plan: PointPlan) -> bool:
    marker = complete_marker(plan)
    return marker.is_file() and marker.read_text(encoding="utf-8").strip() == plan.identity


def recorded_identity(plan: PointPlan) -> str | None:
    """The identity a stage last completed with; None when it never did (or a run of it is under way)."""
    marker = complete_marker(plan)
    try:
        return marker.read_text(encoding="utf-8").strip() if marker.is_file() else None
    except OSError:
        return None


def overwritten(stages) -> list:
    """The stages that completed with other inputs than they are planned with now: running one replaces
    what it made (v3's serials, 03 §6)."""
    return [s for s in stages if (old := recorded_identity(s)) is not None and old != s.identity]


LOCK_FILE = ".lock"


class PointLock:
    """U66: one session runs a point at a time. An flock on the point's `.lock` (in its logs folder),
    which says who holds it ({host, pid, since}); the kernel lets it go when that process ends, however
    it ends, so a lock is never stale on this host."""

    def __init__(self, plan: PointPlan):
        self.path = plan.out / LOCK_FILE
        self.fd: int | None = None

    def acquire(self, wait: bool = False, stopper=None) -> bool:
        """True once this process holds it. Without `wait`, False at once when another does; with it,
        polled until free (a stop request ends the wait with False)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not wait or (stopper is not None and stopper.requested):
                    os.close(fd)
                    return False
                time.sleep(1.0)
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps({"host": socket.gethostname(), "pid": os.getpid(), "since": now()}).encode("utf-8"))
        self.fd = fd
        return True

    def release(self) -> None:
        if self.fd is not None:
            os.ftruncate(self.fd, 0)
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


def holder(plan: PointPlan) -> dict | None:
    """Who runs this point now, from its lock ({host, pid, since}); None when no process does."""
    path = plan.out / LOCK_FILE
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                return json.loads(path.read_text(encoding="utf-8") or "{}") or {"pid": "?", "host": "?"}
            except (OSError, ValueError):
                return {"pid": "?", "host": "?"}
        fcntl.flock(fd, fcntl.LOCK_UN)
        return None
    finally:
        os.close(fd)


def held_by(who: dict) -> str:
    return f"pid {who.get('pid', '?')} on {who.get('host', '?')}" + (f", since {who['since']}" if who.get("since") else "")


def git_state(root: Path) -> dict:
    """A folder's git revision and whether its tracked files changed; {} when it is not a git repo."""
    def git(*args) -> str:
        try:
            return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                                  timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    revision = git("rev-parse", "HEAD") if (root / ".git").exists() else ""
    if not revision:
        return {}
    return {"revision": revision, "dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}


def work_record() -> dict:
    """The work dir a point ran in: its name (hep.toml) and folder; {} outside one (tests set the roots)."""
    work = find_work()
    if work is None:
        return {}
    return {"name": work_meta(work)["name"], "root": str(work)}


def revision_changes(recorded: dict) -> list[str]:
    """How a provenance's git states ({"heimdall": …, "work": …}) differ from today's: a line for each
    repo whose revision moved, or that had uncommitted changes then (`hep reproduce` warns, V77)."""
    now = {"heimdall": git_state(hep_root()), "work": git_state(Path(w["root"])) if (w := work_record()) else {}}
    out = []
    for repo in ("heimdall", "work"):
        then = recorded.get(repo) or {}
        if not then.get("revision"):
            continue
        today = now[repo].get("revision", "")
        if then["revision"] != today:
            out.append(f"{repo} was at {then['revision'][:12]} when it ran, and is at {today[:12] or '(no git)'} now")
        if then.get("dirty"):
            out.append(f"{repo} had uncommitted changes when it ran: what they were is not recorded")
    return out


def provenance(plan: PointPlan, run, configuration, started: str, finished: str, results: dict) -> dict:
    tools = []
    for tag, step in plan.rendered.items():
        entry = {"tag": tag, "tool": step.tool.tool, "exe": portable(step.exe), "version": version_of(step.folder),
                 "argv": [portable(a) for a in step.argv], "ran": step.group >= 0, "result": results.get(tag, {})}
        if step.exe.is_file():
            entry["exe_sha256"] = step.identity_parts.get("exe_sha256", "")
        if step.card_combined:
            entry["card"] = portable(step.card_combined)
            entry["card_sha256"] = hashlib.sha256(plan.writes.get(step.card_combined, "").encode("utf-8")).hexdigest()
        if step.config_path:
            entry["config"] = portable(step.config_path)
        tools.append(entry)
    return {
        "point": plan.point.name,
        "run": run.name, "project": run.project, "configuration": configuration.key,
        "config_file": portable(run.path), "sets": list(getattr(run, "sets", [])),    # what reproduces it (V77)
        "values": {name: {"index": index, "tag": _tag(run, name, index), "value": run.quantities[name].values[index]}
                   for name, index in plan.values.items()},
        "identity": plan.identity, "seed": plan.seed, "threads": plan.threads, "events": plan.events,
        "tools": tools,
        "host": socket.gethostname(), "platform": platform.platform(), "user": os.environ.get("USER", ""),
        "git": {"heimdall": git_state(hep_root()),                # two repos (framework/01 §5.6)
                "work": git_state(Path(work["root"])) if (work := work_record()) else {}},
        "hep": str(hep_root()), "work": work, "stack": os.environ.get("HEP_STACK", ""),
        "started": started, "finished": finished,
    }


def _tag(run, name: str, index: int) -> str:
    from .sweep import tag_of
    return tag_of(run.quantities[name], index)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_atomic(path: Path, text: str) -> None:
    """Written whole, then renamed: a reader never sees half of it. The temporary file is this process's
    and thread's, so several runs on one tree (cluster jobs, V114) never rename each other's."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    partial.write_text(text, encoding="utf-8")
    partial.replace(path)


def points_manifest(plans: list[PointPlan], run, configuration) -> dict:
    """points.json (06 §7): every point's values, page, products and state, for plot and post tools."""
    from .sweep import label_of, tag_of
    page_names = [name for entry in configuration.sweeps for name in (entry if isinstance(entry, list) else [entry])
                  if (set(entry) if isinstance(entry, list) else {entry}) & set(configuration.plot_points)]
    points = []
    for plan in plans:
        quantity = run.quantities
        points.append({
            "name": plan.point.name, "index": plan.point.index,
            "values": {name: {"tag": tag_of(quantity[name], i), "label": label_of(quantity[name], i),
                              "value": quantity[name].values[i], "swept": name in plan.point.choice}
                       for name, i in plan.values.items()},
            "page": [tag_of(quantity[name], plan.point.choice[name]) for name in page_names],
            "products": {i.name: str(i.path) for i in plan.interfaces.values() if i.kind == "product" and not i.shard},
            "results": str(plan.res), "output": str(plan.out),
            "identity": plan.identity, "seed": plan.seed, "complete": is_complete(plan),
        })
    return {"run": run.name, "project": run.project, "configuration": configuration.key,
            "config_file": str(run.path), "plot_points": configuration.plot_points, "points": points}

