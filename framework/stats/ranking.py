"""Ranking: rows in, losses out. No files, no drawing.

The rows are a statistics table's (stats/table.py): one per curve of a page, with the metric columns. A *point* is a
curve's `point`, ranked within a page *cell* (points of different cells never meet). A curve on a page is an observation;
the page's reference rows have no loss.

    cost        each metric made a cost (`cost`: hinged thresholds by default, which depend on the metric alone, so a loss is
                the same whatever else is in the pool and compares across Runs; the others use the pool of curves on the page)
    category    the RMS of a category's metric costs, metric weights counting
    page loss   the RMS over the categories that have a metric: four accuracy metrics weigh one category, not four
    point loss  the `over_pages` mean (rms by default) of a point's page losses, page weights counting

Before the loss, the gates: a page fails when a gate metric (`peak_bin_ratio`, `yield_sign`) reaches its level, or when its
page loss is above `veto_loss`; a point with a failed page is vetoed and ranks after every point that passes, whatever the
losses. Beside the loss: the worst page, each category's share of the loss, and with `dominated` whether another point beats
it on every category. `aggregate` may instead be `fisher`, `topsis` or `promethee` (each says in its note what it costs).
Lower is better throughout. `rank` returns the order and a `Method`: what was applied, and where each choice came from.
"""

from __future__ import annotations

import fnmatch
import math
from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

from runner.errors import HeimdallError, did_you_mean

from . import means, metrics

COSTS = ("thresholds", "median", "mad", "minmax", "surprisal")
AGGREGATE = ("rms", "fisher", "topsis", "promethee")
CRITIC_MIN = 15          # observations CRITIC needs for a correlation matrix worth weighting by
P_FLOOR = 1e-300


@dataclass(frozen=True, kw_only=True)
class Settings:
    metrics: dict = field(default_factory=dict)        # id → weight
    cost: str = "thresholds"                           # one of COSTS: how a metric's value becomes a cost
    thresholds: dict = field(default_factory=dict)     # id → (good, bad) over the registry's
    weights: dict = field(default_factory=dict)        # object glob → page weight
    weights_by: str = "equal"
    over_pages: str = "rms"                            # the mean of a point's page losses
    veto_loss: float | None = None                     # a page whose loss is above it fails, as a gate's does
    gates: object = True                               # True (every gate metric), False, or a tuple of gate metric ids
    aggregate: str = "rms"
    dominated: bool = False
    trim: float = 0.2                                  # α of a marginal's trimmed means
    by: tuple = ()
    baseline: object = None
    head_to_head: str | None = None                    # "<cell>/<object>" or "all": the pages the summary plays as matches
    detail: bool = False                               # the summary's per-metric sections, after their category's
    sources: dict = field(default_factory=dict)        # key → "default", "[ranking]", "set <name>" or "--<flag>"

    def thresholds_of(self, name: str):
        name = metrics.resolve(name)
        return self.thresholds.get(name) or metrics.REGISTRY[name].thresholds

    def gate_ids(self) -> tuple:
        """The gate metrics in use: every metric with a gate level, none, or those named."""
        if self.gates is True:
            return tuple(n for n, m in metrics.REGISTRY.items() if m.gate is not None)
        return tuple(self.gates or ())

    def source(self, key: str) -> str:
        return self.sources.get(key, "default")


#: The keys of [ranking], in Settings' order: what a source is kept for.
KEYS = ("metrics", "cost", "thresholds", "weights", "weights_by", "over_pages", "veto_loss", "gates", "aggregate", "dominated",
        "trim", "by", "baseline", "head_to_head", "detail")


def overlaid(table: dict | None = None, over: dict | None = None) -> dict:
    """A set's `ranking` laid over the errand's `[ranking]`, as a plain dict a statistics.json can hold."""
    return {**(table or {}), **(over or {})}


def settings_of(table: dict | None = None, flags: dict | None = None, sources: dict | None = None) -> Settings:
    """Settings from a merged `[ranking]` table (a sidecar's, or `overlaid(errand's, set's)`) with a command's `flags` over it;
    names are checked here too (a set's are not at parse). A key's source: "--<flag>" when a flag set it, else `sources[key]`
    when given (a sidecar's record), else "[ranking]" when the table has it, else "default"."""
    table, flags = dict(table or {}), dict(flags or {})
    merged = {**table, **flags}
    where = {key: ("--" + key.replace("_", "-") if key in flags else (sources or {}).get(key)
                   or ("[ranking]" if key in table else "default")) for key in KEYS}
    given = merged.get("metrics")
    if given is None:
        weights = {n: 1.0 for n, m in metrics.REGISTRY.items() if m.default}
    elif isinstance(given, dict):
        weights = {metrics.resolve(n): float(w) for n, w in given.items()}
    else:
        weights = {metrics.resolve(n): 1.0 for n in given}
    for name in weights:
        if name not in metrics.REGISTRY:
            raise HeimdallError(f"no metric '{name}'", hint=did_you_mean(name, metrics.REGISTRY) or "heimdall explain ranking")
    if not weights or sum(weights.values()) <= 0:
        raise HeimdallError("[ranking].metrics weighs no metric", hint="name at least one metric with a weight above zero")
    for key, choices in (("cost", COSTS), ("aggregate", AGGREGATE), ("weights_by", ("equal", "critic"))):
        if merged.get(key, choices[0]) not in choices:
            raise HeimdallError(f"[ranking].{key} is one of {', '.join(choices)}", hint=f"got {merged[key]!r}")
    mean = merged.get("over_pages", "rms")
    if mean not in means.MEANS_BY_NAME:
        raise HeimdallError(f"no mean '{mean}'", hint=did_you_mean(mean, means.MEANS_BY_NAME) or "heimdall explain ranking")
    thresholds = {}
    for name, pair in (merged.get("thresholds") or {}).items():
        name = metrics.resolve(name)
        if name not in metrics.REGISTRY:
            raise HeimdallError(f"no metric '{name}'", hint=did_you_mean(name, metrics.REGISTRY) or "heimdall explain ranking")
        thresholds[name] = (float(pair[0]), float(pair[1]))
    base = merged.get("baseline")
    if base is not None and not isinstance(base, (str, dict)):
        raise HeimdallError("[ranking].baseline is a point's name or a filter { quantity = \"value\" }", hint=f"got {base!r}")
    by = merged.get("by") or ()
    trim = merged.get("trim", 0.2)
    if isinstance(trim, bool) or not isinstance(trim, (int, float)) or not 0 <= trim < 0.5:
        raise HeimdallError("[ranking].trim is 0 or more and under 0.5", hint=f"got {trim!r}; 0.2 trims a fifth off each end")
    return Settings(trim=float(trim), metrics=weights, cost=merged.get("cost", "thresholds"), thresholds=thresholds,
                    weights=dict(merged.get("weights") or {}), weights_by=merged.get("weights_by", "equal"), over_pages=mean,
                    veto_loss=merged.get("veto_loss"), gates=gates_of(merged.get("gates", True)),
                    aggregate=merged.get("aggregate", "rms"), dominated=bool(merged.get("dominated", False)),
                    by=(by,) if isinstance(by, str) else tuple(by), baseline=merged.get("baseline"),
                    head_to_head=merged.get("head_to_head"), detail=bool(merged.get("detail", False)), sources=where)


