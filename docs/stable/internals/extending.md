---
id: extending
summary: how to add a standard tool, a plot backend or a figure class, and what each must touch
code: framework/tools, framework/plot, framework/schema/run.toml, framework/runner/plot.py
---

# Extending

## A standard tool

For a generator `gen` that reads a card and writes HepMC:

1. **Read what is known:** a tool's page in `stable/tools/`, and v1's adapter if there was one (`git show rework/v1-final:utils/python/hekit/adapters/<tool>.py`, in High-Energy).
2. **`framework/tools/gen/tool.toml`** ([tool-contract](tool-contract.md)):

   ```toml
   [tool]
   category        = "event-generator"
   executable      = "gen"
   status          = "filters"
   produces_events = true

   [card]
   style   = "append"
   ext     = "gen"
   comment = "#"
   seed    = ["seed = {seed}"]

   [command]
   argv = ["{exe}", "--card", "{card}", "--events", "{events}", "--out", "{output}"]

   [outputs]
   sidecar = "{output}.json"
   written = "requested"            # only if it truly always makes what it is asked for

   [identity]
   version = "stack:gen"
   ```
3. **`filters.toml`:** a progress rule from a real log, and an error rule.
4. **Quantities:** `quantities.toml`, how it consumes the vocabulary's names. A name the vocabulary lacks goes into `framework/schema/quantities.toml` first, with its shape.
5. **Version:** an entry in `env/stack.toml`.
6. **Tests:** a plan-time test in `tests/runner/` (card, argv, a refusal) using `helpers.raw()`, `parse()`, `plan()`; a slow gate in `tests/integration/` that runs a point and checks a number.
7. **Docs:** its page in `stable/tools/`. A test fails when a folder has none.

These questions decide a folder's design: can it read a FIFO? Does it write σ into its events (Whizard does not)? Does it write exactly what it is asked? Is part of its work card-dependent but seed-independent (`[prepare]`)? Must its output path be relative (Sherpa prepends `./`)?

## A plot backend

`framework/plot/<name>/backend.py`, no `tool.toml`, loaded by `plot.backend(name)`:

- `validate(settings, beside_root=False, curve_styles=())`: refuse at plan time every key it cannot honour.
- `draw(cells, settings, say) -> int`: cells are folders of `plot.Page`s; returns how many failed.
- `INDEX = True`, optional: the runner writes the index.

Add the name to `[plot.backend]`'s choices. `mpl/backend.py` is the example; the yoda backend is frozen. See [plot-backends](plot-backends.md).

## A figure class

A class is a way to choose members and objects. Drawing stays one path, so a new class gets ratios, bands, data, styles, placeholders and every backend for free.

1. **Schema:** add it to `[figure.class]`'s choices, any key of its own as `[figure.<key>]`, and list that in `schema.FIGURE_OWN`. Regenerate.
2. **Rules:** in `config.check_plot`, what can be refused when the file is read; in `plot.check_figures`, what needs the configuration.
3. **`Figure`:** a field per key, read in `plot.figures`.
4. **Members:** a function returning `(members, yodas)`, each made once per change of inputs. Arithmetic on YODA objects belongs in `framework/plot/figures/`, so the runner stays standard library.
5. **Pages:** in `plot.pages` (or `plot.draw`), merge members and call `_pages` as a `defined` figure.
6. **Tests:** a `tests/runner/test_plot.py` case per refusal; an integration test in `test_plot_stage.py`.
7. **Docs:** a section in [plots-figures](../guide/plots-figures.md).
