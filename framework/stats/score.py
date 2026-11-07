"""Scoring: rows in, scores out. No files, no drawing.

The rows are a statistics table's (stats/table.py): one per curve of a page, with the metric columns. A *point* is a
curve's `point`, scored within a page *cell* (points of different cells never meet). A curve on a page is an observation;
the page's reference rows are not scored.

    cost      each metric normalised to a cost (`normalise`: hinged thresholds by default, which depend on the metric alone, so a
              score is the same whatever else is in the pool and compares across Runs; the others use the pool of curves on the page)
    purpose   the RMS of a purpose's metric costs, metric weights counting
    page loss the RMS over the purposes that have a metric: four shape metrics weigh one purpose, not four
    score     the `mean` (rms by default) of a point's page losses, page weights counting

Beside the score: the worst page (and a veto when it loses more than `veto`), each purpose's share of the loss, and with
`dominated` whether another point beats it on every purpose. `aggregate` may instead be `fisher`, `topsis` or `promethee`
(each says in its note what it costs). Lower is better throughout.
"""

from __future__ import annotations

import fnmatch
import math
from dataclasses import dataclass, field

import numpy as np

from runner.errors import HeimdallError, did_you_mean

from . import means, metrics

NORMALISE = ("thresholds", "median", "mad", "minmax", "surprisal")
AGGREGATE = ("rms", "fisher", "topsis", "promethee")
CRITIC_MIN = 15          # observations CRITIC needs for a correlation matrix worth weighting by
P_FLOOR = 1e-300


@dataclass(frozen=True)
class Settings:
    metrics: dict = field(default_factory=dict)        # name → weight
    normalise: str = "thresholds"
    thresholds: dict = field(default_factory=dict)     # name → (good, bad) over the registry's
    weights: dict = field(default_factory=dict)        # object glob → page weight
    weights_by: str = "equal"
    mean: str = "rms"
    veto: float | None = None
    aggregate: str = "rms"
    dominated: bool = False
    by: tuple = ()
    baseline: object = None
    head_to_head: str | None = None                    # "<cell>/<object>" or "all": the pages the summary plays as matches

    def thresholds_of(self, name: str):
        return self.thresholds.get(name) or metrics.REGISTRY[name].thresholds


def overlaid(score: dict | None = None, over: dict | None = None) -> dict:
    """A set's `score` laid over the errand's `[score]`, as a plain dict a statistics.json can hold."""
    return {**(score or {}), **(over or {})}


def settings_of(score: dict | None = None, over: dict | None = None) -> Settings:
    """Settings from a `[score]` table with a set's `score` over it; names are checked here too (a set's are not at parse)."""
    merged = overlaid(score, over)
    given = merged.get("metrics")
    if given is None:
        weights = {n: 1.0 for n, m in metrics.REGISTRY.items() if m.default}
    elif isinstance(given, dict):
        weights = {n: float(w) for n, w in given.items()}
    else:
        weights = {n: 1.0 for n in given}
    for name in weights:
        if name not in metrics.REGISTRY:
            raise HeimdallError(f"no metric '{name}'", hint=did_you_mean(name, metrics.REGISTRY) or "heimdall explain score")
    if not weights or sum(weights.values()) <= 0:
        raise HeimdallError("[score].metrics scores nothing", hint="name at least one metric with a weight above zero")
    for key, choices in (("normalise", NORMALISE), ("aggregate", AGGREGATE), ("weights_by", ("equal", "critic"))):
        if merged.get(key, choices[0] if key != "weights_by" else "equal") not in choices:
            raise HeimdallError(f"[score].{key} is one of {', '.join(choices)}", hint=f"got {merged[key]!r}")
    mean = merged.get("mean", "rms")
    if mean not in means.MEANS_BY_NAME:
        raise HeimdallError(f"no mean '{mean}'", hint=did_you_mean(mean, means.MEANS_BY_NAME) or "heimdall explain score")
    thresholds = {}
    for name, pair in (merged.get("thresholds") or {}).items():
        if name not in metrics.REGISTRY:
            raise HeimdallError(f"no metric '{name}'", hint=did_you_mean(name, metrics.REGISTRY) or "heimdall explain score")
        thresholds[name] = (float(pair[0]), float(pair[1]))
    by = merged.get("by", ())
    return Settings(weights, merged.get("normalise", "thresholds"), thresholds, dict(merged.get("weights") or {}),
                    merged.get("weights_by", "equal"), mean, merged.get("veto"), merged.get("aggregate", "rms"),
                    bool(merged.get("dominated", False)), (by,) if isinstance(by, str) else tuple(by), merged.get("baseline"),
                    merged.get("head_to_head"))