def gates_of(given) -> object:
    """`[ranking].gates`: true (every gate metric), false, or a list of gate metric ids, checked."""
    if isinstance(given, bool):
        return given
    if isinstance(given, str):
        given = [given]
    if not isinstance(given, (list, tuple)):
        raise HeimdallError("[ranking].gates is true, false or a list of gate metrics", hint=f"got {given!r}")
    gates = [n for n, m in metrics.REGISTRY.items() if m.gate is not None]
    out = []
    for name in given:
        name = metrics.resolve(str(name))
        if name not in gates:
            raise HeimdallError(f"'{name}' is not a gate metric", hint="gates: " + ", ".join(gates))
        out.append(name)
    return tuple(out)


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
    row's ndf), chi2_sigma (one-sided Gaussian) and tail_excess_sigma (two-sided Gaussian). Others have none."""
    name = metrics.resolve(name)
    if name == "chi2_ndf":
        ndf = row.get("ndf") or 0
        if not ndf:
            return math.nan
        return chi2_p(value * ndf, ndf)
    if name == "chi2_sigma":
        return 0.5 * math.erfc(value / math.sqrt(2))
    if name == "tail_excess_sigma":
        return math.erfc(abs(value) / math.sqrt(2))
    raise HeimdallError(f"'{name}' has no null distribution, so no surprisal or Fisher p-value",
                        hint="chi2_ndf, chi2_sigma and tail_excess_sigma have one; use cost = \"thresholds\" for the rest")


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
    categories: dict = field(default_factory=dict)    # category → its RMS of costs
    loss: float = math.nan


def weight_of(object_path: str, page: str, st: Settings, page_weights: dict | None) -> tuple[float, str, str]:
    """A page's weight, where it came from and what it beat: its figure's `weight`, else the first glob of
    `[ranking].weights` that matches the object's short name, its path or the page, else 1."""
    short = object_path.rsplit("/", 1)[-1]
    glob = next((g for g in st.weights if fnmatch.fnmatch(short, g) or fnmatch.fnmatch(object_path, g) or fnmatch.fnmatch(page, g)), None)
    if page_weights and page in page_weights:
        beat = f"over [ranking].weights' '{glob}' = {float(st.weights[glob]):g}" if glob is not None else ""
        return float(page_weights[page]), "figure", beat
    if glob is not None:
        return float(st.weights[glob]), st.source("weights"), f"the glob '{glob}'"
    return 1.0, "default", ""


def page_weight(object_path: str, page: str, st: Settings, page_weights: dict | None) -> float:
    """A page's weight: see weight_of."""
    return weight_of(object_path, page, st, page_weights)[0]


