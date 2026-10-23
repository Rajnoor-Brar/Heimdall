"""statistics.csv as bar graphs (V162, V164): results/…/statistics/<set>/bars/<cell>/<object>.<fmt>, one per drawn
page, and the summary (V174). First its standings (V176): each page ranks its own curves in each statistic, a place
scoring 5 points for a 1st … 1 for a 5th, so that they say what is best on the most pages (as a mode), where the
means say what is best on average, and each pair of curves on a page plays a match a statistic (V177): the top
five, scoreboards page by page and by page cell, each cell's head to head, a scoreboard a statistic. Then
per statistic (χ²/ndf, |Δ|/reference, area/reference, mean ratio, mean |ratio − 1|,
V175; TABLES), each point's mean over its pages as sorted bars, then a table, a row per point and a column per
object; the area a table only (each object has its own units: no mean across them). statistics/<set>/summary.pdf
holds every page; a PNG or SVG is a file a page in statistics/<set>/summary/, numbered in the PDF's order
(summary_01.png, summary_02.png, …). Each summary page ends with a footnote: what its number is and how it is
computed (NOTES). Matplotlib (the conda base's), Agg.

A page's image is six panels side by side, one bar per curve in the page's order, each statistic on its own
axis (no two scales on one): χ²/ndf, |Δ|/ref, area/ref, the mean ratio and |ratio − 1| against the page's
reference, and the area. One series, one colour; the values at the bars' tips, in text ink; the reference curve
(a page without data) is named, not drawn. Rows are plot.statistics_of's (runner/plot.py).
"""

from __future__ import annotations

import math
import textwrap
from pathlib import Path

SERIES = "#2a78d6"            # one series: the palette's first categorical slot
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
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
TABLE_NOTE = ("A row per point (its page cell · its label), a column per object; mean: the {mean} mean of the "
              "row's numbers. ref: the page's reference curve itself (compared with nothing); –: no number (no bins "
              "compared, or not on that page).")
RANKING_NOTE = ("Per point (its page cell · its label), the {mean} mean of its {name} over the pages where it was "
                "compared (their number in brackets), {order}.")
GEOMETRIC = "geometric"                                         # a ratio's mean: 2 and 0.5 average to 1
PLAIN = {"chi2_ndf": "χ²/ndf", "rel_abs_area": "|Δ| / reference", "area_ratio": "area / reference",
         "ratio_mean": "mean ratio", "ratio_dev": "mean |ratio − 1|", "area": "area"}
FOOT = 6.5                                                      # the footnote's size, pt


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _shown(value: float) -> str:
    return f"{value:,.0f}" if abs(value) >= 100 else f"{value:.3g}"


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
    ax.tick_params(axis="x", colors=MUTED, labelsize=8, length=0)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylim(len(labels) - 0.5, -0.5)               # the page's first curve on top


def _bars(ax, values: list, notes: list[str]) -> None:
    """Thin bars from one baseline, each value at its tip; a missing value says why."""
    finite = [v for v in values if _finite(v)]
    top = max(finite + [0.0]) or 1.0
    for i, (value, note) in enumerate(zip(values, notes)):
        if _finite(value):
            ax.barh(i, value, height=0.55, color=SERIES, edgecolor=SURFACE, linewidth=2)
            ax.text(value + 0.015 * top, i, _shown(value), va="center", ha="left", color=INK, fontsize=8)
        else:
            ax.text(0.015 * top, i, note, va="center", ha="left", color=MUTED, fontsize=8, style="italic")
    ax.set_xlim(0, top * 1.22)