# ── the null distributions (for surprisal and Fisher) ─────────────────────────────────────────

def _gammaincc(a: float, x: float) -> float:
    """The regularised upper incomplete gamma Q(a, x): the chi-square survival function is Q(ν/2, χ²/2)."""
    if x <= 0:
        return 1.0
    lg = math.lgamma(a)
    if x < a + 1:                                         # series for P, then Q = 1 − P
        term = total = 1.0 / a
        n = a
        for _ in range(1000):
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return max(0.0, 1.0 - total * math.exp(-x + a * math.log(x) - lg))
    b, c, d = x + 1 - a, 1e300, 1 / (x + 1 - a)          # Lentz's continued fraction
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return min(1.0, math.exp(-x + a * math.log(x) - lg) * h)


def chi2_p(chi2: float, ndf: float) -> float:
    return _gammaincc(ndf / 2.0, chi2 / 2.0)


def null_p(name: str, value: float, row: dict) -> float:
    """The probability that a true curve gives a value this large, for the metrics with a known null: chi2_ndf (with the
    row's ndf), chi2_z (one-sided Gaussian) and tail (two-sided Gaussian). Others have none."""
    if name == "chi2_ndf":
        ndf = row.get("ndf") or 0
        if not ndf:
            return math.nan
        return chi2_p(value * ndf, ndf)
    if name == "chi2_z":
        return 0.5 * math.erfc(value / math.sqrt(2))
    if name == "tail":
        return math.erfc(abs(value) / math.sqrt(2))
    raise HeimdallError(f"'{name}' has no null distribution, so no surprisal or Fisher p-value",
                        hint="chi2_ndf, chi2_z and tail have one; use normalise = \"thresholds\" for the rest")


# ── observations ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Obs:
    cell: str
    page: str
    object: str
    point: str
    row: dict
    weight: float = 1.0
    cost: dict = field(default_factory=dict)        # metric → cost (NaN where the metric is missing)
    purposes: dict = field(default_factory=dict)    # purpose → its RMS of costs
    loss: float = math.nan


def page_weight(object_path: str, page: str, st: Settings, figure_weights: dict | None) -> float:
    """A figure's weight, else the first glob of `weights` that matches the object's short name, its path or the page, else 1."""
    if figure_weights and page in figure_weights:
        return float(figure_weights[page])
    short = object_path.rsplit("/", 1)[-1]
    for glob, weight in st.weights.items():
        if fnmatch.fnmatch(short, glob) or fnmatch.fnmatch(object_path, glob) or fnmatch.fnmatch(page, glob):
            return float(weight)
    return 1.0


def observations(rows: list[dict], st: Settings, figure_weights: dict | None = None) -> list[Obs]:
    """The scored curves: a page's reference curve is not scored; when any page is measured against data, only those pages count
    (a page against its first curve ranks the curves against a generator, not the data)."""
    by_page: dict = {}
    for row in rows:
        by_page.setdefault((row["cell"], row["page"]), []).append(row)
    against_curve = {key for key, group in by_page.items() if any(r.get("is_reference") for r in group)}
    keep = [k for k in by_page if k not in against_curve] or list(by_page)
    out = []
    for key in keep:
        for row in by_page[key]:
            if not row.get("is_reference"):
                out.append(Obs(row["cell"], row["page"], row.get("object", ""), row["point"], row,
                               page_weight(row.get("object", ""), row["page"], st, figure_weights)))
    return out


# ── cost ──────────────────────────────────────────────────────────────────────────────────────

