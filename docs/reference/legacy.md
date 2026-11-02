---
id: legacy
summary: the errand file's older (v2) names and today's
code: framework/schema/v3.toml
generated: true
---

# v2 names

`heimdall migrate --v3` rewrites a v2 file. Generated from `framework/schema/v3.toml`.

| Table | v2 | Today |
|---|---|---|
| `[errand]` → `[errand]` | `configuration` | `run` |
| `[errand]` → `[errand]` | `event_count` | `events` |
| `[errand]` → `[errand]` | `tools` | `chain` |
| `[errand]` → `[errand]` | `sweeps` | `vary` |
| `[errand]` → `[errand]` | `seed_type` | gone |
| `[errand]` → `[errand]` | `manual_seed` | gone |
| `[errand]` → `[errand]` | `cfgs` | gone |
| `[configuration]` → `[cfgs]` | `label` | `folder` |
| `[configuration]` → `[cfgs]` | `event_count` | `events` |
| `[configuration]` → `[cfgs]` | `tools` | `chain` |
| `[configuration]` → `[cfgs]` | `sweeps` | `vary` |
| `[configuration]` → `[cfgs]` | `static` | `fixed` |
| `[configuration]` → `[cfgs]` | `seed_type` | gone |
| `[configuration]` → `[cfgs]` | `manual_seed` | gone |
| `[configuration]` → `[cfgs]` | `prelim` | gone |
| `[tool]` → `[tools]` | `tool` | `uses` |
| `[tool]` → `[tools]` | `baseconfig` | `card` |
| `[tool]` → `[tools]` | `output_file` | `output` |
| `[quantity]` → `[quantities]` | `key` | `to` |
| `[quantity]` → `[quantities]` | `values` | gone |
| `[quantity]` → `[quantities]` | `tags` | gone |
| `[quantity]` → `[quantities]` | `labels` | gone |
| `[quantity]` → `[quantities]` | `styles` | gone |
| `[quantity]` → `[quantities]` | `target` | gone |
