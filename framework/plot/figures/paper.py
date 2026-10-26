"""framework/plot/figures/paper.py — tables and bar rankings on A4 pages (V196, I-107), drawn by matplotlib (Agg).

* The model, pure data (bars.py builds it; this module knows no statistic): a `Document(heading, sections,
  notes)`, each `Section(key, title, items)` a flow of items, each a `Table(key, title, headers, rows, …)` of
  `Row(label, cells, bold, band)` and `Cell(text, fill, ink, bold)`, or a `Ranking(key, title, names, values,
  …)`: sorted bars from a base. An item names its notes by key (`Document.notes`).
* `pages(document)`: every page planned before any is drawn, so that each knows its number and the count. A
  section starts a page; its items follow one below another, a new page only when the next does not fit (its
  title and LEAST rows at least). A table wider than the page is cut into column blocks, the fewest that fit,
  its data columns split evenly and its last `tail` columns (a mean, a total) on the last block, each block
  with the row labels. A page holds a range of whole rows, the table's blocks stacked under one another; the
  rest continues on the next page, titled "(continued)". A band (a group's name across the table) never ends a
  page, and a group continued repeats its band.
* `figure(document, page, plt)`: one A4 portrait page, drawn in inches: the running header (the heading, the
  section), the items, the footnote (the notes its items name, each once) and "page n of N".

Text is measured as matplotlib's Agg draws it (hinted, at DPIS; mathtext included), never guessed from its
length.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BAND = "#efeeea"                                    # a band's background
SERIES = "#2a78d6"                                  # a ranking's bars, unless it names its own
A4 = (8.27, 11.69)                                  # inches, portrait
SIDE, EDGE = 0.5, 0.45                              # the margins: left and right, top and bottom
WIDTH = A4[0] - 2 * SIDE                            # what a page holds across
HEAD = 0.34                                         # the running header's strip, under the top margin
FOOT = 0.2                                          # the page number's strip, over the bottom margin
BODY, SMALL, TITLE, SUB = 7.0, 6.5, 9.0, 7.0        # pt: a table's text, the footnote, an item's title, its subtitle
ROW = 0.165                                         # a table row, inches
LINE = BODY * 1.25 / 72                             # a text line in a cell or a header
PAD = 0.045                                         # a cell's padding, each side
LEAST_COLUMN, HEADER_LINES = 0.26, 3                # a data column's least width; its header's most lines
BLOCK_GAP, ITEM_GAP, NOTE_GAP = 0.1, 0.28, 0.12     # between a table's blocks; between items; above the footnote
BAR = 0.17                                          # a ranking's bar
LEAST = 3                                           # the fewest rows an item starts a page with
SAFETY = 1.01                                       # measured text, widened a little
DPIS = (100, 150)                                   # text measured at the figure's own resolution and the PNGs'
                                                    # (hinted, the widest; a PDF's is narrower)


@dataclass
class Cell:
    text: str
    fill: object = SURFACE
    ink: str = INK
    bold: bool = False


@dataclass
class Row:
    label: str
    cells: list = field(default_factory=list)
    bold: bool = False
    band: bool = False                              # a group's name across the table, no cells


@dataclass
class Table:
    key: str
    title: str
    headers: list
    rows: list
    subtitle: str = ""
    tail: int = 0                                   # the last columns, kept together on the last block
    notes: tuple = ()


@dataclass
class Ranking:
    key: str
    title: str
    names: list
    values: list
    subtitle: str = ""
    base: float = 0.0                               # bars from here: 0, or 1 for a ratio
    colours: tuple = (SERIES, SERIES)               # above the base, below it
    notes: tuple = ()


@dataclass
class Section:
    key: str
    title: str
    items: list


@dataclass
class Document:
    heading: str
    sections: list
    notes: dict = field(default_factory=dict)       # key → text


@dataclass
class Piece:
    item: object
    rows: list                                      # the item's rows here (a repeated band first)
    first: bool                                     # with its title and subtitle; else "(continued)"
    top: float                                      # inches under the body's top


@dataclass
class Page:
    number: int
    section: Section
    pieces: list = field(default_factory=list)
    notes: list = field(default_factory=list)       # note keys, each once, in the order met
    count: int = 0                                  # the document's pages
    used: float = 0.0                               # inches of the body taken


# ── text, measured ─────────────────────────────────────────────────────────────────────────────────

def is_math(text: str) -> bool:
    """Whether matplotlib reads `text` as mathtext: an even number of unescaped dollars, at least two."""
    dollars = text.count("$") - text.count(r"\$")
    return dollars >= 2 and dollars % 2 == 0


@lru_cache(maxsize=1)
def _renderers():
    from matplotlib.backends.backend_agg import RendererAgg
    return [RendererAgg(10, 10, dpi) for dpi in DPIS]


@lru_cache(maxsize=65536)
def width(text: str, size: float = BODY, bold: bool = False) -> float:
    """`text`'s width in inches as matplotlib draws it at `size` pt: the widest of DPIS."""
    if not text:
        return 0.0
    from matplotlib.font_manager import FontProperties
    prop = FontProperties(size=size, weight="bold" if bold else "normal")
    widths = []
    for renderer in _renderers():
        try:
            pixels = renderer.get_text_width_height_descent(text, prop, ismath=is_math(text))[0]
        except Exception:                               # mathtext it cannot parse is drawn as written
            pixels = renderer.get_text_width_height_descent(text.replace("$", ""), prop, ismath=False)[0]
        widths.append(pixels / renderer.dpi)
    return SAFETY * max(widths)


