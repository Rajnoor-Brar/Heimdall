"""framework/plot/figures/typeset.py — paper.py's document typeset in LaTeX (I-110): a report's statistics as its own
text, not pictures of other pages.

The third renderer of the model (beside paper.figure, Matplotlib's A4 pages, and webpage.render, one HTML page):
the same facts, items and notes, set in the report's fonts and colours (the macros report.tex's preamble defines:
`\\hdItem`, `\\hdSub`, `\\hdFacts`, `\\hdNotes`, the colours `hdink`, `hdmuted`, `hdrule`, `hdband`, `hdaccent`).

* `document(doc, numbers, scale, tex, width)`: its facts, then each section's items, then its notes, numbered as
  `numbers` says (paper.note_numbers). `scale` is paper.py itself (its colours, its bars' reach, its text widths);
  `tex` the escaper (layout.tex: specials escaped, `$…$` kept); `width` the text's width in bp.
* A **table** is one `longtable` a column block: the fewest blocks that fit the width, as paper.py cuts them (its
  data columns in order, its last `tail` columns on the last block), each with the row labels; its header again on
  each page, a band (a group's name) across it, a cell's fill (the shading), ink and weight as the model says, a
  summing row after a rule.
* A **ranking** is a table of bars drawn with rules: from 0, or both ways from its base (a ratio's 1), as far as
  paper.reach; a bar beyond is cut, its value marked, its colour paper.colour_of's (V205).
* **`bars(rows, title, subtitle, panels, scale, tex, width)`**: a page's statistics as a table, a row a curve, a
  column a statistic (`panels`: bars.PANELS, (key, label) each), each a small bar and its value: what bars.page
  draws as an image.
"""

from __future__ import annotations

import math

SIZE = 8.0                      # pt: a table's text, as the preamble's \hdTable sets it
PAD = 5.0                       # bp: a cell's padding, each side (\tabcolsep)
LABEL_MOST = 170.0              # bp: a row label's column, at most (its text wraps)
HEAD_LINES = 3                  # a column header's most lines
RANK_BAR = 190.0                # bp: a ranking's bar track
BAR_TRACK = 34.0                # bp: a statistic's bar track in a page's table
BAR_HEIGHT = 5.0                # bp


def _hex(value) -> str:
    """A colour as xcolor's HTML model takes it: #rrggbb, or (r, g, b) of 0–1."""
    if isinstance(value, (tuple, list)):
        return "".join(f"{max(0, min(255, round(255 * c))):02X}" for c in value[:3])
    return str(value).lstrip("#").upper()


def _inches(text: str, scale) -> float:
    return scale.width(text, SIZE) if text else 0.0


def _width(text: str, scale, lines: int = 1) -> float:
    """bp a text takes at SIZE, over at most `lines` lines (its longest word at least)."""
    if not text:
        return 0.0
    whole = _inches(text, scale)
    longest = max((_inches(w, scale) for w in text.split()), default=whole)
    return 72.0 * max(longest, whole / lines)


def _marks(item, numbers: dict) -> str:
    named = sorted({numbers[k] for k in getattr(item, "notes", ()) if k in numbers})
    return "\\textsuperscript{" + ",".join(str(n) for n in named) + "}" if named else ""


def _title(item, numbers: dict, tex) -> list[str]:
    lines = [f"\\hdItem{{{tex(item.title)}{_marks(item, numbers)}}}"]
    if getattr(item, "subtitle", ""):
        lines.append(f"\\hdSub{{{tex(item.subtitle)}}}")
    return lines


def _cell(cell, tex, ink: str, surface: str) -> str:
    text = tex(cell.text) if cell.text not in ("", None) else ""
    if cell.bold and text:
        text = f"\\textbf{{{text}}}"
    if _hex(cell.ink) != _hex(ink) and text:
        text = f"\\textcolor[HTML]{{{_hex(cell.ink)}}}{{{text}}}"
    if getattr(cell, "align", "center") == "left":
        text = "\\raggedright " + text
    fill = "" if _hex(cell.fill) == _hex(surface) else f"\\cellcolor[HTML]{{{_hex(cell.fill)}}}"
    return fill + text


def _blocks(widths: list[float], room: float, tail: int) -> list[list[int]]:
    """Column indices a block, the fewest that fit `room` bp, in order; the last `tail` columns together on the
    last block."""
    body = list(range(len(widths) - tail)) if tail else list(range(len(widths)))
    kept = list(range(len(widths) - tail, len(widths))) if tail else []
    blocks: list[list[int]] = [[]]
    for j in body:
        if blocks[-1] and sum(widths[i] for i in blocks[-1]) + widths[j] > room:
            blocks.append([])
        blocks[-1].append(j)
    if kept:
        if blocks[-1] and sum(widths[i] for i in blocks[-1] + kept) > room:
            blocks.append([])
        blocks[-1] += kept
    return [b for b in blocks if b]


