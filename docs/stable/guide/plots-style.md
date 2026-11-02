---
id: plots-style
summary: how a page's look is layered, a style file, legends outside the frame, and seeing the merged style
code: src/Apps/Paint/base.toml, framework/runner/plot.py
---

# The style

Every ROOT page starts from `src/Apps/Paint/base.toml`: rivet-mkhtml's look. Every key: [style settings](../../reference/settings/style.md). Over it, key by key:

1. the machine root's `style.toml`: every study on this machine;
2. the work dir's `style.toml`;
3. `[plot].root_style`: a style file beside the errand file;
4. `[plot.style]`, inline;
5. a figure's `style`, for its pages.

Each layer names only what it changes, in base.toml's tables. A work dir's `latex.toml` adds its own macros over `framework/schema/latex.toml`.

```toml
# configs/Demo/talk.toml       (root_style = "talk")
[text]
title  = 12.0             # points
legend = 9.0
[legend]
position = "top-left"     # a corner, "best", or [x, y]: its top-right corner, in fractions of the frame
[curves]
errors = "band"
```

## Outside the frame

```toml
[plot.style]
legend = { position = "out-right" }     # out-right, out-left: a column beside the frame; out-top, out-bottom: as many columns as fit
ratio  = { gap = 6.0 }                  # points between the main frame and the ratio's (0: joined)
```

Paint keeps the page's size and shrinks the frame; `mpl` keeps the frame and grows the page. A long legend beside the frame takes much of a small page, so a wider `page.size` helps. `yoda` cannot draw either, so they are refused for it.

## Checking

- An unknown key, or a value of another kind, is refused at plan time with the nearest spelling.
- `$HEIMDALL_APPS/Paint.exe <page>.toml --dump-style` prints a page's whole style; page documents are in `.cache/<A>/plots/<E>/<R>/<set>/`.
- Denser or sparser ratio ticks: `ratio = { divisions = 508 }`.
- The other backends honour only part of this: [plot-backends](../internals/plot-backends.md).

Paint's command line: `Paint.exe PAGE.toml…`, with `--dump-style`, `--dump-ranges`, `--ranges`, `--ranges-only`: [paint](../internals/paint.md).
