"""framework/plot/figures/webpage.py — paper.py's document as one self-contained HTML page (V199, I-107):
statistics/<set>/summary.html beside summary.pdf.

The same facts, contents, sections, tables, rankings and notes, without pages: a table is whole, however wide, and
scrolls on its own, its header row and its label column sticky. A click on a column's header sorts the table by
it (numbers as numbers, then text; –, ref and blanks last), again the other way; a grouped table sorts within
each of its bands (a <tbody> each), a pinned row (a mean) stays last, and the label column's header puts the table
back in its order. Each item links its notes. Inline CSS and script; no external file or library.

`render(document, numbers, scale)`: the page's text, `numbers` the notes' numbers (paper.note_numbers), `scale`
paper.py itself, for its bars' reach and colours (V205). Items are read by their fields (a table's headers and
rows, a ranking's names and values), not by their class.
"""

from __future__ import annotations

import html
import re

#: TeX's commands as characters, for a label's $…$.
SYMBOLS = {"alpha": "α", "beta": "β", "gamma": "γ", "Gamma": "Γ", "delta": "δ", "Delta": "Δ", "epsilon": "ε",
           "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "Theta": "Θ", "kappa": "κ", "lambda": "λ",
           "Lambda": "Λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "Pi": "Π", "rho": "ρ", "sigma": "σ",
           "Sigma": "Σ", "tau": "τ", "phi": "φ", "varphi": "φ", "Phi": "Φ", "chi": "χ", "psi": "ψ", "Psi": "Ψ",
           "omega": "ω", "Omega": "Ω", "ell": "ℓ", "cdot": "·", "times": "×", "pm": "±", "mp": "∓", "to": "→",
           "rightarrow": "→", "leftarrow": "←", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠",
           "approx": "≈", "sim": "∼", "infty": "∞", "sqrt": "√", "langle": "⟨", "rangle": "⟩", "prime": "′",
           "circ": "°", "gg": "≫", "ll": "≪", "propto": "∝", "sum": "Σ", "int": "∫", "partial": "∂"}
INK, SURFACE = "#0b0b0b", "#fcfcfb"                 # paper.py's: a cell of them needs no style
SPACES = {",": "\u2009", ";": "\u2005", ":": "\u2005", " ": " ", "!": "", "quad": "\u2003", "qquad": "\u2003\u2003"}

CSS = """
:root { color-scheme: light; --ink: #0b0b0b; --muted: #52514e; --grid: #e4e3df; --surface: #fcfcfb; --band: #efeeea;
  --link: #14457a; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--surface); color: var(--ink);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", "DejaVu Sans", sans-serif; }
header, nav, main, #notes { max-width: 1200px; margin: 0 auto; padding: 0 16px; }
header { padding-top: 24px; }
.kicker { margin: 0; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }
h1 { margin: 4px 0 8px; font-size: 22px; font-weight: 600; overflow-wrap: anywhere; }
h2 { margin: 32px 0 8px; font-size: 18px; font-weight: 600; }
.facts p { margin: 2px 0; }
nav ol { margin: 4px 0; padding-left: 20px; }
nav > ol > li { font-weight: 600; }
nav ol ol { font-weight: 400; }
a { color: var(--link); }
figure { margin: 16px 0 24px; }
figcaption { margin-bottom: 6px; }
figcaption .title { display: block; font-weight: 600; }
figcaption .sub { display: block; color: var(--muted); font-size: 12px; }
.scroll { overflow: auto; max-height: 85vh; max-width: 100%; border: 1px solid var(--grid); }
table { border-collapse: separate; border-spacing: 0; font-size: 12px; font-variant-numeric: tabular-nums; }
th, td { padding: 3px 6px; border-right: 1px solid var(--grid); border-bottom: 1px solid var(--grid);
  white-space: nowrap; text-align: center; }
thead th { position: sticky; top: 0; z-index: 2; background: var(--surface); font-weight: 500; cursor: pointer;
  user-select: none; white-space: normal; min-width: 3.2em; max-width: 10em; vertical-align: bottom; }
thead th[data-dir="up"]::after { content: " ▲"; font-size: 9px; }
thead th[data-dir="down"]::after { content: " ▼"; font-size: 9px; }
th.label { position: sticky; left: 0; z-index: 1; background: var(--surface); text-align: left; font-weight: 400; }
thead th.label { z-index: 3; }
tr.band th { position: sticky; left: 0; background: var(--band); text-align: left; font-weight: 600; }
.b, th.label.b { font-weight: 700; }
td.l { text-align: left; }
td.bar { min-width: 260px; text-align: left; }
.track { position: relative; display: inline-block; vertical-align: middle; width: 200px; height: 10px; }
.track .fill { position: absolute; top: 0; height: 10px; }
.track .axis { position: absolute; top: -2px; width: 1px; height: 14px; background: var(--muted); }
td.bar span { margin-left: 6px; }
p.notes { margin: 4px 0 0; color: var(--muted); font-size: 12px; }
#notes ol { padding-left: 28px; }
#notes li { margin: 4px 0; }
#notes li:target { background: var(--band); }
footer { height: 32px; }
"""