def page(rows: list[dict], target: Path, formats: list[str], title: str) -> list[Path]:
    """One page's statistics: three panels, a bar per curve."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = [_label(r["curve"]) for r in rows]
    height = 1.2 + 0.32 * len(rows)
    fig, axes = plt.subplots(1, len(PANELS), figsize=(18.5, height), sharey=True, facecolor=SURFACE)
    for k, (ax, (key, name)) in enumerate(zip(axes, PANELS)):
        notes = ["reference" if r["is_reference"] and key != "area" else "no bins compared" for r in rows]
        values = [None if (r["is_reference"] and key != "area") else r[key] for r in rows]
        _style(ax, labels)
        _bars(ax, values, notes)
        if key in ("area_ratio", "ratio_mean"):
            ax.axvline(1, color=MUTED, linewidth=0.8, linestyle=":")      # the reference's own
        ax.set_title(name, color=INK, fontsize=10, loc="left")
        if k == 0:
            ax.set_yticks(range(len(labels)), labels, color=INK, fontsize=9)
    reference = rows[0]["reference"] if rows else ""
    fig.suptitle(f"{title}  ·  against {_label(reference)}", color=MUTED, fontsize=9, x=0.01, ha="left")
    fig.tight_layout()
    written = []
    target.parent.mkdir(parents=True, exist_ok=True)
    for fmt in formats:
        path = target.with_suffix(f".{fmt}")
        fig.savefig(path, dpi=150, facecolor=SURFACE)
        written.append(path)
    plt.close(fig)
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
COLUMNS, ROWS = 13, 42                                          # a table page's most columns and rows
RULES = {key: rule for key, _, rule in TABLES}


def _footnote(text: str, width: float) -> tuple[str, float]:
    """A footnote wrapped to a figure `width` inches wide, and the height it takes, inches."""
    lines = textwrap.wrap(text, width=max(60, int((width - 0.3) * 72 / (FOOT * 0.55))))
    return "\n".join(lines), 0.16 + len(lines) * FOOT * 1.35 / 72


def _place(fig, note: str, foot: float) -> None:
    """The footnote at the figure's foot, the rest laid out above it."""
    height = fig.get_size_inches()[1]
    fig.tight_layout(rect=(0, foot / height, 1, 1))
    fig.text(0.15 / fig.get_size_inches()[0], 0.08 / height, note, ha="left", va="bottom", color=MUTED,
             fontsize=FOOT, linespacing=1.35)


def _short(objects: list[str]) -> dict[str, str]:
    """Each object's column title: its short name without -x01-y01 when that stays unique."""
    import re
    names = {o: o.rsplit("/", 1)[-1] for o in objects}
    trimmed = {o: re.sub(r"-x01-y01$", "", n) for o, n in names.items()}
    return trimmed if len(set(trimmed.values())) == len(objects) else names


def _shade(fraction: float, low=LIGHT, high=DARK) -> tuple:
    f = min(max(fraction, 0.0), 1.0)
    return tuple(a + (b - a) * f for a, b in zip(low, high))


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


def _ratio_bars(ax, values: list[float]) -> None:
    """Bars from the line at one, blue above it and orange below, each value at its tip."""
    span = max([abs(v - 1) for v in values] + [0.0]) or 0.05
    for i, value in enumerate(values):
        ax.barh(i, value - 1, left=1, height=0.55, color=DARK if value >= 1 else WARM, edgecolor=SURFACE, linewidth=2)
        tip = value + (0.02 if value >= 1 else -0.02) * span
        ax.text(tip, i, _shown(value), va="center", ha="left" if value >= 1 else "right", color=INK, fontsize=8)
    ax.axvline(1, color=MUTED, linewidth=0.8)
    ax.set_xlim(1 - 1.3 * span, 1 + 1.3 * span)


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


