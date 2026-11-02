---
id: plot-backends
summary: how the backends beside Paint draw the same pages, what they honour and refuse
code: framework/plot/mpl/backend.py, framework/plot/yoda/backend.py
---

# Plot backends

Which to choose: [`backend`](../../reference/settings/plot.md#backend). Every backend draws the same page documents with the ranges and voided bins Paint computed, so all show one window.

They keep mkhtml's look, so only these carry over: a `legend.position` corner (or `best`; `mpl` also the four outside ones and `ratio.gap`), `text.legend`, `text.header`, `ratio.divisions`, `ratio.range` with `ratio.limits`. Alone, they refuse `root_style` and every other style key; beside the root backend those are Paint's and allowed. A legend at `[x, y]` is still refused, because the page sets would disagree.

**`mpl`** draws what mkhtml would, without it: rivet's `get_plot_configs` reads `.plot` files, the yoda backend's transforms run in memory, YODA's helpers give every number, and mkhtml's generated script's calls are made directly. About 18× faster than mkhtml. `test_plot_stage.py` checks every page against mkhtml's, pixel for pixel. Overflow marks are its one intentional difference.

**`yoda`** is deprecated and frozen. Per page set it writes point YODA copies with voided bins blanked; `reference.yoda`, the mapped reference objects renamed `/REF/<analysis>/<object>` (mkhtml's own lookup is off: explicit only); and `pages.plot`. It runs `rivet-mkhtml --no-rivet-refs -o <dir> -c pages.plot <yodas…>`, then writes `ratio.divisions`' locators into each page's script and runs it again, since YODA's generator has no key for the ratio's ticks.

Writing one: [extending](extending.md).