def observations(rows: list[dict], st: Settings, page_weights: dict | None = None) -> list[Obs]:
    """The curves with a loss: a page's reference curve has none; when any page is measured against data, only those pages count
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
                               page_weight(row.get("object", ""), row["page"], st, page_weights)))
    return out


def _pages_stage(rows: list[dict], obs: list[Obs], st: Settings, page_weights: dict | None) -> tuple:
    """The record's Pages stage: the mean over pages, each page whose weight is not 1 by default with its source, and the
    pages left out and why."""
    stage = [Choice("over_pages", st.over_pages, st.source("over_pages"), "the mean of a point's page losses, page weights counting")]
    seen, plain = set(), 0
    for o in obs:
        if o.page in seen:
            continue
        seen.add(o.page)
        weight, source, note = weight_of(o.object, o.page, st, page_weights)
        if source == "default":
            plain += 1
        else:
            stage.append(Choice(f"page {o.page}", weight, source, note))
    if plain:
        stage.append(Choice("every other page", 1.0, "default", f"{plain} page(s): no figure weight and no glob of [ranking].weights"))
    every = {r["page"] for r in rows}
    if len(every - seen):
        stage.append(Choice("pages left out", len(every - seen), "table",
                            "against their first curve while other pages are against data: only pages against data are ranked"))
    empty = {o.page for o in obs} - {o.page for o in obs if o.loss == o.loss}
    if empty:
        stage.append(Choice("pages without a cost", len(empty), "table", "no metric on has a number there"))
    return tuple(stage)


# ── cost ──────────────────────────────────────────────────────────────────────────────────────

def _cost_column(name: str, obs: list[Obs], st: Settings) -> list[float]:
    """The cost of one metric for the observations of one page."""
    m = metrics.REGISTRY[name]
    values = [o.row.get(name, math.nan) for o in obs]
    if st.cost == "thresholds":
        if st.thresholds_of(name) is None:
            raise HeimdallError(f"'{name}' has no thresholds, so it cannot be hinged", hint=f"[ranking.thresholds] {name} = [good, bad], or another cost")
        return [m.cost(v, st.thresholds.get(name)) if not math.isnan(v) else math.nan for v in values]
    if st.cost == "surprisal":
        return [(-math.log(max(null_p(name, v, o.row), P_FLOOR)) if not math.isnan(v) else math.nan) for v, o in zip(values, obs)]
    if m.polarity in ("higher", "descriptor"):
        raise HeimdallError(f"'{name}' cannot be normalised against the pool ({st.cost})", hint='use cost = "thresholds"')
    q = np.array([m.oriented(v) if not math.isnan(v) else math.nan for v in values], dtype=float)
    ok = np.isfinite(q)
    if not ok.any():
        return [math.nan] * len(q)
    good, bad = st.thresholds_of(name) or (0.0, 1.0)
    if st.cost == "median":
        floor = max(abs(good), 1e-12)
        return list(np.where(ok, q / max(float(np.median(q[ok])), floor), np.nan))
    if st.cost == "mad":
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
    """Fill every observation's metric costs, category values and page loss; the metric weights used."""
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
        by_category: dict = {}
        for name in names:
            c = o.cost[name]
            if not math.isnan(c) and weights[name] > 0:
                by_category.setdefault(metrics.REGISTRY[name].category, []).append((weights[name], c))
        o.categories = {p: math.sqrt(sum(w * c * c for w, c in v) / sum(w for w, _ in v)) for p, v in by_category.items()}
        o.loss = math.sqrt(sum(v * v for v in o.categories.values()) / len(o.categories)) if o.categories else math.nan
    return weights


# ── losses ────────────────────────────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class PointLoss:
    cell: str
    point: str
    loss: float = math.nan                            # NaN: no scored page
    rank: int | None = None                           # None: vetoed, or no loss
    vetoed: bool = False
    failed_pages: int = 0                             # its pages that fail a gate (or are above veto_loss)
    gate_reason: str = ""                             # which gates, on how many pages, the largest value
    worst_page: str = ""
    worst_loss: float = math.nan
    categories: dict = field(default_factory=dict)    # category → RMS over pages of its cost
    shares: dict = field(default_factory=dict)        # category → its share of the squared loss
    pages: dict = field(default_factory=dict)         # page → loss
    values: dict = field(default_factory=dict)        # metric → median over its pages of its value, for default and shown metrics
    dominated: bool | None = None
    n_pages: int = 0


@dataclass(frozen=True)
class Choice:
    name: str                                         # what was chosen: "cost", "gate peak_bin_ratio", "cells"
    value: object                                     # JSON-safe: str, number, bool, list or dict of those
    source: str                                       # "registry", "default", "[ranking]", "set <name>", "--<flag>", "table"
    note: str = ""                                    # the sentence a reader needs beside it


def _said(value) -> str:
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (list, tuple)):
        return ", ".join(_said(v) for v in value) or "none"
    if isinstance(value, dict):
        return ", ".join(f"{k} = {_said(v)}" for k, v in value.items()) or "none"
    return str(value)


@dataclass(frozen=True)
class Method:
    """What a ranking applied, stage by stage, each choice with its source: what the presenters render, never restate."""
    gates: tuple = ()
    metrics: tuple = ()
    cost: tuple = ()
    category: tuple = ()
    page_loss: tuple = ()
    pages: tuple = ()
    order: tuple = ()
    marginals: tuple = ()
    optin: tuple = ()
    STAGES: ClassVar[tuple] = ("gates", "metrics", "cost", "category", "page_loss", "pages", "order", "marginals", "optin")
    TITLES: ClassVar[dict] = {"gates": "Gates", "metrics": "Metrics", "cost": "Cost", "category": "Category",
                              "page_loss": "Page loss", "pages": "Pages", "order": "Order", "marginals": "Marginals",
                              "optin": "Opt-in aggregators and views"}

    def as_dict(self) -> dict:
        return {stage: [{"name": c.name, "value": c.value, "source": c.source, "note": c.note} for c in getattr(self, stage)]
                for stage in self.STAGES}

    def lines(self, *stages) -> list[str]:
        """A sentence a choice: "<name>: <value> (<source>). <note>"; every stage when none is named."""
        return [f"{c.name}: {_said(c.value)} ({c.source})." + (f" {c.note}" if c.note else "")
                for stage in (stages or self.STAGES) for c in getattr(self, stage)]

    def _of(self, stage: str, keep=lambda c: True) -> list[str]:
        return [line for c in getattr(self, stage) if keep(c) for line in Method(**{stage: (c,)}).lines(stage)]

    def made_by(self, kind: str, metrics=(), quantity: str = "") -> list[str]:
        """The sentences under a table, the choices that shaped its numbers, by its kind: "leaderboard"; "values" (the metric
        values of `metrics`); "category" (a category's ranking, its `metrics`); "detail" (a metric's own tables); "marginal"
        (`quantity`'s); "baseline"; "head_to_head"; "key" (the reading key: the cost, the gates, the order)."""
        def of_metrics(c):
            return c.name == "values shown" or any(c.name == n or c.name.endswith(f" of {n}") for n in metrics)

        def not_vetoed(c):
            return not c.name.startswith("vetoed ")

        def over_pages(c):
            return c.name == "over_pages"
        parts = {"leaderboard": [("gates", not_vetoed), ("cost",), ("category",), ("page_loss",), ("pages",), ("order",)],
                 "values": [("metrics", of_metrics)],
                 "category": [("metrics", of_metrics), ("category",), ("pages",)],
                 "detail": [("metrics", of_metrics), ("pages", over_pages), ("optin", lambda c: c.name == "detail")],
                 "marginal": [("marginals", lambda c: not c.name.startswith("strata of ") or c.name == f"strata of {quantity}")],
                 "baseline": [("optin", lambda c: c.name == "baseline"), ("pages", over_pages)],
                 "head_to_head": [("optin", lambda c: c.name == "head_to_head")],
                 "key": [("cost",), ("gates", not_vetoed), ("order",)]}[kind]
        return [line for stage, *keep in parts for line in self._of(stage, *keep)]