def ranking_figure(rows: list[dict], key: str, plt):
    """A statistic's ranking (V174): each point's mean over the pages where it was compared, as sorted bars, lowest
    first (a ratio: closest to 1 first, its geometric mean); None when no point has one."""
    title, rule = next((t, r) for k, t, r in TABLES if k == key)
    rows = _rows_of(rows)
    points, means = _points(rows), _means(rows, key)
    if not means:
        return None
    ratio = rule == "ratio"
    ranked = sorted(means, key=lambda p: (_distance(key, means[p][0]), points[p]))
    order = "closest to 1 first, bars from 1: blue above, orange below" if ratio else "lowest first"
    note, foot = _footnote(" ".join([RANKING_NOTE.format(mean=GEOMETRIC if ratio else "plain", name=PLAIN[key],
                                                         order=order), NOTES[key], COMPARED]), 8)
    fig, ax = plt.subplots(figsize=(8, 1.2 + 0.3 * len(ranked) + foot), facecolor=SURFACE)
    names = [f"{points[p]}  ({means[p][1]})" for p in ranked]
    _style(ax, names)
    if ratio:
        _ratio_bars(ax, [means[p][0] for p in ranked])
    else:
        _bars(ax, [means[p][0] for p in ranked], ["" for _ in ranked])
    ax.set_yticks(range(len(names)), names, color=INK, fontsize=9)
    ax.set_title(f"{title}: each point's {'geometric ' if ratio else ''}mean over its pages (pages compared)",
                 color=INK, fontsize=10, loc="left")
    _place(fig, note, foot)
    return fig


def _draw(plt, title: str, labels: list[str], headers: list[str], cells: list[list[tuple]], note: str,
          tail: int = 0, bold: frozenset = frozenset()) -> list[tuple[str, object]]:
    """A table over as many pages as it needs: at most COLUMNS columns a page (its last `tail` columns, a mean or a
    total, on the last), at most ROWS rows; each cell (text, background, ink), each column as wide as its text; its
    title (the part after it on a split table), its footnote; the rows in `bold` with their labels bold.
    (suffix, figure) each: "" for one page, else -<column part>-<row part>."""
    body = len(headers) - tail
    starts = list(range(0, max(body, 1), COLUMNS))
    split = len(starts) > 1 or len(labels) > ROWS
    out = []
    for c0 in starts:
        columns = list(range(c0, min(c0 + COLUMNS, body))) + (list(range(body, len(headers))) if c0 == starts[-1] else [])
        for r0 in range(0, len(labels), ROWS):
            block = range(r0, min(r0 + ROWS, len(labels)))
            widths = [max(0.62, 0.15 + 0.065 * max([len(headers[j])] + [len(cells[i][j][0]) for i in block])) for j in columns]
            width = max(6.5, 2.2 + 0.075 * max(len(labels[i]) for i in block) + sum(widths))
            wrapped, foot = _footnote(note, width)
            fig, ax = plt.subplots(figsize=(width, 0.6 + 0.17 * (len(block) + 1) + foot), facecolor=SURFACE)
            ax.axis("off")
            table = ax.table(cellText=[[cells[i][j][0] for j in columns] for i in block],
                             cellColours=[[cells[i][j][1] for j in columns] for i in block],
                             rowLabels=[labels[i] for i in block], colLabels=[headers[j] for j in columns],
                             colWidths=[w / sum(widths) for w in widths], bbox=[0, 0, 1, 1],    # filling its axes
                             cellLoc="center", rowLoc="right")
            table.auto_set_font_size(False)
            table.set_fontsize(7)
            for (i, j), cell in table.get_celld().items():
                cell.set_edgecolor(GRID)
                cell.set_linewidth(0.6)
                if i == 0 or j == -1:
                    cell.get_text().set_color(INK)
                    cell.set_facecolor(SURFACE)
                    if j == -1 and i > 0 and block[i - 1] in bold:
                        cell.get_text().set_fontweight("bold")
                else:
                    cell.get_text().set_color(cells[block[i - 1]][columns[j]][2])
            head, _, rest = title.partition("\n")
            part = f"  ({c0 // COLUMNS + 1}·{r0 // ROWS + 1})" if split else ""
            ax.set_title(head + part + (f"\n{rest}" if rest else ""), color=INK, fontsize=9, loc="left")
            _place(fig, wrapped, foot)
            out.append((f"-{c0 // COLUMNS + 1}-{r0 // ROWS + 1}" if split else "", fig))
    return out


def _natural(objects) -> list[str]:
    """Objects in natural order: d2 before d10."""
    import re
    return sorted(objects, key=lambda o: [int(s) if s.isdigit() else s for s in re.split(r"(\d+)", o)])


