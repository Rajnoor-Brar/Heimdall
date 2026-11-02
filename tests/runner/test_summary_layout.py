"""Statistics on A4 (V196, V197): every summary page and page image is A4 portrait; a table wider than the
page is cut into column blocks stacked on its page; a page holds whole rows, a band never last; small tables share
a page within their section; the footer counts the pages; the facts, contents and notes come first, each page's
footnote a line of note numbers. The worst case is shaped like a real one (76 points in 38 page cells, 12
objects, 57-character labels), made here."""

from __future__ import annotations

import random
import re
from pathlib import Path

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from runner import plugins  # noqa: E402

FIGURES = Path(__file__).resolve().parents[2] / "framework" / "plot" / "figures"
bars = plugins.load(FIGURES / "bars.py", "bars")
paper = bars.paper
PDFS = ("NNPDF23lo", "NNPDF23nlo", "MSTW08lo", "PDF4LHC21", "MSHT20lo_as130", "MSHT20qed_lo",
        "NNPDF40nnlo_hessian_pdfas", "MSTW08lo90cl", "MSHT20nlo_as120", "MSHT20nlo_as118", "NNPDF40MClo_as01180qed",
        "NNPDF40MCnlo_as01180qed", "NNPDF40MClo_as01180", "NNPDF40lopch_as01180", "NNPDF40lo_as01180",
        "HERAPDF20loEig", "HERAPDF20nloEig", "HERAPDF20nloVar", "HERAPDF20JetsNLOEig")


def worst_rows() -> list[dict]:
    """76 points: 38 page cells (a PDF, the lepton PDF on or off) of two curves (the QED shower), 12 objects."""
    draw = random.Random(7)
    rows = []
    for pdf in PDFS:
        for lepton in ("lpdfon", "lpdfoff"):
            cell = f"{pdf}_{lepton}"
            for k in range(1, 13):
                obj = f"/ZEUS_2012_I1116258/d{k:02d}-x01-y01"
                for shower in ("on", "off"):
                    area = draw.uniform(0.5, 2.0)
                    rows.append({"page": f"{cell}/d{k:02d}", "cell": cell, "object": obj,
                                 "curve": f"lepton QED shower {shower}", "point": f"{cell}_{shower}",
                                 "reference": "ZEUS 2012", "is_reference": False, "bins": 10, "area": area,
                                 "area_err": 0.01, "ref_area": 1.0, "cmp_area": area, "abs_area": draw.uniform(0.05, 0.4),
                                 "rel_abs_area": draw.uniform(0.05, 0.4), "area_ratio": area,
                                 "ratio_mean": draw.uniform(0.4, 1.6), "ratio_dev": draw.uniform(0.1, 0.9),
                                 "chi2": 0.0, "ndf": 10, "chi2_ndf": draw.uniform(1.0, 60.0)})
    return rows


@pytest.fixture(scope="module")
def worst():
    document = bars.summary_model(worst_rows(), "eic/zeus_validation/01_pythia_qed_lepton · totality")
    return document, paper.pages(document)


def texts_inside(figure) -> list[str]:
    """The texts drawn outside the page's margins (none, when all is well)."""
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    w, h = (v * figure.dpi for v in paper.A4)
    side, edge, slack = paper.SIDE * figure.dpi, paper.EDGE * figure.dpi, 1.0
    out = []
    for text in figure.texts:
        box = text.get_window_extent(renderer)
        if box.x0 < side - slack or box.x1 > w - side + slack or box.y0 < edge - slack or box.y1 > h - edge + slack:
            out.append(text.get_text())
    return out


def test_every_page_is_a4_and_drawn_within_its_margins(worst):
    document, pages = worst
    assert len(pages) < 70                                       # the content-sized pages of today were 70
    sections = {p.section.key for p in pages}
    for key in sorted(sections):                                 # each section's first page, and the last page
        page = next(p for p in pages if p.section.key == key)
        figure = paper.figure(document, page, plt)
        try:
            assert tuple(round(v, 2) for v in figure.get_size_inches()) == paper.A4
            assert texts_inside(figure) == [], key
        finally:
            plt.close(figure)


