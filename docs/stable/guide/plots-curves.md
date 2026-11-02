---
id: plots-curves
summary: curves' labels and looks, per quantity value, per tag across Runs, and bands
code: framework/runner/plot.py, framework/runner/plotdoc.py
---

# Curves: labels, looks and bands

A curve is labelled by its points' `label`s, joined with `, `, and drawn in the next colour of the style's palette. A quantity can give a point its own look, kept on every page:

```toml
[quantities.pdf]
points = [
  { tag = "MSTW08lo",  value = "LHAPDF6:MSTW2008lo68cl",         label = "MSTW 2008 LO", style = { colour = "#EE3311" } },
  { tag = "NNPDF23lo", value = "LHAPDF6:NNPDF23_lo_as_0130_qed", label = "NNPDF 2.3 LO", style = { colour = "kBlue+1", line = "dashed", width = 1.5 } },
]
```

A row's `style` belongs to the Run, so a Run made before it does not have it. **`[plot.looks]`** gives looks in `[plot]` instead, so `--style-sync` carries them to every Run, and a value commented out keeps its look:

```toml
[plot.looks.pdf]
NNPDF23lo = "#0067A5"
HERAPDF20JetsNLOEig = { colour = "#008856", line = "dashed" }
```

A set's `look` and a curves filter's styled values go over it ([plots-sets](plots-sets.md)).

**A band** folds a curve axis into an envelope:

```toml
[plot]
band = ["scale"]   # per value of the other curve axes, one curve (the scale's first value), min–max shaded around it
```

The legend entry ends `(scale envelope)`. A band must be a curve axis: varied, not `plot_points`, not combined. Every backend draws it.