@dataclass(kw_only=True)
class Ranking:
    settings: Settings
    points: list                                      # PointLoss, in rank order
    cells: list                                       # the cells, in the rows' order
    flat: bool                                        # one order over every cell, else an order a cell
    method: Method
    weights: dict                                     # the metric weights used (CRITIC's when weights_by = "critic")
    notes: list = field(default_factory=list)
    marginals: list = field(default_factory=list)     # Marginal, when `values` is given
    baseline: object = None                           # Baseline, when settings.baseline is set and `values` given
    values: dict = field(default_factory=dict)        # {point: {quantity: value}}, as given: the leaderboard's quantity columns

    def of(self, cell: str | None = None) -> list[PointLoss]:
        """A cell's points in order; every point when `cell` is None."""
        return [p for p in self.points if cell is None or p.cell == cell]


#: The metrics a point's `values` tell: those scored by default and those shown.
TOLD = tuple(n for n, m in metrics.REGISTRY.items() if m.default or m.shown)


def _median(values) -> float:
    have = [float(v) for v in values if v is not None and v == v]
    return float(np.median(have)) if have else math.nan


def _weighted(name: str, values, weights) -> float:
    return means.evaluate(name, values, weights)


def rank(rows: list[dict], settings: Settings | None = None, page_weights: dict | None = None, values: dict | None = None) -> Ranking:
    """Rank the points of a table's rows: see the module note. `page_weights` is {page: weight} from the figures; `values`
    {point: {quantity: value}}, for the marginals and the baseline."""
    st = settings or settings_of()
    obs = observations(rows, st, page_weights)
    used = costs(obs, st)
    groups: dict = {}
    for o in obs:
        groups.setdefault((o.cell, o.point), []).append(o)
    out = []
    for (cell, point), group in groups.items():
        good = [o for o in group if not math.isnan(o.loss)]
        ps = PointLoss(cell=cell, point=point, n_pages=len(good), pages={o.page: o.loss for o in good},
                       values={name: _median([o.row.get(name, math.nan) for o in group]) for name in TOLD})
        if good:
            weights = [o.weight for o in good]
            ps.loss = _weighted(st.over_pages, [o.loss for o in good], weights)
            worst = max(good, key=lambda o: o.loss)
            ps.worst_page, ps.worst_loss = worst.page, worst.loss
            for p in metrics.CATEGORIES:
                have = [(o.categories[p], o.weight) for o in good if p in o.categories]
                if have:
                    ps.categories[p] = means.power_mean([v for v, _ in have], [w for _, w in have], 2.0)
            total = sum(v * v for v in ps.categories.values())
            ps.shares = {p: (v * v / total if total else 0.0) for p, v in ps.categories.items()}
        out.append(ps)
    result = Ranking(settings=st, points=out, cells=list(dict.fromkeys(r["cell"] for r in rows)), flat=True, method=Method(),
                     weights=used, values=dict(values or {}))
    if st.aggregate != "rms":
        _aggregate(result, obs, groups)
    if st.dominated:
        _dominated(result)
    gates = _gates(result, obs, groups)
    order = _order(result, obs)
    marginal_stage = ()
    if values:
        result.marginals, marginal_stage = marginals(result.points, values, st)
        if st.baseline:
            result.baseline = baseline(result, values)
    result.method = Method(gates=gates, order=order, pages=_pages_stage(rows, obs, st, page_weights), marginals=marginal_stage,
                           **_stages(result, rows, obs))
    return result


# ── the record of how the numbers were made ────────────────────────────────────────────────────

COST_NOTES = {
    "thresholds": "each metric oriented (lower: T(m), higher: −T(m), one: |log10 m|; T is log10 on a log scale), hinged on its "
                  "thresholds to z = max(0, (q − q(g)) / (q(b) − q(g))) and compressed to c = log₂(1 + z): 0 within good, 1 at bad, "
                  "2 at z = 3. The metric's own thresholds, so a loss does not depend on the other curves",
    "median": "each metric's oriented value over the median of the page's curves: pool-dependent, and not compressed",
    "mad": "each metric's distance to the page's median in units of their spread, through a softplus: pool-dependent, and not compressed",
    "minmax": "each metric 0 for the page's best curve, 1 for its worst: pool-dependent, and not compressed",
    "surprisal": "−ln of the probability a true curve reads as badly, under the metric's null: of the curve alone, not compressed",
}
OPTIN_NOTES = {
    "aggregate": "how a point's pages become its loss; rms is the Grand Ranking, the others are opt-in and say what they cost",
    "dominated": "a column marking a point another beats on every category (Pareto); it moves no rank",
    "weights_by": "equal: the metric weights as given; critic: learned from the metrics' correlations, so pool-dependent",
    "baseline": "the point every loss is also shown against; it moves no rank",
    "head_to_head": "the pages the summary plays as matches; it moves no rank",
    "detail": "each metric's ranking, page cells against curves and object table, after its category; it moves no rank",
}


def _why_not(name: str) -> str:
    m = metrics.REGISTRY[name]
    if m.polarity == "descriptor":
        return "a descriptor: it describes a curve and has no better or worse"
    if m.gate is not None and not m.thresholds:
        return "a gate only"
    if m.shown:
        return "shown, not scored unless [ranking].metrics names it"
    return "not named in [ranking].metrics"


