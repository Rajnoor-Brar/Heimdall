---
id: code
summary: how code here is written; rules that hold across modules and are not visible from one file
for: dev agent
---

# Code

- **The runner is one flat package, by ranks.** A module imports only from its own rank or a lower one (`RANKS`, `runner/__init__.py`), enforced by `tests/runner/test_imports.py`.
- **The runner core never names a tool.** What it knows about a tool lives in that tool's folder.
- **Standard library in the runner.** Plugins import only `PLUGINS_MAY_IMPORT`.
- **One error type:** `HeimdallError(message, where=…, hint=…)`. `where` is a file and key, a point or a path; `hint` says what to do, with `did_you_mean` for names. A message that only restates the failure is not enough.
- **Refuse the convenient inference.** Where a correspondence could be guessed (names, paths, which tool a quantity is for, a data map), require it stated, and make a wrong one loud.
- **A key a consumer cannot honour is an error,** in configs, styles and backends.
- **Name `encoding="utf-8"` on every text read and write,** text-mode subprocesses included: reading a YODA resets `LC_ALL` to `C` (L17).
- **A breaking config form:** refuse the old form with a hint, and teach `heimdall migrate` to rewrite it.
- **C++ in `src/`** is a few headers and apps, no library namespaces. A header holds one PascalCase namespace with `camelCase` functions, and no `using namespace` of an external library at namespace scope. A source declares what it links in a `// requires: …` line near the top.
- **Names:** assignments PascalCase; configs, quantities and tool tags lowercase, short and filename-safe; a Rivet analysis's file, class and `.info` name are one string.
- **Before writing code for a tool,** read its page (`stable/tools/`).
