"""The identity golden file: every fixture point's `identity_parts`, kept in tests/golden/identity_parts.json.

A change to what an identity hashes reruns every point it touches, so it is the developer's to order
(docs/rules/invariants.md). This test plans every point of every fixture config and compares its parts with the
kept ones; a difference names the point and the first key that differs. Binaries are masked (an app or a Rivet
plugin rebuilt must not fail it; a changed card, option or rule must), and the scratch folder is `{scratch}`.

The golden file is never regenerated to make a test pass: `write(path)` below is what wrote it, run by hand once.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from runner import config, house, quantities, record, sweep, tools

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "identity_parts.json"
BINARY = "<binary>"


def _masked(value, key: str = "", scratch: str = ""):
    """The parts with every binary's hash replaced and the scratch folder written as {scratch}."""
    if isinstance(value, dict):
        return {k: (BINARY if key == "files_sha256" and "/build/" in k else _masked(v, k, scratch)) for k, v in value.items()}
    if isinstance(value, list):
        return [_masked(v, key, scratch) for v in value]
    if key == "exe_sha256":
        return BINARY
    if isinstance(value, str) and scratch:
        return value.replace(scratch, "{scratch}")
    return value


def collect() -> dict[str, dict]:
    """`<Assignment>/<Errand>|<configuration>|<point>` → its masked identity parts, for every fixture config."""
    from conftest import SCRATCH
    out = {}
    for name in house.config_names():
        errand = config.load(name)
        master = quantities.load_master(errand.assignment, errand.master_toml)
        for key, conf in errand.configurations.items():
            for point in sweep.points(errand, conf):
                plan = tools.plan_point(errand, conf, point, master)
                parts = json.loads(json.dumps(record.identity_parts(plan), sort_keys=True, default=str))
                out[f"{name}|{key}|{plan.point.name}"] = _masked(parts, scratch=str(SCRATCH))
    return out


def write(path: Path = GOLDEN) -> int:
    """The golden file, a point a line (so a change reads as a diff). By hand, once; never to pass a test."""
    rows = [f"{json.dumps(k)}:{json.dumps(v, sort_keys=True, separators=(',', ':'))}" for k, v in sorted(collect().items())]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{\n" + ",\n".join(rows) + "\n}\n", encoding="utf-8")
    return len(rows)


def first_difference(kept, now, at: str = "") -> str:
    """Where two parts first differ, as `tools[0].argv[3]: kept … now …`; "" when equal."""
    if isinstance(kept, dict) and isinstance(now, dict):
        for key in sorted(set(kept) | set(now)):
            if key not in kept or key not in now:
                return f"{at}.{key}: {'only now' if key not in kept else 'only in the golden file'}"
            found = first_difference(kept[key], now[key], f"{at}.{key}" if at else key)
            if found:
                return found
        return ""
    if isinstance(kept, list) and isinstance(now, list):
        for i, (a, b) in enumerate(zip(kept, now)):
            found = first_difference(a, b, f"{at}[{i}]")
            if found:
                return found
        return f"{at}: {len(kept)} kept, {len(now)} now" if len(kept) != len(now) else ""
    return "" if kept == now else f"{at}: kept {kept!r}, now {now!r}"


def test_the_golden_file_holds_the_fixture_points():
    kept = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert len(kept) > 150 and all("|" in key for key in kept)
    assert "<binary>" in GOLDEN.read_text(encoding="utf-8") and str(Path.home()) not in GOLDEN.read_text(encoding="utf-8")


def test_every_fixture_point_still_has_the_identity_parts_it_had(work_built):
    kept = json.loads(GOLDEN.read_text(encoding="utf-8"))
    now = collect()
    assert not set(kept) ^ set(now), (f"points only in the golden file: {sorted(set(kept) - set(now))[:5]}; "
                                      f"only now: {sorted(set(now) - set(kept))[:5]}")
    for point, parts in now.items():
        difference = first_difference(kept[point], parts)
        assert not difference, (f"{point}: {difference}. A change to what an identity hashes reruns every point it "
                                f"touches: ask first (docs/rules/invariants.md); never regenerate this file to pass.")


def test_the_difference_names_the_first_key():
    assert first_difference({"a": [{"b": 1}, {"c": 2}]}, {"a": [{"b": 1}, {"c": 3}]}) == "a[1].c: kept 2, now 3"
    assert first_difference({"a": 1}, {"a": 1, "z": 2}) == ".z: only now"
    assert first_difference({"a": [1, 2]}, {"a": [1]}) == "a: 2 kept, 1 now"


def test_binaries_are_masked_and_the_scratch_is_a_placeholder():
    parts = {"tools": [{"exe_sha256": "ab" * 32, "files_sha256": {"{work}/build/Rivet/Rivet_x.so": "cd" * 32, "{work}/card.cmnd": "ef" * 32},
                        "argv": ["--in", "/s/cache/x"]}]}
    masked = _masked(parts, scratch="/s")
    assert masked["tools"][0]["exe_sha256"] == BINARY
    assert masked["tools"][0]["files_sha256"] == {"{work}/build/Rivet/Rivet_x.so": BINARY, "{work}/card.cmnd": "ef" * 32}
    assert masked["tools"][0]["argv"] == ["--in", "{scratch}/cache/x"]
