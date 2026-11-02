---
id: results-python
summary: reading a run's results from Python, for notebooks and statistics tools
code: framework/runner/results.py
---

# Results from Python

```python
from runner import results     # framework/ is on the base's path; elsewhere, sys.path.insert(0, os.environ["HEIMDALL"] + "/framework")

for point in results.load("Demo/jets", "energy_pdf"):
    print(point.name, point.values["pdf"].label, point.complete, point.yoda())
```

`results.load(CONFIG, CONFIGURATION)` reads `points.json` and returns its points. Each has `name`; `values` (quantity → `tag`, `label`, `value`, `swept`); `products` (name → path), `results`, `output`; `complete`, `identity`, `seed`; `yoda()` and `root()`. `results.runs(CONFIG)` gives every configuration that has run. It plans nothing, so it needs no tool installed.