def table_figures(rows: list[dict], plt) -> list[tuple[str, object]]:
    """The summary's tables (V174): per statistic, a row per point (in curve order, its page cell before its label)
    and a column per object, each cell the point's number on that object's page, then its mean; the reference
    curve's cell says "ref", a missing one "–". Shaded by value (TABLES' rule), its text white on dark. Cut into
    pages of at most COLUMNS objects and ROWS points. (statistic key, figure) each."""
    return list(_tables(rows, plt))


def _tables(rows: list[dict], plt, only: tuple = ()):
    """table_figures' pages as they are drawn, of the statistics in `only` (else all)."""
    rows = _rows_of(rows)
    points, cells = _points(rows), {}
    for r in rows:
        cells[(r["point"], r["object"])] = r
    objects = _natural({r["object"] for r in rows})
    if not points or not objects:
        return
    short = _short(objects)
    references = sorted({str(r["reference"]) for r in rows})
    for key, title, rule in TABLES:
        if only and key not in only:
            continue

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
        low, high = min(found), max(found)
        spread = max(abs(math.log10(v)) for v in found) if rule == "ratio" else 0.0

        def fraction(value, obj):
            if rule == "ratio":
                return 0.0 if not spread or value <= 0 else abs(math.log10(value)) / spread
            if rule == "log":
                lo, hi = math.log10(max(low, 1e-3)), math.log10(max(high, 1e-3))
                return 0.0 if hi == lo else (math.log10(max(value, 1e-3)) - lo) / (hi - lo)
            if rule == "column" and obj is not None:
                column = [v for p in points if (v := number(p, obj)) is not None]
                lo, hi = min(column), max(column)
                return 0.0 if hi == lo else (value - lo) / (hi - lo)
            return 0.0 if high == low else (value - low) / (high - low)

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
        shading = {"log": "darker is larger, log scale", "linear": "darker is larger",
                   "column": "darker is larger within each column; mean unshaded",
                   "ratio": "blue above 1, orange below, darker further from 1 (log scale: 2 and 0.5 alike)"}[rule]
        against = "" if key == "area" else (f" against {', '.join(_label(r) for r in references)}"
                                            if len(references) <= 2 else " against each page's reference")
        table_note = TABLE_NOTE.format(mean=GEOMETRIC if rule == "ratio" else "plain")
        note = " ".join([NOTES[key]] + ([COMPARED] if key != "area" else []) + [table_note])
        yield from ((key + suffix, fig) for suffix, fig in
                    _draw(plt, f"{title}{against}\n{shading}", [points[p] for p in points],
                          [short[o] for o in objects] + ["mean"], styled, note, tail=1))


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


def _scoreboard(plt, title: str, points: dict, board: dict, ranks: dict, rates: dict, columns: list[tuple[str, str]],
                note: str, cells_of: dict | None = None) -> list[tuple[str, object]]:
    """A scoreboard: a row per point in `board` ({point: {column: points}}), its place before its name (within its
    page cell when `cells_of` names them), a column per (key, header) in `columns`, then its total, its wins, its
    head-to-head win rate (`rates`) and the mean of its places (`ranks`). Points darker as they score more."""
    groups = list(dict.fromkeys(cells_of[p] for p in board)) if cells_of else [None]
    order, labels, bold, totals, wins, mean_rank = [], [], set(), {}, {}, {}
    for group in groups:
        members = {p: s for p, s in board.items() if cells_of is None or cells_of[p] == group}
        ordered, places, total, won, mean = _standing(members, ranks, points)
        totals.update(total), wins.update(won), mean_rank.update(mean)
        for p in ordered:
            if places[p] <= 3:
                bold.add(len(order))
            order.append(p)
            labels.append(f"{places[p]}. {points[p]}")
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
    return _draw(plt, title, labels, [h for _, h in columns] + ["total", "wins", "win rate", "mean rank"], styled,
                 note, tail=4, bold=frozenset(bold))