def _cost_column(name: str, obs: list[Obs], st: Settings) -> list[float]:
    """The cost of one metric for the observations of one page."""
    m = metrics.REGISTRY[name]
    values = [o.row.get(name, math.nan) for o in obs]
    if st.normalise == "thresholds":
        if st.thresholds_of(name) is None:
            raise HeimdallError(f"'{name}' has no thresholds, so it cannot be hinged", hint=f"[score.thresholds] {name} = [good, bad], or another normalise")
        return [m.loss(v, st.thresholds.get(name)) if not math.isnan(v) else math.nan for v in values]
    if st.normalise == "surprisal":
        return [(-math.log(max(null_p(name, v, o.row), P_FLOOR)) if not math.isnan(v) else math.nan) for v, o in zip(values, obs)]
    if m.better in ("higher", "none"):
        raise HeimdallError(f"'{name}' cannot be normalised against the pool ({st.normalise})", hint='use normalise = "thresholds"')
    q = np.array([m.scored(v) if not math.isnan(v) else math.nan for v in values], dtype=float)
    ok = np.isfinite(q)
    if not ok.any():
        return [math.nan] * len(q)
    good, bad = st.thresholds_of(name) or (0.0, 1.0)
    if st.normalise == "median":
        floor = max(abs(good), 1e-12)
        return list(np.where(ok, q / max(float(np.median(q[ok])), floor), np.nan))
    if st.normalise == "mad":
        med = float(np.median(q[ok]))
        mad = 1.4826 * float(np.median(np.abs(q[ok] - med)))
        z = (q - med) / max(mad, 0.1 * abs(bad - good), 1e-12)
        return list(np.where(ok, np.log1p(np.exp(np.clip(z, -50, 50))), np.nan))
    lo, hi = float(q[ok].min()), float(q[ok].max())          # minmax
    return list(np.where(ok, (q - lo) / (hi - lo) if hi > lo else 0.0, np.nan))


def critic_weights(obs: list[Obs], names: list[str]) -> dict[str, float]:
    """CRITIC's decorrelation weights: c_j = Σ_k (1 − |ρ_jk|) over the Spearman correlations of the metrics' costs, normalised
    to mean 1. A metric that says what the others say counts less. Needs CRITIC_MIN observations."""
    y = np.array([[o.cost[n] for n in names] for o in obs], dtype=float)
    y = y[np.all(np.isfinite(y), axis=1)]
    if len(y) < CRITIC_MIN:
        raise HeimdallError(f"weights_by = \"critic\" needs {CRITIC_MIN} curves with every metric; there are {len(y)}",
                            hint="its correlations are noise below that; use weights_by = \"equal\"")
    ranks = np.argsort(np.argsort(y, axis=0), axis=0).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        rho = np.nan_to_num(np.corrcoef(ranks, rowvar=False)) if len(names) > 1 else np.ones((1, 1))
    c = np.sum(1 - np.abs(rho), axis=1) if len(names) > 1 else np.ones(1)
    c = np.where(np.diag(np.atleast_2d(rho)) == 0, 0.0, c)
    total = c.sum()
    return {n: float(len(names) * v / total) if total > 0 else 1.0 for n, v in zip(names, c)}


def costs(obs: list[Obs], st: Settings) -> dict[str, float]:
    """Fill every observation's metric costs, purpose values and page loss; the metric weights used."""
    names = list(st.metrics)
    pages: dict = {}
    for o in obs:
        pages.setdefault((o.cell, o.page), []).append(o)
    for group in pages.values():
        for name in names:
            for o, c in zip(group, _cost_column(name, group, st)):
                o.cost[name] = c
    weights = dict(st.metrics)
    if st.weights_by == "critic":
        learned = critic_weights(obs, names)
        weights = {n: weights[n] * learned[n] for n in names}
    for o in obs:
        by_purpose: dict = {}
        for name in names:
            c = o.cost[name]
            if not math.isnan(c) and weights[name] > 0:
                by_purpose.setdefault(metrics.REGISTRY[name].purpose, []).append((weights[name], c))
        o.purposes = {p: math.sqrt(sum(w * c * c for w, c in v) / sum(w for w, _ in v)) for p, v in by_purpose.items()}
        o.loss = math.sqrt(sum(v * v for v in o.purposes.values()) / len(o.purposes)) if o.purposes else math.nan
    return weights


