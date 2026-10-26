"""statistics.csv as bar graphs (V162, V164): results/…/statistics/<set>/bars/<cell>/<object>.<fmt>, one per drawn
page, and the summary (V174). First its standings (V176): each page ranks its own curves in each statistic, a place
scoring 5 points for a 1st … 1 for a 5th, so that they say what is best on the most pages (as a mode), where the
means say what is best on average, and each pair of curves on a page plays a match a statistic (V177): the top
five, scoreboards page by page and by page cell, each cell's head to head, a scoreboard a statistic. Then
per statistic (χ²/ndf, |Δ|/reference, area/reference, mean ratio, mean |ratio − 1|,
V175; TABLES), each point's mean over its pages as sorted bars, then a table, a row per point and a column per
object; the area a table only (each object has its own units: no mean across them).

The summary is a document (V196, I-107): `summary_model` builds it as paper.py's model, sections of tables and
rankings, and paper.py lays it out on A4 portrait pages. statistics/<set>/summary.pdf holds every page; a PNG or
SVG is a file a page in statistics/<set>/summary/, numbered in the PDF's order (summary_01.png, …). Each page
ends with its items' notes, each once: what its numbers are and how they are computed (NOTES). Matplotlib (the
conda base's), Agg.

A page's image is six panels on an A4 portrait page, in the grid that gives each bar the most height (2 × 3,
3 × 2 or 6 × 1), one bar per curve in the page's order, each statistic on its own axis (no two scales on one):
χ²/ndf, |Δ|/ref, area/ref, the mean ratio and |ratio − 1| against the page's reference, and the area. One series,
one colour; the values at the bars' tips, in text ink; the reference curve (a page without data) is named, not
drawn. Rows are plot.statistics_of's (runner/plot.py).
"""

from __future__ import annotations

import math
from pathlib import Path

from runner import plugins

paper = plugins.load(Path(__file__).with_name("paper.py"), "paper")
webpage = plugins.load(Path(__file__).with_name("webpage.py"), "webpage")

SERIES = paper.SERIES         # one series: the palette's first categorical slot
INK, MUTED, GRID, SURFACE = paper.INK, paper.MUTED, paper.GRID, paper.SURFACE
PANELS = (("chi2_ndf", r"$\chi^{2}$/ndf"), ("rel_abs_area", r"$|\Delta|$ / reference"),
          ("area_ratio", "area / reference"), ("ratio_mean", "mean ratio"), ("ratio_dev", "mean |ratio − 1|"),
          ("area", "area"))

#: What each summary page's number is and how Paint computes it (src/Apps/Paint/Transform.hh), as its footnote.
COMPARED = ("Each page as drawn (after voiding, alignment and normalisation), over its drawn x range, against its "
            "reference: the page's data, else its first curve. Compared bins: the reference's bins that the curve "
            "covers exactly, its own bins summed onto them.")
NOTES = {
    "chi2_ndf": "χ²/ndf = Σ (y − y_ref)² / (σ² + σ_ref²) over the compared bins whose errors are not both zero, "
                "divided by their number, ndf. Near 1: the curve agrees with the reference within errors; "
                "larger: further apart.",
    "rel_abs_area": "|Δ| / reference = Σ |y − y_ref|·Δx / Σ y_ref·Δx over the compared bins: the area between "
                    "the curve and the reference, as a fraction of the reference's area. 0: identical. Shape and "
                    "normalisation differences both count; bins above and below do not cancel.",
    "area_ratio": "area / reference = Σ y·Δx / Σ y_ref·Δx over the compared bins: the curve's area over the "
                  "reference's (MC over data). 1: the same normalisation; above 1 (blue) the curve holds more, "
                  "below 1 (orange) less. Each bin weighs "
                  "as much as the reference holds there, so the peak decides; bins above and below the reference "
                  "cancel: |Δ| / reference and mean |ratio − 1| show those.",
    "ratio_mean": "mean ratio = Σ (y/y_ref)·Δx / Σ Δx over the compared bins where y_ref ≠ 0: the ratio pad's "
                  "mean height (Δx in log10 x on a log-x page, as the pad draws it). Every x counts alike, the "
                  "tails as much as the peak, where area / reference weighs by y_ref. 1: on par on average; blue "
                  "above, orange below. Beside mean |ratio − 1|: equal distances from 1 mean the "
                  "curve is off one way throughout (normalisation); a larger |ratio − 1| means it crosses the "
                  "reference (shape).",
    "ratio_dev": "mean |ratio − 1| = Σ |y/y_ref − 1|·Δx / Σ Δx over the compared bins where y_ref ≠ 0: the area "
                 "between the ratio pad's curve and its line at one, over the width compared (Δx in log10 x on a "
                 "log-x page, as the pad draws it). 0.1: 10% off on average across x. Every x counts alike, the "
                 "tails as much as the peak; |Δ| / reference weights by y_ref instead.",
    "area": "area = Σ y·Δx over the curve's finite bins inside the drawn x range, compared or not, in the page's "
            "units of y times x; each page as drawn (after voiding, alignment and normalisation). Each object has "
            "its own units, so each column is shaded on its own.",
}
TABLE_NOTE = ("A row per point (its label, under its page cell's band), a column per object; mean: the {mean} mean of the "
              "row's numbers. ref: the page's reference curve itself (compared with nothing); –: no number (no bins "
              "compared, or not on that page).")
