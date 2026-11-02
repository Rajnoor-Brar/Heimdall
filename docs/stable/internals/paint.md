---
id: paint
summary: Paint inside: the order of a page's arithmetic, drawing, heat maps, dumps; what is load-bearing
code: src/Apps/Paint/main.cc, src/Apps/Paint/Page.hh, src/Apps/Paint/Style.hh, src/Apps/Paint/Transform.hh, src/Apps/Paint/Draw.hh
---

# Paint inside

`main.cc` the batch and modes; `Page.hh` the page TOML; `Style.hh` base.toml and the layers; `Transform.hh` void, align, normalise, ranges; `Draw.hh` the canvases. Built to `$HEIMDALL_APPS/Paint.exe`. Plot-only, so rebuilding it reruns nothing.

## A page, in this order

This order is load-bearing.

1. **Load** curves, and `/RAW` entries when `raw` is given.
2. **Void** bins across the page: `void_empty` (zero in every curve), `min_entries` (fewer raw entries in any curve). Only when curves share one binning; otherwise a warning.
3. **Align** the data to the first curve's bins: its longest run whose edges are all MC edges. Otherwise dropped with a warning.
4. **Normalise:** with `normalise = "area"`, every curve and the data to unit area, Σ value × width over bins drawn.
5. **x range:** auto-range or the full range, then `x_gutter`: the span statistics are taken over. Then `x_range`'s explicit ends, which only show.
6. **y range:** `(1 + y_gutter) ×` the largest drawn value within x. On a log axis, that fraction of the decades shown. With no gutter, ROOT's own choice for one histogram holding every value (`THistPainter`). `y_range`'s explicit ends follow. An axis with an explicit end is refused (`Kit::Config`) when the ends leave no increasing range, or the minimum is ≤ 0 on a log axis; one without is never checked, so an empty log-y page still draws.
7. **Draw:**
   - **MC:** steps per run of non-void bins (a voided bin is a gap), with error bars at bin centres, or a band, or none. With `markers`, a marker per bin. A band is the members' envelope, shaded in the curve's colour.
   - **Overflow marks** (`overflowMarks`): for a numeric `y_range` end, each bin past it gets a line in the curve's pen at 0.6 width, 2 px outside the frame edge. Curves past one end in one bin split its width, nearest first. With no room beyond the edge, the mark goes 2 px inside, as the default `ratio.gap = 0` always does. A value ≤ 0 on a log axis, and the data, get none. mpl draws the same (`_overflow_marks`).
   - **Data:** points with x bars, under the MC.
   - **Legend:** a "+" per entry, header first, data first. A curve with every bin voided is "(no entries)".
   - **Ratio pad:** each curve over the data, or over the first curve, on the reference's bins. Range at least `ratio.range`, widened to ratios within `ratio.limits`. Labels at the pads' joint are dropped.
8. **Save** each format. The PDF page is `page.size`; the PNG size × dpi.

## A heat map page

`heatmap = true` draws one 2D object: a `TH2D` from App_yd2rt, `COLZ`, `kBird`, with a z scale (`z_label`, `logz`). The 1D pages' frame, titles and sizes; no ratio, data or voiding. Its ranges are its own figure's alone (`page_settings(own_ranges=True)`), checked first (`heatmapRefusal`), then kept within it and set with `SetRangeUser`, which widens each end to its bin's edge.

## Dumps

- `--dump-ranges` prints steps 1–6 as JSON and draws nothing: `x`, `y`, `largest`, `voided`, `data_bins`, `data_x`, `x_tool`, `y_tool`. This is how the arithmetic is tested. `--ranges` writes the same beside each page.
- `--dump-style` prints the merged style as TOML.

## The style

`base.toml`, found under `$HEIMDALL` (else, on Linux, from Paint's own folder), with the page's `[style]` merged over it. An unknown key, or a value of another kind, is an error.

The command line, the page TOML and what it accepts: `Paint.exe --help` and [plots-style](../guide/plots-style.md).
