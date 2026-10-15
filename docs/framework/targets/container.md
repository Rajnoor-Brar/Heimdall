# Target: an Apptainer image

Heimdall and a machine root built inside it, shipped as one read-only image (`.sif`); work dirs stay
outside, bound into it at their own paths. Apptainer (or SingularityCE) on a PC or a cluster; no Docker.
The user chooses this target; P0 never picks it alone. Only what differs from the phase files is here
(D11).

- explain each command before running it;
- never build an image without asking (it downloads Ubuntu and the stack, and builds for hours with a
  source-built set, minutes with an `@…-conda` one);
- the image stays private: it is moved as a file, never pushed to a registry.

## Prerequisites

- **Apptainer**, the system's: `sudo apt install apptainer` (or SingularityCE), or a cluster's `module
  load apptainer`. It needs setuid or user namespaces, so it is never installed into the machine root.
- **Building without sudo** (`--fakeroot`): the user in `/etc/subuid` and `/etc/subgid` (`grep $USER
  /etc/subuid`). Otherwise the build runs with sudo.
- Room for the image in the machine root's `images/` (about 3 GB with `@core-conda`, about 10 GB with
  `@primary`), and about 25 GB free while it builds (in the system's temporary folder).
- 3 GB of memory per ROOT or Rivet compiler (`root_cores`).

## The image's recipe

`recipes/platforms/container/heimdall.def`: a stock Ubuntu 24.04 pulled by Apptainer; a clean copy of the
checkout (its tracked files) at `/opt/heimdall`, which is `$HEP` inside; the machine root built at
`/opt/himinbjorg` by `build_stack.py` (the conda base, then the stack; `shell_rc=false`), then Heimdall's
apps, then `forge/` removed, so the image keeps the installs only. Its labels say Heimdall's revision, the
toolkit and the date. `heimdall image build` fills it and runs the build; its head says how to build it by
hand. The Dockerfile beside it is only the CI workflow's.

## What replaces which phase

**P1 is replaced by the image build.** That is a gate: the downloads and the build time.

```bash
heimdall image build packages=@primary             # → <machine root>/images/primary.sif (hours)
heimdall image                                     # the images, their size and labels
```

P1 S3's rows then run inside it: `launch.sh --image primary bash -lc 'root-config --version'`.

**P2's tests** run inside it, from a clone bound over the image's Heimdall: `launch.sh --image primary --dev
heimdall make --framework test` (the tests write `$HEP_FORGE/scratch/`, so the machine root's scratch must
be writable: a work clone's `HEP_FORGE`, or run them on the host's stack instead).

**P3's work dirs** are bound at their own paths:

```bash
gjallarhorn --image primary Top-Quark              # a shell in the image, in that work dir
launch.sh --image primary heimdall run Jets/jets   # one command, in the current folder
```

So the absolute paths in provenance mean the same on both sides; a point run inside records the image (its
path and labels).

## Verification (added to P1 S3, P3)

| # | Command | Expected |
|---|---|---|
| C1 | `ls -l <machine root>/images/primary.sif` | recorded (about 10 GB) |
| C2 | `launch.sh --image primary heimdall where --hep` | `/opt/heimdall` |
| C3 | the P1 S3 rows, each through `launch.sh --image primary bash -lc '…'` | as there |
| C4 | in a bound Top-Quark: `launch.sh --image primary heimdall check; echo "exit $?"` | `exit 0` |
| C5 | after a run inside: `find ~/Github/Top-Quark/results ! -user "$USER" \| wc -l` | `0` (Apptainer runs as the user) |

## Known limits

- **The image is read-only.** Runs write only the work dir; the image's Heimdall, stack and Python never
  change (`PYTHONDONTWRITEBYTECODE`). A change of Heimdall is a new image, or `--dev` while developing.
- **A clean environment.** `--cleanenv`: nothing of the host's shell (its stack, a loaded environment,
  `LD_LIBRARY_PATH`) reaches the image; the host's home is bound by Apptainer's default.
- **The image is Ubuntu 24.04**, so the lab PC's baselines hold inside it, whatever the host runs.
