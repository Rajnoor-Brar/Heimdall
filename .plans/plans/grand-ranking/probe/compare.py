"""Phase 7.2's comparison: a Run's order before the round against its order now. A throwaway for the round.

    python -I -W ignore probe/compare.py old FRAMEWORK_AT_BASELINE STATISTICS_CSV > old.json   # the engine as it was, on the Run's own table
    python -I -W ignore probe/compare.py new STATISTICS_CSV > new.json                         # today's engine, on the rescored table
    python -I -W ignore probe/compare.py diff old.json new.json                                # who moved more than five places, and why

It reads only; the old framework is a `git archive` of the baseline commit in scratch.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def old(framework: str, csv: str) -> dict:
    sys.path.insert(0, framework)
    from stats import score as S, table as T
    side = T.sidecar(Path(csv)) or {}
    result = S.score(T.read(Path(csv)), S.settings_of(side.get("score") or {}))
    return {"cells": sorted({p.cell for p in result.points}),
            "order": [[p.cell, p.point, p.score] for p in result.ranked()]}


def new(csv: str) -> dict:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "framework"))
    from stats import ranking as R, table as T
    side = T.sidecar(Path(csv)) or {}
    result = R.rank(T.read(Path(csv)), R.settings_of(side.get("ranking") or {}))
    return {"cells": sorted({p.cell for p in result.points}), "flat": result.flat,
            "order": [[p.cell, p.point, p.loss, p.rank, p.worst_page, {c: round(s, 3) for c, s in p.shares.items()}]
                      for p in result.points]}


def diff(a: str, b: str) -> None:
    before, after = json.loads(Path(a).read_text()), json.loads(Path(b).read_text())
    was = {p: i for i, (_, p, *_) in enumerate(before["order"])}
    now = {r[1]: (i, r) for i, r in enumerate(after["order"])}
    common = [p for p in was if p in now]
    n = len(common)
    ra = {p: i for i, p in enumerate(sorted(common, key=was.get))}
    rb = {p: i for i, p in enumerate(sorted(common, key=lambda p: now[p][0]))}
    rho = 1 - 6 * sum((ra[p] - rb[p]) ** 2 for p in common) / (n * (n * n - 1)) if n > 2 else math.nan
    moved = sorted((p for p in common if abs(ra[p] - rb[p]) > 5), key=lambda p: -abs(ra[p] - rb[p]))
    print(f"points {n}; cells before {len(before['cells'])}, now {len(after['cells'])} ({'flat' if after.get('flat') else 'banded'}); "
          f"Spearman before/now {rho:.3f}; moved more than five places: {len(moved)}")
    for p in moved:
        _, r = now[p]
        top = sorted(r[5].items(), key=lambda kv: -kv[1])[:2]
        print(f"   {p[:44]:44} {ra[p] + 1:3d} → {rb[p] + 1:3d}  loss {r[2]:.3g}; its loss is mostly "
              f"{', '.join(f'{c} {100 * s:.0f} %' for c, s in top)}; worst page {r[4]}")


if __name__ == "__main__":
    side, *args = sys.argv[1:]
    if side == "diff":
        diff(*args)
    else:
        print(json.dumps(old(*args) if side == "old" else new(*args)))