def table(item, numbers: dict, scale, tex, width: float) -> list[str]:
    """A table as `longtable` column blocks (see the module's doc)."""
    headers, rows = list(item.headers), list(item.rows)
    cells = [r for r in rows if not r.band]
    label_w = min(LABEL_MOST, max([_width(r.label, scale) for r in rows] + [_width("point", scale)])) + 2 * PAD
    widths = []
    for j, head in enumerate(headers):
        texts = [r.cells[j].text for r in cells if j < len(r.cells)]
        widths.append(max([_width(head, scale, HEAD_LINES)] + [_width(t, scale) for t in texts]) * 1.06 + 2 * PAD)
    blocks = _blocks(widths, width - label_w - 1, getattr(item, "tail", 0)) if headers else [[]]
    out = _title(item, numbers, tex)
    for k, block in enumerate(blocks):
        spec = f"@{{}}>{{\\raggedright\\arraybackslash}}p{{{label_w - 2 * PAD:.1f}bp}}" + \
            "".join(f">{{\\centering\\arraybackslash}}p{{{widths[j] - 2 * PAD:.1f}bp}}" for j in block)
        head = " & " + " & ".join(f"\\textbf{{{tex(headers[j])}}}" for j in block) + "\\\\"
        span = len(block) + 1
        if k:
            out.append("\\hdBlockGap")
        out += [f"\\begin{{hdTable}}{{{spec}}}", "\\toprule", head, "\\midrule", "\\endfirsthead",
                f"\\multicolumn{{{span}}}{{@{{}}l}}{{\\hdContinued}}\\\\", "\\toprule", head, "\\midrule", "\\endhead",
                "\\bottomrule", "\\endfoot"]
        for row in rows:
            if row.band:
                out.append(f"\\multicolumn{{{span}}}{{@{{}}>{{\\columncolor{{hdband}}[0pt][\\tabcolsep]}}l}}{{\\textbf{{{tex(row.label)}}}}}\\\\")
                continue
            if getattr(row, "pinned", False):
                out.append("\\midrule")
            label = tex(row.label)
            label = f"\\textbf{{{label}}}" if row.bold else label
            out.append(label + " & " + " & ".join(_cell(row.cells[j], tex, scale.INK, scale.SURFACE)
                                                  if j < len(row.cells) else "" for j in block) + "\\\\")
        out.append("\\end{hdTable}")
    return out


def _shown(value: float) -> str:
    return f"{value:,.0f}" if 100 <= abs(value) < 1e6 else f"{value:.3g}"


def _bar(offset: float, span: float, track: float, both: bool, colour: str) -> str:
    """A bar in a picture `track` bp wide: from its left, or both ways from its middle; an axis line at 0."""
    drawn = min(span, max(-span if both else 0.0, offset))
    if both:
        middle = track / 2
        length = abs(drawn) / span * middle if span else 0.0
        x = middle - length if drawn < 0 else middle
        axis = middle
    else:
        length = drawn / span * track if span else 0.0
        x, axis = 0.0, 0.0
    return (f"\\begin{{picture}}({track:.1f},{BAR_HEIGHT + 2:.1f})"
            f"\\put({x:.2f},1){{\\textcolor[HTML]{{{_hex(colour)}}}{{\\rule{{{max(length, 0.0):.2f}bp}}{{{BAR_HEIGHT}bp}}}}}}"
            f"\\put({axis:.2f},0){{\\textcolor{{hdrule}}{{\\rule{{0.5bp}}{{{BAR_HEIGHT + 2:.1f}bp}}}}}}"
            "\\end{picture}")


def ranking(item, numbers: dict, scale, tex, width: float) -> list[str]:
    """A ranking as a table of bars (see the module's doc)."""
    values = list(item.values)
    base = item.base
    offsets = [v - base if base else max(v, 0.0) for v in values]
    span = scale.reach(offsets) or (0.05 if base else 1.0)
    absurd = scale.absurd_from(offsets)
    label_w = min(LABEL_MOST + 40, max([_width(n, scale) for n in item.names] + [60.0])) + 2 * PAD
    value_w = max([_width(_shown(v), scale) for v in values] + [30.0]) + 18 + 2 * PAD
    track = max(60.0, min(RANK_BAR, width - label_w - value_w - 2 * PAD))
    spec = (f"@{{}}>{{\\raggedright\\arraybackslash}}p{{{label_w - 2 * PAD:.1f}bp}}"
            f">{{\\raggedright\\arraybackslash}}p{{{track:.1f}bp}}>{{\\raggedleft\\arraybackslash}}p{{{value_w - 2 * PAD:.1f}bp}}")
    head = "\\textbf{point (pages)} & & \\textbf{value}\\\\"
    out = _title(item, numbers, tex)
    out += [f"\\begin{{hdTable}}{{{spec}}}", "\\toprule", head, "\\midrule", "\\endfirsthead",
            "\\multicolumn{3}{@{}l}{\\hdContinued}\\\\", "\\toprule", head, "\\midrule", "\\endhead", "\\bottomrule", "\\endfoot"]
    for name, value, offset in zip(item.names, values, offsets):
        both = bool(base)
        drawn = min(span, max(-span if both else 0.0, offset))
        colour = scale.colour_of(offset, span, absurd, *item.colours)
        said = _shown(value) if drawn == offset else (scale.CUT[0] + _shown(value) if drawn >= 0 else _shown(value) + scale.CUT[1])
        out.append(f"{tex(name)} & {_bar(offset, span, track, both, colour)} & {tex(said)}\\\\")
    out.append("\\end{hdTable}")
    return out


