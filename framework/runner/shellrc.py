"""Heimdall in the user's shell: the block it keeps in ~/.bashrc and ~/.zshrc (rank 0).

The block defines `gjallarhorn`, which loads Heimdall's environment (gjallarhorn.sh) and, given a title, goes
to that work dir (`heimdall recognise` records them in <Himinbjorg>/workdirs.toml), and `bifrost`, the
environment's packages (framework/bin/bifrost), reachable before the environment is loaded. In bash,
gjallarhorn sources gjallarhorn.sh into the shell itself; in zsh, which cannot hold the environment (it is
bash), it opens launch.sh's bash. The block sits between two marker lines: written again in place, taken out
whole, the rest of the file left as it was. recipes/build_stack.py writes it at the end of a build (unless
shell_rc = false) and loads this file by its path, so it uses the standard library only; `bifrost --shell
install|remove` writes or removes it.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

BEGIN = "# >>> Heimdall >>>"
END = "# <<< Heimdall <<<"
DEFAULT_MACHINE = "~/Himinbjorg"
#: The titles' headers in workdirs.toml (["<title>"]), for the shells' completion.
TITLES = r"""sed -n 's/^\["\(.*\)"\]$/\1/p'"""


def block(shell: str, heimdall: Path, machine: Path) -> str:
    """The block for `shell` ("bash" or "zsh"): `gjallarhorn` and `bifrost` for the checkout `heimdall` and the
    Himinbjorg `machine` (named in it only when it is not the default)."""
    machine = Path(machine).expanduser().resolve()
    own = machine != Path(DEFAULT_MACHINE).expanduser().resolve()
    registry = shlex.quote(str(machine / "workdirs.toml"))
    lines = [BEGIN,
             "# Written by Heimdall (bifrost --shell install; --shell remove takes it out). `gjallarhorn` loads",
             "# Heimdall's environment; `gjallarhorn <title>` also goes to that work dir (heimdall recognise --list",
             "# shows them). `bifrost` adds packages to the environment (bifrost --help)."]
    bifrost = shlex.quote(str(heimdall / "framework" / "bin" / "bifrost"))
    if shell == "bash":
        export = f"export HEIMDALL_MACHINE={shlex.quote(str(machine))}; " if own else ""
        env = f"HEIMDALL_MACHINE={shlex.quote(str(machine))} " if own else ""
        launch = shlex.quote(str(heimdall / "launch.sh"))
        lines += [f"gjallarhorn() {{ if [ \"${{1-}}\" = --image ]; then {env}{launch} --gjallarhorn \"$@\"; "
                  f"else {export}source {shlex.quote(str(heimdall / 'gjallarhorn.sh'))} \"$@\"; fi; }}",
                  f"_gjallarhorn_titles() {{ {TITLES} {registry} 2>/dev/null; }}",
                  "complete -W '$(_gjallarhorn_titles)' gjallarhorn",
                  f"bifrost() {{ {env}{bifrost} \"$@\"; }}"]
    elif shell == "zsh":
        env = f"HEIMDALL_MACHINE={shlex.quote(str(machine))} " if own else ""
        lines += [f"gjallarhorn() {{ {env}{shlex.quote(str(heimdall / 'launch.sh'))} --gjallarhorn \"$@\"; }}",
                  f"_gjallarhorn() {{ compadd -- ${{(f)\"$({TITLES} {registry} 2>/dev/null)\"}}; }}",
                  "(( $+functions[compdef] )) && compdef _gjallarhorn gjallarhorn",
                  f"bifrost() {{ {env}{bifrost} \"$@\"; }}"]
    else:
        raise ValueError(f"no block for the shell {shell!r}")
    return "\n".join([*lines, END]) + "\n"


def rc_files(home: Path, login_shell: str) -> list[tuple[str, Path]]:
    """Which files get the block: ~/.bashrc when the login shell is bash or the file is there, ~/.zshrc when
    it is zsh or that file is there."""
    name = Path(login_shell or "").name
    return [(shell, file) for shell, file in (("bash", home / ".bashrc"), ("zsh", home / ".zshrc"))
            if name == shell or file.exists()]


def current(text: str) -> str | None:
    """The block in a file's text, its marker lines included; None when there is none."""
    start = text.find(BEGIN)
    if start < 0 or (start and text[start - 1] != "\n"):
        return None
    end = text.find(END, start)
    if end < 0:
        return None
    end += len(END)
    return text[start:end + 1] if text[end:end + 1] == "\n" else text[start:end]


def _write(rc: Path, text: str) -> None:
    """The file written whole, in place of the old (a symlinked rc keeps its link: its target is written)."""
    target = rc.resolve() if rc.is_symlink() else rc
    mode = target.stat().st_mode & 0o777 if target.exists() else 0o644
    temporary = target.with_name(f".{target.name}.heimdall")
    temporary.write_text(text, encoding="utf-8")
    os.chmod(temporary, mode)
    temporary.replace(target)


def status(rc: Path, text: str) -> str:
    """"installed" (this block), "another" (a block for another checkout or Himinbjorg) or "absent"."""
    found = current(rc.read_text(encoding="utf-8")) if rc.is_file() else None
    return "absent" if found is None else "installed" if found == text else "another"


def install(rc: Path, text: str, replace: bool = True) -> str:
    """Put the block into `rc`: "written" (it had none), "replaced", "unchanged", or "another" (a different
    block left in place, with replace=False)."""
    old = rc.read_text(encoding="utf-8") if rc.is_file() else ""
    found = current(old)
    if found == text:
        return "unchanged"
    if found is not None and not replace:
        return "another"
    if found is None:
        new = old + ("\n" if old and not old.endswith("\n") else "") + ("\n" if old.strip() else "") + text
    else:
        new = old.replace(found, text, 1)
    _write(rc, new)
    return "written" if found is None else "replaced"


def remove(rc: Path) -> bool:
    """Take the block out of `rc`, with the blank line put before it; False when it had none."""
    old = rc.read_text(encoding="utf-8") if rc.is_file() else ""
    found = current(old)
    if found is None:
        return False
    start = old.index(found)
    before = old[:start]
    if before.endswith("\n\n"):
        before = before[:-1]
    _write(rc, before + old[start + len(found):])
    return True
