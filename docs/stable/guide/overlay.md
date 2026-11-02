---
id: overlay
summary: heimdall overlay: any YODA or ROOT files on one page, with no errand file
code: framework/runner/plot.py, framework/runner/cli.py
---

# Any files, overlaid

```bash
heimdall overlay a.yoda b.yoda --labels "Tune A,Tune B" --ratio --objects "/MC_JETS/*"
heimdall overlay .cache/Demo/plots/jets/01_pdf/pdf.root            # a sweep: a curve per point
```

No errand file is needed: one page per object any file holds, a curve per file, or per point of a merged sweep. `-o DIR` where pages go (default `results/plots/<first file>/`), `--formats pdf,png`, `--style FILE`. The pages are Paint's, with an `index.html`. [Arguments](../../reference/commands.md).
