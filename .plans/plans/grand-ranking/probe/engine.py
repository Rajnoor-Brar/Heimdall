"""Phase 7's probe: the Grand Ranking as built (stats.ranking) on real Runs, against an independent computation.

A throwaway for the round, not Heimdall code. It reads the Runs only. Each Run is LABEL=RESULTS:PAGES, where RESULTS is
the Run's results folder (statistics/<set>/statistics.csv and plot.toml) and PAGES the folder of its pages' <page>.toml
and <page>.toml.stats.json with `measured` bins (the Run's .cache, or a scratch copy re-measured with Paint --ranges-only).

    source gjallarhorn.sh
    python -I -W ignore probe/engine.py B1=RESULTS:PAGES … --bad 'B1=*qed_lo*' … [--out SCRATCH]

The rows are made by Heimdall's own table code (stats.table.statistics_of) from the measured bins. --bad names the
pathological points so the probe can check where they land; scoring never uses it. With --out, each Run's set is rescored
through statstable.write_set into SCRATCH/<LABEL>/results/<A>/<E>/<R>/statistics/<set>/, beside a copy of its plot.toml.
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import math
import shutil
import statistics as st
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "framework"))
from stats import metrics as M, ranking as R, table as T  # noqa: E402

TODAY = ["chi2_ndf", "log_yield_ratio", "shape", "tilt", "peak_pull2"]          # 05's "today": its five, linear, no gate


def pages_of(results: Path, pages: Path, set_: str = "totality") -> list:
    """The Run's pages as the plot stage hands them to write_set: config, document, rel, cell, object (from its table)."""
    old = list(csv.DictReader(open(results / "statistics" / set_ / "statistics.csv", encoding="utf-8")))
    seen: dict = {}
    for r in old:
        seen.setdefault(r["page"], (r["cell"], r["object"]))
    out = []
    for rel, (cell, obj) in seen.items():
        config = pages / f"{rel}.toml"
        out.append(SimpleNamespace(config=config, document=tomllib.loads(config.read_text(encoding="utf-8")), rel=rel,
                                   name=rel.rsplit("/", 1)[-1], cell=cell, object=obj, plain=[], weight=None, overlay="", merged={}))
    return out


def rows_of(pages: list) -> list[dict]:
    return [r for p in pages for r in (T.statistics_of(p) or [])]


# ── the independent loss: the hinge, log2(1 + z), RMS in a category, over categories, over pages ──────────

def z_of(name: str, v: float) -> float:
    m = M.REGISTRY[name]
    good, bad = m.thresholds
    if m.polarity != "lower" or m.scale != "linear":
        raise SystemExit(f"{name}: the probe's hand computation covers lower, linear metrics only")
    if v == math.inf:
        return math.inf
    return max(0.0, (v - good) / (bad - good))


def rms(xs):
    xs = [x for x in xs if not math.isnan(x)]
    if not xs:
        return math.nan
    return math.inf if any(math.isinf(x) for x in xs) else math.sqrt(sum(x * x for x in xs) / len(xs))


def by_hand(rows: list[dict], names: list[str], compressed=True) -> dict:
    pages: dict = {}
    for r in rows:
        if r["is_reference"]:
            continue
        cats: dict = {}
        for n in names:
            v = r.get(n, math.nan)
            if isinstance(v, float) and math.isnan(v):
                continue
            z = z_of(n, v)
            cats.setdefault(M.REGISTRY[n].category, []).append((math.log2(1 + z) if math.isfinite(z) else math.inf) if compressed else z)
        page = rms([rms(c) for c in cats.values()])
        if not math.isnan(page):
            pages.setdefault(r["point"], []).append(page)
    return {p: rms(v) for p, v in pages.items()}


def metric_shares(rows: list[dict], names: list[str], ordinary) -> dict:
    """Each metric's share of the summed squared page loss of the ordinary points (a page's loss² is the mean over its
    categories of the mean over a category's metrics of c²)."""
    total, part = 0.0, {n: 0.0 for n in names}
    for r in rows:
        if r["is_reference"] or not ordinary(r["point"]):
            continue
        cats: dict = {}
        for n in names:
            v = r.get(n, math.nan)
            if not (isinstance(v, float) and math.isnan(v)):
                z = z_of(n, v)
                cats.setdefault(M.REGISTRY[n].category, []).append((n, math.log2(1 + z) if math.isfinite(z) else math.inf))
        if not cats or any(math.isinf(c) for cs in cats.values() for _, c in cs):
            continue
        for cs in cats.values():
            for n, c in cs:
                share = c * c / len(cs) / len(cats)
                part[n] += share
                total += share
    return {n: 100 * v / total for n, v in part.items()} if total else {}