RANKING_NOTE = ("Per point (its page cell · its label), the {mean} mean of its {name} over the pages where it was "
                "compared (their number in brackets), {order}.")
GEOMETRIC = "geometric"                                         # a ratio's mean: 2 and 0.5 average to 1
PLAIN = {"chi2_ndf": "χ²/ndf", "rel_abs_area": "|Δ| / reference", "area_ratio": "area / reference",
         "ratio_mean": "mean ratio", "ratio_dev": "mean |ratio − 1|", "area": "area"}

#: A page image's grids of the six panels (columns, rows); a panel's least width, the room around a panel row
#: (its title, its x labels, the gap), the space between panels, a bar's most and least height, inches.
GRIDS = ((2, 3), (3, 2), (6, 1))
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
    """Thin bars from one baseline, each value at its tip; a missing value says why. The axis runs both ways from 0
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


def grid(curves: int, label: float) -> tuple[int, int, float, int]:
    """A page image's grid for `curves` curves whose labels take `label` inches: (columns, rows, a bar's height,
    curves a page). The grid gives each bar the most height with every panel at least PANEL wide (2 × 3 when none
    does); a bar is at most MOST_BAR, and below LEAST_BAR the curves continue on further pages, in the grid that
    holds the most."""
    room = paper.A4[1] - 2 * paper.EDGE - STRIP - KEY
    fits = [(c, r) for c, r in GRIDS if (paper.WIDTH - label - (c - 1) * PANEL_GAP) / c >= PANEL] or [GRIDS[0]]
    each = {g: (room - g[1] * PANEL_ROOM) / g[1] for g in fits}               # a panel's height for bars
    best = max(fits, key=lambda g: each[g])
    if each[best] / max(curves, 1) >= LEAST_BAR:
        return best[0], best[1], min(MOST_BAR, each[best] / max(curves, 1)), max(curves, 1)
    per = max(1, int(each[best] // LEAST_BAR))
    return best[0], best[1], min(MOST_BAR, each[best] / per), per


def _page_figure(rows: list[dict], title: str, columns: int, bar: float, label: float, plt):
    """One A4 page of a page's statistics: the six panels in `columns` columns, a bar per curve."""
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
    for k, (key, name) in enumerate(PANELS):
        r, c = divmod(k, columns)
        left = paper.SIDE + label + c * (panel + PANEL_GAP)
        top = paper.EDGE + STRIP + r * (height + PANEL_ROOM) + 0.25
        ax = fig.add_axes((left / w, 1 - (top + height) / h, panel / w, height / h))
        notes = ["reference" if r_["is_reference"] and key != "area" else "no bins compared" for r_ in rows]
        values = [None if (r_["is_reference"] and key != "area") else r_[key] for r_ in rows]
        _style(ax, labels)
        cut = _bars(ax, values, notes, size, panel) or cut
        if key in ("area_ratio", "ratio_mean"):
            ax.axvline(1, color=MUTED, linewidth=0.8, linestyle=":")      # the reference's own
        ax.set_title(name, color=INK, fontsize=9, loc="left")
        ax.set_yticks(range(len(labels)), labels if c == 0 else [""] * len(labels), color=INK, fontsize=size)
    if cut:                                                     # the key, at the page's foot
        fig.text(paper.SIDE / w, paper.EDGE / h, "\n".join(paper.wrap(paper.CUT_KEY, paper.WIDTH, 7)), color=MUTED,
                 fontsize=7, ha="left", va="bottom")
    return fig


def page(rows: list[dict], target: Path, formats: list[str], title: str) -> list[Path]:
    """One page's statistics on A4: six panels, a bar per curve; more curves than a page holds continue on further
    pages (`target`.pdf holds them all, `target`_NN.png one each)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    label = max([paper.width(_label(r["curve"]), 8) for r in rows] + [0.5]) + 0.12
    columns, _, bar, per = grid(len(rows), label)
    chunks = [rows[s:s + per] for s in range(0, len(rows), per)] or [rows]
    written = []
    target.parent.mkdir(parents=True, exist_ok=True)
    pdf = None
    try:
        for number, chunk in enumerate(chunks, 1):
            fig = _page_figure(chunk, title if len(chunks) == 1 else f"{title} ({number}/{len(chunks)})",
                               columns, bar, label, plt)
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


#: The summary's tables (V174): a statistic each, its title, and how its cells are shaded: "log" across the whole
#: table (χ²/ndf spans decades), "linear" across it, "column" within each object's column (an area's scale is
#: the object's own: pb/GeV on one page, a fraction on another), "ratio" diverging from 1 on a log scale (V175).
TABLES = (("chi2_ndf", r"$\chi^{2}$/ndf", "log"), ("rel_abs_area", r"$|\Delta|$ / reference", "linear"),
          ("area_ratio", "area / reference", "ratio"), ("ratio_mean", "mean ratio", "ratio"),
          ("ratio_dev", "mean |ratio − 1|", "linear"),
          ("area", "area", "column"))
LIGHT, DARK = (0.937, 0.957, 0.984), (0.078, 0.271, 0.478)     # #eff4fb → #14457a: one hue, light to dark
NEUTRAL, WARM = (0.941, 0.941, 0.933), (0.561, 0.239, 0.078)   # a ratio's 1 (#f0f0ee), and below it (#8f3d14)
RULES = {key: rule for key, _, rule in TABLES}


def _short(objects: list[str]) -> dict[str, str]:
    """Each object's column title: its short name without -x01-y01 when that stays unique."""
    import re
    names = {o: o.rsplit("/", 1)[-1] for o in objects}
    trimmed = {o: re.sub(r"-x01-y01$", "", n) for o, n in names.items()}
    return trimmed if len(set(trimmed.values())) == len(objects) else names