SCRIPT = """
(function () {
  function value(row, col) {
    var cell = row.cells[col + 1];
    if (!cell) return null;
    var text = (cell.dataset.v !== undefined ? cell.dataset.v : cell.textContent).trim();
    if (text === "" || text === "\\u2013" || text === "ref") return null;
    var number = parseFloat(text.replace(/,/g, "").replace("%", ""));
    return isNaN(number) ? text : number;
  }
  function compare(x, y) {
    if (typeof x === "number" && typeof y === "number") return x - y;
    if (typeof x === "number") return -1;
    if (typeof y === "number") return 1;
    return String(x).localeCompare(String(y));
  }
  Array.prototype.forEach.call(document.querySelectorAll("table.sortable"), function (table) {
    var heads = table.tHead.rows[0].cells;
    Array.prototype.forEach.call(heads, function (th) {
      th.addEventListener("click", function () {
        var col = +th.dataset.col, up = th.dataset.dir !== "up";
        Array.prototype.forEach.call(heads, function (h) { delete h.dataset.dir; });
        if (col >= 0) th.dataset.dir = up ? "up" : "down";
        Array.prototype.forEach.call(table.tBodies, function (body) {
          var rows = Array.prototype.filter.call(body.rows, function (r) { return !r.classList.contains("band"); });
          var pinned = rows.filter(function (r) { return r.classList.contains("pin"); });
          var free = rows.filter(function (r) { return !r.classList.contains("pin"); });
          free.sort(function (a, b) {
            var order = a.dataset.i - b.dataset.i;
            if (col < 0) return order;
            var x = value(a, col), y = value(b, col);
            if (x === null || y === null) return x === y ? order : x === null ? 1 : -1;
            return (up ? compare(x, y) : compare(y, x)) || order;
          });
          free.concat(pinned).forEach(function (r) { body.appendChild(r); });
        });
      });
    });
  });
})();
"""


def _math(tex: str) -> str:
    """A $…$ span as HTML: TeX's commands as characters, ^{…} and _{…} raised and lowered."""
    s = html.escape(tex, quote=False)
    s = re.sub(r"\\(?:mathrm|text|textrm|mathit|mathbf|mathsf|rm|it|bf|operatorname)\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(quad|qquad|[,;:! ])", lambda m: SPACES[m[1]], s)
    s = re.sub(r"\\([A-Za-z]+)", lambda m: SYMBOLS.get(m[1], m[1]), s)
    s = re.sub(r"\^\{([^{}]*)\}", r"<sup>\1</sup>", s)
    s = re.sub(r"_\{([^{}]*)\}", r"<sub>\1</sub>", s)
    s = re.sub(r"\^(\S)", r"<sup>\1</sup>", s)
    s = re.sub(r"_(\S)", r"<sub>\1</sub>", s)
    return s.replace("{", "").replace("}", "")