def _matches(plt, cell: str, members: list[str], points: dict, pairs: dict, rates: dict,
             note: str) -> list[tuple[str, object]]:
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
    title = f"Head to head{f': {cell}' if cell else ''}\nthe row's point against each column's: matches won of played"
    return _draw(plt, title, [f"{places[p]}. {points[p]}" for p in order], [short[q] for q in order]
                 + ["win rate", "matches"], styled, note, tail=2, bold=frozenset(i for i, p in enumerate(order)
                                                                                if places[p] <= 3))


def standings_figures(rows: list[dict], plt) -> list[tuple[str, object]]:
    """The summary's standings (V176, V177): each page's own rankings scored (POINTS) and played as matches, so that
    they say what is best on most pages, as a mode does, where the ranking pages' means say what is best on average.
    Each a table: the top five, the scoreboard of all five statistics page by page, by page cell, each cell's head
    to head, then a scoreboard a statistic. (name, figure) each: top5, scoreboard, scoreboard-cells,
    head-to-head-<n>, scoreboard-<statistic> (and their parts)."""
    return list(_standings(rows, plt))


def _standings(rows: list[dict], plt):
    """standings_figures' pages as they are drawn."""
    rows = _rows_of(rows)
    points = _points(rows)
    rankings, object_of, data_only = _page_rankings(rows)
    if not points or not rankings:
        return
    counted = ("Only the pages compared against data count: on a page compared against its first curve, that curve "
               "cannot be ranked." if data_only else
               "No page here has data: each is compared against its first curve, which cannot be ranked there, so a "
               "point that is a page's reference scores nothing on it.")
    apart = "Points of different page cells never meet: a page holds one cell's points."
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

    boards = [("all five", every, ranks)] + [(PLAIN[k], by_key[k], key_ranks[k]) for k in keys]
    standings = [_standing(board, rank, points) for _, board, rank in boards]
    by_rate = sorted(rates, key=lambda p: (-rates[p][0] / rates[p][1], points[p]))
    rate_places = _places({p: -rates[p][0] / rates[p][1] for p in by_rate})
    cells = []
    for row in range(len(POINTS)):
        line = []
        for order, places, totals, wins, _ in standings:
            if row < len(order):
                p = order[row]
                line.append((f"{points[p]}  {totals[p]} pts, {wins[p]} {'win' if wins[p] == 1 else 'wins'}"
                             + (f"  (={_ordinal(places[p])})" if places[p] != row + 1 else ""), SURFACE, INK))
            else:
                line.append(("–", SURFACE, MUTED))
        if row < len(by_rate):
            p = by_rate[row]
            line.append((f"{points[p]}  {rates[p][0] / rates[p][1]:.0%} of {rates[p][1]}"
                         + (f"  (={_ordinal(rate_places[p])})" if rate_places[p] != row + 1 else ""), SURFACE, INK))
        else:
            line.append(("–", SURFACE, MUTED))
        cells.append(line)
    note = ("Each column: a scoreboard's first five, its points and wins over the pages (all five: every statistic's "
            "points together, as the page-by-page scoreboard); head to head: the first five by win rate over every "
            f"match, and their number; (=2nd): sharing that place. {apart} {counted} {SCORE_NOTE} {H2H_NOTE}")
    yield from ((f"top5{s}", f) for s, f in
                _draw(plt, "The top five: best on the most pages\neach scoreboard's first five",
                      [_ordinal(n) for n in range(1, len(POINTS) + 1)],
                      [name for name, _, _ in boards] + ["head to head"], cells, note))
    note = ("A row per point, a column per object's page: the points it scored on that page, its five statistics' "
            f"together (at most 25); total: over its pages. {apart} {counted} {SCORE_NOTE} {H2H_NOTE}")
    yield from ((f"scoreboard{s}", f) for s, f in
                _scoreboard(plt, "Scoreboard: all five statistics, page by page\nsorted by total; darker: more points",
                            points, every, ranks, rates, [(o, short[o]) for o in objects], note))
    note = ("The same points, a row per point by its page cell (its plot_points), placed within its cell: a column "
            "per statistic, the points it scored in that statistic over the cell's pages; total: their sum (its "
            f"page-by-page total). {counted} {SCORE_NOTE} {H2H_NOTE}")
    cells_of = {r["point"]: r.get("cell", "") for r in rows}
    yield from ((f"scoreboard-cells{s}", f) for s, f in
                _scoreboard(plt, "Scoreboard: by page cell\neach cell's points placed among themselves", points,
                            by_cell, ranks, rates, [(k, PLAIN[k]) for k in keys], note, cells_of=cells_of))
    note = (f"A cell: the matches the row's point won against the column's, over the cell's pages and the five "
            f"statistics, of those they played (a draw counts half); blue: it won most, orange: it lost most, "
            f"darker further from even. Win rate: over all its matches. Sorted by win rate; bold: the top three. "
            f"{counted} {H2H_NOTE}")
    for n, cell in enumerate(dict.fromkeys(cells_of[p] for p in every), 1):
        members = [p for p in every if cells_of[p] == cell]
        if len(members) > 1:
            yield from ((f"head-to-head-{n}{s}", f) for s, f in
                        _matches(plt, cell, members, points, pairs, rates, note))
    for key in keys:
        note = (f"A row per point, a column per object's page: the points its place in {PLAIN[key]} on that page "
                f"scored; total: over its pages; win rate: its matches in {PLAIN[key]} alone. {NOTES[key]} {apart} "
                f"{counted} {SCORE_NOTE} {H2H_NOTE}")
        yield from ((f"scoreboard-{key}{s}", f) for s, f in
                    _scoreboard(plt, f"Scoreboard: {PLAIN[key]}, page by page\nsorted by total; darker: more points",
                                points, by_key[key], key_ranks[key], key_rates[key], [(o, short[o]) for o in objects],
                                note))


