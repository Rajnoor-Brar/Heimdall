"""Apptainer images of Heimdall and a machine root (rank 0; docs/05_Commands_and_Tools.md §2, V150).

The runtime is the system's: `apptainer`, else SingularityCE's `singularity` (setuid or user namespaces: an
admin's, never the machine root's). An image holds /opt/heimdall (a clean copy of this checkout) and
/opt/himinbjorg (a machine root built inside it, by recipes/platforms/container/heimdall.def), and lives in
the machine root's images/. Work dirs stay outside, bound at their own paths. `heimdall image build` makes one,
`heimdall image` lists them; `gjallarhorn --image` (launch.sh) and `[cluster] image` run in one.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import HepError, did_you_mean
from .paths import hep_root, machine_root

RUNTIMES = ("apptainer", "singularity")
#: Where a running image says its labels (Apptainer and SingularityCE both).
LABELS = Path("/.singularity.d/labels.json")


def definition() -> Path:
    return hep_root() / "recipes" / "platforms" / "container" / "heimdall.def"


def runtime() -> str:
    """The system's Apptainer (or SingularityCE)."""
    for name in RUNTIMES:
        if found := shutil.which(name):
            return found
    raise HepError("no apptainer (or singularity) on PATH",
                   hint="the system's: `sudo apt install apptainer`, or a cluster's `module load apptainer`")


def images_dir() -> Path:
    return machine_root() / "images"


def image_path(name: str) -> Path:
    """An image by name (a file of <machine root>/images/, without .sif) or by path."""
    if "/" in name or name.endswith(".sif"):
        path = Path(name).expanduser()
    else:
        path = images_dir() / f"{name}.sif"
    if not path.is_file():
        known = sorted(p.stem for p in images_dir().glob("*.sif"))
        raise HepError(f"no image {path}", hint=did_you_mean(name, known) or
                       (f"the images: {', '.join(known)}" if known else "heimdall image build makes one"))
    return path.resolve()


def render(values: dict[str, str]) -> str:
    """heimdall.def with its {{ NAME }}s filled (what Apptainer 1.2's --build-arg does, for every version)."""
    text = definition().read_text(encoding="utf-8")
    for name, value in values.items():
        text = text.replace("{{ %s }}" % name, value)
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    if left := sorted(set(re.findall(r"\{\{ (\w+) \}\}", body))):
        raise HepError(f"heimdall.def's {', '.join(left)} not given", where=str(definition()))
    return text


def dirty() -> bool:
    """Tracked changes in the checkout: an image of it would not say what it holds."""
    done = subprocess.run(["git", "-C", str(hep_root()), "status", "--porcelain", "--untracked-files=no"],
                          capture_output=True, text=True, encoding="utf-8")
    return done.returncode != 0 or bool(done.stdout.strip())


def revision() -> str:
    done = subprocess.run(["git", "-C", str(hep_root()), "rev-parse", "HEAD"], capture_output=True, text=True,
                          encoding="utf-8")
    return done.stdout.strip()[:12] if done.returncode == 0 else "unknown"


def copy_checkout(target: Path) -> None:
    """The checkout's tracked files, as they are in the working tree, into `target` (no ignored trees)."""
    listed = subprocess.run(["git", "-C", str(hep_root()), "ls-files", "-z"], capture_output=True, check=True)
    for name in filter(None, listed.stdout.decode("utf-8").split("\0")):
        source = hep_root() / name
        if source.is_file():
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target / name)


def build(packages: str = "@primary", cores: str = "0", root_cores: str = "0", name: str = "",
          allow_dirty: bool = False, out=print) -> int:
    """`heimdall image build`: <machine root>/images/<name>.sif from heimdall.def, with --fakeroot. It downloads
    Ubuntu and the stack and builds it (hours for a source-built set; minutes for an @…-conda one)."""
    command = runtime()
    if dirty() and not allow_dirty:
        raise HepError("Heimdall has uncommitted changes: an image of them would not say what it holds",
                       hint="commit them first, or --dirty to take the working tree as it is")
    name = name or packages.lstrip("@").replace(" ", "-") or "heimdall"
    target = images_dir() / f"{name}.sif"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="heimdall-image-") as stage:
        source = Path(stage) / "heimdall"
        copy_checkout(source)
        recipe = Path(stage) / "heimdall.def"
        recipe.write_text(render({"HEIMDALL": str(source), "PACKAGES": packages, "CORES": cores, "ROOT_CORES": root_cores,
                                  "REVISION": revision() + ("-dirty" if allow_dirty and dirty() else ""),
                                  "BUILT": datetime.date.today().isoformat()}), encoding="utf-8")
        argv = [command, "build", "--fakeroot", str(target), str(recipe)]
        out(" ".join(argv))
        if subprocess.run(argv).returncode != 0:
            raise HepError(f"{Path(command).name} build failed", where=str(target),
                           hint="--fakeroot needs your user in /etc/subuid and /etc/subgid; else build with sudo: "
                                f"sudo {' '.join(argv[:2] + argv[3:])}")
    out(f"made {target}")
    return 0


def labels(sif: Path) -> dict[str, str]:
    """An image's labels (`inspect --labels`: "key: value" lines)."""
    done = subprocess.run([runtime(), "inspect", "--labels", str(sif)], capture_output=True, text=True,
                          encoding="utf-8")
    return dict(line.split(": ", 1) for line in done.stdout.splitlines() if ": " in line)


def listing() -> list[str]:
    """`heimdall image`: the images of this machine root, with what they hold."""
    found = sorted(images_dir().glob("*.sif"))
    if not found:
        return [f"no image in {images_dir()}: heimdall image build [packages=@kit] makes one"]
    rows = []
    for sif in found:
        held = labels(sif) if any(shutil.which(r) for r in RUNTIMES) else {}
        rows.append(f"{sif.stem:20} {sif.stat().st_size / 2**30:5.1f} GB  "
                    + "  ".join(f"{k.removeprefix('heimdall.')}={v}" for k, v in held.items() if k.startswith("heimdall.")))
    return rows


def inside() -> dict | None:
    """The image this process runs in (for provenance): its path and labels; None outside one."""
    path = os.environ.get("APPTAINER_CONTAINER") or os.environ.get("SINGULARITY_CONTAINER")
    if not path:
        return None
    try:
        held = json.loads(LABELS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        held = {}
    return {"path": path, "labels": {k: v for k, v in held.items() if k.startswith("heimdall.")}}