def _stages(result: "Ranking", rows: list[dict], obs: list[Obs]) -> dict:
    """The record's Metrics, Cost, Category, Page loss and Opt-in stages."""
    st = result.settings
    columns = {k for r in rows for k in r if k in metrics.REGISTRY}
    stage = []
    for name, weight in st.metrics.items():
        m = metrics.REGISTRY[name]
        if name not in columns:
            stage.append(Choice(name, "not in this table", "table", "its column is missing: it is skipped, not scored as zero"))
            continue
        stage.append(Choice(name, f"{m.polarity}, {m.scale} scale", "registry", f"category {m.category}"))
        good_bad = st.thresholds_of(name)
        if good_bad is not None:
            mine = name in st.thresholds
            stage.append(Choice(f"thresholds of {name}", list(good_bad), st.source("thresholds") if mine else "registry",
                                "" if mine else m.why))
        stage.append(Choice(f"weight of {name}", result.weights.get(name, weight), st.source("metrics") if st.weights_by == "equal"
                            else st.source("weights_by"), "" if st.weights_by == "equal" else f"given {weight:g}, times CRITIC's"))
    stage.append(Choice("values shown", "median over a point's pages", "default",
                        "each default and shown metric's value beside the loss: it explains the loss and is not in it"))
    gates = set(st.gate_ids())
    for name in sorted(columns - set(st.metrics) - gates, key=list(metrics.REGISTRY).index):
        stage.append(Choice(name, "computed, not scored", "registry", _why_not(name)))
    cost = (Choice("cost", st.cost, st.source("cost"), COST_NOTES[st.cost] + "."),)
    used: dict = {}
    for name in st.metrics:
        if name in columns:
            used.setdefault(metrics.REGISTRY[name].category, []).append(name)
    category = (Choice("mean in a category", "rms", "default", "the root mean square of its metrics' costs, metric weights counting"),
                *(Choice(f"category {key}", names, "registry") for key, names in used.items()))
    had = list(dict.fromkeys(k for o in obs for k in o.categories))
    page_loss = (Choice("mean over categories", "rms", "default",
                        "the root mean square over the categories with a cost, each equal: four metrics of one category weigh as one"),
                 Choice("categories with a cost", had, "table"))
    optin = []
    for key in ("aggregate", "dominated", "weights_by", "baseline", "head_to_head", "detail"):
        value = getattr(st, key)
        note = OPTIN_NOTES[key]
        if key == "aggregate" and value != "rms":
            note = next((n for n in result.notes if n.startswith(value)), note)
        if key == "weights_by" and value == "critic":
            note += ": " + ", ".join(f"{n} {w:.3g}" for n, w in result.weights.items())
        optin.append(Choice(key, value if value is not None else "none", st.source(key), note))
    return {"metrics": tuple(stage), "cost": cost, "category": category, "page_loss": page_loss, "optin": tuple(optin)}


# ── the gates and the order ───────────────────────────────────────────────────────────────────

def _fails(name: str, value) -> bool:
    """A gate's test: the value is finite and at the gate's level or more, or is +inf; NaN never fails."""
    if value is None or value != value:
        return False
    return value == math.inf or (math.isfinite(value) and value >= metrics.REGISTRY[name].gate)


def _reason(name: str, worst: float, failed: int, of: int) -> str:
    pages = f"on {failed} of {of} page{'s' if of != 1 else ''}"
    if name == "peak_bin_ratio":
        return f"a bin 10^{worst:.3g} × reference {pages}" if math.isfinite(worst) else f"a bin with an infinite ratio to its reference {pages}"
    if name == "yield_sign":
        return f"a yield of zero or less {pages}"
    if name == "veto_loss":
        return f"a page loss of up to {worst:.3g} {pages}"
    return f"{name} up to {worst:.3g} {pages}"


def _gates(result: Ranking, obs: list[Obs], groups: dict) -> tuple:
    """Mark each point's failed pages, its veto and its reason; the record's Gates stage."""
    st = result.settings
    stage = []
    if st.gates is False:
        stage.append(Choice("gates", False, st.source("gates"), "no gate metric is applied"))
    elif st.gates is not True:
        stage.append(Choice("gates", list(st.gates), st.source("gates"), "only these gate metrics are applied"))
    used = []
    for name in st.gate_ids():
        level = metrics.REGISTRY[name].gate
        if not any(name in o.row for o in obs):
            stage.append(Choice(f"gate {name}", level, "table", f"not evaluated: no `{name}` column (a table written before format 3)"))
            continue
        used.append(name)
        stage.append(Choice(f"gate {name}", level, "registry", f"a page fails at {name} ≥ {level:g} (or +inf); a missing value never fails"))
    if st.veto_loss is not None:
        stage.append(Choice("veto_loss", st.veto_loss, st.source("veto_loss"), "a page whose loss is above it fails as a gate's does"))
    by_point = {(p.cell, p.point): p for p in result.points}
    for key, group in groups.items():
        p = by_point[key]
        failed: set = set()
        reasons = []
        checks = [(name, lambda o, n=name: o.row.get(n)) for name in used]
        if st.veto_loss is not None:
            checks.append(("veto_loss", lambda o: o.loss))
        for name, value_of in checks:
            bad = [o for o in group if (_fails(name, value_of(o)) if name != "veto_loss" else value_of(o) > st.veto_loss)]
            if bad:
                failed |= {o.page for o in bad}
                reasons.append(_reason(name, max(value_of(o) for o in bad), len(bad), len(group)))
        p.failed_pages, p.vetoed, p.gate_reason = len(failed), bool(failed), "; ".join(reasons)
    for p in result.points:
        if p.vetoed:
            stage.append(Choice(f"vetoed {p.cell + '/' if len(result.cells) > 1 else ''}{p.point}", p.failed_pages, "table", p.gate_reason))
    return tuple(stage)


