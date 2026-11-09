---
id: decisions-chain
summary: why tools connect and run as they do: FIFOs, stages, shards, context files, tool folders
---

# Decisions: the chain and tools

The full account of each is at tag `docs/pre-rebuild`, in `docs/07_Record.md`.

- **V15** After-all-points tools go in `post`, handed a points manifest.
- **V16** Fan-out is a list-valued `output` on a producer. Gave up: a general tee.
- **V18** Rivet sources may be `modules/<A>/Rivet/<x>.cc` or `modules/<A>/Rivet_<x>.cc`.
- **V21** Standard configurations for custom tools. Superseded by V126.
- **V24** A `pre` stage runs once before every point; its identity is part of every point's.
- **V31** `shards = K`: K Rivet processes, events dealt among them, merged by the folder's merge tool. The chain is unchanged.
- **V33** The integrated program runs Pythia as App_Pythia does, through shared headers.
- **V34** Several Rivets in one process: `rivet_threads`, fed first-free from one queue.
- **V63** One Pythia core, `PythiaRun.hh`, shared by App_Pythia and the integrated program.
- **V77** `heimdall reproduce` replans a point from its provenance and refuses unless the identity matches.
- **V125** A tool folder is found nearest first: work dir, Himinbjorg, Heimdall.
- **V126** One context file per point; exec and module are ordinary folders; module settings are checked.
- **V146** A tool folder names its packages. Three nouns: a package (a recipe), a library, a tool.
- **V148** `// requires: pkg:<name>` links any library pkg-config knows; `path:<command>` asks for a program.
- **V187** A point keeps the commands its tools were given, and its context file.
