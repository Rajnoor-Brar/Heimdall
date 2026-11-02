---
id: docs-system
summary: how the docs are generated and checked; the page model, the map, the drift report, the site
for: dev agent
code: framework/runner/knowledge.py, framework/runner/docs.py, framework/runner/knowledge_site.html
---

# The docs system

- `knowledge.py` (low rank, so the CLI can use it) reads pages and frontmatter, and builds the map, the drift report and the site. It holds no text of its own.
- `docs.py` (top rank, as it reads the CLI's parser) renders generated pages and writes them: `heimdall make --framework docs`.
- `tests/runner/test_knowledge.py` holds the pages to [writing](../../rules/writing.md).

| Output | From | Where | Committed |
|---|---|---|---|
| The map | every page's frontmatter | `docs/MAP.md` | yes, and a test fails when it is stale |
| Settings reference | the schema, one block per key | `docs/reference/settings/` | yes, likewise |
| The site | the same, as one self-contained page | the forge's `docs/index.html`, by `heimdall docs` | no: Heimdall holds nothing built |

**Drift** is `git diff --name-only <CRYSTAL.toml's commit>` against each stable page's `code:`, leaving out pages a live doc names. It finds what prose alone never could: code that moved under a page.

**Why generated markdown is committed:** agents and GitHub read it with no stack loaded. **Why the site is not:** it would churn on every change, and nothing reads it but a browser on this machine.