def _flat(obs: list[Obs]) -> tuple[bool, str]:
    """One order over every cell when each cell's scored pages are the same objects against the same reference."""
    cells: dict = {}
    for o in obs:
        cells.setdefault(o.cell, set()).add((o.object.rsplit("/", 1)[-1], str(o.row.get("reference", ""))))
    if len(cells) <= 1:
        return True, "one page cell"
    if len({frozenset(v) for v in cells.values()}) == 1:
        return True, f"the {len(cells)} page cells have the same objects against the same reference"
    return False, f"the {len(cells)} page cells differ in their objects or their reference, so a point is ranked within its cell"


def _order(result: Ranking, obs: list[Obs]) -> tuple:
    """Put the points in rank order and number the passing ones; the record's Order stage. The key: passing points with a
    loss, then those with no scored page, then the vetoed (fewer failed pages first); then the loss (NaN last), then the
    name. Losses equal to three significant figures share a rank: 1, 2, 2, 4."""
    result.flat, why = _flat(obs)

    def key(p: PointLoss):
        group = 2 if p.vetoed else 1 if p.loss != p.loss else 0
        return (group, p.failed_pages if p.vetoed else 0, math.inf if p.loss != p.loss else p.loss, p.point)
    bands = [result.points] if result.flat else [[p for p in result.points if p.cell == c] for c in result.cells]
    ordered = []
    for band in bands:
        band = sorted(band, key=key)
        last, place = None, 0
        for i, p in enumerate(band, 1):
            if p.vetoed or p.loss != p.loss:
                p.rank = None
                continue
            shown = f"{p.loss:.3g}"
            place = place if shown == last else i
            p.rank, last = place, shown
        ordered += band
    result.points[:] = ordered
    return (Choice("rule", "passing points by loss; then points with no scored page; then the vetoed, fewer failed pages first, "
                           "then by loss", "default", "no loss can buy a failed page back"),
            Choice("ties", "equal to 3 significant figures share a rank (1, 2, 2, 4), tied points by name", "default"),
            Choice("cells", "flat" if result.flat else "banded", "table", why))


def _dominated(result: Ranking) -> None:
    """A point is dominated when another in its cell is no worse on every category and better on one (Pareto)."""
    for p in result.points:
        mine = p.categories
        p.dominated = any(q is not p and q.cell == p.cell and q.categories and all(
            q.categories.get(k, math.inf) <= v for k, v in mine.items()) and any(q.categories.get(k, math.inf) < v for k, v in mine.items())
            for q in result.points) if mine else None


# ── the other aggregators (3c): each says what it costs ───────────────────────────────────────

def _aggregate(result: Ranking, obs: list[Obs], groups: dict) -> None:
    st = result.settings
    if st.aggregate == "fisher":
        result.notes.append("fisher: Σ −2 ln p over each page's χ² and tail p-values; needs chi2_ndf (with ndf) and optionally tail_excess_sigma; "
                            "a p-value under 1e-300 is capped, so hopeless fits tie")
        for p in result.points:
            terms, weights = [], []
            for o in groups[(p.cell, p.point)]:
                x = 0.0
                for name in ("chi2_ndf", "tail_excess_sigma"):
                    if name in st.metrics or name == "chi2_ndf":
                        v = o.row.get(name, math.nan)
                        if not math.isnan(v):
                            pv = null_p(name, v, o.row)
                            if not math.isnan(pv):
                                x += -2 * math.log(max(pv, P_FLOOR))
                terms.append(x)
                weights.append(o.weight)
            p.loss = float(np.average(terms, weights=weights)) if terms else math.nan
        return
    if st.aggregate == "topsis":
        result.notes.append("topsis: 1 − closeness to the best and worst page loss among the cell's points; pool-dependent: adding "
                            "a curve changes the others' losses (rank reversal)")
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
            p.loss = 1 - math.sqrt(dm) / (math.sqrt(dp) + math.sqrt(dm)) if dp + dm > 0 else 0.0
        return
    result.notes.append("promethee: net outranking flow Φ over the curves of each page, per metric with indifference 0.1 and strict "
                        "preference 1.0 of the good-to-bad span; loss (1 − Φ)/2; pool-dependent, and a 100× blow-up costs no more than a 5×")
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
        p.loss = float(np.average(vals, weights=w)) if vals else math.nan


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


def matched_pages(rows: list[dict], want: str | None) -> list[str]:
    """The pages `[ranking].head_to_head` names, in the rows' order: every page with a curve for "all", else those whose name
    or "<cell>/<object>" (the object's short name) is `want`; none when unset."""
    if not want:
        return []
    pages = list(dict.fromkeys(r["page"] for r in rows if not r["is_reference"]))
    if want == "all":
        return pages
    named = {r["page"] for r in rows if r["page"] == want or f"{r['cell']}/{str(r.get('object', '')).rsplit('/', 1)[-1]}" == want}
    return [p for p in pages if p in named]


# ── marginals and baselines ───────────────────────────────────────────────────────────────────
#
# `values` is {point: {quantity: value}}: what each point's sweep chose (the plot document's members, kept in statistics.json). A
# marginal is a mean of the points' losses, never the loss of a mean curve: a curve merged from several points has no entry
# in `values`, so it never enters one.

DELTA = 0.01            # a point's log loss is ln(δ + L): finite for a point within good everywhere