def _words(text: str) -> list[str]:
    """`text`'s words, a $…$ span kept whole."""
    words, open_ = [], ""
    for word in text.split():
        open_ = f"{open_} {word}" if open_ else word
        if open_.count("$") % 2 == 0:
            words.append(open_)
            open_ = ""
    return words + ([open_] if open_ else [])


def wrap(text: str, room: float, size: float = SMALL, bold: bool = False) -> list[str]:
    """`text` on lines at most `room` inches wide; a longer word alone on its line."""
    lines, line = [], ""
    for word in _words(text):
        trial = f"{line} {word}" if line else word
        if line and width(trial, size, bold) > room:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + ([line] if line else [])


def _height(lines: int, size: float) -> float:
    return lines * size * 1.3 / 72


# ── shapes: an item's measures, once ───────────────────────────────────────────────────────────────

@dataclass
class _TableShape:
    labels: list                                    # each row's label lines
    label_width: float
    widths: list                                    # each column's
    heads: list                                     # each column's header lines
    blocks: list                                    # column indices, a block each
    head_heights: list                              # each block's header row
    heights: list                                   # each row's
    title: list
    subtitle: list
    banded: bool


@dataclass
class _RankingShape:
    label_width: float
    value_width: float
    title: list
    subtitle: list


#: The ways a table's labels may be laid: as they are, cut at their first " · ", or wrapped to so many inches.
LABEL_WAYS = (None, "·", 2.4, 1.8, 1.4)


def _label_lines(label: str, way, bold: bool = False) -> list[str]:
    """A label's lines laid one of LABEL_WAYS: whole; on two lines at its first " · "; or its words wrapped to
    `way` inches (a cut at " · " first)."""
    if way is None:
        return [label]
    head, dot, rest = label.partition(" · ")
    parts = [f"{head} ·", rest] if dot else [label]
    if way == "·":
        return parts
    return [line for part in parts for line in (wrap(part, way, BODY, bold) or [part])]


def blocks_of(widths: list[float], tail: int, room: float) -> list[list[int]]:
    """The columns cut into the fewest blocks that fit `room` inches, the data columns split evenly and the last
    `tail` columns on the last block."""
    n = len(widths)
    body = n - tail
    if body <= 0:
        return [list(range(n))]
    for k in range(1, body + 1):
        q, r = divmod(body, k)
        groups, at = [], 0
        for g in range(k):
            size = q + (1 if g < r else 0)
            groups.append(list(range(at, at + size)))
            at += size
        groups[-1] += list(range(body, n))
        if all(sum(widths[j] for j in g) <= room + 1e-9 for g in groups):
            return groups
    return [[j] for j in range(body - 1)] + [[body - 1] + list(range(body, n))]


def _column(header: str, cells: float) -> tuple[float, list[str]]:
    """A data column's width and its header's lines: as wide as its widest cell (at least LEAST_COLUMN), its
    header wrapped to that, widened while it takes more than HEADER_LINES lines or a word does not fit."""
    column = max(LEAST_COLUMN, cells + 2 * PAD, max([width(w) for w in _words(header)] + [0.0]) + 2 * PAD)
    lines = wrap(header, column - 2 * PAD, BODY)
    while len(lines) > HEADER_LINES:
        column += 0.05
        lines = wrap(header, column - 2 * PAD, BODY)
    return column, lines


