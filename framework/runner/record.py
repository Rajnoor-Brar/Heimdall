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
* A configuration folder may have a tag (V223), records/<A>/<E>/<R>/tag: a name for people, never in an identity.
* Each attempt at a point ends with a line in its records' attempts.jsonl (V200): when, with what identity
  and cards, its verdict and cause, and each tool's exit, stall, warnings, errors and what it reported. A
  record without the file (it ran before V200) has no cause to give.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import threading
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from .errors import HeimdallError
from .paths import find_work, heimdall_root, portable, work_meta
from .image import inside
from .tools import DEFAULT_SEED_RANGE, PointPlan, package_states, version_of



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
        raise HeimdallError(f"two seed quantities give this point the seeds {values}", where=where,
                       hint="a point has one seed: target <tool>/seed from one quantity")
    seed = values[0] if values else plan.manual_seed
    if seed is None:
        raise HeimdallError("seed_type is manual but this point has no seed", where=where,
                       hint="set manual_seed in [errand] or [errand.cfgs.<cfg>], or sweep a quantity targeting <tool>/seed")
    lo, hi = plan.seed_range
    if isinstance(seed, bool) or not isinstance(seed, int) or not lo <= seed <= hi - plan.threads:
        raise HeimdallError(f"the seed {seed!r} is not an integer from {lo:,} to {hi - plan.threads:,}", where=where,
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
                raise HeimdallError(f"points {other.point.name} (seed {other.seed}) and {plan.point.name} (seed {plan.seed}) "
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


def record_dir(plan: PointPlan) -> Path:
    """A point's or stage's records, records/<A>/<E>/<R>/points/<name>/ (V157): apart from its working folder
    (records/<A>/<E>/<R>/logs/<name>/), so deleting logs or .cache/ reruns nothing (U21)."""
    return plan.folders.points / plan.point.name


def provenance_file(plan: PointPlan) -> Path:
    return record_dir(plan) / "provenance.json"


ATTEMPTS = "attempts.jsonl"
ATTEMPT_VERSION = 1


def attempts_file(plan: PointPlan) -> Path:
    """A point's attempts (V200): a JSON line each, in its records, beside its provenance."""
    return record_dir(plan) / ATTEMPTS


def attempts(plan: PointPlan) -> list[dict]:
    """A point's attempts, oldest first; [] for a record without the file (one older than V200). A line that
    is not JSON (a write cut short) is passed over."""
    try:
        text = attempts_file(plan).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def append_attempt(plan: PointPlan, data: dict) -> int:
    """An attempt's line appended (under the point's lock: one writer); its number, from 1."""
    number = len(attempts(plan)) + 1
    path = attempts_file(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"v": ATTEMPT_VERSION, "n": number, **data}, default=str) + "\n")
    return number


def card_hashes(plan: PointPlan) -> dict[str, str]:
    """Each tool's combined card's sha256, as the point wrote it: what an attempt ran with."""
    return {tag: hashlib.sha256(plan.writes.get(step.card_combined, "").encode("utf-8")).hexdigest()
            for tag, step in plan.rendered.items() if step.card_combined}


def cause_text(attempt: dict) -> str:
    """An attempt's cause in a few words (V200): "sherpa:prepare stalled (silent 5200 s)", "pythia failed (exit
    code 3)", "stopped", "[prelim] failed"; "" for one that went well."""
    verdict, cause, blamed = attempt.get("verdict"), attempt.get("cause", ""), attempt.get("blamed", "")
    if verdict == "ok":
        return ""
    if verdict == "stopped" or cause == "stopped":
        return "stopped"
    if cause == "prelim":
        return "[prelim] failed"
    tool = (attempt.get("tools") or {}).get(blamed, {})
    detail = ""
    if cause == "stalled" and tool.get("stall"):
        detail = f" (silent {tool['stall'].get('silent', '?')} s)"
    elif cause == "failed" and tool.get("exit") is not None:
        code = tool["exit"]
        detail = f" (signal {-code})" if code < 0 else f" (exit code {code})"
    elif cause in ("count", "missing") and attempt.get("message"):
        detail = f": {attempt['message']}"
    return f"{blamed or 'a tool'} {cause or 'failed'}{detail}".strip()