@dataclass(frozen=True)
class MarginalRow:
    value: str
    n: int                  # matched strata this value has a loss in
    g: int                  # trimmed from each end
    vetoed: int             # the slice's vetoed points, out of every number
    unmatched: int          # strata of the slice where no other value survives
    effect: float           # E_v, in ln: the trimmed mean of ℓ(p) − ℓ̄(stratum); NaN when n = 0
    effect_se: float
    level: float            # M_v: the trimmed mean of ℓ(p) over the slice
    vs_best: float          # the trimmed mean of the paired differences against the best row; 0 for the best
    vs_best_se: float
    same_as_best: bool
    mark: str               # "", "one stratum", "n = 2: not robust", or why there is no number


@dataclass(frozen=True)
class Marginal:
    quantity: str
    rows: tuple             # MarginalRow, ordered by effect, rows without one last
    strata: tuple           # the other varied quantities the strata are made of
    headline: str
    confounded: str = ""    # today's sentence, for a quantity with no matched stratum


def varied(values: dict, ranked: set | None = None) -> dict[str, list[str]]:
    """The quantities with at least two values among the points (those in `ranked`, when given): {quantity: its values, in the order met}."""
    seen: dict[str, dict] = {}
    for point, chosen in values.items():
        if ranked is not None and point not in ranked:
            continue
        for quantity, value in chosen.items():
            seen.setdefault(quantity, {})[str(value)] = None
    return {a: list(v) for a, v in seen.items() if len(v) >= 2}


def _confounded(quantity: str, every: dict[str, list[str]], values: dict, points: set) -> list[str]:
    """For `quantity`, which values of the other varied quantities are not spread evenly over its values: each point counts once."""
    out = []
    mine = every[quantity]
    for b, b_values in every.items():
        if b == quantity:
            continue
        for bv in b_values:
            count = {a: sum(1 for p in points if values[p].get(quantity) == a and values[p].get(b) == bv) for a in mine}
            have = [a for a, n in count.items() if n]
            if len(have) < len(mine):
                out.append(f"{b} = {bv} only with {quantity} = {', '.join(have)}" if have else f"{b} = {bv} has no point")
            elif len(set(count.values())) > 1:
                out.append(f"{b} = {bv} has unequal numbers of points over {quantity}'s values")
    return out


def _ell(loss: float) -> float:
    return math.log(DELTA + loss)


def _shown_ratio(x: float) -> str:
    return f"×{math.exp(x):.2f}" if math.isfinite(x) else "–"


def marginals(points: list, values: dict, settings: Settings) -> tuple[list, tuple]:
    """For each quantity in `settings.by` (every varied one when it names none, in the order met), a row a value: its matched
    effect E (the trimmed mean of ℓ(p) − ℓ̄(stratum) over the slice's points whose stratum holds another value), its level M
    (the trimmed mean of ℓ over the slice) and the paired test against the best row; vetoed points are out and counted.
    ℓ = ln(δ + L), a stratum a point's values on the other varied quantities. (the Marginals, the record's Marginals stage)."""
    alpha = settings.trim
    known = [p for p in points if p.point in values and p.loss == p.loss]
    every = varied(values, {p.point for p in known})
    names = list(settings.by) or list(every)
    for quantity in names:
        if quantity not in every:
            raise HeimdallError(f"[ranking].by: '{quantity}' is not a quantity these points vary",
                                hint=("quantities varied: " + ", ".join(every)) if every else "no quantity is varied among the ranked points")
    out = []
    for quantity in names:
        others = tuple(q for q in every if q != quantity)
        stratum = {p.point: tuple(str(values[p.point].get(q)) for q in others) for p in known}
        alive = [p for p in known if not p.vetoed]
        members: dict = {}
        for p in alive:
            members.setdefault(stratum[p.point], []).append(p)
        mean_of = {r: float(np.mean([_ell(p.loss) for p in ps])) for r, ps in members.items()}
        per_value = {}                                    # value → {stratum: the mean ℓ of its points there}
        rows = []
        for value in every[quantity]:
            mine = [p for p in known if str(values[p.point].get(quantity)) == value]
            slice_ = [p for p in mine if not p.vetoed]
            cells: dict = {}
            for p in slice_:
                cells.setdefault(stratum[p.point], []).append(_ell(p.loss))
            per_value[value] = {r: float(np.mean(v)) for r, v in cells.items()}
            matched = {r: float(np.mean([v - mean_of[r] for v in vs])) for r, vs in cells.items() if len(members[r]) >= 2}
            effect = means.trimmed_se(list(matched.values()), alpha)
            level = means.trimmed_se([_ell(p.loss) for p in slice_], alpha)
            vetoed = len(mine) - len(slice_)
            n = effect.n
            if n == 0:
                mark = (f"every point vetoed ({vetoed} of {len(mine)})" if mine and not slice_ else "no stratum holds another value")
            else:
                mark = "one stratum" if n == 1 else "n = 2: not robust" if n == 2 else ""
            rows.append(dict(value=value, n=n, g=effect.g, vetoed=vetoed, unmatched=len(cells) - len(matched),
                             effect=effect.mean, effect_se=effect.se, level=level.mean, mark=mark))
        matched_any = any(r["n"] for r in rows)
        key = "effect" if matched_any else "level"
        rows.sort(key=lambda r: (r[key] != r[key], r[key] if r[key] == r[key] else 0.0))
        best = rows[0]["value"] if rows and rows[0][key] == rows[0][key] else None
        done = []
        for r in rows:
            if best is None or r[key] != r[key]:
                done.append(MarginalRow(**r, vs_best=math.nan, vs_best_se=math.nan, same_as_best=False))
                continue
            if r["value"] == best:
                done.append(MarginalRow(**r, vs_best=0.0, vs_best_se=0.0, same_as_best=True))
                continue
            shared = [per_value[r["value"]][k] - per_value[best][k] for k in per_value[r["value"]] if k in per_value[best]]
            d = means.trimmed_se(shared, alpha)
            same = d.se == d.se and abs(d.mean) <= 2 * d.se
            done.append(MarginalRow(**r, vs_best=d.mean, vs_best_se=d.se, same_as_best=same))
        confounded = "" if matched_any else "; ".join(_confounded(quantity, every, values, {p.point for p in known}))
        out.append(Marginal(quantity, tuple(done), others, _headline(quantity, done, key), confounded))
    return out, _marginals_stage(settings, out)