# ── scores ────────────────────────────────────────────────────────────────────────────────────

@dataclass
class PointScore:
    cell: str
    point: str
    score: float
    worst_page: str = ""
    worst_loss: float = math.nan
    veto: bool = False
    purposes: dict = field(default_factory=dict)      # purpose → RMS over pages of its value
    shares: dict = field(default_factory=dict)        # purpose → its share of the squared loss
    pages: dict = field(default_factory=dict)         # page → loss
    dominated: bool | None = None
    n_pages: int = 0


@dataclass
class Scores:
    settings: Settings
    points: list[PointScore]
    weights: dict                                     # the metric weights used
    notes: list = field(default_factory=list)

    def ranked(self, cell: str | None = None) -> list[PointScore]:
        return sorted((p for p in self.points if cell is None or p.cell == cell), key=lambda p: (p.score != p.score, p.score))


def _weighted(name: str, values, weights) -> float:
    return means.evaluate(name, values, weights)


def score(rows: list[dict], st: Settings | None = None, figure_weights: dict | None = None) -> Scores:
    """Score the points of a table's rows: see the module note. `figure_weights` is {page: weight} from the figures."""
    st = st or settings_of()
    obs = observations(rows, st, figure_weights)
    used = costs(obs, st)
    groups: dict = {}
    for o in obs:
        groups.setdefault((o.cell, o.point), []).append(o)
    out = []
    for (cell, point), group in groups.items():
        good = [o for o in group if not math.isnan(o.loss)]
        ps = PointScore(cell, point, math.nan, n_pages=len(good), pages={o.page: o.loss for o in good})
        if good:
            weights = [o.weight for o in good]
            ps.score = _weighted(st.mean, [o.loss for o in good], weights)
            worst = max(good, key=lambda o: o.loss)
            ps.worst_page, ps.worst_loss = worst.page, worst.loss
            ps.veto = st.veto is not None and worst.loss > st.veto
            for p in metrics.PURPOSES:
                have = [(o.purposes[p], o.weight) for o in good if p in o.purposes]
                if have:
                    ps.purposes[p] = means.power_mean([v for v, _ in have], [w for _, w in have], 2.0)
            total = sum(v * v for v in ps.purposes.values())
            ps.shares = {p: (v * v / total if total else 0.0) for p, v in ps.purposes.items()}
        out.append(ps)
    result = Scores(st, out, used)
    if st.aggregate != "rms":
        _aggregate(result, obs, groups)
    if st.dominated:
        _dominated(result)
    return result


def _dominated(result: Scores) -> None:
    """A point is dominated when another in its cell is no worse on every purpose and better on one (Pareto)."""
    for p in result.points:
        mine = p.purposes
        p.dominated = any(q is not p and q.cell == p.cell and q.purposes and all(
            q.purposes.get(k, math.inf) <= v for k, v in mine.items()) and any(q.purposes.get(k, math.inf) < v for k, v in mine.items())
            for q in result.points) if mine else None


# ── the other aggregators (3c): each says what it costs ───────────────────────────────────────

