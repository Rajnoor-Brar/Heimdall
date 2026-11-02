---
id: plots-data
summary: reference data on pages, why the map is explicit, and ratio pads
code: framework/runner/plot.py
---

# Reference data and ratios

```toml
[plot]
ratio = true                              # MC/Data in a ratio pad

[plot.data]
file   = "rivet:ZEUS_2012_I1116258"       # Rivet's own; a bare name is under datasets/
legend = "ZEUS 2012"

[plot.data.map]                           # explicit: never matched by name
"d01-x01-y01" = "/REF/ZEUS_2012_I1116258/d01-x01-y01"
"d09-x01-y01" = "/REF/ZEUS_2012_I1116258/d09-x01-y01"
```

- **Data are drawn only on pages the map names,** aligned to the MC's bins: cut to their longest run of bins whose edges line up, or dropped with a warning.
- **The map is explicit** because ZEUS's `d08` and `photo_eic`'s `d08` are different observables.
- **The ratio pad** is each curve over the data. Without data, or with `use_data = false`, each curve over the page's first curve.
- **A configuration's own data:** `[cfgs.<name>] data`, in place of `[plot.data]`.
