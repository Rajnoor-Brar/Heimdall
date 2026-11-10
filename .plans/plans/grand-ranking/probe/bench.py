"""The probe behind 05_Benchmarks.md: today's engine against the proposed Grand Ranking, on real Runs.

A throwaway for the plan, not Heimdall code. It reads only. Each Run is given as LABEL=RESULTS:PAGES, where
RESULTS is the Run's results folder (statistics/<set>/statistics.csv and plot.toml) and PAGES the folder holding its
pages' <page>.toml and <page>.toml.stats.json with `measured` bins (.cache/<A>/plots/<A>/<E>/<R>/<set>, or a scratch
copy re-measured with `Paint.exe <page>.toml … --ranges-only`).

    source gjallarhorn.sh
    python -I -W ignore probe/bench.py B1=$WD/results/<A>/<E>/<R>:$WD/.cache/<A>/plots/<E>/<R>/totality …

Pathological points are named with --bad LABEL=GLOB (e.g. B1='*qed_lo*'): the probe checks the engine finds them, it
does not use them to score.
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import math
import random
import statistics as st
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "framework"))
import numpy as np  # noqa: E402
from stats import bins, metrics as M, score as S  # noqa: E402

TODAY = ["chi2_ndf", "norm", "shape", "tilt", "worst"]
PROPOSED = ["chi2_z", "poisson", "norm", "shape", "L4", "tilt", "rho1", "worst", "roughness"]   # today's ids
CATEGORY = {n: m.purpose for n, m in M.REGISTRY.items()}


# ── loading ───────────────────────────────────────────────────────────────────────────────────

def axes_of(results: Path) -> dict:
    data = tomllib.loads((results / "plot.toml").read_text())
    q = data.get("quantities", {})
    out = {}
    for name, m in (data.get("members") or {}).items():
        out[name] = {k: (i if isinstance(i, str) else str(((q.get(k) or {}).get("points") or [])[i]["tag"]))
                     for k, i in (m.get("choice") or {}).items()}
    return out


def load(results: Path, pages: Path, set_: str = "totality"):
    rows = list(csv.DictReader(open(results / "statistics" / set_ / "statistics.csv")))
    by_page: dict = {}
    for r in rows:
        by_page.setdefault(r["page"], []).append(r)
    out = []
    for page, rs in by_page.items():
        doc = tomllib.loads((pages / f"{page}.toml").read_text())
        curves = bins.curves(json.loads((pages / f"{page}.toml.stats.json").read_text()), bool(doc.get("page", {}).get("logx")))
        for i, r in enumerate(rs):
            row = {k: r[k] for k in ("page", "cell", "object", "point")}
            row["is_reference"] = r["is_reference"] == "True"
            row["ndf"] = int(float(r["ndf"] or 0))
            for name in M.REGISTRY:
                try:
                    row[name] = float(M.evaluate(name, curves[i], pool=curves))
                except Exception:                                   # a metric that cannot be made here is missing
                    row[name] = math.nan
            row["peak_bin_ratio"] = peak_bin_ratio(curves[i])
            out.append(row)
    return out, axes_of(results)


def peak_bin_ratio(c) -> float:
    use = np.isfinite(c.y) & np.isfinite(c.ref_y) & (c.ref_y > 0)
    if not use.any():
        return math.nan
    with np.errstate(all="ignore"):
        top = float(np.max(np.abs(c.y[use]) / c.ref_y[use]))
    return math.log10(top) if top > 0 else -math.inf


# ── the proposed engine ───────────────────────────────────────────────────────────────────────

def pm(values, p=2.0, w=None):
    pairs = [(v, 1.0 if w is None else w[i]) for i, v in enumerate(values) if not math.isnan(v)]
    if not pairs:
        return math.nan
    if any(math.isinf(v) for v, _ in pairs):
        return math.inf
    return (sum(wi * v ** p for v, wi in pairs) / sum(wi for _, wi in pairs)) ** (1 / p)


def cost(name, value, compressed):
    if math.isnan(value):
        return math.nan
    z = M.REGISTRY[name].loss(value)
    return (math.log2(1 + z) if math.isfinite(z) else math.inf) if compressed else z


def grand(rows, names, compressed=True, gate=True, p_category=2.0):
    """{point: (vetoed, failed pages, loss)}"""
    by: dict = {}
    for r in rows:
        if r["is_reference"]:
            continue
        per: dict = {}
        for n in names:
            c = cost(n, r[n], compressed)
            if not math.isnan(c):
                per.setdefault(CATEGORY[n], []).append(c)
        failed = gate and r["peak_bin_ratio"] >= 3.0
        by.setdefault(r["point"], []).append((pm([pm(v) for v in per.values()], p_category), failed))
    return {p: (any(f for _, f in v), sum(f for _, f in v), pm([l for l, _ in v])) for p, v in by.items()}


def order(res):
    return sorted(res, key=lambda p: (res[p][0], -res[p][1] if res[p][0] else 0, res[p][2]))


def spearman(a: dict, b: dict) -> float:
    common = [k for k in a if k in b and math.isfinite(a[k]) and math.isfinite(b[k])]
    n = len(common)
    ra = {k: i for i, k in enumerate(sorted(common, key=a.get))}
    rb = {k: i for i, k in enumerate(sorted(common, key=b.get))}
    return 1 - 6 * sum((ra[k] - rb[k]) ** 2 for k in common) / (n * (n * n - 1)) if n > 2 else math.nan


def kendall(a: list, b: list) -> float:
    pos = {v: i for i, v in enumerate(b)}
    c = d = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a)):
            s = pos[a[j]] - pos[a[i]]
            c, d = c + (s > 0), d + (s < 0)
    return (c - d) / (c + d) if c + d else 1.0


# ── marginals (03 §2) ─────────────────────────────────────────────────────────────────────────

def g_of(n, alpha):
    return 0 if n <= 2 else max(1, math.floor(alpha * n))


def tmean(x, alpha=0.2):
    x = sorted(v for v in x if math.isfinite(v))
    n = len(x)
    if not n:
        return math.nan, math.nan, 0, 0
    g = g_of(n, alpha)
    core = x[g:n - g]
    se = math.nan
    if len(core) >= 2:
        w = [x[g]] * g + core + [x[n - g - 1]] * g
        mu = sum(w) / n
        se = math.sqrt(sum((v - mu) ** 2 for v in w) / (n - 1)) / ((1 - 2 * g / n) * math.sqrt(n))
    return sum(core) / len(core), se, n, g


def marginal(losses: dict, axes: dict, vetoed: set, quantity: str, alpha=0.2, centred=True):
    ell = {p: math.log(0.01 + l) for p, l in losses.items() if p in axes and math.isfinite(l)}
    strata: dict = {}
    for p in ell:
        if p not in vetoed:
            strata.setdefault(tuple(sorted((k, v) for k, v in axes[p].items() if k != quantity)), {})[axes[p][quantity]] = ell[p]
    values = sorted({axes[p][quantity] for p in ell})
    rows = []
    for v in values:
        xs = [by[v] - (sum(by.values()) / len(by) if centred else 0.0) for by in strata.values()
              if v in by and (len(by) >= 2 or not centred)]
        rows.append((v, *tmean(xs, alpha), sum(1 for p in ell if axes[p][quantity] == v and p in vetoed)))
    return sorted(rows, key=lambda r: (math.isnan(r[1]), r[1]))


# ── the report ────────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="LABEL=RESULTS:PAGES")
    ap.add_argument("--bad", action="append", default=[], help="LABEL=GLOB of points known to be pathological")
    ap.add_argument("--boot", type=int, default=40)
    a = ap.parse_args()
    bad = dict(b.split("=", 1) for b in a.bad)
    random.seed(1)
    for spec in a.runs:
        label, paths = spec.split("=", 1)
        results, pages = (Path(p) for p in paths.split(":", 1))
        rows, axes = load(results, pages)
        isbad = (lambda p: fnmatch.fnmatch(p, bad[label])) if label in bad else (lambda p: False)
        print(f"\n######## {label}: {len({r['point'] for r in rows})} points, {len({r['page'] for r in rows})} pages, {len(rows)} curves")

        # §1 gates
        per: dict = {}
        for r in rows:
            per.setdefault(r["point"], []).append(r["peak_bin_ratio"])
        print("gate peak_bin_ratio >= 3: failed pages per bad point", sorted(sum(v >= 3 for v in per[p]) for p in per if isbad(p)),
              "| max failed pages of an ordinary point", max([sum(v >= 3 for v in per[p]) for p in per if not isbad(p)] or [0]),
              "| ordinary max", round(max(v for p in per if not isbad(p) for v in per[p] if math.isfinite(v)), 2),
              "| bad median", round(st.median([v for p in per if isbad(p) for v in per[p]]), 2) if any(map(isbad, per)) else "-")

        # §1 compatibility inversion
        for names in (["chi2_ndf"], ["chi2_z", "poisson"]):
            sc = S.score(rows, S.settings_of({"metrics": names}))
            o = [p.point for p in sorted(sc.points, key=lambda p: p.purposes.get("compatibility", math.inf))]
            print(f"compatibility ranking by {'+'.join(names):15}: bad points at ranks {[i + 1 for i, p in enumerate(o) if isbad(p)]} of {len(o)}")

        # §2 engines: bad at bottom, shares, page-bootstrap stability
        engines = {"today": dict(names=TODAY, compressed=False, gate=False),
                   "today, compressed": dict(names=TODAY, compressed=True, gate=False),
                   "proposed": dict(names=PROPOSED, compressed=True, gate=True)}
        objects = sorted({r["page"].rsplit("/", 1)[-1] for r in rows})
        base = {p: v[2] for p, v in grand(rows, **engines["today"]).items()}
        for name, kw in engines.items():
            res = grand(rows, **kw)
            o = order(res)
            nb = sum(map(isbad, res))
            at_bottom = all(isbad(p) for p in o[len(o) - nb:]) if nb else True
            ok = {p: v[2] for p, v in res.items() if not isbad(p)}
            shares: dict = {}
            for r in rows:
                if r["is_reference"] or isbad(r["point"]):
                    continue
                cat: dict = {}
                for n in kw["names"]:
                    c = cost(n, r[n], kw["compressed"])
                    if math.isfinite(c):
                        cat.setdefault(CATEGORY[n], []).append(c)
                tot = sum(pm(v) ** 2 for v in cat.values())
                for k, v in cat.items():
                    shares.setdefault(k, []).append(pm(v) ** 2 / tot if tot else 0.0)
            rhos = []
            for _ in range(a.boot):
                pick = [random.choice(objects) for _ in objects]
                sample = [r for o_ in pick for r in rows if r["page"].rsplit("/", 1)[-1] == o_]
                rhos.append(spearman(ok, {p: v[2] for p, v in grand(sample, **kw).items() if p in ok}))
            print(f"{name:18} bad at bottom {at_bottom!s:5} vetoed {sum(v[0] for v in res.values())}/{nb} "
                  f"| Spearman vs today {spearman({p: base[p] for p in ok}, ok):.3f} | page-bootstrap stability {st.mean(rhos):.3f} "
                  f"| category shares % {({k: round(100 * st.mean(v)) for k, v in shares.items()})} | top 3 {o[:3]}")

        # §3 marginals
        res = grand(rows, **engines["proposed"])
        losses = {p: v[2] for p, v in res.items()}
        vetoed = {p for p, v in res.items() if v[0]}
        varied = [q for q in next(iter(axes.values())) if len({axes[p][q] for p in axes}) > 1]
        for q in varied:
            print(f"-- marginal {q}: value  ×vs-strata ±SE  n g vetoed | level e^M  | today's (RMS of scores)")
            today = {v: s for m in S.marginals(S.score(rows, S.settings_of()), axes) if m.axis == q for v, s, _, _ in m.rows}
            level = {r[0]: r for r in marginal(losses, axes, vetoed, q, centred=False)}
            for v, e, se, n, g, nv in marginal(losses, axes, vetoed, q):
                lv = level[v][1]
                print(f"   {v[:26]:26} ×{math.exp(e) if math.isfinite(e) else math.nan:5.3f} ±{se:5.3f} n={n:3d} g={g} vet={nv} "
                      f"| {math.exp(lv) if math.isfinite(lv) else math.nan:6.3f} | {today.get(v, math.nan):7.2f}")
            for gate in (True, False):
                res_g = grand(rows, **{**engines["proposed"], "gate": gate})
                lg = {p: v[2] for p, v in res_g.items()}
                vg = {p for p, v in res_g.items() if v[0]}
                full = [r[0] for r in marginal(lg, axes, vg, q, centred=False)]
                taus = []
                points = list(lg)
                for _ in range(30):
                    pick = [random.choice(points) for _ in points]
                    bl = {f"{p}#{i}": lg[p] for i, p in enumerate(pick)}
                    bx = {f"{p}#{i}": axes[p] for i, p in enumerate(pick) if p in axes}
                    bv = {f"{p}#{i}" for i, p in enumerate(pick) if p in vg}
                    got = [r[0] for r in marginal(bl, bx, bv, q, centred=False) if math.isfinite(r[1])]
                    if sorted(got) == sorted(full):
                        taus.append(kendall(full, got))
                print(f"   bootstrap Kendall τ of the level's order, gate {gate!s:5}: {st.mean(taus) if taus else math.nan:.2f} ({len(taus)} draws)")


if __name__ == "__main__":
    main()