def spearman(a: dict, b: dict) -> float:
    common = [k for k in a if k in b and math.isfinite(a[k]) and math.isfinite(b[k])]
    n = len(common)
    ra = {k: i for i, k in enumerate(sorted(common, key=a.get))}
    rb = {k: i for i, k in enumerate(sorted(common, key=b.get))}
    return 1 - 6 * sum((ra[k] - rb[k]) ** 2 for k in common) / (n * (n * n - 1)) if n > 2 else math.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="LABEL=RESULTS:PAGES")
    ap.add_argument("--bad", action="append", default=[], help="LABEL=GLOB of points known to be pathological")
    ap.add_argument("--out", type=Path, help="rescore each Run's set into this scratch folder")
    a = ap.parse_args()
    bad = dict(b.split("=", 1) for b in a.bad)
    defaults = [n for n, m in M.REGISTRY.items() if m.default]
    today = [M.resolve(n) for n in TODAY]
    for spec in a.runs:
        label, paths = spec.split("=", 1)
        results, pages_dir = (Path(p) for p in paths.split(":", 1))
        pages = pages_of(results, pages_dir)
        rows = rows_of(pages)
        isbad = (lambda p: fnmatch.fnmatch(p, bad[label])) if label in bad else (lambda p: False)
        from runner import statstable
        values = statstable.point_values(results / "statistics" / "totality")
        points = sorted({r["point"] for r in rows if not r["is_reference"]})
        print(f"\n######## {label}: {len(points)} points, {len(pages)} pages, {len(rows)} curves; pathological {sum(map(isbad, points))}")

        plain = R.rank(rows, R.settings_of({}), None, values)
        gated = R.rank(rows, R.settings_of({"gates": True}), None, values)
        order = [p.point for p in plain.points]
        nb = sum(map(isbad, order))
        print(f"defaults: vetoed {sum(p.vetoed for p in plain.points)}; every pathological point after every ordinary one: "
              f"{all(isbad(p) for p in order[len(order) - nb:]) if nb else True} (pathological at ranks "
              f"{[p.rank for p in plain.points if isbad(p.point)]} of {len(order)})")
        loss = {p.point: p.loss for p in plain.points}
        if nb:
            worst_ok = max(l for p, l in loss.items() if not isbad(p))
            print(f"          ordinary losses up to {worst_ok:.3g}; pathological from {min(l for p, l in loss.items() if isbad(p)):.3g} "
                  f"to {max(l for p, l in loss.items() if isbad(p)):.3g}")
        gorder = [p.point for p in gated.points]
        vet = [p for p in gated.points if p.vetoed]
        print(f"gates on: vetoed {len(vet)} (pathological {sum(isbad(p.point) for p in vet)} of {nb}); vetoed after every passing: "
              f"{[p.vetoed for p in gated.points] == sorted(p.vetoed for p in gated.points)}; first passing rank 1: "
              f"{next((p.rank for p in gated.points if not p.vetoed), None) == 1}")
        cats_ok = True
        for cat in {c for p in gated.points for c in p.categories}:
            ranked = sorted(gated.points, key=lambda p: (p.vetoed, p.categories.get(cat, math.inf)))
            cats_ok &= [p.vetoed for p in ranked] == sorted(p.vetoed for p in ranked)
        print(f"          vetoed last in every category ranking: {cats_ok}")

        hand = by_hand(rows, defaults)
        diff = max((abs(hand[p] - loss[p]) for p in loss if math.isfinite(loss[p]) and math.isfinite(hand.get(p, math.nan))), default=math.nan)
        same_inf = all(math.isinf(hand[p]) == math.isinf(loss[p]) for p in loss)
        print(f"engine against the hand computation: largest |Δ loss| {diff:.2e}; infinities agree {same_inf}")

        ok = [p for p in plain.points if not isbad(p.point)]
        shares: dict = {}
        for p in ok:
            for c, s in p.shares.items():
                shares.setdefault(c, []).append(s)
        mean_shares = {c: round(100 * st.mean(v)) for c, v in shares.items()}
        print(f"category shares of the ordinary points' loss (%): {mean_shares}; the largest {max(mean_shares.values()) if mean_shares else '-'}")
        ms = metric_shares(rows, defaults, lambda p: not isbad(p))
        print(f"metric shares (%): pull_autocorr {ms.get('pull_autocorr', math.nan):.1f}, log_ratio_roughness "
              f"{ms.get('log_ratio_roughness', math.nan):.1f}; every metric {({n: round(v, 1) for n, v in ms.items()})}")

        then = by_hand(rows, today, compressed=False)
        okl = {p.point: p.loss for p in ok}
        print(f"Spearman of the ordinary points against 05's today (five metrics, linear, no gate): "
              f"{spearman({p: then[p] for p in okl if p in then}, okl):.3f}")

        for m in plain.marginals:
            print(f"-- marginal {m.quantity}: {m.headline}")
            for row in m.rows:
                print(f"   {row.value[:28]:28} ×{math.exp(row.effect) if math.isfinite(row.effect) else math.nan:6.3f} "
                      f"±{row.effect_se:5.3f} vs best ×{math.exp(-row.vs_best) if math.isfinite(row.vs_best) else math.nan:6.3f} "
                      f"±{row.vs_best_se:5.3f} ≈best {row.same_as_best!s:5} n={row.n:3d} g={row.g} vet={row.vetoed} "
                      f"level {math.exp(row.level) if math.isfinite(row.level) else math.nan:6.3f} {row.mark}")

        for m in gated.marginals:
            print(f"-- gates on, marginal {m.quantity}: {m.headline}")
            for row in m.rows:
                print(f"   {row.value[:28]:28} ×{math.exp(row.effect) if math.isfinite(row.effect) else math.nan:6.3f} "
                      f"±{row.effect_se:5.3f} vs best ×{math.exp(-row.vs_best) if math.isfinite(row.vs_best) else math.nan:6.3f} "
                      f"±{row.vs_best_se:5.3f} ≈best {row.same_as_best!s:5} n={row.n:3d} vet={row.vetoed}")

        if a.out:
            from runner import statstable
            parts = results.parts[-3:]
            run = a.out / label / "results" / Path(*parts)
            numbers = run / "statistics" / "totality"
            if numbers.exists():
                shutil.rmtree(numbers)
            numbers.mkdir(parents=True)
            shutil.copy2(results / "plot.toml", run / "plot.toml")
            import os
            os.environ["HEIMDALL_RESULTS"] = str(a.out / label / "results")      # the Run is named from its scratch root
            count, images = statstable.write_set(pages, numbers, ["pdf"])
            print(f"rescored into scratch: {count} rows, {images} images, {sorted(p.name for p in numbers.iterdir())}")


if __name__ == "__main__":
    main()