def text_of(label: str) -> str:
    """A label as HTML: its text escaped, its $…$ spans as _math reads them (an odd dollar is a dollar)."""
    parts = str(label).split("$")
    if len(parts) % 2 == 0:
        return html.escape(str(label), quote=False)
    return "".join(_math(part) if k % 2 else html.escape(part, quote=False) for k, part in enumerate(parts))


def colour(value) -> str:
    """A colour for CSS: a name or #hex as it is, an (r, g, b) of 0–1 as #hex."""
    if isinstance(value, (tuple, list)):
        return "#" + "".join(f"{max(0, min(255, round(255 * c))):02x}" for c in value[:3])
    return html.escape(str(value), quote=True)


def anchor(prefix: str, key: str) -> str:
    return f"{prefix}-" + re.sub(r"[^A-Za-z0-9_-]", "-", key)


def _notes(item, numbers: dict) -> str:
    named = sorted({numbers[k] for k in item.notes if k in numbers})
    if not named:
        return ""
    links = ", ".join(f'<a href="#note-{n}">{n}</a>' for n in named)
    return f'<p class="notes">{"Notes" if len(named) > 1 else "Note"} {links}</p>'


def _caption(item) -> str:
    sub = f'<span class="sub">{text_of(item.subtitle)}</span>' if getattr(item, "subtitle", "") else ""
    return f'<figcaption><span class="title">{text_of(item.title)}</span>{sub}</figcaption>'


def _table(table, numbers: dict) -> list[str]:
    heads = "".join(f'<th data-col="{j}">{text_of(h)}</th>' for j, h in enumerate(table.headers))
    out = [f'<figure class="item" id="{anchor("i", table.key)}">', _caption(table),
           '<div class="scroll"><table class="sortable">',
           f'<thead><tr><th class="label" data-col="-1" title="the table\'s own order"></th>{heads}</tr></thead>']
    body, at = [], 0
    for row in table.rows:
        if row.band:
            if body:
                out.append("<tbody>" + "".join(body) + "</tbody>")
            body = [f'<tr class="band"><th colspan="{len(table.headers) + 1}">{text_of(row.label)}</th></tr>']
            continue
        cells = []
        for cell in row.cells:
            kinds = " ".join(k for k, on in (("b", cell.bold), ("l", getattr(cell, "align", "center") == "left")) if on)
            style = ";".join(f"{name}:{colour(value)}" for name, value, plain in (("background", cell.fill, SURFACE),
                                                                                ("color", cell.ink, INK))
                             if colour(value) != plain)              # the page's own colours go without saying
            cells.append(f'<td{f" class={chr(34)}{kinds}{chr(34)}" if kinds else ""}'
                         f'{f" style={chr(34)}{style}{chr(34)}" if style else ""}>{text_of(cell.text)}</td>')
        kinds = " ".join(k for k, on in (("pin", getattr(row, "pinned", False)),) if on)
        label = f'<th class="label{" b" if row.bold else ""}">{text_of(row.label)}</th>'
        body.append(f'<tr data-i="{at}"{f" class={chr(34)}{kinds}{chr(34)}" if kinds else ""}>{label}{"".join(cells)}</tr>')
        at += 1
    if body:
        out.append("<tbody>" + "".join(body) + "</tbody>")
    out += ["</table></div>", _notes(table, numbers), "</figure>"]
    return out


def shown(value: float) -> str:
    """A number as the PDF shows it (paper.shown)."""
    return f"{value:,.0f}" if 100 <= abs(value) < 1e6 else f"{value:.3g}"


