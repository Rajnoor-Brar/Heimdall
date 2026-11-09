# Phase 2: path and name kinds

Plan: [00_Plan](00_Plan.md). Blocked by: phase 1. Size: M.

## Steps

1. **The kind table (S).**
   - `KINDS = {(command, dest): kind}` and `FREE = {(command, dest)}` in `complete.py`.
   - A test walks the parser: every positional, and every option with a metavar, is in one of the two.
2. **Path kinds (M).** Each one works over a folder and the typed prefix, and offers the next level, with `/` when there is more below (directive `nospace`):
   - errand: `house.config_names`, plus the Errand's Runs from `records_root()` after `<A>/<E>/` (D2);
   - errand or drawing (`plot` only, D7): as errand, with the Runs of `records_root()` and `results_root()` together, without duplicates;
   - assignment;
   - record;
   - record-deep: points from `points/`, tools from `logs/<point>/*.log`;
   - result;
   - record-scope.

   A word that starts with `./`, `../` or `/` gives `files:*.toml` (errand) or `files:` (others), and bash answers.
3. **Name kinds (S):**
   - configuration: `config.load(word before)`, which takes both dialects;
   - schema key: `schema.keys`, table first;
   - tool folder: `paths.tool_chains`;
   - command;
   - recipe: `report.recipes`;
   - the states list, after the last comma.
4. **Run kinds (S, D4):** ids from the registry by glob plus `runs._own`, never `runs.entries()` (it prunes). Indices only if the registry alone numbers them as `heimdall runs` does: see the plan's *Not yet specified*.

## Checks

- One test per row of the plan's table, on the scratch work dir that `conftest.py` sets up. It never uses a real work dir.
- `library` never appears as an Errand.
- `plot Demo/jets/` offers a Run that exists only under `results/`. `run Demo/jets/` does not offer it.
- A broken errand gives no configurations and no error.

## Log