def summary_figures(rows: list[dict], plt) -> list[tuple[str, object]]:
    """The summary's pages in order: the standings (V176), then per statistic its ranking (but the area's) and its
    tables (V174)."""
    return list(_summary_pages(rows, plt))


def _summary_pages(rows: list[dict], plt):
    """summary_figures' pages as they are drawn, so that each is written and closed before the next."""
    yield from _standings(rows, plt)
    for key, _, _ in TABLES:
        ranking = ranking_figure(rows, key, plt) if key != "area" else None
        if ranking is not None:
            yield f"{key}-ranking", ranking
        yield from _tables(rows, plt, only=(key,))


def summary_of(rows: list[dict], target: Path, formats: list[str]) -> list[Path]:
    """The summary (V174): `target`.pdf holds every page; a PNG or SVG is a file a page in the folder `target`,
    <target name>_<NN>.<fmt> in the PDF's order."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    written, pdf, number = [], None, 0
    try:
        for number, (_, figure) in enumerate(_summary_pages(rows, plt), 1):
            if "pdf" in formats:
                if pdf is None:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    pdf = PdfPages(target.with_suffix(".pdf"))
                    written.append(target.with_suffix(".pdf"))
                pdf.savefig(figure, facecolor=SURFACE)
            for fmt in (f for f in formats if f != "pdf"):
                target.mkdir(parents=True, exist_ok=True)
                path = target / f"{target.name}_{number:02d}.{fmt}"
                figure.savefig(path, dpi=150, facecolor=SURFACE)
                written.append(path)
            plt.close(figure)
    finally:
        if pdf is not None:
            pdf.close()
    return written


def draw(pages: list[tuple[str, list[dict]]], folder: Path, formats: list[str], summary: Path | None = None) -> int:
    """Every page's image into `folder`, then the summary (`summary`, else folder/summary); the number of images."""
    formats = [f for f in formats if f in ("png", "pdf", "svg")] or ["png"]
    made = 0
    for name, rows in pages:
        if rows:
            made += bool(page(rows, folder / name, formats, name))
    made += bool(summary_of([r for _, rows in pages for r in rows], summary or folder / "summary", formats))
    return made