def _ranking(ranking, numbers: dict, scale) -> list[str]:
    """A ranking as a table, a bar in each row's cell: from 0, or from its base both ways (a ratio's 1), as far as
    `scale`.reach; a bar beyond is cut at the cell's end, its value marked, and coloured as the PDF's (V205)."""
    values = ranking.values
    offsets = [v - ranking.base if ranking.base else max(v, 0.0) for v in values]
    span, absurd = (scale.reach(offsets) or (0.05 if ranking.base else 1.0)), scale.absurd_from(offsets)
    out = [f'<figure class="item" id="{anchor("i", ranking.key)}">', _caption(ranking),
           '<div class="scroll"><table class="sortable">',
           '<thead><tr><th class="label" data-col="-1" title="the ranking\'s own order">point (pages)</th>'
           '<th data-col="0">value</th></tr></thead><tbody>']
    for i, (name, value, offset) in enumerate(zip(ranking.names, values, offsets)):
        drawn = min(span, max(-span if ranking.base else 0.0, offset))
        if ranking.base:
            share = drawn / span * 50
            left, wide, axis = 50 + min(share, 0.0), abs(share), '<span class="axis" style="left:50%"></span>'
        else:
            left, wide, axis = 0.0, drawn / span * 100, '<span class="axis" style="left:0"></span>'
        fill = colour(scale.colour_of(offset, span, absurd, *ranking.colours))
        said = shown(value) if drawn == offset else \
            (scale.CUT[0] + shown(value) if drawn >= 0 else shown(value) + scale.CUT[1])
        out.append(f'<tr data-i="{i}"><th class="label">{text_of(name)}</th><td class="bar" data-v="{value!r}">'
                   f'<span class="track">{axis}<span class="fill" style="left:{left:.2f}%;width:{wide:.2f}%;'
                   f'background:{fill}"></span></span><span>{html.escape(said)}</span></td></tr>')
    out += ["</tbody></table></div>", _notes(ranking, numbers), "</figure>"]
    return out


def _text(text, numbers: dict) -> list[str]:
    lines = "".join(f"<p>{text_of(line[1])}</p>" for line in text.lines if line[1])
    return [f'<figure class="item" id="{anchor("i", text.key)}">', _caption(text), lines, _notes(text, numbers),
            "</figure>"]


def _item(item, numbers: dict, scale) -> list[str]:
    if hasattr(item, "headers"):
        return _table(item, numbers)
    if hasattr(item, "values"):
        return _ranking(item, numbers, scale)
    return _text(item, numbers)


def render(document, numbers: dict, scale) -> str:
    """`document` as one HTML page: its heading and facts, its contents (each section, and the items of a section
    of a few), its sections, its notes numbered as `numbers` says."""
    heading = text_of(document.heading or "Statistics")
    out = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           f"<title>Statistics: {html.escape(document.heading or 'summary')}</title>", f"<style>{CSS}</style>",
           "</head>", "<body>", "<header>", '<p class="kicker">Statistics</p>', f"<h1>{heading}</h1>",
           '<div class="facts">' + "".join(f"<p>{text_of(f)}</p>" for f in document.facts) + "</div>", "</header>",
           '<nav id="contents">', "<h2>Contents</h2>", "<ol>"]
    for section in document.sections:
        if not section.items:
            continue
        inner = ""
        if 1 < len(section.items) <= 8:
            inner = "<ol>" + "".join(f'<li><a href="#{anchor("i", i.key)}">{text_of(i.title)}</a></li>'
                                     for i in section.items) + "</ol>"
        out.append(f'<li><a href="#{anchor("s", section.key)}">{text_of(section.title)}</a>{inner}</li>')
    if numbers:
        out.append('<li><a href="#notes">Notes</a></li>')
    out += ["</ol>", "</nav>", "<main>"]
    for section in document.sections:
        if not section.items:
            continue
        out += [f'<section id="{anchor("s", section.key)}">', f"<h2>{text_of(section.title)}</h2>"]
        for item in section.items:
            out += _item(item, numbers, scale)
        out.append("</section>")
    out.append("</main>")
    if numbers:
        out += ['<section id="notes">', "<h2>Notes</h2>", "<ol>"]
        out += [f'<li id="note-{n}" value="{n}">{text_of(document.notes[key])}</li>'
                for key, n in sorted(numbers.items(), key=lambda kv: kv[1])]
        out += ["</ol>", "</section>"]
    out += ["<footer></footer>", f"<script>{SCRIPT}</script>", "</body>", "</html>", ""]
    return "\n".join(line for line in out if line)