def text(item, numbers: dict, tex) -> list[str]:
    out = _title(item, numbers, tex)
    for line in item.lines:
        number, said, _, bold = (list(line) + ["", "", "", False])[:4]
        if not said:
            continue
        said = tex(said)
        out.append((f"\\hdMuted{{{number}.}}~" if number else "") + ("\\textbf{" + said + "}" if bold else said) + "\\par")
    return out


def _item(item, numbers: dict, scale, tex, width: float) -> list[str]:
    if hasattr(item, "headers"):
        return table(item, numbers, scale, tex, width)
    if hasattr(item, "values"):
        return ranking(item, numbers, scale, tex, width)
    return text(item, numbers, tex)


def document(doc, numbers: dict, scale, tex, width: float) -> list[str]:
    """A document's facts, its sections' items (each section's title over them when it has several), its notes."""
    out: list[str] = []
    if doc.facts:
        out += ["\\begin{hdFacts}", *(f"\\item {tex(fact)}" for fact in doc.facts), "\\end{hdFacts}"]
    for section in doc.sections:
        if not section.items:
            continue
        if len(doc.sections) > 1 or len(section.items) > 1:
            out.append(f"\\hdStatSection{{{tex(section.title)}}}")
        for item in section.items:
            out += _item(item, numbers, scale, tex, width)
    if numbers:
        out += ["\\begin{hdNotes}"]
        out += [f"\\item[{n}.] {tex(doc.notes[key])}" for key, n in sorted(numbers.items(), key=lambda kv: kv[1])]
        out.append("\\end{hdNotes}")
    return out


def bars(rows: list[dict], title: str, subtitle: str, panels, scale, tex, width: float) -> list[str]:
    """A page's statistics as a table: a row a curve (the reference's marked), a column a statistic, each a bar
    from 0 (both ways when one is below it) as far as paper.reach, and its value; a value missing is a dash."""
    def number(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) or math.isinf(value) else None

    label_w = min(LABEL_MOST - 30, max([_width(str(r.get("curve", "")), scale) for r in rows] + [60.0])) + 2 * PAD
    column = (width - label_w) / len(panels)
    value_w = 38.0
    track = max(14.0, column - value_w - 2 * PAD)
    spec = f"@{{}}>{{\\raggedright\\arraybackslash}}p{{{label_w - 2 * PAD:.1f}bp}}" + \
        "".join(f">{{\\raggedright\\arraybackslash}}p{{{column - 2 * PAD:.1f}bp}}" for _ in panels)
    head = "\\textbf{curve} & " + " & ".join(f"\\textbf{{{tex(name)}}}" for _, name in panels) + "\\\\"
    out = [f"\\hdItem{{{tex(title)}}}"] + ([f"\\hdSub{{{tex(subtitle)}}}"] if subtitle else [])
    out += [f"\\begin{{hdTable}}{{{spec}}}", "\\toprule", head, "\\midrule", "\\endfirsthead",
            f"\\multicolumn{{{len(panels) + 1}}}{{@{{}}l}}{{\\hdContinued}}\\\\", "\\toprule", head, "\\midrule", "\\endhead",
            "\\bottomrule", "\\endfoot"]
    scales = {}
    for key, _ in panels:
        found = [v for v in (number(r.get(key)) for r in rows if not _true(r.get("is_reference"))) if v is not None and math.isfinite(v)]
        scales[key] = (scale.reach(found) or 1.0, scale.absurd_from(found), any(v < 0 for v in found))
    for row in rows:
        label = tex(str(row.get("curve", "")))
        if _true(row.get("is_reference")):
            out.append(f"\\textit{{{label}}} & " + " & ".join("\\hdMuted{reference}" if k == 0 else "" for k in range(len(panels))) + "\\\\")
            continue
        cells = []
        for key, _ in panels:
            value = number(row.get(key))
            if value is None:
                cells.append("\\hdMuted{–}")
                continue
            span, absurd, both = scales[key]
            if math.isinf(value):
                cells.append("\\hdMuted{" + ("∞" if value > 0 else "−∞") + "}")
                continue
            drawn = min(span, max(-span if both else 0.0, value))
            said = _shown(value) if drawn == value else (scale.CUT[0] + _shown(value) if drawn >= 0 else _shown(value) + scale.CUT[1])
            colour = scale.colour_of(value, span, absurd)
            cells.append(f"{_bar(value, span, track, both, colour)}\\hspace{{3bp}}{{\\hdSmall {tex(said)}}}")
        out.append(label + " & " + " & ".join(cells) + "\\\\")
    out.append("\\end{hdTable}")
    return out


def _true(value) -> bool:
    return value is True or str(value).strip().lower() == "true"