def test_the_footer_counts_the_pages(worst):
    document, pages = worst
    figure = paper.figure(document, pages[-1], plt)
    try:
        assert f"page {len(pages)} of {len(pages)}" in [t.get_text() for t in figure.texts]
    finally:
        plt.close(figure)


def wide_table(rows: int = 30, bands: int = 0) -> object:
    """16 columns of wide numbers, the last four a tail; labels as long as real ones; a band every `bands` rows."""
    out = []
    for i in range(rows):
        if bands and i % bands == 0:
            out.append(paper.Row(f"NNPDF40nnlo_hessian_pdfas_lpdfoff {i // bands}", band=True))
        out.append(paper.Row(f"{i + 1}. NNPDF40nnlo_hessian_pdfas_lpdfoff · lepton QED shower off",
                             [paper.Cell(f"{0.0001 * (i + 1) + 0.05:.4f}") for _ in range(16)]))
    return paper.Table("wide", "A wide table", [f"d{j:02d}" for j in range(1, 13)] + ["total", "wins", "win rate",
                                                                                      "mean rank"], out, tail=4)


def test_a_wide_table_is_cut_into_blocks_stacked_on_its_page():
    table = wide_table()
    shape = paper._table_shape(table)
    assert len(shape.blocks) >= 2
    assert [j for block in shape.blocks for j in block] == list(range(16))              # in order, each once
    assert shape.blocks[-1][-4:] == [12, 13, 14, 15]                                     # the tail on the last
    body = [len([j for j in block if j < 12]) for block in shape.blocks]
    assert max(body) - min(body) <= 1                                                     # split evenly
    assert all(shape.label_width + sum(shape.widths[j] for j in block) <= paper.WIDTH + 1e-9 for block in shape.blocks)
    document = paper.Document("heading", [paper.Section("s", "S", [table])])
    pages = paper.pages(document)
    figure = paper.figure(document, pages[0], plt)
    try:
        drawn = [t.get_text() for t in figure.texts]
        first = pages[0].pieces[0].rows[0]
        label = shape.labels[first][0]
        assert drawn.count(label) == len(shape.blocks)                                     # each block its labels
        assert texts_inside(figure) == []
    finally:
        plt.close(figure)


def test_a_page_holds_whole_rows_and_a_band_never_ends_it():
    table = wide_table(rows=120, bands=5)
    document = paper.Document("heading", [paper.Section("s", "S", [table])])
    pages = paper.pages(document)
    assert len(pages) > 1
    seen = []
    for page in pages:
        (piece,) = page.pieces
        rows = piece.rows
        assert not table.rows[rows[-1]].band                                              # never last
        if len(rows) > 1 and rows[1] != rows[0] + 1:                                      # a group continued
            assert table.rows[rows[0]].band and not table.rows[rows[1]].band
            rows = rows[1:]
        seen += rows
        assert piece.first == (page is pages[0])
    assert seen == list(range(len(table.rows)))                                           # every row once, in order


def test_small_tables_share_a_page_and_each_section_starts_one(worst):
    _, pages = worst
    head_to_head = [p for p in pages if p.section.key == "head-to-head"]
    assert sum(len(p.pieces) for p in head_to_head) == 38 and len(head_to_head) <= 7
    keys = [p.section.key for p in pages]
    for page in pages:                                           # a section's pieces never share a page with another's
        assert {piece.item.key for piece in page.pieces} <= {i.key for i in page.section.items}
    order = ["front"] + [s.key for s in worst[0].sections]
    assert keys == sorted(keys, key=order.index)


def test_a_ranking_continues_on_the_next_page():
    names = [f"point {i}  (12)" for i in range(130)]
    ranking = paper.Ranking("r", "A ranking", names, [i / 10 for i in range(130)])
    document = paper.Document("heading", [paper.Section("s", "S", [ranking])])
    pages = paper.pages(document)
    assert len(pages) >= 2
    assert [i for p in pages for i in p.pieces[0].rows] == list(range(130))
    assert [p.pieces[0].first for p in pages] == [True] + [False] * (len(pages) - 1)


