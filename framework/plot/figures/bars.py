"""statistics.csv as bar graphs (V162, V164): results/…/statistics/<set>/bars/<cell>/<object>.<fmt>, one per drawn
page, and the summary (V174). Drawing only: the numbers are stats/ (metrics and means from Paint's measured bins), the
losses are stats/ranking.py's, the sentences are the registries' notes (stats/metrics.py).

The summary is a document (V196): `summary_model` builds it as paper.py's model, and paper.py lays it out on A4 portrait
pages. First the leaderboard: each point's loss, its worst page and a veto (a page that fails a gate, or a loss beyond `[ranking].veto_loss`:
ranked last), and a column a category, the question each asks beside; then a section per category that has a metric on (what it asks, a ranking of the
points, and for each metric of it a ranking, its page cells against its curves and a table, a row per point and a column
per object); a head-to-head section only for the pages `[ranking].head_to_head` names. statistics/<set>/summary.pdf holds
every page; a PNG or SVG is a file a page in statistics/<set>/summary/, numbered in the PDF's order (summary_01.png, …).
Each page ends with its items' notes, each once. Matplotlib (the conda base's), Agg.

A page's image is the panels of the metrics on, in the grid that gives each bar the most height, one bar per curve in
the page's order, each metric on its own axis (no two scales on one): one series, one colour; the values at the bars'
tips, in text ink; the reference curve (a page without data) is named, not drawn. Rows are statstable.statistics_of's
(runner/statstable.py).
"""

from __future__ import annotations

import math
from pathlib import Path

from runner import plugins
from runner.errors import HeimdallError
from stats import metrics as M
from stats import ranking as S

paper = plugins.load(Path(__file__).with_name("paper.py"), "paper")
webpage = plugins.load(Path(__file__).with_name("webpage.py"), "webpage")

SERIES = paper.SERIES         # one series: the palette's first categorical slot
INK, MUTED, GRID, SURFACE = paper.INK, paper.MUTED, paper.GRID, paper.SURFACE

#: What each summary page's number is and how Paint computes it (src/Apps/Paint/Transform.hh), as its footnote.
COMPARED = ("Each page as drawn (after voiding, alignment and normalisation), over its x span (after auto-range and the gutters), against its "
            "reference: the page's data, else its first curve. Compared bins: the reference's bins that the curve "
            "covers exactly, its own bins summed onto them.")
TABLE_NOTE = ("A row per point (its label, under its page cell's band), a column per object; rms: the root mean square of the "
              "row's numbers. ref: the page's reference curve itself (compared with nothing); –: no number (no bins "
              "compared, or not on that page).")
RANKING_NOTE = ("Per point (its page cell · its label), the {mean} of its {name} over the pages where it was "
                "compared (their number in brackets), {order}.")
APART = "Points of different page cells never meet: a page holds one cell's points."
COUNTED_DATA = ("Only the pages compared against data count: on a page compared against its first curve, that curve "
                "has no loss.")
COUNTED_CURVE = ("No page here has data: each is compared against its first curve, which has no loss there, so a "
                 "point that is a page's reference has no loss on it.")
CROSSED_NOTE = ("Page cells against curves: each entry a point's mean over the pages where it was compared "
                "(its ranking's number), its page cell one way and its curve the other; rms: the root mean square of the "
                "row's, the column's, or all the entries; bold: the best in its row, closest to agreement; –: no "
                "such point, or no number.")

#: A page image's grids of panels (columns); a panel's least width, the room around a panel row
#: (its title, its x labels, the gap), the space between panels, a bar's most and least height, inches.
GRIDS = (2, 3, 6)
PANEL, PANEL_ROOM, PANEL_GAP, MOST_BAR, LEAST_BAR = 1.4, 0.75, 0.3, 0.32, 0.12
STRIP = 0.35                                                    # the page image's title strip
KEY = 0.3                                                       # its foot: what an orange or a pink bar means (V205)


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _infinite(value) -> bool:
    return isinstance(value, float) and math.isinf(value)


def _shown(value: float) -> str:
    return f"{value:,.0f}" if 100 <= abs(value) < 1e6 else f"{value:.3g}"


def _label(text: str) -> str:
    """A curve label as mathtext reads it: its $…$ kept, unbalanced dollars dropped."""
    from runner.labels import mathtext
    try:
        return mathtext(text)
    except Exception:                                   # a label mathtext cannot take is drawn as written
        return text.replace("$", "")


def _style(ax, labels: list[str]) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", colors=MUTED, labelsize=7, length=0)
    from matplotlib.ticker import MaxNLocator
    ax.xaxis.set_major_locator(MaxNLocator(4))                  # a narrow panel's numbers apart
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylim(len(labels) - 0.5, -0.5)               # the page's first curve on top