def _headline(quantity: str, rows: list, key: str) -> str:
    """A quantity's headline: the best value, its ratio to the next, the strata it holds, and those indistinguishable from it."""
    ranked = [r for r in rows if getattr(r, key) == getattr(r, key)]
    if not ranked:
        return f"{quantity}: no value has a loss that is not vetoed"
    best = ranked[0]
    if len(ranked) == 1:
        return f"{quantity}: {best.value} alone has a loss"
    nxt = ranked[1]
    against = -nxt.vs_best if key == "effect" else best.level - nxt.level
    line = f"{quantity}: {best.value}, {_shown_ratio(against)} against {nxt.value}"
    line += f", {best.n} strata" if key == "effect" else ", by level alone: no stratum holds two values"
    same = [r.value for r in ranked[1:] if r.same_as_best]
    return line + (f"; indistinguishable from the best: {', '.join(same)}" if same else "")


def _marginals_stage(settings: Settings, found: list) -> tuple:
    stage = [Choice("by", list(settings.by) or "every varied quantity", settings.source("by"), "the quantities whose marginals are shown"),
             Choice("trim", settings.trim, settings.source("trim"),
                    "α: g = ⌊α n⌋ values off each end, at least one at n ≥ 3, none at n ≤ 2; the error is Tukey and McLaughlin's"),
             Choice("δ", DELTA, "default", "a point's log loss is ln(δ + L): a ratio of losses, finite at 0"),
             Choice("order", "the matched effect E", "default",
                    "E: the trimmed mean of ℓ(p) − ℓ̄(its stratum), over the slice's points whose stratum holds another value; "
                    "the level M, the trimmed mean of ℓ over the slice, is shown beside and orders a quantity with no matched stratum"),
             Choice("against the best", "paired", "default",
                    "each value against the best over the strata both hold, its differences trimmed; ≈ best within 2 SE; "
                    "one test a value, not corrected for multiplicity"),
             Choice("vetoed", "out", "default", "a vetoed point is in no slice and no stratum's mean; each row counts its own")]
    for m in found:
        stage.append(Choice(f"strata of {m.quantity}", list(m.strata) or ["none"], "table",
                            "; ".join(f"{r.value}: n {r.n}, g {r.g}, vetoed {r.vetoed}, unmatched {r.unmatched}" for r in m.rows)))
    return tuple(stage)


@dataclass
class BaselineRow:
    cell: str
    point: str
    partner: str                                    # the baseline point it is taken against
    loss: float
    base: float
    delta: float                                    # loss − base: negative is better
    objects: dict = field(default_factory=dict)     # object → the page loss less the partner's
    is_baseline: bool = False


@dataclass
class Baseline:
    filter: dict
    rows: list = field(default_factory=list)
    unmatched: list = field(default_factory=list)   # (cell, point, why): never dropped quietly


def baseline_filter(given, values: dict) -> dict:
    """`[ranking].baseline` as a filter {quantity: value}: a table as it is, a point's name as that point's every quantity."""
    if isinstance(given, str):
        if given not in values:
            raise HeimdallError(f"[ranking].baseline: no point '{given}'", hint="a point's name, or a filter { quantity = \"value\" }")
        return dict(values[given])
    return {str(k): str(v) for k, v in dict(given).items()}


def baseline(result: Ranking, values: dict, given=None) -> Baseline:
    """Each point's Δ against the baseline point equal to it on every quantity the filter leaves alone (the filter's values on the
    others): its Δloss, and its Δloss on each object. A point with no partner, or none of whose values are known, is listed as
    unmatched with the reason."""
    given = result.settings.baseline if given is None else given
    if not given:
        raise HeimdallError("no baseline: [ranking].baseline is not set")
    wanted = baseline_filter(given, values)
    known = set().union(*(set(a) for a in values.values())) if values else set()
    for quantity in wanted:
        if quantity not in known:
            raise HeimdallError(f"[ranking].baseline: '{quantity}' is not a quantity of these points", hint="quantities: " + ", ".join(sorted(known)))
    by_values: dict = {}
    for ps in result.points:
        if ps.point in values:
            by_values.setdefault(frozenset((k, str(v)) for k, v in values[ps.point].items()), []).append(ps)
    out = Baseline(wanted)
    for ps in result.points:
        if ps.point not in values:
            out.unmatched.append((ps.cell, ps.point, "not a point of the sweep (a merged curve), or its values were not recorded"))
            continue
        mine = {k: str(v) for k, v in values[ps.point].items()}
        partners = by_values.get(frozenset({**mine, **wanted}.items()), [])
        partner = next((q for q in partners if q.cell == ps.cell), partners[0] if partners else None)
        if partner is None:
            out.unmatched.append((ps.cell, ps.point, "no point equal to it but for " + ", ".join(f"{k} = {v}" for k, v in wanted.items())))
            continue
        if ps.loss != ps.loss or partner.loss != partner.loss:
            out.unmatched.append((ps.cell, ps.point, f"it or its baseline {partner.point} has no loss"))
            continue
        objects = {}
        for page, loss in ps.pages.items():
            name = page.rsplit("/", 1)[-1]
            other = next((v for k, v in partner.pages.items() if k.rsplit("/", 1)[-1] == name), None)
            if other is not None:
                objects[name] = loss - other
        out.rows.append(BaselineRow(ps.cell, ps.point, partner.point, ps.loss, partner.loss, ps.loss - partner.loss, objects,
                                    partner is ps or all(mine.get(k) == v for k, v in wanted.items())))
    return out