def _shade(fraction: float, low=LIGHT, high=DARK) -> tuple:
    f = min(max(fraction, 0.0), 1.0)
    return tuple(a + (b - a) * f for a, b in zip(low, high))


#: How a table's cells are shaded, by its rule, as its subtitle says.
SHADING = {"log": "darker is larger, log scale", "linear": "darker is larger",
           "column": "darker is larger within each column; mean unshaded",
           "ratio": "blue above 1, orange below, darker further from 1 (log scale: 2 and 0.5 alike)"}


def _scale(rule: str, found: list[float]):
    """How dark a number's cell is, 0 to 1, among the numbers `found`, by a table's rule ("column" as "linear":
    each column is the caller's)."""
    low, high = min(found), max(found)
    spread = max([abs(math.log10(v)) for v in found if v > 0] + [0.0]) if rule == "ratio" else 0.0

    def fraction(value: float) -> float:
        if rule == "ratio":
            return 0.0 if not spread or value <= 0 else abs(math.log10(value)) / spread
        if rule == "log":
            lo, hi = math.log10(max(low, 1e-3)), math.log10(max(high, 1e-3))
            return 0.0 if hi == lo else (math.log10(max(value, 1e-3)) - lo) / (hi - lo)
        return 0.0 if high == low else (value - low) / (high - low)
    return fraction


def _mean(values: list[float], rule: str) -> float | None:
    """A row's or a point's mean: geometric for a ratio (its values above 0), else plain."""
    if rule == "ratio":
        values = [v for v in values if v > 0]
        return 10 ** (sum(math.log10(v) for v in values) / len(values)) if values else None
    return sum(values) / len(values) if values else None


def _points(rows: list[dict]) -> dict[str, str]:
    """Each point's name in the summary: its page cell · its label, in curve order."""
    points = {}
    for r in rows:
        points.setdefault(r["point"], f"{r['cell']} · {_label(r['curve'])}" if r.get("cell") else _label(r["curve"]))
    return points


def _rows_of(rows: list[dict]) -> list[dict]:
    """The rows the summary reads: an overlay figure's curves are other objects of a point, not its own page."""
    return [r for r in rows if not str(r.get("object", "")).startswith("/overlay/")]


def _means(rows: list[dict], key: str) -> dict[str, tuple[float, int]]:
    """Each point's mean of a statistic over the pages where it was compared, and their number."""
    rule = RULES[key]
    by: dict[str, list[float]] = {}
    for r in rows:
        if not r["is_reference"] and _finite(r[key]) and (rule != "ratio" or r[key] > 0):
            by.setdefault(r["point"], []).append(float(r[key]))
    return {p: (_mean(v, rule), len(v)) for p, v in by.items()}


def _distance(key: str, value) -> float | None:
    """How far a number is from agreement, smaller better: a ratio's |log10|, how far from 1 either way; else the
    number itself. None when it has none."""
    if not _finite(value):
        return None
    if RULES[key] == "ratio":
        return abs(math.log10(value)) if value > 0 else None
    return float(value)


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


def _ranking(rows: list[dict], key: str, notes: dict):
    """A statistic's ranking (V174): each point's mean over the pages where it was compared, as sorted bars, lowest
    first (a ratio: closest to 1 first, its geometric mean, bars from 1); None when no point has one."""
    title, rule = next((t, r) for k, t, r in TABLES if k == key)
    rows = _rows_of(rows)
    points, means = _points(rows), _means(rows, key)
    if not means:
        return None
    ratio = rule == "ratio"
    ranked = sorted(means, key=lambda p: (_distance(key, means[p][0]), points[p]))
    order = "closest to 1 first, bars from 1: blue above, orange below" if ratio else "lowest first"
    notes[f"ranking-{key}"] = RANKING_NOTE.format(mean=GEOMETRIC if ratio else "plain", name=PLAIN[key], order=order)
    notes[f"stat-{key}"], notes["compared"] = NOTES[key], COMPARED
    values = [means[p][0] for p in ranked]
    if paper.any_cut([v - 1.0 if ratio else max(v, 0.0) for v in values]):
        order += ". " + paper.CUT_KEY                                       # V205
    return paper.Ranking(f"{key}-ranking",
                         f"{title}: each point's {'geometric ' if ratio else ''}mean over its pages (pages compared)",
                         [f"{points[p]}  ({means[p][1]})" for p in ranked], values,
                         subtitle=order, base=1.0 if ratio else 0.0,
                         colours=(DARK, WARM) if ratio else (SERIES, SERIES),
                         notes=(f"ranking-{key}", f"stat-{key}", "compared"))