def _bars(ax, values: list, notes: list[str], size: float = 8, panel: float = 2.0) -> bool:
    """Thin bars from one zero line, each value at its tip; a missing value says why. The axis runs both ways from 0
    (a mean ratio may be below it), as far as paper.reach: a bar far beyond the rest is cut at the axis's end, its
    value beside with » (or « below 0); blue above 0 and orange below, violet and golden yellow when cut, pink and
    red when absurd or infinite (paper.colour_of). Beside the bars
    is room for their values as measured, in a panel `panel` inches wide, so no text is drawn off it (V205: one
    10⁸ pixels off it was more than FreeType could raster). Whether a bar was cut."""
    finite = [v for v in values if _finite(v)]
    reach = paper.reach(finite) or 1.0
    absurd = paper.absurd_from(finite)
    said: dict[int, tuple[float, str, str]] = {}
    for i, value in enumerate(values):
        if _finite(value) or _infinite(value):
            drawn = min(reach, max(-reach, value))
            text = _shown(value) if _finite(value) else ("∞" if value > 0 else "−∞")
            if drawn != value:
                text = paper.CUT[0] + text if drawn >= 0 else text + paper.CUT[1]
            said[i] = (drawn, text, paper.colour_of(value, reach, absurd))
    high = max([drawn for drawn, _, _ in said.values()] + [0.0])
    low = min([drawn for drawn, _, _ in said.values()] + [0.0])
    span = (high - low) or reach
    gap = 0.04                                                    # inches from a bar's tip to its value
    right = max([paper.width(text, size) for drawn, text, _ in said.values() if drawn >= 0] + [0.0]) + gap
    left = max([paper.width(text, size) + gap for drawn, text, _ in said.values() if drawn < 0] + [0.0])
    per_inch = span / max(panel - left - right, 0.3 * panel)       # the bars keep a third of the panel at least
    for i, note in enumerate(notes):
        if i not in said:
            ax.text(gap * per_inch, i, note, va="center", ha="left", color=MUTED, fontsize=size, style="italic")
            continue
        drawn, text, colour = said[i]
        ax.barh(i, drawn, height=0.55, color=colour, edgecolor=SURFACE, linewidth=1)
        ax.text(drawn + gap * per_inch if drawn >= 0 else drawn - gap * per_inch, i, text, va="center",
                ha="left" if drawn >= 0 else "right", color=INK, fontsize=size)
    ax.set_xlim(low - left * per_inch, high + right * per_inch)
    return any(colour not in (paper.ABOVE, paper.BELOW) for _, _, colour in said.values())



def panels(names=None) -> list[tuple[str, str]]:
    """A page image's panels: the metrics `names` (the default metrics when None) as (name, title)."""
    return [(n, M.title_of(n)) for n in (names if names is not None else default_names())]


def default_names() -> list[str]:
    return [n for n, m in M.REGISTRY.items() if m.default]


