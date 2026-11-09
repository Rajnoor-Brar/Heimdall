---
id: plot-backends
summary: how the backends beside Paint draw the same pages, what they honour and refuse
code: framework/plot/mpl/backend.py, framework/plot/mpl/transforms.py
---

# Plot backends

Which to choose: [`backend`](../../reference/settings/plot.md#backend). Every backend draws the same page documents with the ranges and voided bins Paint computed, so all show one window.

`[plot] backend` is `"root"`, `"mpl"` or a list of them. The rivet-mkhtml backend (`yoda`, and `both`) is gone: a file naming it is refused with `"mpl"` or `["root", "mpl"]` as the way on, and `heimdall migrate` rewrites it, comments kept.

`mpl` keeps mkhtml's look, so only these carry over: a `legend.position` corner (or `best`; `mpl` also the four outside ones and `ratio.gap`), `text.legend`, `text.header`, `ratio.divisions`, `ratio.range` with `ratio.limits`. Alone, they refuse `root_style` and every other style key; beside the root backend those are Paint's and allowed. A legend at `[x, y]` is still refused, because the page sets would disagree.

**`mpl`** draws what mkhtml did, without it: rivet's `get_plot_configs` reads `.plot` files, YODA's helpers give every number, and mkhtml's generated script's calls are made directly. What it borrowed from the old backend is its own: `mpl/transforms.py` holds the voided bins, area normalisation, band envelopes, the reference cut, the ratio window, the page's `.plot` block and `validate`; `mpl/backend.toml` the legend corners and honoured style keys. The pages were checked byte for byte across the move (104 PNGs unchanged); its look stays a thing the developer verifies. The YODA Python library stays, as YODA files are read everywhere.

Writing one: [extending](extending.md).
