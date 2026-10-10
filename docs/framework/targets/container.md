# Target: a container image

Heimdall, with its stack built inside it, shipped as one image; work dirs are mounted into it.
Docker on a PC, Apptainer on a cluster ([cluster](cluster.md), way A). The user chooses this
target; P0 never picks it alone. Only what differs from the phase files is here (D11).

**The user is learning Docker** (the user, 2026-10-07):
- explain each command before running it;
- never build, push or tag an image without asking;
- the image stays private: it is moved as a file, never pushed to a public registry.

## Prerequisites

- **Docker usable by the user.** Joining the `docker` group is the user's own action (it is
  root-equivalent), so P0 records "installed, no group" and stops there.
- About 25 GB free while building (the image keeps the installs only: about 10 GB with
  `@primary`).
- 3 GB of memory per ROOT compiler (`ROOT_CORES`).

## The image's recipe

`recipes/platforms/container/Dockerfile`: the build context is Heimdall itself, and the image holds
it at `/opt/heimdall`, which is `$HEP` inside. It builds the stack (`PACKAGES`, `@primary` by
default; `CORES`, `ROOT_CORES`, `GRAPHICS`, `GEANT4_DATA` as build arguments) and Heimdall's apps,
then removes `stash/` and `forge/` in the same layer, so the image keeps the installs only. Its
`Dockerfile.dockerignore` keeps the ignored trees of the context out, and `heimdall.def` makes an
Apptainer `.sif` from a saved image (the commands are in each file's head). Read them; this annex
does not copy them.

## What replaces which phase

**P1 is replaced by `docker build`.** That is a gate: hours of build, plus the downloads. P1 S3's
rows then run inside the image:

```bash
docker run --rm heimdall bash -lc 'root-config --version; lhapdf list --installed | wc -l'
```

**P2's tests** run inside the image (`hep make --framework test`, with `/opt/heimdall` writable for
`forge/scratch/`, or from a clone mounted at the same path).

**P3's work dirs** are mounted at the same path inside as outside:

```bash
docker run --rm -it --user "$(id -u):$(id -g)" -v "$HOME/Github/Top-Quark:$HOME/Github/Top-Quark" -w "$HOME/Github/Top-Quark" heimdall
```

Then the absolute paths in provenance mean the same thing on both sides.

## Verification (added to P1 S3, P3)

| # | Command | Expected |
|---|---|---|
| C1 | `docker image inspect heimdall --format '{{.Size}}'` | recorded (about 10 GB) |
| C2 | `docker run --rm heimdall bash -lc 'hep where --hep'` | `/opt/heimdall` |
| C3 | the P1 S3 rows, each through `docker run --rm heimdall bash -lc '…'` | as there |
| C4 | in a mounted Top-Quark: `hep check; echo "exit $?"` | `exit 0` |
| C5 | after a run inside: `find ~/Github/Top-Quark/results -user root \| wc -l` | `0` (`--user` kept the files the user's) |

## Known limits

- **`hep watch`** only sees runs in the same network namespace: run it in the same container, or
  start containers with `--network host`.
- **Graphics are off** (`GRAPHICS=OFF`). The pages are files (PDF and PNG), and the deck viewer is
  served to the host by `-p <port>:<port>`.
- **The image is Ubuntu 24.04**, so the lab PC's baselines hold inside it, whatever the host runs.