def test_a_label_wraps_when_that_saves_height():
    shape = paper._table_shape(wide_table())
    assert max(len(lines) for lines in shape.labels) >= 1
    one_line = max(paper.width(r.label) for r in wide_table().rows) + 2 * paper.PAD
    assert shape.label_width <= one_line                         # wrapped only when the table takes less height


def test_a_page_image_is_a4_in_the_grid_that_suits_its_curves(scratch):
    assert bars.grid(19, 2.7)[:2] == (2, 3)                     # long labels: two panels across
    assert bars.grid(4, 1.0)[:2] == (3, 2)                      # short ones: three across, bars taller
    columns, rows, bar, per = bars.grid(400, 1.0)
    assert per < 400 and bar >= bars.LEAST_BAR                  # too many for a page: they continue
    rows_ = [r for r in worst_rows() if r["page"] == "NNPDF23lo_lpdfon/d01"]
    made = bars.page(rows_, scratch / "bars" / "d01", ["pdf", "png"], "NNPDF23lo_lpdfon/d01")
    pdf = (scratch / "bars" / "d01.pdf").read_bytes()
    assert {tuple(map(float, b)) for b in re.findall(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", pdf)} == {
        (595.44, 841.68)}
    many = [dict(rows_[0], point=f"p{i}", curve=f"curve {i}") for i in range(200)]
    made = bars.page(many, scratch / "bars" / "many", ["pdf", "png"], "many")
    pngs = sorted(p.name for p in made if p.suffix == ".png")
    assert len(pngs) >= 2 and pngs[0] == "many_01.png"
    assert len(re.findall(rb"/Type\s*/Page\b(?!s)", (scratch / "bars" / "many.pdf").read_bytes())) == len(pngs)


def test_the_front_matter_holds_the_facts_the_contents_and_every_note_once(worst):
    document, pages = worst
    front = [p for p in pages if p.section.key == "front"]
    assert pages[0] in front and document.facts[0].startswith("76 point(s) in 38 page cell(s), on 12 object(s)")
    starts = {}
    for page in pages:
        for piece in page.pieces:
            starts.setdefault(piece.item.key, page.number)
    contents = next(i for i in front[0].section.items if i.key == "front-contents")
    for (_, _, number, _), target in zip(contents.lines, contents._targets):
        assert number == str(starts[target])                     # each entry, the page it starts on
    assert [s.title for s in document.sections] == [line[1] for line in contents.lines if line[3]]
    numbers = paper.note_numbers(document)
    assert sorted(numbers.values()) == list(range(1, len(numbers) + 1)) and set(numbers) <= set(document.notes)
    named = [k for s in document.sections for i in s.items for k in i.notes]
    assert list(numbers) == list(dict.fromkeys(k for k in named if k in document.notes))   # in the order first named
    notes = next(i for i in front[-1].section.items if i.key == "front-notes")
    assert [n for n, *_ in notes.lines if n] == [f"{n}." for n in range(1, len(numbers) + 1)]   # each once


def test_each_page_footnote_is_a_line_of_note_numbers(worst):
    document, pages = worst
    where = f"(pages 1–{sum(1 for p in pages if p.section.key == 'front')})"
    for page in pages:
        text = paper.footnote(document, page.notes)
        if page.section.key == "front":
            assert text == ""
            continue
        assert re.fullmatch(r"Notes? [\d, ]+ " + re.escape(where) + r": what these numbers are and how they are computed\.",
                            text), text
        assert len(paper.wrap(text, paper.WIDTH, paper.SMALL)) == 1


def test_rows_in_curve_order_are_grouped_under_their_cells():
    document = bars.summary_model(worst_rows(), "")
    items = {i.key: i for s in document.sections for i in s.items}
    table = items["chi2_ndf"]
    bands = [r.label for r in table.rows if r.band]
    assert len(bands) == 38 and bands[0] == "NNPDF23lo_lpdfon"
    assert {r.label for r in table.rows if not r.band} == {"lepton QED shower on", "lepton QED shower off"}
    assert all(" · " in r.label for r in items["scoreboard"].rows)              # sorted across cells: whole names
    assert [r.label for r in items["head-to-head-1"].rows][0].startswith("1. lepton QED shower")
    top = [i for i in document.sections[0].items]
    assert [i.headers for i in top][:2] == [["point", "points", "wins"]] * 2 and top[-1].headers[1:] == ["win rate",
                                                                                                    "matches"]
    assert all(c.cells[0].align == "left" for i in top for c in i.rows)
    one = bars.summary_model([dict(r, cell="") for r in worst_rows() if r["cell"] == "NNPDF23lo_lpdfon"], "")
    assert not any(r.band for s in one.sections for i in s.items if isinstance(i, paper.Table) for r in i.rows)


# ── page cells against curves (V198) ─────────────────────────────────────────────────────────────────

def test_cells_against_curves_hold_each_points_mean_the_longer_list_down():
    import math
    rows = worst_rows()
    document = bars.summary_model(rows, "")
    items = {i.key: i for s in document.sections for i in s.items}
    keys = [i.key for s in document.sections if s.key == "area_ratio" for i in s.items]
    assert keys == ["area_ratio-ranking", "area_ratio-crossed", "area_ratio"]
    assert "area-crossed" not in items                                         # each object its own units
    crossed = items["chi2_ndf-crossed"]
    assert crossed.headers == ["lepton QED shower on", "lepton QED shower off", "mean"]   # 38 cells down, 2 across
    assert [r.label for r in crossed.rows][:2] == ["NNPDF23lo_lpdfon", "NNPDF23lo_lpdfoff"]
    assert crossed.rows[-1].label == "mean" and crossed.rows[-1].bold and len(crossed.rows) == 39
    means = bars._means(rows, "chi2_ndf")
    first = crossed.rows[0]
    on, off = means["NNPDF23lo_lpdfon_on"][0], means["NNPDF23lo_lpdfon_off"][0]
    assert [c.text for c in first.cells] == [bars._shown(on), bars._shown(off), bars._shown((on + off) / 2)]
    assert [c.bold for c in first.cells[:2]] == [on <= off, off <= on]          # the best in its row
    ratio = items["area_ratio-crossed"].rows[0].cells
    a, b = (means_ := bars._means(rows, "area_ratio"))["NNPDF23lo_lpdfon_on"][0], means_["NNPDF23lo_lpdfon_off"][0]
    assert ratio[2].text == bars._shown(math.sqrt(a * b))                      # a ratio's mean: geometric


def test_cells_against_curves_turn_and_leave_gaps_and_are_left_out_when_nothing_crosses():
    rows = [r for r in worst_rows() if r["cell"] in ("NNPDF23lo_lpdfon", "MSTW08lo_lpdfon")]
    many = [dict(r, curve=f"curve {k}", point=f"{r['cell']}_{k}") for r in rows for k in range(5)]
    many = [r for r in many if not (r["cell"] == "MSTW08lo_lpdfon" and r["curve"] == "curve 4")]
    crossed = next(i for s in bars.summary_model(many, "").sections for i in s.items if i.key == "chi2_ndf-crossed")
    assert crossed.headers == ["NNPDF23lo_lpdfon", "MSTW08lo_lpdfon", "mean"]  # 5 curves down, 2 cells across
    assert [r.label for r in crossed.rows] == [f"curve {k}" for k in range(5)] + ["mean"]
    assert crossed.rows[4].cells[1].text == "–" and crossed.rows[4].cells[0].text != "–"   # no such point
    one_cell = [r for r in worst_rows() if r["cell"] == "NNPDF23lo_lpdfon"]
    alone = [dict(r, curve=f"{r['cell']} {r['curve']}") for r in worst_rows()[:96]]     # no curve in two cells
    for case in (one_cell, alone):
        assert not any(i.key.endswith("-crossed") for s in bars.summary_model(case, "").sections for i in s.items)


# ── summary.html (V199) ──────────────────────────────────────────────────────────────────────────────

def page_of(document) -> tuple[str, dict]:
    """The document's HTML, and what is in it: ids, local links, other references, each item's <tbody> count."""
    from html.parser import HTMLParser
    text = bars.webpage.render(document, paper.note_numbers(document), paper)
    found = {"ids": set(), "links": [], "others": [], "bodies": {}, "pins": set()}

    class Reader(HTMLParser):
        item = None

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if "id" in attrs:
                found["ids"].add(attrs["id"])
                if tag == "figure":
                    Reader.item = attrs["id"]
            for name in ("href", "src"):
                if name in attrs:
                    (found["links"] if attrs[name].startswith("#") else found["others"]).append(attrs[name])
            if tag == "tbody":
                found["bodies"][Reader.item] = found["bodies"].get(Reader.item, 0) + 1
            if tag == "tr" and "pin" in (attrs.get("class") or ""):
                found["pins"].add(Reader.item)
    Reader().feed(text)
    return text, found


def test_the_page_holds_every_section_and_item_its_links_resolve_and_it_needs_nothing_else(worst):
    document, _ = worst
    text, found = page_of(document)
    assert text.startswith("<!DOCTYPE html>") and '<meta charset="utf-8">' in text
    for section in document.sections:
        assert bars.webpage.anchor("s", section.key) in found["ids"]
        assert all(bars.webpage.anchor("i", i.key) in found["ids"] for i in section.items)
    assert found["links"] and all(link[1:] in found["ids"] for link in found["links"])    # every link lands
    assert found["others"] == [] and "http" not in text and "<script src" not in text      # self-contained
    numbers = paper.note_numbers(document)
    assert {f"note-{n}" for n in numbers.values()} <= found["ids"]
    assert found["bodies"]["i-chi2_ndf"] == 38                                   # a <tbody> a cell's band
    assert found["pins"] == {f"i-{k}-crossed" for k in bars.SCORED}             # the mean row stays last


def test_the_page_escapes_its_text_and_reads_mathtext():
    table = paper.Table("t", "A <b> & title", ["$\\chi^{2}$/ndf", "x_{1}"],
                        [paper.Row("<script>alert(1)</script> & co", [paper.Cell("1.5"), paper.Cell("<2")])])
    text, _ = page_of(paper.Document("a & b", [paper.Section("s", "S", [table])], {"n": "x < y"}, ["4 < 5"]))
    assert "<script>alert" not in text and "&lt;script&gt;alert(1)&lt;/script&gt; &amp; co" in text
    assert "A &lt;b&gt; &amp; title" in text and "&lt;2" in text and "4 &lt; 5" in text
    assert bars.webpage.text_of("$\\chi^{2}$/ndf") == "χ<sup>2</sup>/ndf"
    assert bars.webpage.text_of("$p_{T}$ [GeV]") == "p<sub>T</sub> [GeV]"
    assert bars.webpage.text_of("costs $5") == "costs $5"                      # a lone dollar is a dollar


def test_the_summary_writes_its_page_whatever_the_formats(scratch):
    rows = [r for r in worst_rows() if r["cell"] in ("NNPDF23lo_lpdfon", "NNPDF23lo_lpdfoff")]
    made = bars.summary_of(rows, scratch / "html" / "summary", ["png"], "a · b")
    assert scratch / "html" / "summary.html" in made and not (scratch / "html" / "summary.pdf").exists()
    assert "<title>Statistics: a · b</title>" in (scratch / "html" / "summary.html").read_text(encoding="utf-8")


def test_the_sets_index_links_each_sets_statistics(scratch):
    from runner import plot
    run = scratch / "indexed"
    for folder in ("plots/totality/mpl", "plots/pdfs/mpl", "statistics/totality"):
        (run / folder).mkdir(parents=True, exist_ok=True)
    for page in ("plots/totality/mpl/index.html", "plots/pdfs/mpl/index.html", "statistics/totality/summary.html"):
        (run / page).write_text("<html></html>", encoding="utf-8")
    index = plot.write_sets_index(run / "plots", "a run").read_text(encoding="utf-8")
    assert '<a href="../statistics/totality/summary.html">statistics</a>' in index
    assert "../statistics/pdfs/" not in index                                   # no summary there: no link


def test_a_bar_far_beyond_the_rest_is_cut_and_every_value_stays_on_its_panel(scratch):
    """V205: a curve gone wild (Sherpa with one PDF: σ 10⁹ times the rest, a mean ratio of −3.8·10⁸) put its value
    10⁸ pixels off the panel, more than FreeType could raster; a negative value drew over the curve labels."""
    assert paper.reach([0.3, 0.8, 0.5, 0.2, 3.8e8]) == 0.8 and paper.reach([1.0, 30.0]) == 30.0
    assert paper.reach([0.0, 0.0, 5.0]) == 5.0 and paper.reach([]) == 0.0
    wild = {"area": 1.3e13, "area_ratio": 7.2e9, "ratio_mean": -3.8e8, "rel_abs_area": 8.0e9, "ratio_dev": 4.3e9,
            "chi2_ndf": 1.86}
    rows = [r for r in worst_rows() if r["page"] == "NNPDF23lo_lpdfon/d01"]
    rows = [dict(rows[0], point=f"p{i}", curve=f"curve {i}", ratio_mean=0.5 - 0.15 * i) for i in range(6)] + \
        [dict(rows[0], point="wild", curve="wild", **wild)]
    label = max(paper.width(r["curve"], 8) for r in rows) + 0.12
    columns, _, bar, _ = bars.grid(len(rows), label)
    figure = bars._page_figure(rows, "a page", columns, bar, label, plt)
    figure.savefig(scratch / "wild.png", dpi=150)                          # raster overflow before
    renderer = figure.canvas.get_renderer()
    for ax in figure.axes:
        panel = ax.get_window_extent(renderer)
        for text in ax.texts:
            box = text.get_window_extent(renderer)
            assert panel.x0 - 1 <= box.x0 and box.x1 <= panel.x1 + 1, (ax.get_title(loc="left"), text.get_text())
    said = {ax.get_title(loc="left"): [t.get_text() for t in ax.texts] for ax in figure.axes}
    assert said["mean ratio"][-1] == "-3.8e+08 «" and said["area"][-1] == "» 1.3e+13"
    assert paper.CUT_KEY in [t.get_text().replace("\n", " ") for t in figure.texts]          # its key at the foot
    plt.close(figure)
    ranking = paper.Ranking("r", "mean ratio", [f"p{i}" for i in range(7)], [0.9, 1.1, 0.8, 1.2, 0.95, 1.05, -3.8e8],
                            base=1.0)
    document = paper.Document("heading", [paper.Section("s", "S", [ranking])])
    figure = paper.figure(document, paper.pages(document)[0], plt)
    assert "-3.8e+08 «" in [t.get_text() for t in figure.texts] and not texts_inside(figure)
    plt.close(figure)
    page = bars.webpage.render(document, paper.note_numbers(document), paper)
    assert "-3.8e+08 «" in page and f"background:{paper.WILD[1]}" in page


def test_a_bar_is_blue_or_orange_by_its_side_violet_or_golden_when_cut_pink_or_red_when_absurd(scratch):
    """The user, 2026-10-26: "blue, indigo/violet, pink for positive; orange, golden yellow, red for negative"."""
    values = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 0.95, -0.5, 40.0, -40.0, 2e7, -2e7, float("inf")]
    figure = plt.figure()
    ax = figure.add_subplot()
    assert bars._bars(ax, values, [""] * len(values), panel=2.5)
    colours = [paper.colour_of(v, paper.reach(values), paper.absurd_from(values)) for v in values]
    assert colours == [paper.ABOVE] * 10 + [paper.BELOW, paper.TOO_BIG[0], paper.TOO_BIG[1], paper.WILD[0],
                                            paper.WILD[1], paper.WILD[0]]
    import matplotlib.colors as mc
    assert [mc.to_hex(bar.get_facecolor()) for bar in ax.patches] == [mc.to_hex(c) for c in colours]
    assert [t.get_text() for t in ax.texts][-6:] == ["-0.5", "» 40", "-40 «", "» 2e+07", "-2e+07 «", "» ∞"]
    plt.close(figure)
    figure = plt.figure()
    assert not bars._bars(figure.add_subplot(), [0.5, 1.0, -0.2], ["", "", ""])          # nothing cut: no key
    plt.close(figure)