CROSSED_NOTE = ("Page cells against curves: each entry a point's {mean} mean over the pages where it was compared "
                "(its ranking's number), its page cell one way and its curve the other; mean: the {mean} mean of the "
                "row's, the column's, or all the entries; bold: the best in its row, closest to agreement; –: no "
                "such point, or no number.")


def _crossed(rows: list[dict], key: str, notes: dict):
    """A statistic's page cells against its curves (V198): each entry that point's mean over its pages (as its
    ranking's), the longer list down the rows, a mean column and a mean row, each row's best bold. None for the
    area (its units are each object's), with one cell, when no curve is in two cells, or when a cell repeats a
    label."""
    title, rule = next((t, r) for k, t, r in TABLES if k == key)
    rows = _rows_of(rows)
    parts, means = _parts(rows), _means(rows, key)
    cells = list(dict.fromkeys(c for c, _ in parts.values()))
    curves = list(dict.fromkeys(v for _, v in parts.values()))
    if key == "area" or len(cells) < 2 or len(curves) < 2 or not all(cells) or len(set(parts.values())) < len(parts):
        return None
    if not any(sum(1 for _, v in parts.values() if v == curve) > 1 for curve in curves):
        return None                                     # no curve in two cells: nothing crosses
    grid = {parts[p]: means[p][0] for p in parts if p in means and means[p][0] is not None}
    found = [v for v in grid.values() if rule != "ratio" or v > 0]
    if not found:
        return None
    down, across = (cells, curves) if len(cells) >= len(curves) else (curves, cells)

    def entry(r, c):
        return grid.get((r, c) if down is cells else (c, r))
    row_means = {r: _mean([v for c in across if (v := entry(r, c)) is not None], rule) for r in down}
    column_means = {c: _mean([v for r in down if (v := entry(r, c)) is not None], rule) for c in across}
    overall = _mean(found, rule)
    scale = _scale(rule, [v for v in found + list(row_means.values()) + list(column_means.values())
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
    mean = GEOMETRIC if rule == "ratio" else "plain"
    notes[f"crossed-{mean}"] = CROSSED_NOTE.format(mean=mean)
    notes[f"stat-{key}"], notes["compared"] = NOTES[key], COMPARED
    way = "page cells against curves" if down is cells else "curves against page cells"
    return _table(f"{key}-crossed", f"{title}: {way}\n{SHADING[rule]}; bold: the best in its row", list(down) + ["mean"],
                  list(across) + ["mean"], styled, (f"crossed-{mean}", f"stat-{key}", "compared"), tail=1,
                  bold=frozenset({len(down)}), pinned=frozenset({len(down)}))


def _natural(objects) -> list[str]:
    """Objects in natural order: d2 before d10."""
    import re
    return sorted(objects, key=lambda o: [int(s) if s.isdigit() else s for s in re.split(r"(\d+)", o)])


def _tables(rows: list[dict], notes: dict) -> dict:
    """The summary's tables (V174), {statistic key: table}: a row per point (in curve order, its page cell before
    its label) and a column per object, each cell the point's number on that object's page, then its mean; the
    reference curve's cell says "ref", a missing one "–". Shaded by value (TABLES' rule), its text white on dark."""
    rows = _rows_of(rows)
    points, parts, cells = _points(rows), _parts(rows), {}
    for r in rows:
        cells[(r["point"], r["object"])] = r
    objects = _natural({r["object"] for r in rows})
    out: dict = {}
    if not points or not objects:
        return out
    short = _short(objects)
    references = sorted({str(r["reference"]) for r in rows})
    for key, title, rule in TABLES:
        def number(point, obj):
            r = cells.get((point, obj))
            compared = key != "area"                    # an area is the curve's own: the reference has one too
            return None if r is None or (compared and r["is_reference"]) or not _finite(r[key]) else float(r[key])
        means = {point: _mean([v for o in objects if (v := number(point, o)) is not None], rule) for point in points}
        found = [v for p in points for o in objects if (v := number(p, o)) is not None]
        if rule == "ratio":
            found = [v for v in found if v > 0]
        if not found:
            continue
        scale = _scale(rule, found)

        def fraction(value, obj):
            if rule == "column" and obj is not None:
                column = [v for p in points if (v := number(p, obj)) is not None]
                lo, hi = min(column), max(column)
                return 0.0 if hi == lo else (value - lo) / (hi - lo)
            return scale(value)

        styled = []
        for point in points:
            row = []                                            # (text, background, ink) a cell
            for obj in objects + [None]:                        # None: the mean
                r = cells.get((point, obj)) if obj is not None else None
                value = means[point] if obj is None else number(point, obj)
                shaded = obj is not None or rule != "column"
                if r is not None and r["is_reference"] and key != "area":
                    row.append(("ref", SURFACE, MUTED))
                elif value is None:
                    row.append(("–", SURFACE, MUTED))
                else:
                    f = fraction(value, obj) if shaded else 0.0
                    pole = (NEUTRAL, DARK if value >= 1 else WARM) if rule == "ratio" else (LIGHT, DARK)
                    row.append((_shown(value), _shade(f, *pole) if shaded else SURFACE,
                                "white" if shaded and f > 0.55 else INK))
            styled.append(row)
        shading = SHADING[rule]
        against = "" if key == "area" else (f" against {', '.join(_label(r) for r in references)}"
                                            if len(references) <= 2 else " against each page's reference")
        mean = GEOMETRIC if rule == "ratio" else "plain"
        notes[f"stat-{key}"], notes[f"table-{mean}"] = NOTES[key], TABLE_NOTE.format(mean=mean)
        if key != "area":
            notes["compared"] = COMPARED
        order = list(points)
        grouped = _grouped(order, parts)
        if grouped:
            at = {p: i for i, p in enumerate(order)}
            order = _by_cell(order, parts)
            styled = [styled[at[p]] for p in order]
        out[key] = _table(key, f"{title}{against}\n{shading}",
                          [parts[p][1] if grouped else points[p] for p in order],
                          [short[o] for o in objects] + ["mean"], styled,
                          (f"stat-{key}",) + (("compared",) if key != "area" else ()) + (f"table-{mean}",), tail=1,
                          groups=[parts[p][0] for p in order] if grouped else None)
    return out


# ── the standings (V176): what is best on the most pages, as a mode is: each page's places scored ───────────

#: A place's points: 1st 5, 2nd 4, 3rd 3, 4th 2, 5th 1, the rest none.
POINTS = (5, 4, 3, 2, 1)
#: The statistics ranked: those against a reference (the area is each object's own units).
SCORED = ("chi2_ndf", "rel_abs_area", "area_ratio", "ratio_mean", "ratio_dev")
SCORE_NOTE = ("Scoring: each page ranks its own curves in each of χ²/ndf, |Δ| / reference, area / reference, the mean "
              "ratio and mean |ratio − 1|, by the distance from agreement: the number itself, but the two ratios by "
              "|log10 r|, how far from 1 either way. 1st scores 5 points, 2nd 4, 3rd 3, 4th 2, 5th 1, the rest 0; "
              "equal numbers share the better place and its points (1, 1, 3, …). Points count how often a point is "
              "near the top, page after page, not by how much (the ranking pages' means say how good on average). "
              "Wins: its 1st places; mean rank: the mean of its places. Sorted by total, then wins, then mean rank; "
              "bold: the top three.")
H2H_NOTE = ("Head to head: on every page counted, in each statistic, each pair of its curves is a match: the "
            "one closer to agreement wins it, equal numbers draw (half each). Win rate: the share of its matches a "
            "point won (75%: it beats the others 3 times in 4); every place counts and the number of curves on a "
            "page does not, where points end at the 5th.")
APART = "Points of different page cells never meet: a page holds one cell's points."


def _places(values: dict) -> dict:
    """Competition places, 1 for the smallest: equal values share the better place (1, 1, 3, …)."""
    return {p: 1 + sum(1 for w in values.values() if w < v) for p, v in values.items()}


def _score(place: int) -> int:
    return POINTS[place - 1] if place <= len(POINTS) else 0


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _page_rankings(rows: list[dict]) -> tuple[dict, dict, bool]:
    """Each page's own rankings, {page: {statistic: {point: place among that page's curves}}}, each page's object,
    and whether only pages against data were counted (when any page has data: a page against its first curve
    cannot rank it)."""
    pages: dict[str, list[dict]] = {}
    for r in rows:
        pages.setdefault(r["page"], []).append(r)
    with_data = {name: rs for name, rs in pages.items() if not any(r["is_reference"] for r in rs)}
    rankings, objects = {}, {}
    for name, rs in (with_data or pages).items():
        objects[name] = rs[0]["object"]
        for key in SCORED:
            values = {r["point"]: d for r in rs if not r["is_reference"] and (d := _distance(key, r[key])) is not None}
            if values:
                rankings.setdefault(name, {})[key] = _places(values)
    return rankings, objects, bool(with_data)


def _head_to_head(rankings: dict, keys) -> dict[tuple[str, str], list]:
    """Every match (V177): {(point, opponent): [won, played]} over the pages and the statistics in `keys`, a draw
    half each."""
    pairs: dict = {}
    for by_key in rankings.values():
        for key in keys:
            places = by_key.get(key, {})
            for a, mine in places.items():
                for b, theirs in places.items():
                    if a != b:
                        record = pairs.setdefault((a, b), [0.0, 0])
                        record[0] += 1.0 if mine < theirs else 0.5 if mine == theirs else 0.0
                        record[1] += 1
    return pairs


def _rates(pairs: dict) -> dict[str, tuple[float, int]]:
    """Each point's matches won and played, over every opponent."""
    out: dict = {}
    for (a, _), (won, played) in pairs.items():
        w, n = out.get(a, (0.0, 0))
        out[a] = (w + won, n + played)
    return out


def _won(won: float) -> str:
    return f"{won:g}"


def _standing(board: dict, ranks: dict, points: dict) -> tuple[list, dict, dict, dict, dict]:
    """A board's order (by total, then wins, then mean rank, then name), each point's place by total and wins,
    and its total, wins and mean rank."""
    totals = {p: sum(s.values()) for p, s in board.items()}
    wins = {p: sum(1 for v in ranks.get(p, ()) if v == 1) for p in board}
    mean_rank = {p: sum(v) / len(v) for p, v in ranks.items() if v and p in board}
    order = sorted(board, key=lambda p: (-totals[p], -wins[p], mean_rank.get(p, math.inf), points[p]))
    return order, _places({p: (-totals[p], -wins[p]) for p in board}), totals, wins, mean_rank


def _scoreboard(key: str, title: str, points: dict, board: dict, ranks: dict, rates: dict,
                columns: list[tuple[str, str]], notes: tuple, cells_of: dict | None = None):
    """A scoreboard: a row per point in `board` ({point: {column: points}}), its place before its name (within its
    page cell when `cells_of` names them), a column per (key, header) in `columns`, then its total, its wins, its
    head-to-head win rate (`rates`) and the mean of its places (`ranks`). Points darker as they score more."""
    groups = list(dict.fromkeys(cells_of[p] for p in board)) if cells_of else [None]
    banded = cells_of is not None and len(groups) > 1 and all(groups)
    order, labels, bold, totals, wins, mean_rank = [], [], set(), {}, {}, {}
    for group in groups:
        members = {p: s for p, s in board.items() if cells_of is None or cells_of[p] == group}
        ordered, places, total, won, mean = _standing(members, ranks, points)
        totals.update(total), wins.update(won), mean_rank.update(mean)
        for p in ordered:
            if places[p] <= 3:
                bold.add(len(order))
            order.append(p)
            name = points[p][len(group) + 3:] if banded and points[p].startswith(f"{group} · ") else points[p]
            labels.append(f"{places[p]}. {name}")
    top = max([v for s in board.values() for v in s.values()] + [1])
    best = max(list(totals.values()) + [1])

    def shaded(value, high):
        f = value / high
        return (str(value), _shade(f), "white" if f > 0.55 else INK)
    styled = []
    for p in order:
        won, played = rates.get(p, (0.0, 0))
        row = [shaded(board[p][k], top) if k in board[p] else ("–", SURFACE, MUTED) for k, _ in columns]
        row += [shaded(totals[p], best), (str(wins[p]), SURFACE, INK),
                (f"{won / played:.0%}" if played else "–", SURFACE, INK),
                (f"{mean_rank[p]:.2f}" if p in mean_rank else "–", SURFACE, INK)]
        styled.append(row)
    return _table(key, title, labels, [h for _, h in columns] + ["total", "wins", "win rate", "mean rank"], styled,
                  notes, tail=4, bold=frozenset(bold), groups=[cells_of[p] for p in order] if banded else None)


def _matches(key: str, cell: str, members: list[str], points: dict, pairs: dict, rates: dict, notes: tuple,
             first: bool = True):
    """A page cell's head to head (V177): a row per point, sorted by win rate, a column per opponent, the matches
    the row's point won against it of those played; then its win rate and matches. Blue: won most, orange: lost
    most, darker further from even."""
    def rate(p):
        won, played = rates.get(p, (0.0, 0))
        return won / played if played else 0.0
    order = sorted(members, key=lambda p: (-rate(p), points[p]))
    places = _places({p: -rate(p) for p in order})
    prefix = f"{cell} · " if cell else ""
    short = {p: points[p][len(prefix):] if points[p].startswith(prefix) else points[p] for p in order}
    styled = []
    for p in order:
        row = []
        for q in order:
            won, played = pairs.get((p, q), (0.0, 0))
            if p == q or not played:
                row.append(("–", SURFACE, MUTED))
                continue
            share = won / played
            f = min(abs(share - 0.5) * 2, 1.0)
            row.append((f"{_won(won)}/{played}", _shade(f, NEUTRAL, DARK if share >= 0.5 else WARM),
                        "white" if f > 0.55 else INK))
        won, played = rates.get(p, (0.0, 0))
        row += [(f"{won / played:.0%}" if played else "–", SURFACE, INK), (str(played), SURFACE, INK)]
        styled.append(row)
    title = f"Head to head{f': {cell}' if cell else ''}" + (
        "\nthe row's point against each column's: matches won of played" if first else "")
    return _table(key, title, [f"{places[p]}. {short[p]}" for p in order], [short[q] for q in order]
                  + ["win rate", "matches"], styled, notes, tail=2,
                  bold=frozenset(i for i, p in enumerate(order) if places[p] <= 3))


def _standings(rows: list[dict], notes: dict) -> list:
    """The summary's standings (V176, V177), its first sections: each page's own rankings scored (POINTS) and
    played as matches, so that they say what is best on most pages, as a mode does, where the ranking pages' means
    say what is best on average. The top five; the scoreboard of all five statistics page by page; by page cell;
    each cell's head to head; a scoreboard a statistic. Tables keyed top5, scoreboard, scoreboard-cells,
    head-to-head-<n>, scoreboard-<statistic>."""
    rows = _rows_of(rows)
    points = _points(rows)
    rankings, object_of, data_only = _page_rankings(rows)
    if not points or not rankings:
        return []
    notes["counted"] = ("Only the pages compared against data count: on a page compared against its first curve, "
                        "that curve cannot be ranked." if data_only else
                        "No page here has data: each is compared against its first curve, which cannot be ranked "
                        "there, so a point that is a page's reference scores nothing on it.")
    notes["apart"], notes["score"], notes["h2h"] = APART, SCORE_NOTE, H2H_NOTE
    objects = _natural(set(object_of.values()))
    short = _short(objects)
    keys = [k for k in SCORED if any(k in by_key for by_key in rankings.values())]
    every, ranks, by_cell = {}, {}, {}
    by_key, key_ranks = {k: {} for k in keys}, {k: {} for k in keys}
    for page, scored in rankings.items():
        obj = object_of[page]
        for key, places in scored.items():
            for point, place in places.items():
                points_now = _score(place)
                every.setdefault(point, {})[obj] = every.get(point, {}).get(obj, 0) + points_now
                ranks.setdefault(point, []).append(place)
                by_key[key].setdefault(point, {})[obj] = points_now
                key_ranks[key].setdefault(point, []).append(place)
                cell = by_cell.setdefault(point, {})
                cell[key] = cell.get(key, 0) + points_now
    in_order = lambda board: {p: board[p] for p in points if p in board}          # noqa: E731  (curve order)
    every, by_cell = in_order(every), in_order(by_cell)
    by_key = {k: in_order(b) for k, b in by_key.items()}
    pairs = _head_to_head(rankings, keys)
    rates = _rates(pairs)
    key_rates = {k: _rates(_head_to_head(rankings, (k,))) for k in keys}

    boards = [("all", "All five statistics", every, ranks)] + [(k, PLAIN[k], by_key[k], key_ranks[k]) for k in keys]
    by_rate = sorted(rates, key=lambda p: (-rates[p][0] / rates[p][1], points[p]))
    rate_places = _places({p: -rates[p][0] / rates[p][1] for p in by_rate})

    def placed(places: dict, chosen: list) -> list[str]:
        shared = {}
        for place in places.values():
            shared[place] = shared.get(place, 0) + 1
        return [("=" if shared[places[p]] > 1 else "") + _ordinal(places[p]) for p in chosen]

    def name(p):
        return (points[p], SURFACE, INK, False, "left")
    top5 = []
    for key, title, board, rank in boards:
        order, places, totals, wins, _ = _standing(board, rank, points)
        chosen = order[:len(POINTS)]
        top5.append(_table(f"top5-{key}", title, placed(places, chosen), ["point", "points", "wins"],
                           [[name(p), (str(totals[p]), SURFACE, INK), (str(wins[p]), SURFACE, INK)] for p in chosen],
                           ("how-top5", "score") + (() if key == "all" else (f"stat-{key}",)) + ("apart", "counted")))
    chosen = by_rate[:len(POINTS)]
    top5.append(_table("top5-h2h", "Head to head: by win rate", placed(rate_places, chosen),
                       ["point", "win rate", "matches"],
                       [[name(p), (f"{rates[p][0] / rates[p][1]:.0%}", SURFACE, INK), (str(rates[p][1]), SURFACE, INK)]
                        for p in chosen], ("how-top5", "h2h", "apart", "counted")))
    sections = []
    notes["how-top5"] = ("The top five: a table a scoreboard (all five statistics' points together, as the "
                         "page-by-page scoreboard, then each statistic's), its first five with their points and wins "
                         "(1st places), and the first five by head-to-head win rate with their matches; =2nd: sharing "
                         "that place.")
    standard = ("apart", "counted", "score", "h2h")
    sections.append(paper.Section("top5", "The top five: best on the most pages", top5))
    notes["how-scoreboard"] = ("A row per point, a column per object's page: the points it scored on that page, its "
                               "five statistics' together (at most 25); total: over its pages.")
    sections.append(paper.Section("scoreboard", "Scoreboard: page by page", [
        _scoreboard("scoreboard", "Scoreboard: all five statistics, page by page\nsorted by total; darker: more points",
                    points, every, ranks, rates, [(o, short[o]) for o in objects], ("how-scoreboard",) + standard)]))
    notes["how-cells"] = ("The same points, a row per point by its page cell (its plot_points), placed within its "
                          "cell: a column per statistic, the points it scored in that statistic over the cell's "
                          "pages; total: their sum (its page-by-page total).")
    cells_of = {r["point"]: r.get("cell", "") for r in rows}
    sections.append(paper.Section("scoreboard-cells", "Scoreboard: by page cell", [
        _scoreboard("scoreboard-cells", "Scoreboard: by page cell\neach cell's points placed among themselves",
                    points, by_cell, ranks, rates, [(k, PLAIN[k]) for k in keys], ("how-cells", "counted", "score", "h2h"),
                    cells_of=cells_of)]))
    notes["how-h2h"] = ("A cell: the matches the row's point won against the column's, over the cell's pages and the "
                        "five statistics, of those they played (a draw counts half); blue: it won most, orange: it "
                        "lost most, darker further from even. Win rate: over all its matches. Sorted by win rate; "
                        "bold: the top three.")
    matches = []
    for n, cell in enumerate(dict.fromkeys(cells_of[p] for p in every), 1):
        members = [p for p in every if cells_of[p] == cell]
        if len(members) > 1:
            matches.append(_matches(f"head-to-head-{n}", cell, members, points, pairs, rates,
                                    ("how-h2h", "counted", "h2h"), first=not matches))
    if matches:
        sections.append(paper.Section("head-to-head", "Head to head", matches))
    boards_by_key = []
    for key in keys:
        notes[f"how-scoreboard-{key}"] = (f"A row per point, a column per object's page: the points its place in "
                                          f"{PLAIN[key]} on that page scored; total: over its pages; win rate: its "
                                          f"matches in {PLAIN[key]} alone.")
        notes[f"stat-{key}"] = NOTES[key]
        boards_by_key.append(_scoreboard(
            f"scoreboard-{key}", f"Scoreboard: {PLAIN[key]}, page by page\nsorted by total; darker: more points",
            points, by_key[key], key_ranks[key], key_rates[key], [(o, short[o]) for o in objects],
            (f"how-scoreboard-{key}", f"stat-{key}") + standard))
    if boards_by_key:
        sections.append(paper.Section("scoreboards", "Scoreboards, a statistic each", boards_by_key))
    return sections


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


def summary_model(rows: list[dict], heading: str = ""):
    """The summary as a document (V196): its facts and notes up front (V197), the standings (V176, V177), then a
    section a statistic, its ranking (but the area's), its page cells against its curves (V198) and its table
    (V174)."""
    notes: dict = {}
    sections = _standings(rows, notes)
    tables = _tables(rows, notes)
    for key, _, _ in TABLES:
        items = [r for r in [_ranking(rows, key, notes) if key != "area" else None, _crossed(rows, key, notes)]
                 if r is not None]
        if key in tables:
            items.append(tables[key])
        if items:
            sections.append(paper.Section(key, PLAIN[key], items))
    return paper.Document(heading, sections, notes, _facts(rows) if rows else [])


def summary_of(rows: list[dict], target: Path, formats: list[str], heading: str = "") -> list[Path]:
    """The summary (V174, V196): `target`.pdf holds every page, each A4 portrait; a PNG or SVG is a file a page in
    the folder `target`, <target name>_<NN>.<fmt> in the PDF's order; `target`.html the same document as one page
    (V199), whatever the formats."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    document = summary_model(rows, heading)
    written, pdf = [], None
    if document.sections:
        target.parent.mkdir(parents=True, exist_ok=True)
        page_ = target.with_suffix(".html")
        page_.write_text(webpage.render(document, paper.note_numbers(document), paper), encoding="utf-8")
        written.append(page_)
    try:
        for page_ in paper.pages(document):
            figure = paper.figure(document, page_, plt)
            if "pdf" in formats:
                if pdf is None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    pdf = PdfPages(target.with_suffix(".pdf"),
                                   metadata={"Title": f"Statistics: {heading}" if heading else "Statistics"})
                    written.append(target.with_suffix(".pdf"))
                pdf.savefig(figure, facecolor=SURFACE)
            for fmt in (f for f in formats if f != "pdf"):
                target.mkdir(parents=True, exist_ok=True)
                path = target / f"{target.name}_{page_.number:02d}.{fmt}"
                figure.savefig(path, dpi=150, facecolor=SURFACE)
                written.append(path)
            plt.close(figure)
    finally:
        if pdf is not None:
            pdf.close()
    return written


def draw(pages: list[tuple[str, list[dict]]], folder: Path, formats: list[str], summary: Path | None = None,
         heading: str = "") -> int:
    """Every page's image into `folder`, then the summary (`summary`, else folder/summary, under `heading`); the
    number of images."""
    formats = [f for f in formats if f in ("png", "pdf", "svg")] or ["png"]
    made = 0
    for name, rows in pages:
        if rows:
            made += bool(page(rows, folder / name, formats, name))
    made += bool(summary_of([r for _, rows in pages for r in rows], summary or folder / "summary", formats, heading))
    return made