def _aggregate(result: Scores, obs: list[Obs], groups: dict) -> None:
    st = result.settings
    if st.aggregate == "fisher":
        result.notes.append("fisher: Σ −2 ln p over each page's χ² and tail p-values; needs chi2_ndf (with ndf) and optionally tail; "
                            "a p-value under 1e-300 is capped, so hopeless fits tie")
        for p in result.points:
            terms, weights = [], []
            for o in groups[(p.cell, p.point)]:
                x = 0.0
                for name in ("chi2_ndf", "tail"):
                    if name in st.metrics or name == "chi2_ndf":
                        v = o.row.get(name, math.nan)
                        if not math.isnan(v):
                            pv = null_p(name, v, o.row)
                            if not math.isnan(pv):
                                x += -2 * math.log(max(pv, P_FLOOR))
                terms.append(x)
                weights.append(o.weight)
            p.score = float(np.average(terms, weights=weights)) if terms else math.nan
        return
    if st.aggregate == "topsis":
        result.notes.append("topsis: 1 − closeness to the best and worst page loss among the cell's points; pool-dependent: adding "
                            "a curve changes the others' scores (rank reversal)")
        pages: dict = {}
        for o in obs:
            pages.setdefault((o.cell, o.page), []).append(o)
        best = {k: min((o.loss for o in v if not math.isnan(o.loss)), default=math.nan) for k, v in pages.items()}
        worst = {k: max((o.loss for o in v if not math.isnan(o.loss)), default=math.nan) for k, v in pages.items()}
        for p in result.points:
            dp = dm = 0.0
            for o in groups[(p.cell, p.point)]:
                k = (o.cell, o.page)
                span = worst[k] - best[k]
                if math.isnan(o.loss) or not span > 0:
                    continue
                dp += (o.weight * (o.loss - best[k]) / span) ** 2
                dm += (o.weight * (worst[k] - o.loss) / span) ** 2
            p.score = 1 - math.sqrt(dm) / (math.sqrt(dp) + math.sqrt(dm)) if dp + dm > 0 else 0.0
        return
    result.notes.append("promethee: net outranking flow Φ over the curves of each page, per metric with indifference 0.1 and strict "
                        "preference 1.0 of the good-to-bad span; score (1 − Φ)/2; pool-dependent, and a 100× blow-up costs no more than a 5×")
    names = list(st.metrics)
    pages = {}
    for o in obs:
        pages.setdefault((o.cell, o.page), []).append(o)
    flows: dict = {}
    total_w = sum(result.weights[n] for n in names) or 1.0
    for key, group in pages.items():
        for a in group:
            phi = 0.0
            for b in group:
                if a is b:
                    continue
                for n in names:
                    g, bd = st.thresholds_of(n) or (0.0, 1.0)
                    span = abs(bd - g) or 1.0
                    ca, cb = a.cost[n], b.cost[n]
                    if math.isnan(ca) or math.isnan(cb):
                        continue
                    psi = lambda d: min(1.0, max(0.0, (d - 0.1) / 0.9))      # in spans of the hinged cost
                    phi += result.weights[n] / total_w * (psi(cb - ca) - psi(ca - cb))
            flows[id(a)] = phi / max(len(group) - 1, 1)
    for p in result.points:
        vals = [(1 - flows[id(o)]) / 2 for o in groups[(p.cell, p.point)] if id(o) in flows]
        w = [o.weight for o in groups[(p.cell, p.point)] if id(o) in flows]
        p.score = float(np.average(vals, weights=w)) if vals else math.nan


# ── head to head, for one page ────────────────────────────────────────────────────────────────

def head_to_head(rows: list[dict], page: str, st: Settings | None = None) -> dict:
    """The curves of one page pairwise: for each pair (a, b) the loss difference and each metric's cost difference (a − b;
    negative: a is better). No wins are counted. `page` is the table's page name, or `cell/object` of it."""
    st = st or settings_of()
    chosen = [r for r in rows if r["page"] == page or f"{r['cell']}/{r.get('object', '').rsplit('/', 1)[-1]}" == page]
    if not chosen:
        raise HeimdallError(f"no page '{page}' in the table", hint="pages: " + ", ".join(sorted({r["page"] for r in rows})[:8]))
    obs = observations(chosen, st)
    if not obs:
        raise HeimdallError(f"page '{page}' has no curve to compare")
    costs(obs, st)
    pairs = []
    for i, a in enumerate(obs):
        for b in obs[i + 1:]:
            pairs.append({"a": a.point, "b": b.point, "loss": a.loss - b.loss,
                          "metrics": {n: a.cost[n] - b.cost[n] for n in st.metrics}})
    return {"page": chosen[0]["page"], "points": [o.point for o in obs], "pairs": pairs,
            "losses": {o.point: o.loss for o in obs}}
