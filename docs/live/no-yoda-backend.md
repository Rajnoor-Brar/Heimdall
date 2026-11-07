---
id: live-no-yoda-backend
summary: the yoda plot backend (rivet-mkhtml) is gone; mpl owns the transforms it borrowed
affects: plots
issue: I-43
---

**Now holds:** `[plot] backend` is `"root"`, `"mpl"` or a list of them. mpl draws the pages mkhtml did (its look until the developer has verified it), with no rivet-mkhtml. What mpl borrowed from the yoda backend lives in `framework/plot/mpl/transforms.py` (voided bins, area normalisation, band envelopes, the reference cut, the ratio window, the page's `.plot` block, `validate`) and `mpl/backend.toml` (legend corners, honoured style keys). A report section's `backend` is `"root"` or `"mpl"`.

**No longer holds:** `backend = "yoda"` and `"both"`, which a file naming is refused (`config.RETIRED_BACKENDS`: "backend = … is retired", with `"mpl"` or `["root", "mpl"]` as the way on) and `heimdall migrate` rewrites (`migrate.backend_text`: yoda → mpl, both → root and mpl, comments kept); `framework/plot/yoda/`; `plots/yoda/` as a tree a run writes; the pixel test of mpl against mkhtml (the pages were verified byte for byte across the move instead: 104 PNGs unchanged).

**Decisions:** the yoda *Python library* stays (YODA files are read everywhere). `migrate` still knows `plots/yoda/` as an old layout, and `RESERVED_SETS` still holds `yoda`, so an old results tree is moved, not mistaken for a set.

**Stable pages need:** `internals/plot-backends.md` (the yoda backend's section goes; mpl's names `transforms.py`), `guide/plots.md` and `internals/extending.md` (backend choices), `guide/plots-style.md` (which backend refuses which key: only mpl, beside root).