def _table_shape(table: Table) -> _TableShape:
    """A table's measures: its columns, its blocks, its rows' labels, laid the way of LABEL_WAYS that takes the
    least height overall (fewer blocks stacked, against rows of more lines)."""
    shape = table.__dict__.get("_shape")
    if shape is not None:
        return shape
    banded = any(r.band for r in table.rows)
    indent = 0.1 if banded else 0.0
    widths, heads = [], []
    for j, header in enumerate(table.headers):
        cells = max([width(r.cells[j].text, BODY, r.cells[j].bold) for r in table.rows if not r.band] + [0.0])
        column, lines = _column(header, cells)
        widths.append(column)
        heads.append(lines)
    best = None
    for way in LABEL_WAYS:
        labels = [[r.label] if r.band else _label_lines(r.label, way, r.bold) for r in table.rows]
        label_width = max([max(width(line, BODY, r.bold) for line in lines) + 2 * PAD + indent
                           for r, lines in zip(table.rows, labels) if not r.band] + [0.6])
        blocks = blocks_of(widths, table.tail, WIDTH - label_width)
        head_heights = [max(ROW, max([len(heads[j]) for j in block] + [1]) * LINE + 0.06) for block in blocks]
        heights = [ROW + (len(lines) - 1) * LINE for lines in labels]
        total = sum(head_heights) + len(blocks) * sum(heights)
        if best is None or total < best[0] - 1e-9:
            best = (total, labels, label_width, blocks, head_heights, heights)
    _, labels, label_width, blocks, head_heights, heights = best
    shape = _TableShape(labels, label_width, widths, heads, blocks, head_heights, heights,
                        wrap(table.title, WIDTH, TITLE), wrap(table.subtitle, WIDTH, SUB) if table.subtitle else [],
                        banded)
    table.__dict__["_shape"] = shape
    return shape


def shown(value: float) -> str:
    """A ranking's value at its bar's tip."""
    return f"{value:,.0f}" if abs(value) >= 100 else f"{value:.3g}"


def _ranking_shape(ranking: Ranking) -> _RankingShape:
    shape = ranking.__dict__.get("_shape")
    if shape is None:
        shape = _RankingShape(max([width(n) for n in ranking.names] + [0.6]) + 2 * PAD,
                              max([width(shown(v)) for v in ranking.values] + [0.3]) + 0.08,
                              wrap(ranking.title, WIDTH, TITLE), wrap(ranking.subtitle, WIDTH, SUB) if ranking.subtitle else [])
        ranking.__dict__["_shape"] = shape
    return shape


def _title_height(shape, first: bool) -> float:
    return (_height(len(shape.title), TITLE) + _height(len(shape.subtitle), SUB) if first else _height(1, TITLE)) + 0.06


def _size(item) -> int:
    return len(item.rows) if isinstance(item, Table) else len(item.names)


def _band_before(table: Table, start: int) -> int | None:
    """The band of the group the row `start` is in, when that group began before it."""
    if table.rows[start].band:
        return None
    for i in range(start - 1, -1, -1):
        if table.rows[i].band:
            return i
    return None


def piece_height(item, rows: list[int], first: bool) -> float:
    """The inches a piece of `item` takes: its title, then each block's header and rows (a table's blocks
    stacked), or its bars."""
    if isinstance(item, Table):
        shape = _table_shape(item)
        body = sum(shape.heights[i] for i in rows)
        return (_title_height(shape, first) + sum(shape.head_heights) + len(shape.blocks) * body
                + (len(shape.blocks) - 1) * BLOCK_GAP)
    return _title_height(_ranking_shape(item), first) + BAR * len(rows) + 0.05


def _fit(item, start: int, first: bool, room: float, alone: bool) -> list[int]:
    """The rows of `item` from `start` that fit `room` inches (a band continued first), at least LEAST of them
    (or all that are left) unless the page holds nothing else; [] when too few fit."""
    n = _size(item)
    lead = [] if not isinstance(item, Table) or (b := _band_before(item, start)) is None else [b]
    end = start
    while end < n and piece_height(item, lead + list(range(start, end + 1)), first) <= room:
        end += 1
    if isinstance(item, Table):
        while end < n and end - 1 > start and item.rows[end - 1].band:     # a band never ends a page
            end -= 1
    if end - start < min(LEAST, n - start):
        if not alone:
            return []
        end = max(end, start + 1)
    return lead + list(range(start, end))