def grid(curves: int, label: float, panels: int = 6) -> tuple[int, int, float, int]:
    """A page image's grid for `curves` curves whose labels take `label` inches, of `panels` panels: (columns, rows, a
    bar's height, curves a page). The grid gives each bar the most height with every panel at least PANEL wide (the
    narrowest when none does); a bar is at most MOST_BAR, and below LEAST_BAR the curves continue on further pages, in
    the grid that holds the most."""
    room = paper.A4[1] - 2 * paper.EDGE - STRIP - KEY
    options = list(dict.fromkeys((min(c, panels), -(-panels // min(c, panels))) for c in GRIDS))
    fits = [(c, r) for c, r in options if (paper.WIDTH - label - (c - 1) * PANEL_GAP) / c >= PANEL] or [options[0]]
    each = {g: (room - g[1] * PANEL_ROOM) / g[1] for g in fits}               # a panel's height for bars
    best = max(fits, key=lambda g: each[g])
    if each[best] / max(curves, 1) >= LEAST_BAR:
        return best[0], best[1], min(MOST_BAR, each[best] / max(curves, 1)), max(curves, 1)
    per = max(1, int(each[best] // LEAST_BAR))
    return best[0], best[1], min(MOST_BAR, each[best] / per), per


def _number(value):
    """A cell's number, whether read as text or typed: None when it has none."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) or math.isinf(value) else None


def _page_figure(rows: list[dict], title: str, columns: int, bar: float, label: float, plt, shown):
    """One A4 page of a page's statistics: a panel a metric of `shown` ((name, title)s) in `columns` columns, a bar per curve."""
    fig = plt.figure(figsize=paper.A4, facecolor=SURFACE)
    w, h = paper.A4
    labels = [_label(r["curve"]) for r in rows]
    panel = (paper.WIDTH - label - (columns - 1) * PANEL_GAP) / columns
    height = bar * len(rows)
    size = 8 if bar >= 0.16 else 7
    reference = rows[0]["reference"] if rows else ""
    fig.text(paper.SIDE / w, 1 - (paper.EDGE + STRIP / 2) / h, f"{title}  ·  against {_label(reference)}",
             color=MUTED, fontsize=9, ha="left", va="center")
    cut = False
    for k, (key, name) in enumerate(shown):
        r, c = divmod(k, columns)
        left = paper.SIDE + label + c * (panel + PANEL_GAP)
        top = paper.EDGE + STRIP + r * (height + PANEL_ROOM) + 0.25
        ax = fig.add_axes((left / w, 1 - (top + height) / h, panel / w, height / h))
        notes = ["reference" if r_["is_reference"] else "no value" for r_ in rows]
        values = [None if r_["is_reference"] else _number(r_.get(key)) for r_ in rows]
        _style(ax, labels)
        cut = _bars(ax, values, notes, size, panel) or cut
        if key in M.REGISTRY and M.REGISTRY[key].polarity == "one":
            ax.axvline(1, color=MUTED, linewidth=0.8, linestyle=":")          # the reference's own
        ax.set_title(name, color=INK, fontsize=9, loc="left")
        ax.set_yticks(range(len(labels)), labels if c == 0 else [""] * len(labels), color=INK, fontsize=size)
    if cut:                                                     # the key, at the page's foot
        fig.text(paper.SIDE / w, paper.EDGE / h, "\n".join(paper.wrap(paper.CUT_KEY, paper.WIDTH, 7)), color=MUTED,
                 fontsize=7, ha="left", va="bottom")
    return fig


def page(rows: list[dict], target: Path, formats: list[str], title: str, names=None) -> list[Path]:
    """One page's statistics on A4: a panel a metric on (`names`, else the default ones), a bar per curve; more curves
    than a page holds continue on further pages (`target`.pdf holds them all, `target`_NN.png one each)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    shown = panels(names)
    label = max([paper.width(_label(r["curve"]), 8) for r in rows] + [0.5]) + 0.12
    columns, _, bar, per = grid(len(rows), label, len(shown))
    chunks = [rows[s:s + per] for s in range(0, len(rows), per)] or [rows]
    written = []
    target.parent.mkdir(parents=True, exist_ok=True)
    pdf = None
    try:
        for number, chunk in enumerate(chunks, 1):
            fig = _page_figure(chunk, title if len(chunks) == 1 else f"{title} ({number}/{len(chunks)})",
                               columns, bar, label, plt, shown)
            for fmt in formats:
                if fmt == "pdf" and len(chunks) > 1:
                    if pdf is None:
                        from matplotlib.backends.backend_pdf import PdfPages
                        pdf = PdfPages(target.with_suffix(".pdf"))
                        written.append(target.with_suffix(".pdf"))
                    pdf.savefig(fig, facecolor=SURFACE)
                    continue
                path = target.with_suffix(f".{fmt}") if len(chunks) == 1 else \
                    target.with_name(f"{target.name}_{number:02d}.{fmt}")
                fig.savefig(path, dpi=150, facecolor=SURFACE)
                written.append(path)
            plt.close(fig)
    finally:
        if pdf is not None:
            pdf.close()
    return written


# ── the summary's tables: a metric each (V174) ───────────────────────────────────────────────────────────

LIGHT, DARK = (0.937, 0.957, 0.984), (0.078, 0.271, 0.478)     # #eff4fb → #14457a: one hue, light to dark
NEUTRAL, WARM = (0.941, 0.941, 0.933), (0.561, 0.239, 0.078)   # a ratio's 1 (#f0f0ee), and below it (#8f3d14)

#: How a table's cells are shaded, by its rule, as its subtitle says.
SHADING = {"cost": "darker is costlier: palest within good, darkest at bad, or at the table's worst when that is beyond", "linear": "darker is larger",
           "ratio": "blue above 1, orange below, darker further from 1 (log scale: 2 and 0.5 alike)"}


def _rule(name: str) -> str:
    """How a metric's cells are shaded: "ratio" for a number that is best at 1; "cost" for one with thresholds (the hinged
    cost, so a colour means the same on every table); "linear" for a descriptor."""
    m = M.REGISTRY[name]
    return "ratio" if m.polarity == "one" else "cost" if m.thresholds else "linear"


def _short(objects: list[str]) -> dict[str, str]:
    """Each object's column title: its short name without -x01-y01 when that stays unique."""
    import re
    names = {o: o.rsplit("/", 1)[-1] for o in objects}
    trimmed = {o: re.sub(r"-x01-y01$", "", n) for o, n in names.items()}
    return trimmed if len(set(trimmed.values())) == len(objects) else names


def _shade(fraction: float, low=LIGHT, high=DARK) -> tuple:
    f = min(max(fraction, 0.0), 1.0)
    return tuple(a + (b - a) * f for a, b in zip(low, high))


def _fraction(name: str, st, rule: str, found: list[float]):
    """How dark a number's cell is, 0 to 1, among the numbers `found`, by a metric's rule."""
    if rule == "cost":
        m = M.REGISTRY[name]
        cost = lambda v: m.loss(v, st.thresholds.get(name))          # noqa: E731
        top = max([1.0] + [c for v in found if _finite(c := cost(v))])
        return lambda v: min(cost(v) / top, 1.0) if _finite(v) else 0.0   # a table past bad still tells its worst from its next
    low, high = min(found), max(found)
    spread = max([abs(math.log10(v)) for v in found if v > 0] + [0.0]) if rule == "ratio" else 0.0

    def fraction(value: float) -> float:
        if rule == "ratio":
            return 0.0 if not spread or value <= 0 else abs(math.log10(value)) / spread
        return 0.0 if high == low else (value - low) / (high - low)
    return fraction


def _rms(values) -> float:
    return math.sqrt(sum(v * v for v in values) / len(values))


def _mean(values: list[float], rule: str, st=None) -> float | None:
    """A row's or a point's number over pages: the `[ranking].over_pages` mean of its values (a ratio's above 0), the root mean square
    by default, so a page far off weighs more and no two pages cancel."""
    if rule == "ratio":
        values = [v for v in values if v > 0]
    if not values:
        return None
    if st is None or st.over_pages == "rms":
        return _rms(values)
    from stats import means
    return means.evaluate(st.over_pages, values)


def _points(rows: list[dict]) -> dict[str, str]:
    """Each point's name in the summary: its page cell · its label, in curve order."""
    points = {}
    for r in rows:
        points.setdefault(r["point"], f"{r['cell']} · {_label(r['curve'])}" if r.get("cell") else _label(r["curve"]))
    return points


def _rows_of(rows: list[dict]) -> list[dict]:
    """The rows the summary reads: an overlay figure's curves are other objects of a point, not its own page."""
    return [r for r in rows if not str(r.get("object", "")).startswith("/overlay/")]


def _means(rows: list[dict], key: str, st=None) -> dict[str, tuple[float, int]]:
    """Each point's mean of a metric over the pages where it was compared, and their number."""
    rule = _rule(key)
    by: dict[str, list[float]] = {}
    for r in rows:
        if not r["is_reference"] and _finite(r.get(key)) and (rule != "ratio" or r[key] > 0):
            by.setdefault(r["point"], []).append(float(r[key]))
    return {p: (_mean(v, rule, st), len(v)) for p, v in by.items()}


def _distance(key: str, value) -> float | None:
    """How far a number is from agreement, smaller better: a ratio's |log10|, how far from 1 either way; the negative of a
    higher-is-better metric; else the number itself. None when it has none."""
    if not _finite(value):
        return None
    m = M.REGISTRY[key]
    if m.polarity == "one":
        return abs(math.log10(value)) if value > 0 else None
    return -float(value) if m.polarity == "higher" else float(value)


def _table(key: str, title: str, labels: list[str], headers: list[str], cells: list[list[tuple]], notes: tuple,
           tail: int = 0, bold: frozenset = frozenset(), groups: list | None = None, pinned: frozenset = frozenset()):
    """A table of the summary's document: `title`'s first line its title, the rest its subtitle; each cell (text,
    background, ink[, bold, align]); the rows in `bold` with their labels bold, those in `pinned` (a mean) last
    however the page sorts the table. With `groups` (each row's page cell, V197), a band names each group above its
    rows."""
    head, _, rest = title.partition("\n")
    rows, current = [], None
    for i, (label, line) in enumerate(zip(labels, cells)):
        if groups is not None and groups[i] != current:
            current = groups[i]
            rows.append(paper.Row(current, band=True))
        rows.append(paper.Row(label, [paper.Cell(*cell) for cell in line], bold=i in bold, pinned=i in pinned))
    return paper.Table(key, head, list(headers), rows, subtitle=rest, tail=tail, notes=tuple(notes))


def _parts(rows: list[dict]) -> dict[str, tuple[str, str]]:
    """Each point's page cell and its curve's label."""
    parts = {}
    for r in rows:
        parts.setdefault(r["point"], (r.get("cell") or "", _label(r["curve"])))
    return parts


def _grouped(order: list[str], parts: dict) -> bool:
    """Whether rows of these points are grouped under their cells' bands (V197): when they span two cells or
    more."""
    return len({parts[p][0] for p in order}) > 1 and all(parts[p][0] for p in order)


def _by_cell(order: list[str], parts: dict) -> list[str]:
    """The points with each cell's together, the cells in the order they first come, each cell's points in
    theirs."""
    cells = list(dict.fromkeys(parts[p][0] for p in order))
    return sorted(order, key=lambda p: cells.index(parts[p][0]))


def _notes_of(name: str, st, notes: dict) -> None:
    notes[f"stat-{name}"] = M.describe(name, st.thresholds.get(name))


def _ranking(rows: list[dict], key: str, notes: dict, st):
    """A metric's ranking (V174): each point's mean over the pages where it was compared, as sorted bars, best first (a
    ratio: closest to 1 first, bars from 1); None when no point has one."""
    rule = _rule(key)
    rows = _rows_of(rows)
    points, means = _points(rows), _means(rows, key, st)
    means = {p: v for p, v in means.items() if v[0] is not None}
    if not means:
        return None
    ratio = rule == "ratio"
    ranked = sorted(means, key=lambda p: (_distance(key, means[p][0]), points[p]))
    higher = M.REGISTRY[key].polarity == "higher"
    order = "closest to 1 first, bars from 1: blue above, orange below" if ratio else "highest first" if higher else "lowest first"
    name = M.title_of(key)
    notes[f"ranking-{key}"] = RANKING_NOTE.format(name=name, order=order, mean=_mean_name(st))
    _notes_of(key, st, notes)
    notes["compared"] = COMPARED
    values = [means[p][0] for p in ranked]
    if paper.any_cut([v - 1.0 if ratio else max(v, 0.0) for v in values]):
        order += ". " + paper.CUT_KEY                                       # V205
    return paper.Ranking(f"{key}-ranking", f"{name}: each point's {_mean_name(st)} over its pages (pages compared)",
                         [f"{points[p]}  ({means[p][1]})" for p in ranked], values,
                         subtitle=order, base=1.0 if ratio else 0.0,
                         colours=(DARK, WARM) if ratio else (SERIES, SERIES),
                         notes=(f"ranking-{key}", f"stat-{key}", "compared"))


def _mean_name(st) -> str:
    return "root mean square" if st is None or st.over_pages == "rms" else st.over_pages.replace("_", " ")


def _crossed(rows: list[dict], key: str, notes: dict, st):
    """A metric's page cells against its curves (V198): each entry that point's mean over its pages (as its
    ranking's), the longer list down the rows, a mean column and a mean row, each row's best bold. None with one cell,
    when no curve is in two cells, or when a cell repeats a label."""
    rule = _rule(key)
    rows = _rows_of(rows)
    parts, means = _parts(rows), _means(rows, key, st)
    cells = list(dict.fromkeys(c for c, _ in parts.values()))
    curves = list(dict.fromkeys(v for _, v in parts.values()))
    if len(cells) < 2 or len(curves) < 2 or not all(cells) or len(set(parts.values())) < len(parts):
        return None
    if not any(sum(1 for _, v in parts.values() if v == curve) > 1 for curve in curves):
        return None                                     # no curve in two cells: nothing crosses
    grid_ = {parts[p]: means[p][0] for p in parts if p in means and means[p][0] is not None}
    found = [v for v in grid_.values() if rule != "ratio" or v > 0]
    if not found:
        return None
    down, across = (cells, curves) if len(cells) >= len(curves) else (curves, cells)

    def entry(r, c):
        return grid_.get((r, c) if down is cells else (c, r))
    row_means = {r: _mean([v for c in across if (v := entry(r, c)) is not None], rule, st) for r in down}
    column_means = {c: _mean([v for r in down if (v := entry(r, c)) is not None], rule, st) for c in across}
    overall = _mean(found, rule, st)
    scale = _fraction(key, st, rule, [v for v in found + list(row_means.values()) + list(column_means.values())
                                      if v is not None and (rule != "ratio" or v > 0)])

    def cell(value, bold=False):
        if value is None:
            return ("–", SURFACE, MUTED, False)
        f = scale(value)
        pole = (NEUTRAL, DARK if value >= 1 else WARM) if rule == "ratio" else (LIGHT, DARK)
        return (_shown(value), _shade(f, *pole), "white" if f > 0.55 else INK, bold)
    styled = []
    for r in down:
        values = [entry(r, c) for c in across]
        near = [d for v in values if (d := _distance(key, v)) is not None]
        best = min(near) if near else None
        styled.append([cell(v, best is not None and _distance(key, v) == best) for v in values] + [cell(row_means[r])])
    styled.append([cell(column_means[c]) for c in across] + [cell(overall)])
    notes["crossed"] = CROSSED_NOTE
    _notes_of(key, st, notes)
    notes["compared"] = COMPARED
    way = "page cells against curves" if down is cells else "curves against page cells"
    return _table(f"{key}-crossed", f"{M.title_of(key)}: {way}\n{SHADING[rule]}; bold: the best in its row", list(down) + ["rms"],
                  list(across) + ["rms"], styled, ("crossed", f"stat-{key}", "compared"), tail=1,
                  bold=frozenset({len(down)}), pinned=frozenset({len(down)}))


def _natural(objects) -> list[str]:
    """Objects in natural order: d2 before d10."""
    import re
    return sorted(objects, key=lambda o: [int(s) if s.isdigit() else s for s in re.split(r"(\d+)", o)])


def _table_of(rows: list[dict], key: str, notes: dict, st):
    """A metric's table (V174): a row per point (in curve order, its page cell before its label) and a column per
    object, each cell the point's number on that object's page, then its mean; the reference curve's cell says "ref", a
    missing one "–". Shaded by its rule, its text white on dark. None when no point has a number."""
    rule = _rule(key)
    rows = _rows_of(rows)
    points, parts, cells = _points(rows), _parts(rows), {}
    for r in rows:
        cells[(r["point"], r["object"])] = r
    objects = _natural({r["object"] for r in rows})
    if not points or not objects:
        return None
    short = _short(objects)
    references = sorted({str(r["reference"]) for r in rows})

    def number(point, obj):
        r = cells.get((point, obj))
        return None if r is None or r["is_reference"] or not _finite(r.get(key)) else float(r[key])
    means = {point: _mean([v for o in objects if (v := number(point, o)) is not None], rule, st) for point in points}
    found = [v for p in points for o in objects if (v := number(p, o)) is not None]
    if rule == "ratio":
        found = [v for v in found if v > 0]
    if not found:
        return None
    scale = _fraction(key, st, rule, found)
    styled = []
    for point in points:
        row = []                                                # (text, background, ink) a cell
        for obj in objects + [None]:                            # None: the mean
            r = cells.get((point, obj)) if obj is not None else None
            value = means[point] if obj is None else number(point, obj)
            if r is not None and r["is_reference"]:
                row.append(("ref", SURFACE, MUTED))
            elif value is None:
                row.append(("–", SURFACE, MUTED))
            else:
                f = scale(value)
                pole = (NEUTRAL, DARK if value >= 1 else WARM) if rule == "ratio" else (LIGHT, DARK)
                row.append((_shown(value), _shade(f, *pole), "white" if f > 0.55 else INK))
        styled.append(row)
    against = (f" against {', '.join(_label(r) for r in references)}" if len(references) <= 2
               else " against each page's reference")
    _notes_of(key, st, notes)
    notes["table"], notes["compared"] = TABLE_NOTE, COMPARED
    order = list(points)
    grouped = _grouped(order, parts)
    if grouped:
        at = {p: i for i, p in enumerate(order)}
        order = _by_cell(order, parts)
        styled = [styled[at[p]] for p in order]
    return _table(key, f"{M.title_of(key)}{against}\n{SHADING[rule]}",
                  [parts[p][1] if grouped else points[p] for p in order],
                  [short[o] for o in objects] + ["rms"], styled, (f"stat-{key}", "compared", "table"), tail=1,
                  groups=[parts[p][0] for p in order] if grouped else None)


# ── the leaderboard: ranked by stats/ranking.py ────────────────────────────────────────────────────────────

def _on(rows: list[dict], st) -> list[str]:
    """The metrics on that the rows have a number for, grouped by category in the registry's order."""
    have = [n for n in st.metrics if any(_number(r.get(n)) is not None for r in rows)]
    categories = list(M.CATEGORIES)
    named = list(st.metrics)
    return sorted(have, key=lambda n: (categories.index(M.REGISTRY[n].category), named.index(n)))


def _loss_text(st) -> str:
    """How a loss is made, as `st` sets it."""
    norm = {"thresholds": "Each metric becomes a cost: 0 at or inside its good threshold, 1 at its bad one, in proportion "
                          "beyond; a metric's own thresholds, so a loss does not move when other curves are added.",
            "median": "Each metric becomes a cost: its value over the median of the page's curves.",
            "mad": "Each metric becomes a cost from its distance to the page's median in units of their spread.",
            "minmax": "Each metric becomes a cost: 0 for the page's best curve, 1 for its worst.",
            "surprisal": "Each metric becomes a cost: the minus log of the probability a true curve would read as badly."}
    return (f"{norm[st.cost]} A category's value is the root mean square of its metrics' costs; a curve's loss on a page "
            f"is the root mean square over the categories, so a category with four metrics weighs as one with a single metric. "
            f"A point's loss is the {_mean_name(st)} of its losses over its pages, a page weighted as set "
            f"(0: every page within good, 1: every page at bad; lower is better). Worst page: the page where its loss is largest"
            + (f"; veto: that loss is beyond {st.veto_loss:g}." if st.veto_loss is not None else "."))


def _leaderboard_tables(rows: list[dict], names: list[str], st, notes: dict, ranked):
    """The leaderboard table: a row per point in the engine's order (one order, or one a page cell; the vetoed last), its loss,
    its worst page, a veto when a point has one or `veto_loss` is set, and a column a category (its value, shaded as a cost).
    Then the categories' list."""
    rows = _rows_of(rows)
    points, parts = _points(rows), _parts(rows)
    by_point = {(p.cell, p.point): p for p in ranked.points}
    cell_of = {r["point"]: r.get("cell") or "" for r in rows}
    categories = [p for p in M.CATEGORIES if any(M.REGISTRY[n].category == p for n in names)]
    order = [s.point for s in ranked.points if s.point in points and cell_of[s.point] == s.cell]
    banded = not ranked.flat and len({cell_of[p] for p in order}) > 1 and all(cell_of[p] for p in order)
    shown, labels, groups = [], [], []
    for p in order:                                   # the engine's order: within a cell when banded, the vetoed last
        s = by_point[(cell_of[p], p)]
        shown.append(p)
        labels.append(f"{s.rank}. {parts[p][1] if banded else points[p]}" if s.rank else f"– {parts[p][1] if banded else points[p]}")
        groups.append(cell_of[p])
    vetoed = [by_point[(cell_of[p], p)] for p in shown if by_point[(cell_of[p], p)].vetoed]
    veto = st.veto_loss is not None or bool(vetoed)

    finite = [v for p in shown for v in (by_point[(cell_of[p], p)].loss, by_point[(cell_of[p], p)].worst_loss,
                                          *by_point[(cell_of[p], p)].categories.values()) if math.isfinite(v)]
    top = max([1.0] + finite)

    def cost_cell(v):
        if v != v:
            return ("–", SURFACE, MUTED)
        f = min(v / top, 1.0)
        return ("∞" if math.isinf(v) else _shown(v), _shade(f), "white" if f > 0.55 else INK)
    headers = ["loss", "worst page", "worst"] + (["veto"] if veto else []) + \
        [M.CATEGORIES[p] for p in categories] + (["dominated"] if st.dominated else [])
    styled = []
    for p in shown:
        s = by_point[(cell_of[p], p)]
        row = [cost_cell(s.loss), (s.worst_page.rsplit("/", 1)[-1] if s.worst_page else "–", SURFACE, INK, False, "left"),
               cost_cell(s.worst_loss)]
        if veto:
            row.append(("veto", WARM, "white", True) if s.vetoed else ("", SURFACE, INK))
        row += [cost_cell(s.categories.get(q, math.nan)) for q in categories]
        if st.dominated:
            row.append(("yes", SURFACE, INK) if s.dominated else ("–", SURFACE, MUTED) if s.dominated is None else ("", SURFACE, INK))
        styled.append(row)
    with_data = any(not any(r["is_reference"] for r in rows if r["page"] == page) for page in {r["page"] for r in rows})
    notes["loss"], notes["apart"] = _loss_text(st), APART
    notes["counted"] = COUNTED_DATA if with_data else COUNTED_CURVE
    if vetoed:
        notes["vetoed"] = ("Vetoed: a page that fails a gate, ranked after every point that passes, whatever its loss; fewer failed "
                           "pages first. " + "; ".join(f"{points[s.point]}: {s.gate_reason}" for s in vetoed) + ".")
    leaderboard = _table("leaderboard", "Leaderboard: each point's loss\nlower is better; darker: costlier, darkest at the table's worst (at least bad)",
                         labels, headers, styled, ("loss", "apart", "counted") + (("vetoed",) if vetoed else ()),
                       groups=groups if banded else None) if shown else None
    for p in categories:
        notes[f"category-{p}"] = f"{M.CATEGORIES[p]}. {M.QUESTIONS[p]}"
    listed = []
    for p in categories:
        here = [n for n in names if M.REGISTRY[n].category == p]
        listed.append((M.CATEGORIES[p], [(", ".join(M.title_of(n) for n in here), SURFACE, INK, False, "left")]))
    categories_table = _table("categories", "The categories: what each asks\nthe metrics on under each", [l for l, _ in listed], ["metrics on"],
                            [c for _, c in listed], tuple(f"category-{p}" for p in categories)) if listed else None
    return [t for t in (leaderboard, categories_table) if t is not None]


def _category_sections(rows: list[dict], names: list[str], st, notes: dict, ranked) -> list:
    """A section a category with a metric on: what it asks, a ranking of its value, then each metric's ranking, its page cells
    against its curves, and its table."""
    sections = []
    rows_ = _rows_of(rows)
    points = _points(rows_)
    by_point = {(p.cell, p.point): p for p in ranked.points}
    cell_of = {r["point"]: r.get("cell") or "" for r in rows_}
    for category in M.CATEGORIES:
        here = [n for n in names if M.REGISTRY[n].category == category]
        if not here:
            continue
        items = []
        notes[f"category-{category}"] = f"{M.CATEGORIES[category]}. {M.QUESTIONS[category]}"
        values = {p: by_point[(cell_of[p], p)].categories[category] for p in points
                  if (cell_of[p], p) in by_point and category in by_point[(cell_of[p], p)].categories}
        if values:
            ranked = sorted(values, key=lambda p: (values[p], points[p]))
            notes["loss"] = _loss_text(st)
            items.append(paper.Ranking(f"category-{category}-ranking",
                                       f"{M.CATEGORIES[category]}: each point's value over its pages",
                                       [points[p] for p in ranked], [values[p] for p in ranked],
                                       subtitle="lowest first; 1: its metrics at their bad thresholds",
                                       notes=(f"category-{category}", "loss")))
        for key in here:
            for item in (_ranking(rows, key, notes, st), _crossed(rows, key, notes, st), _table_of(rows, key, notes, st)):
                if item is not None:
                    items.append(item)
        sections.append(paper.Section(f"category-{category}", M.CATEGORIES[category], items))
    return sections


def _matches(rows: list[dict], st, notes: dict) -> list:
    """The head-to-head section: for each page `[ranking].head_to_head` names, its curves pairwise, the row's loss less the
    column's (blue: the row's curve is better), each pair on its own and no wins counted."""
    want = st.head_to_head
    if not want:
        return []
    rows = _rows_of(rows)
    pages = list(dict.fromkeys(r["page"] for r in rows if not r["is_reference"]))
    if want != "all":
        pages = [p for p in pages if any(f"{r['cell']}/{r['object'].rsplit('/', 1)[-1]}" == want or r["page"] == want
                                         for r in rows if r["page"] == p)]
    notes["h2h"] = ("Each pair of a page's curves: the row's loss less the column's on that page (negative: the row's curve "
                    "is closer to agreement), blue where the row's is better, orange where it is worse, darker further from "
                    "even; no wins are counted. loss: the curve's own loss on the page.")
    items = []
    for n, name in enumerate(pages, 1):
        try:
            out = S.head_to_head(rows, name, st)
        except HeimdallError:                               # a page with no loss on it
            continue
        parts = _parts(rows)                                # a page holds one cell's points: their labels alone
        losses = out["losses"]
        biggest = max([abs(p["loss"]) for p in out["pairs"] if math.isfinite(p["loss"])] + [1e-12])
        diff = {(p["a"], p["b"]): p["loss"] for p in out["pairs"]}
        diff.update({(b, a): -v for (a, b), v in list(diff.items())})
        members = out["points"]
        short = {p: parts[p][1] if p in parts else p for p in members}
        styled = []
        for a in members:
            row = []
            for b in members:
                v = diff.get((a, b))
                if a == b or v is None or v != v:
                    row.append(("–", SURFACE, MUTED))
                else:
                    f = min(abs(v) / biggest, 1.0)                  # a curve with an infinite loss: ±∞, the darkest
                    row.append(("+∞" if v == math.inf else "−∞" if v == -math.inf else f"{v:+.2f}",
                                _shade(f, NEUTRAL, DARK if v < 0 else WARM), "white" if f > 0.55 else INK))
            row.append((_shown(losses[a]) if losses.get(a) == losses.get(a) else "–", SURFACE, INK))
            styled.append(row)
        items.append(_table(f"head-to-head-{n}", f"Head to head: {out['page']}" + ("\nthe row's loss less the column's"
                                                                                  if n == 1 else ""),
                            [short[p] for p in members], [short[p] for p in members] + ["loss"], styled, ("h2h",), tail=1))
    return [paper.Section("head-to-head", "Head to head", items)] if items else []


def _shown_delta(v: float) -> str:
    return "∞" if math.isinf(v) else f"{v:+.2f}"


def _marginals(rows: list[dict], st, notes: dict, ranked) -> list:
    """The marginals section: for each quantity (`[ranking].by`, else every varied quantity) a table of its values, the mean loss
    of the points having each, their number and a column a category; a confounded quantity says which values confound it."""
    found = ranked.marginals
    items = []
    for marginal in found:
        if len(marginal.rows) < 2:
            continue
        categories = [p for p in M.CATEGORIES if any(p in r[3] for r in marginal.rows)]
        top = max([1.0] + [r[1] for r in marginal.rows if math.isfinite(r[1])])

        def cost(v):
            f = min(v / top, 1.0) if math.isfinite(v) else 1.0
            return ("∞" if math.isinf(v) else _shown(v), _shade(f), "white" if f > 0.55 else INK)
        styled = [[cost(loss), (str(n), SURFACE, INK)] + [cost(by[p]) if p in by else ("–", SURFACE, MUTED) for p in categories]
                  for _, loss, n, by in marginal.rows]
        key = f"marginal-{marginal.quantity}"
        notes["marginals"] = ("A marginal: the mean of the losses of the points having each value of the quantity (not the loss of a "
                              "mean curve), their number, and each category's value likewise; best first. Confounded: other quantities' "
                              "values that share this quantity's values unevenly, so the difference between them is not this quantity's alone.")
        if marginal.confounded:
            notes[f"confounded-{marginal.quantity}"] = f"Confounded: {'; '.join(marginal.confounded)}."
        items.append(_table(key, f"By {marginal.quantity}\nthe mean loss of the points having each value" + (
            "; confounded" if marginal.confounded else ""), [r[0] for r in marginal.rows],
            ["loss", "points"] + [M.CATEGORIES[p] for p in categories], styled,
            ("marginals",) + ((f"confounded-{marginal.quantity}",) if marginal.confounded else ())))
    return [paper.Section("marginals", "Marginals", items)] if items else []


def _baseline(rows: list[dict], st, notes: dict, ranked) -> list:
    """The baseline section: each point's Δloss against its baseline partner and its Δloss on each object (negative, blue:
    better than the baseline); the points with no partner listed."""
    result = ranked.baseline
    if result is None:
        return []
    if not result.rows and not result.unmatched:
        return []
    parts = _parts(_rows_of(rows))
    objects = _natural({o for r in result.rows for o in r.objects})
    shown = [r for r in result.rows if not r.is_baseline] or result.rows
    biggest = max([abs(v) for r in shown for v in [r.delta, *r.objects.values()] if math.isfinite(v)] + [1e-12])

    def delta(v):
        if v is None or v != v:
            return ("–", SURFACE, MUTED)
        f = min(abs(v) / biggest, 1.0) if math.isfinite(v) else 1.0
        return (_shown_delta(v), _shade(f, NEUTRAL, DARK if v < 0 else WARM), "white" if f > 0.55 else INK)
    by_cell = list(dict.fromkeys(r.cell for r in result.rows))
    banded = len(by_cell) > 1 and all(by_cell)
    ordered = [r for c in by_cell for r in sorted((r for r in result.rows if r.cell == c), key=lambda r: r.delta)]
    labels = [(f"{parts[r.point][1]}" if banded and r.point in parts else f"{r.cell} · {r.point}" if r.cell else r.point)
              + (" (baseline)" if r.is_baseline else "") for r in ordered]
    styled = [[(_shown(r.loss), SURFACE, INK), (_shown(r.base), SURFACE, INK), delta(r.delta)] +
              [delta(r.objects.get(o)) for o in objects] for r in ordered]
    given = ", ".join(f"{k} = {v}" for k, v in result.filter.items())
    notes["baseline"] = (f"Each point against the point equal to it on every quantity but {', '.join(result.filter)}, which take the "
                         f"values {given}: its loss less the baseline's, and its page loss less the baseline's on each object. "
                         "Negative (blue): better than the baseline.")
    items = [_table("baseline", f"Baseline: {given}\nΔ against the baseline point; negative is better", labels,
                    ["loss", "baseline", "Δloss"] + [o.replace("-x01-y01", "") for o in objects],
                    styled, ("baseline",), groups=[r.cell for r in ordered] if banded else None)]
    if result.unmatched:
        notes["unmatched"] = "Unmatched: points with no baseline partner, so no Δ: " + "; ".join(
            f"{c + ' · ' if c else ''}{p} ({why})" for c, p, why in result.unmatched) + "."
        items[0].notes = items[0].notes + ("unmatched",)
    return [paper.Section("baseline", "Baseline", items)]


def _facts(rows: list[dict]) -> list[str]:
    """What a summary holds (V197): its points, cells, objects and pages, and what they are compared against."""
    rows = _rows_of(rows)
    points, cells = _points(rows), {r.get("cell") or "" for r in rows}
    pages: dict = {}
    for r in rows:
        pages.setdefault(r["page"], []).append(r)
    with_data = sum(1 for rs in pages.values() if not any(r["is_reference"] for r in rs))
    references = sorted({_label(str(r["reference"])) for r in rows})
    against = ", ".join(references) if len(references) <= 2 else "each page's reference"
    objects = {r["object"] for r in rows}
    cells.discard("")
    return [f"{len(points)} point(s){f' in {len(cells)} page cell(s)' if cells else ''}, on {len(objects)} object(s): "
            f"{len(pages)} page(s) measured.",
            f"Compared against {against}: "
            f"{with_data} of the {len(pages)} page(s) have data"
            + ("; the others are compared against their first curve." if with_data < len(pages) else ".")]


def summary_model(rows: list[dict], heading: str = "", ranking=None):
    """The summary as a document (V196): its facts and notes up front (V197), the leaderboard and the categories' list, a
    section a category with a metric on (what it asks, a ranking, and each metric's ranking, page cells against curves and
    table), then the head to head for the pages `[ranking].head_to_head` names. `ranking`: the stats.ranking.Ranking of these
    rows (ranked here with the defaults when None: no marginals then, having no values)."""
    ranked = ranking or S.rank(_rows_of(rows))
    st = ranked.settings
    notes: dict = {}
    names = _on(_rows_of(rows), st)
    sections = []
    if names:
        notes["loss"] = _loss_text(st)
        front = _leaderboard_tables(rows, names, st, notes, ranked)
        if front:
            sections.append(paper.Section("leaderboard", "Leaderboard", front))
        sections += _category_sections(rows, names, st, notes, ranked)
        sections += _marginals(rows, st, notes, ranked)
        sections += _baseline(rows, st, notes, ranked)
        sections += _matches(rows, st, notes)
    return paper.Document(heading, sections, notes, _facts(rows) if rows else [])


def summary_of(rows: list[dict], target: Path, formats: list[str], heading: str = "", ranking=None) -> list[Path]:
    """The summary (V174, V196): `target`.pdf holds every page, each A4 portrait; a PNG or SVG is a file a page in
    the folder `target`, <target name>_<NN>.<fmt> in the PDF's order; `target`.html the same document as one page
    (V199), whatever the formats."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    document = summary_model(rows, heading, ranking)
    written = []
    if document.sections:
        target.parent.mkdir(parents=True, exist_ok=True)
        page_ = target.with_suffix(".html")
        page_.write_text(webpage.render(document, paper.note_numbers(document), paper), encoding="utf-8")
        written.append(page_)
    return written + paper.write(document, target, formats, f"Statistics: {heading}" if heading else "Statistics", plt)


def draw(pages: list[tuple[str, list[dict]]], folder: Path, formats: list[str], summary: Path | None = None,
         heading: str = "", ranking=None) -> int:
    """Every page's image into `folder` (a panel a metric on), then the summary (`summary`, else folder/summary, under
    `heading`, of `ranking`: the rows' stats.ranking.Ranking); the number of images."""
    st = ranking.settings if ranking is not None else S.settings_of()
    formats = [f for f in formats if f in ("png", "pdf", "svg")] or ["png"]
    made = 0
    every = [r for _, rows in pages for r in rows]
    names = _on(every, st) or default_names()
    for name, rows in pages:
        if rows:
            made += bool(page(rows, folder / name, formats, name, names))
    made += bool(summary_of(every, summary or folder / "summary", formats, heading, ranking))
    return made
