---
id: images
summary: Heimdall and a machine root as one Apptainer image: building, using, what it can and cannot do
code: framework/runner/image.py, recipes/platforms/container/heimdall.def
---

# Apptainer images

An image holds a clean copy of this Heimdall and a machine root built inside it (`/opt/heimdall`, `/opt/himinbjorg`), read-only, in the machine root's `images/`. Work dirs stay outside, bound at their own paths, so paths in provenance mean the same on both sides. No Docker; the Dockerfile beside `heimdall.def` is only the CI workflow's.

**Needs:** the system's `apptainer`, else `singularity` (setuid or user namespaces, so never in the machine root). To build without sudo, the user in `/etc/subuid` and `/etc/subgid`. About 3 GB for `@core-conda`, 10 GB for `@primary`, 25 GB free while building, and 3 GB of memory per ROOT or Rivet compiler. It downloads Ubuntu and the stack, and takes minutes with a ready-made set, hours from source.

```bash
heimdall image build packages=@core-conda root_cores=2 [--name NAME]   # → images/core-conda.sif
heimdall image                                                         # the images and their labels
gjallarhorn --image core-conda <title>                                 # a shell in it, in that work dir
launch.sh --image core-conda heimdall run Jets/jets                    # one command
launch.sh --image core-conda --dev …                                   # binds this checkout over the image's Heimdall
```

- A checkout with uncommitted changes is refused (`--dirty`). Labels say Heimdall's revision, the toolkit, the date.
- The host's environment never reaches it (`--cleanenv`).
- A point run inside records the image in provenance; the identity is the tools' binaries', as always.
- **It is read-only.** Runs write only the work dir. A change of Heimdall is a new image, or `--dev`.
- Keep images private: move them as files, never push to a registry.

Checks: `launch.sh --image <name> heimdall where --heimdall` prints `/opt/heimdall`; `launch.sh --image <name> heimdall check` exits 0 in a work dir. A real image has not been built and run end to end everywhere: treat a failure as a finding.