def _notes_height(document: Document, keys: list[str]) -> float:
    if not keys:
        return 0.0
    return _height(len(wrap(footnote(document, keys), WIDTH, SMALL)), SMALL) + NOTE_GAP


def footnote(document: Document, keys: list[str]) -> str:
    """A page's footnote: the notes its items name, each once."""
    return " ".join(document.notes[k] for k in keys if k in document.notes)


def body_height(document: Document, keys: list[str]) -> float:
    """The inches a page holds for its items, its footnote (the notes `keys`) taken."""
    return A4[1] - 2 * EDGE - HEAD - FOOT - _notes_height(document, keys)


def pages(document: Document) -> list[Page]:
    """Every page of `document`, planned: which pieces of which items, where, and each page's notes."""
    out: list[Page] = []
    for section in document.sections:
        page = None
        for item in section.items:
            start, first, n = 0, True, _size(item)
            while start < n:
                if page is None:
                    page = Page(len(out) + 1, section)
                    out.append(page)
                keys = page.notes + [k for k in item.notes if k not in page.notes]
                room = body_height(document, keys) - page.used
                rows = _fit(item, start, first, room, alone=not page.pieces)
                if not rows:
                    page = None
                    continue
                page.pieces.append(Piece(item, rows, first, page.used))
                page.notes = keys
                page.used += piece_height(item, rows, first) + ITEM_GAP
                start, first = rows[-1] + 1, False
    for page in out:
        page.count = len(out)
    return out


# ── drawing ────────────────────────────────────────────────────────────────────────────────────────

class _Canvas:
    """A page's figure, drawn in inches from its top left."""

    def __init__(self, plt):
        from matplotlib.collections import PatchCollection
        from matplotlib.patches import Rectangle
        self.figure = plt.figure(figsize=A4, facecolor=SURFACE)
        self.inch = self.figure.dpi_scale_trans
        self.rectangle, self.collection, self.boxes = Rectangle, PatchCollection, []

    def text(self, x: float, top: float, text: str, **style) -> None:
        style.setdefault("color", INK)
        style.setdefault("fontsize", BODY)
        style.setdefault("va", "center")
        style.setdefault("ha", "left")
        if not is_math(text):
            text = text.replace("$", r"\$")                    # a lone dollar is a dollar
        self.figure.text(x, A4[1] - top, text, transform=self.inch, **style)

    def box(self, x: float, top: float, w: float, h: float, fill=SURFACE, edge=GRID) -> None:
        self.boxes.append(self.rectangle((x, A4[1] - top - h), w, h, facecolor=fill, edgecolor=edge, linewidth=0.5))

    def line(self, x0: float, x1: float, top: float, colour=GRID, top1: float | None = None) -> None:
        from matplotlib.lines import Line2D
        self.figure.add_artist(Line2D([x0, x1], [A4[1] - top, A4[1] - (top if top1 is None else top1)],
                                      transform=self.inch, color=colour, linewidth=0.6))

    def done(self):
        if self.boxes:
            self.figure.add_artist(self.collection(self.boxes, match_original=True, transform=self.inch, zorder=0))
        return self.figure


def _title(canvas: _Canvas, shape, title: str, first: bool, top: float) -> float:
    """An item's title and subtitle (or its title "(continued)"); the top under them."""
    lines = [(line, TITLE, INK) for line in shape.title] + [(line, SUB, MUTED) for line in shape.subtitle] \
        if first else [(f"{title} (continued)", TITLE, MUTED)]
    for line, size, colour in lines:
        h = _height(1, size)
        canvas.text(SIDE, top + h / 2, line, fontsize=size, color=colour)
        top += h
    return top + 0.06


