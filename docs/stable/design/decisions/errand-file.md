---
id: decisions-errand-file
summary: why an errand file is read as it is: forms, imports, vars, defaults, paths
---

# Decisions: the errand file

The full account of each is at tag `docs/pre-rebuild`, in `docs/07_Record.md`.

- **V13** A leading `./` means the work dir's root; `../` is an error. Gave up: paths relative to the current folder. Amended by V229.
- **V54** Correctness fixes: Rivet options go parent → child (table, inline, quantity); a custom `executable` is built under `build/` or refused.
- **V55** One schema holds every key once, and `"default"` means "keep it as it is": the parent's value, or nothing set at the top.
- **V56** Configurations share keys through `extends` and imports; this file wins. A quantity or configuration is replaced whole, a tool table merges.
- **V59** Cards: each key once; the runner's keys reported; the tool checks the card.
- **V79** Break and migrate: old forms are refused with a hint, and `heimdall migrate` rewrites them. Configs are migrated only on the user's word.
- **V93** `[config]` (v3 `[file]`) says how a file is read: `import`, `master`.
- **V94** Imports nest depth-first and cross assignments; a circle is refused.
- **V95** An import may take part of a file (`only`) and `drop` keys; a misspelt name is refused rather than ignored.
- **V96** `{var:name}` is replaced after imports and `--set`, before any check, so identity sees only the result.
- **V97** `[file.meta]` records the stack a file ran with, and warns rather than gatekeeps.
- **V98** Configurations are their own table, so a misspelt one is an error instead of a configuration.
- **V99** `[errand]` is what every configuration starts from.
- **V100** An import's location rule is per folder.
- **V101** An imported file's vars come with what is taken of it.
- **V128** The third form is read as the second, table by table: same points, folders and identities. Gave up: one reader's simplicity, for one release.
- **V129** `--plan --card <tag>` prints a card, each line with its origin.
- **V130** `heimdall migrate --v3` rewrites a v2 file, comments kept.
- **V131** A v3 configuration with no serial gets its number from the runner; `"default"` has one meaning.
- **V136** Docs match the code: every whole example in the docs loads through the real parser.
- **V179** A configuration's own cards and data (`vars`, `data`); only the sets it picks are checked against its points.
- **V188** `[heimdall]`: a command's flags in the errand file. Narrowed by V190.
- **V190** `[heimdall]` takes preference switches only, since a flag that changes results belongs in the file's own keys.
- **V225** `[run]` → `[errand]`, `project` → `assignment`.
- **V226** A plot document's `[source]` uses those names.
- **V227** The code uses those names: `RunConfig` → `Errand`.
- **V229** A bare name is beside the file naming it, not rederived from `<A>/<E>`.