def state_of(plan: PointPlan) -> tuple[str, dict | None]:
    """A point's state and its last attempt (V200): running (a session holds its lock, U66); complete; stale
    (complete for an earlier identity: a changed setup reruns it); failed or stopped (its last attempt's
    verdict); incomplete (begun, with no attempt recorded: before V200); to run (never begun, or its logs
    are gone)."""
    if holder(plan) is not None:
        return "running", None
    last = (attempts(plan) or [None])[-1]
    if is_complete(plan):
        return "complete", last
    if complete_marker(plan).exists():
        return "stale", last
    if last is not None and last.get("verdict") in ("failed", "stopped"):
        return last["verdict"], last
    if (plan.out.exists() and any(p.name != LOCK_FILE for p in plan.out.iterdir())) or record_dir(plan).exists():
        return "incomplete", last
    return "to run", last


def manifest_file(plans: list) -> Path:
    """A configuration's points.json: in its records, beside its points' folder."""
    return plans[0].folders.manifest


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
    """The git state of the repository a folder is in (U67): its revision and whether the folder's
    tracked files changed; `subfolder` when the folder is not the repository's top, `unborn` when the
    repository has no commit yet. {} when the folder is in no repository."""
    def git(*args) -> str:
        try:
            return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                                  timeout=10, encoding="utf-8").stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    top = git("rev-parse", "--show-toplevel") if Path(root).is_dir() else ""
    if not top:
        return {}
    revision = git("rev-parse", "--verify", "-q", "HEAD")
    state = {"revision": revision, "dirty": bool(git("status", "--porcelain", "--untracked-files=no", "--", "."))}
    if not revision:
        state["unborn"] = True
    sub = Path(root).resolve().relative_to(Path(top).resolve()).as_posix()
    if sub != ".":
        state["subfolder"] = sub
    return state


def work_record() -> dict:
    """The work dir a point ran in: its name (heimdall.toml) and folder; {} outside one (tests set the roots)."""
    work = find_work()
    if work is None:
        return {}
    return {"name": work_meta(work)["name"], "root": str(work)}


def revision_changes(recorded: dict) -> list[str]:
    """How a provenance's git states ({"heimdall": …, "work": …}) differ from today's: a line for each
    repo whose revision moved, or that had uncommitted changes then (`heimdall reproduce` warns, V77)."""
    now = {"heimdall": git_state(heimdall_root()), "work": git_state(Path(w["root"])) if (w := work_record()) else {}}
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


def provenance(plan: PointPlan, errand, configuration, started: str, finished: str, results: dict) -> dict:
    tools = []
    for tag, step in plan.rendered.items():
        entry = {"tag": tag, "tool": step.tool.tool, "exe": portable(step.exe), "version": version_of(step.folder),
                 "argv": [portable(a) for a in step.argv], "ran": step.group >= 0, "result": results.get(tag, {})}
        if step.exe.is_file():
            entry["exe_sha256"] = step.identity_parts.get("exe_sha256", "")
        if named := step.folder.get("tool", "packages", []):            # how they were installed (not identity)
            entry["packages"] = package_states(named)
        if step.card_combined:
            entry["card"] = portable(step.card_combined)
            entry["card_sha256"] = hashlib.sha256(plan.writes.get(step.card_combined, "").encode("utf-8")).hexdigest()
        if step.config_path:
            entry["config"] = portable(step.config_path)
        tools.append(entry)
    return {
        "point": plan.point.name,
        "run": errand.name, "project": errand.assignment, "configuration": configuration.key,
        "config_file": portable(errand.path), "sets": list(getattr(errand, "sets", [])),    # what reproduces it (V77)
        "values": {name: {"index": index, "tag": _tag(errand, name, index), "value": errand.quantities[name].values[index]}
                   for name, index in plan.values.items()},
        "identity": plan.identity, "seed": plan.seed, "threads": plan.threads, "events": plan.events,
        "tools": tools,
        "host": socket.gethostname(), "platform": platform.platform(), "user": os.environ.get("USER", ""),
        "git": {"heimdall": git_state(heimdall_root()),                # two repos (framework/01 §5.6)
                "work": git_state(Path(work["root"])) if (work := work_record()) else {}},
        "heimdall": str(heimdall_root()), "work": work, "stack": os.environ.get("HEIMDALL_STACK", ""),
        **({"image": held} if (held := inside()) else {}),         # an Apptainer image's path and labels (V150)
        "started": started, "finished": finished,
    }