def _table(canvas: _Canvas, table: Table, piece: Piece, top: float) -> None:
    shape = _table_shape(table)
    top = _title(canvas, shape, table.title, piece.first, top)
    for b, block in enumerate(shape.blocks):
        lefts, x = [], SIDE + shape.label_width
        for j in block:
            lefts.append(x)
            x += shape.widths[j]
        right, hh = x, shape.head_heights[b]
        for j, left in zip(block, lefts):
            canvas.box(left, top, shape.widths[j], hh)
            lines = shape.heads[j]
            for k, line in enumerate(lines):
                canvas.text(left + shape.widths[j] / 2, top + hh / 2 + (k - (len(lines) - 1) / 2) * LINE, line,
                            ha="center")
        top += hh
        for at, i in enumerate(piece.rows):
            row, h = table.rows[i], shape.heights[i]
            if row.band:
                continued = at == 0 and len(piece.rows) > 1 and piece.rows[1] != i + 1
                canvas.box(SIDE, top, right - SIDE, h, fill=BAND)
                canvas.text(SIDE + PAD, top + h / 2, row.label + (" (continued)" if continued else ""),
                            fontweight="bold")
            else:
                canvas.box(SIDE, top, shape.label_width, h)
                lines = shape.labels[i]
                for k, line in enumerate(lines):
                    canvas.text(SIDE + PAD + (0.1 if shape.banded else 0.0),
                                top + h / 2 + (k - (len(lines) - 1) / 2) * LINE, line,
                                fontweight="bold" if row.bold else "normal")
                for j, left in zip(block, lefts):
                    cell = row.cells[j]
                    canvas.box(left, top, shape.widths[j], h, fill=cell.fill)
                    canvas.text(left + shape.widths[j] / 2, top + h / 2, cell.text, ha="center", color=cell.ink,
                                fontweight="bold" if cell.bold else "normal")
            top += h
        top += BLOCK_GAP


def _ranking(canvas: _Canvas, ranking: Ranking, piece: Piece, top: float) -> None:
    shape = _ranking_shape(ranking)
    top = _title(canvas, shape, ranking.title, piece.first, top)
    left = SIDE + shape.label_width + 0.08                    # the bars clear of the longest name
    room = WIDTH - shape.label_width - 0.08 - shape.value_width * (2 if ranking.base else 1)
    values = ranking.values
    if ranking.base:                                    # from the base both ways, as far as the furthest
        span = max([abs(v - ranking.base) for v in values] + [0.0]) or 0.05
        zero, scale = left + shape.value_width + room / 2, room / 2 / span
    else:
        zero, scale = left, room / (max([v for v in values if v > 0] + [0.0]) or 1.0)
    for i in piece.rows:
        value, middle = values[i], top + BAR / 2
        canvas.text(SIDE + PAD, middle, ranking.names[i])
        length = (value - ranking.base) * scale
        colour = ranking.colours[0] if value >= ranking.base else ranking.colours[1]
        canvas.box(min(zero, zero + length), middle - 0.55 * BAR / 2, abs(length), 0.55 * BAR, fill=colour,
                   edge=colour)
        tip = zero + length + (0.04 if length >= 0 else -0.04)
        canvas.text(tip, middle, shown(value), ha="left" if length >= 0 else "right")
        top += BAR
    first_top = top - BAR * len(piece.rows)
    canvas.line(zero, zero, first_top, MUTED, top)


def figure(document: Document, page: Page, plt):
    """`page` drawn: an A4 portrait figure."""
    canvas = _Canvas(plt)
    canvas.text(SIDE, EDGE + HEAD / 2 - 0.04, document.heading, fontsize=SMALL + 0.5, color=MUTED)
    canvas.text(A4[0] - SIDE, EDGE + HEAD / 2 - 0.04, page.section.title, fontsize=SMALL + 0.5, color=MUTED,
                ha="right")
    canvas.line(SIDE, A4[0] - SIDE, EDGE + HEAD - 0.1)
    body = EDGE + HEAD
    for piece in page.pieces:
        (_table if isinstance(piece.item, Table) else _ranking)(canvas, piece.item, piece, body + piece.top)
    lines = wrap(footnote(document, page.notes), WIDTH, SMALL)
    top = A4[1] - EDGE - FOOT - _height(len(lines), SMALL)
    for line in lines:
        canvas.text(SIDE, top + _height(1, SMALL) / 2, line, fontsize=SMALL, color=MUTED)
        top += _height(1, SMALL)
    canvas.text(A4[0] - SIDE, A4[1] - EDGE - FOOT / 2, f"page {page.number} of {page.count}", fontsize=SMALL,
                color=MUTED, ha="right")
    return canvas.done()