def _tag(errand, name: str, index: int) -> str:
    from .sweep import tag_of
    return tag_of(errand.quantities[name], index)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_atomic(path: Path, text: str) -> None:
    """Written whole, then renamed: a reader never sees half of it. The temporary file is this process's
    and thread's, so several runs on one tree (cluster jobs, V114) never rename each other's."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    partial.write_text(text, encoding="utf-8")
    partial.replace(path)


def points_manifest(plans: list[PointPlan], errand, configuration, known: dict | None = None) -> dict:
    """points.json (06 §7): every point's values, page, products and state, for plot and post tools, and the run's
    constants (V200; `known`: as the run began, its points' counts made again)."""
    from .sweep import label_of, split_axes, tag_of
    page_names = [name for group in split_axes(configuration)[0] for name in group]    # a listed group's paged members (V154)
    points = []
    for plan in plans:
        quantity = errand.quantities
        points.append({
            "name": plan.point.name, "index": plan.point.index,
            "values": {name: {"tag": tag_of(quantity[name], i), "label": label_of(quantity[name], i),
                              "value": quantity[name].values[i], "swept": name in plan.point.choice}
                       for name, i in plan.values.items()},
            "page": [tag_of(quantity[name], plan.point.choice[name]) for name in page_names],
            "products": {i.name: str(i.path) for i in plan.interfaces.values() if i.kind == "product" and not i.shard},
            "results": str(plan.res), "output": str(plan.out),
            "identity": plan.identity, "seed": plan.seed, "complete": is_complete(plan),
            "texts": {k: v for step in plan.rendered.values() for k, v in step.texts.items()},   # {opt:…} (V158)
            **_last(plan),                                                                     # V200
        })
    return {"run": errand.name, "project": errand.assignment, "configuration": configuration.key,
            "config_file": str(errand.path), "plot_points": configuration.plot_points,
            "constants": _counted(known, plans) if known else constants(plans, errand, configuration), "points": points}


def _counted(known: dict, plans: list[PointPlan]) -> dict:
    from collections import Counter
    return {**known, "points": dict(Counter(state_of(p)[0] for p in plans))}


def _last(plan: PointPlan) -> dict:
    """A point's state and, when its last attempt failed, its cause (points.json, V200)."""
    state, last = state_of(plan)
    return {"state": state, **({"cause": cause_text(last)} if last and state in ("failed", "stopped") else {})}


def constants(plans: list[PointPlan], errand, configuration, machine: bool = True) -> dict:
    """What every point of a run shares (V200, the user's ask): its events, threads, parallelism and seed rule;
    its chain and stages; its fixed quantities; each tool (folder, executable, version, packages, analyses); the
    base cards and their sha256s; the data it is compared with; and (`machine`) the revisions, host, stack and
    image, and the points by state. In points.json, and in the run's `run started` event."""
    from collections import Counter
    from .sweep import label_of, tag_of
    out: dict = {"events": configuration.event_count, "threads": configuration.threads,
                 "parallelism": "auto" if configuration.parallelism_auto else configuration.parallelism,
                 "seeds": configuration.seed_type if configuration.seed_type != "manual"
                 else ["manual", configuration.manual_seed],
                 "chain": configuration.tools,
                 "stages": {k: v for k, v in (("pre", configuration.pre), ("post", configuration.post),
                                              ("combine", configuration.combine)) if v}}
    swept = {name for plan in plans for name in plan.point.choice}          # what the points vary
    fixed = {}
    for name, tag in configuration.static.items():
        if name in swept:                              # a file's default the configuration varies
            continue
        quantity = errand.quantities.get(name)
        index = next((i for i in range(len(quantity.values)) if tag_of(quantity, i) == tag), None) if quantity else None
        fixed[name] = {"tag": tag, **({"label": label_of(quantity, index), "value": quantity.values[index]}
                                      if index is not None else {})}
    if fixed:
        out["fixed"] = fixed
    tools, cards = {}, {}
    for plan in plans:
        for tag, step in plan.rendered.items():
            if tag in tools:
                continue
            entry = {"tool": step.tool.tool, "folder": str(getattr(step.folder, "name", "")), "exe": portable(step.exe)}
            if machine:
                entry["version"] = version_of(step.folder)
                if named := step.folder.get("tool", "packages", []):
                    entry["packages"] = package_states(named)
            if analyses := (step.tool.extra or {}).get("analyses"):
                entry["analyses"] = analyses
            tools[tag] = entry
            for base in step.card_base:
                if base.is_file() and base.name not in cards:
                    cards[base.name] = hashlib.sha256(base.read_bytes()).hexdigest()
    out["tools"] = tools
    if cards:
        out["base_cards"] = cards
    data = (configuration.own or {}).get("data") or (errand.plot or {}).get("data")
    if data:
        out["data"] = data
    if machine:
        out["git"] = {"heimdall": git_state(heimdall_root()), "work": git_state(Path(w["root"])) if (w := work_record()) else {}}
        out["host"], out["stack"] = socket.gethostname(), os.environ.get("HEIMDALL_STACK", "")
        if held := inside():
            out["image"] = held
        out["points"] = dict(Counter(state_of(p)[0] for p in plans))
    return out


def constants_lines(data: dict) -> list[str]:
    """A run's constants in two lines, as `heimdall status` heads its points with them (V200)."""
    seeds = data.get("seeds")
    first = [f"{data.get('events', 0):,} events", f"{data.get('threads', 1)} thread(s)",
             f"{data.get('parallelism', 1)} at once", f"seeds {seeds if isinstance(seeds, str) else ' '.join(map(str, seeds))}"]
    if fixed := data.get("fixed"):
        first.append("fixed " + ", ".join(f"{k} {v.get('tag')}" for k, v in fixed.items()))
    tools = [f"{tag} ({t.get('tool')}{' ' + t['version'] if t.get('version') else ''})" for tag, t in data.get("tools", {}).items()]
    return ["   " + " · ".join(first), *(["   tools: " + ", ".join(tools)] if tools else [])]



# ── a run's snapshot (V158) ─────────────────────────────────────────────────────────────────────

#: A record's snapshot: records/<A>/<E>/<R>/config/<A>/… (its files, as configs/ holds them) and this file.
SNAPSHOT = "snapshot.toml"


def snapshot_files(errand, plans: list) -> list[Path]:
    """The files a run read from its configs: its errand file, every file it imports, its [report]'s templates, the
    base cards and configs its points read, its tools' own filters, its [plot].root_style file and its master."""
    from .paths import resolve
    wanted = [Path(errand.path), *map(Path, errand.imported), *map(Path, getattr(errand, "templates", []))]   # V209: its reports' too
    wanted += [base for plan in plans for step in plan.rendered.values() for base in step.card_base]
    for tool in errand.tools.values():
        if tool.filters:
            wanted.append(resolve(tool.filters, "filters", assignment=errand.assignment))
    style = (errand.plot or {}).get("root_style")
    if isinstance(style, str) and style not in ("default", "native"):
        wanted.append(resolve(style if style.endswith(".toml") else f"{style}.toml", "root_style", assignment=errand.assignment))
    if errand.master_toml:
        wanted.append(resolve(errand.master_toml, "master", assignment=errand.assignment))
    return list(dict.fromkeys(p.resolve() for p in wanted if p.is_file()))


def config_name(errand) -> str:
    """How `heimdall run` names a run's config: <A>/<E>, its path under configs/ without .toml."""
    from .paths import configs_root
    path = Path(errand.path).resolve()
    try:
        return str(path.relative_to(configs_root().resolve()).with_suffix(""))
    except ValueError:
        return f"{errand.assignment}/{path.stem}"


def write_snapshot(errand, configuration, plans: list) -> Path | None:
    """records/<A>/<E>/<R>/config/ (V158): the files the run read from its configs, as configs/ holds them (an errand file
    given by path goes in as <A>/<its name>), and snapshot.toml: the config's name, the configuration,
    the --set overrides, each file's sha256, the files read from elsewhere (./… and absolute: datasets,
    modules, tool folders, read live), Heimdall's revision and when. Written whole, then put in place; a run
    of its own snapshot writes nothing (it is what it ran with). Returns the folder, or None."""
    from .paths import configs_root
    if not plans:
        return None
    target = plans[0].folders.config
    if Path(errand.path).resolve().is_relative_to(target.resolve()):
        return None
    root = configs_root().resolve()
    name = config_name(errand)
    files: dict[str, str] = {}
    live: list[str] = []
    staging = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    shutil.rmtree(staging, ignore_errors=True)
    for path in snapshot_files(errand, plans):
        if path == Path(errand.path).resolve() and not path.is_relative_to(root):
            rel = Path(f"{name}.toml")                         # an errand file given by path: under its assignment
        elif path.is_relative_to(root):
            rel = path.relative_to(root)
        else:
            live.append(portable(path))
            continue
        (staging / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, staging / rel)
        files[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    import tomli_w
    meta = {"snapshot": {"config": name, "configuration": configuration.key, "sets": list(errand.sets),
                         "heimdall": git_state(heimdall_root()).get("revision", ""), "written": now()},
            "files": files, **({"live": {"files": live}} if live else {})}
    staging.mkdir(parents=True, exist_ok=True)
    (staging / SNAPSHOT).write_text("# A run's snapshot (V158): the config it ran with. heimdall plot|run|status "
                                    "<A>/<E>/<R> read it; edit it to restyle that run alone.\n"
                                    + tomli_w.dumps(meta), encoding="utf-8")
    if target.exists():
        shutil.rmtree(target)
    staging.rename(target)
    return target


#: A configuration folder's tag (V223): records/<A>/<E>/<R>/tag, one line, the source of truth; its plot document's
#: [source].tag is written from it. No file, no tag.
TAG_FILE = "tag"


def run_tag(record: Path) -> str | None:
    """The tag of the configuration folder whose record is `record`: None when it has never had one, "" when
    `heimdall tag --clear` took it (an empty file, so its configuration's `tag` key does not give it again)."""
    from .config import check_tag
    try:
        line = (record / TAG_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return check_tag(line.splitlines()[0].strip(), str(record / TAG_FILE)) if line else ""


def write_run_tag(record: Path, tag: str | None, cleared: bool = False) -> None:
    """A folder's tag written into its record (None: removed; `cleared`: kept as none, an empty file). The plot
    document is the caller's."""
    if tag or cleared:
        write_atomic(record / TAG_FILE, f"{tag}\n" if tag else "")
    else:
        (record / TAG_FILE).unlink(missing_ok=True)


def record_of(name: str, need_snapshot: bool = True) -> Path | None:
    """The record a command's config argument names (V158): `<A>/<E>/<R>` (three parts, where a config
    has two), or a path to such a folder of records/ or results/ (or into it); None when it names a config.
    A record without a snapshot (it ran before V158) is refused, with the way to give it one."""
    from .paths import records_root, results_root
    if not isinstance(name, str) or name.endswith(".toml"):
        return None
    path = Path(name).expanduser()
    candidate = None
    if path.is_absolute() or name.startswith(("./", "../")) or (path.exists() and path.is_dir()):
        resolved = path.resolve()
        for root in (records_root().resolve(), results_root().resolve()):
            if resolved.is_relative_to(root) and len(resolved.relative_to(root).parts) >= 3:
                candidate = records_root() / Path(*resolved.relative_to(root).parts[:3])
                break
        else:
            return None
    elif name.count("/") == 2 and all(name.split("/")):
        candidate = records_root() / name
    if candidate is None or not (candidate.is_dir() or (results_root() / candidate.relative_to(records_root())).is_dir()):
        return None
    if need_snapshot and not (candidate / "config" / SNAPSHOT).is_file():
        rel = candidate.relative_to(records_root())
        raise HeimdallError(f"the record {rel} has no snapshot: it ran before Runs kept the errand file they ran with",
                       where=str(candidate / "config"),
                       hint=f"heimdall migrate --snapshot {rel} copies a config into it (default: the one it names) and "
                            "says which of its points that config gives the same identity")
    return candidate


def read_snapshot(record: Path) -> dict:
    data = tomllib.loads((record / "config" / SNAPSHOT).read_text(encoding="utf-8"))
    snap = data.get("snapshot", {})
    if not snap.get("config") or not snap.get("configuration"):
        raise HeimdallError("a snapshot names its config and configuration", where=str(record / "config" / SNAPSHOT))
    return snap
