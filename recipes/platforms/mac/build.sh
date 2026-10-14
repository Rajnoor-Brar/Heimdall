#!/usr/bin/env bash
# recipes/platforms/mac/build.sh — build the HEP stack into the machine root on macOS. build_stack.py lays
# mac.toml (and this folder's file for the base) under every toolkit by itself. Run it after README.md's
# manual steps (Xcode's command-line tools; Homebrew only for base=system).
#
#   bash recipes/platforms/mac/build.sh                       # the core stack into ~/Himinbjorg, on a conda base
#   bash recipes/platforms/mac/build.sh packages=@core-conda  # the core ready-made from conda-forge: minutes
#   bash recipes/platforms/mac/build.sh packages=all cores=8  # every build_stack.py argument passes through
#   bash recipes/platforms/mac/build.sh --dry-run             # the commands as bash; nothing installed or built
#   bash recipes/platforms/mac/build.sh base=system           # the old way: Homebrew's packages and a venv
#   BREW_BUNDLE=0 bash recipes/platforms/mac/build.sh base=system   # … without `brew bundle` (it is installed)
#
# The conda base (the default; docs/conda/): macOS's own Python is too old to run build_stack.py (it
# reads TOML), so this fetches pixi first (recipes/base.toml: its release and sha256) and runs
# build_stack.py with a Python pixi provides; build_stack.py then makes the base with the same pixi.
# Not yet proven by a build on a Mac. base=system: Homebrew's packages (Brewfile) and Python, as before.
# Rerunning resumes: finished packages are stamped and skipped (recipes/README.md).

set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

say() { printf '\033[1m==> %s\033[0m\n' "$*" >&2; }
die() { printf '\033[31merror: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(uname -s)" = Darwin ] || die "this is the macOS build; on Linux run recipes/build_stack.py"
xcode-select -p >/dev/null 2>&1 || die "no Xcode command-line tools: run 'xcode-select --install' (README step 1)"
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = 1 ] && [ "$(uname -m)" != arm64 ]; then
    die "this shell runs under Rosetta (x86_64) on an Apple Silicon Mac: open a native terminal (README step 0)"
fi

# Which base: the command line's, else machine.toml's, else "system" for a machine root made before the
# base (a venv/, no base/), else "conda": as build_stack.py decides it.
machine=${HEP_MACHINE:-$HOME/Himinbjorg}
dry=0 base=""
for a in "$@"; do
    case "$a" in
        -n|--dry-run) dry=1 ;;
        base=*)       base=${a#base=} ;;
        machine=*)    machine=${a#machine=} ;;
    esac
done
machine=${machine/#\~/$HOME}
if [ -z "$base" ] && [ -f "$machine/machine.toml" ]; then
    base=$(sed -n 's/^[[:space:]]*base[[:space:]]*=[[:space:]]*"\([a-z]*\)".*/\1/p' "$machine/machine.toml" | head -n 1)
fi
if [ -z "$base" ]; then
    if [ -d "$machine/venv" ] && [ ! -d "$machine/base" ]; then base=system; else base=conda; fi
fi
export HEP_BUILD_SH=1                                        # build_stack.py's preflight: built through here

if [ "$base" = conda ]; then
    # pixi, as recipes/base.toml pins it; build_stack.py finds it there and makes the base with it
    toml=$HERE/../../base.toml
    target=aarch64-apple-darwin
    [ "$(uname -m)" = arm64 ] || die "the conda base has pixi for Apple Silicon only here: base=system on an Intel Mac"
    release=$(awk '/^\[pixi\]/{f=1; next} /^\[/{f=0} f && /^release/{gsub(/[" ]/, "", $3); print $3}' "$toml")
    sha=$(sed -n "s/^$target[[:space:]]*=[[:space:]]*\"\([0-9a-f]*\)\".*/\1/p" "$toml")
    [ -n "$release" ] && [ -n "$sha" ] || die "recipes/base.toml names no pixi release or sha256 for $target"
    pixi=$machine/forge/pixi/bin/pixi
    if [ ! -x "$pixi" ] || [ "$(cat "$machine/forge/pixi/bin/.release" 2>/dev/null)" != "$release" ]; then
        [ "$dry" = 0 ] || die "a dry run needs pixi, which the first build fetches: run once without --dry-run (or base=system)"
        archive=$machine/forge/downloads/pixi-$release-$target.tar.gz
        mkdir -p "$(dirname "$archive")" "$(dirname "$pixi")"
        if [ ! -s "$archive" ]; then
            say "pixi $release (github.com/prefix-dev/pixi)"
            curl -fL --retry 5 -o "$archive.part" \
                "https://github.com/prefix-dev/pixi/releases/download/v$release/pixi-$target.tar.gz"
            mv "$archive.part" "$archive"
        fi
        echo "$sha  $archive" | shasum -a 256 -c - >/dev/null \
            || { rm -f "$archive"; die "$archive: not the archive recipes/base.toml names (its sha256 differs)"; }
        tar -xzf "$archive" -O pixi > "$pixi"
        chmod +x "$pixi"
        echo "$release" > "$machine/forge/pixi/bin/.release"
    fi
    export PIXI_HOME=$machine/forge/pixi PIXI_CACHE_DIR=$machine/forge/downloads/conda RATTLER_CACHE_DIR=$machine/forge/downloads/conda
    exec "$pixi" exec --spec "python=3.12" -- python "$HERE/../../build_stack.py" "$@"
fi

# base=system: Homebrew, on PATH even when the shell's profile does not set it up yet
if ! command -v brew >/dev/null; then
    for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && break; done
fi
command -v brew >/dev/null || die "no Homebrew: install it from https://brew.sh (README step 2)"
eval "$(brew shellenv)"                                       # HOMEBREW_PREFIX, which system.toml uses
say "Homebrew in $HOMEBREW_PREFIX ($(uname -m))"

if [ "$dry" = 1 ]; then                                       # a dry run installs nothing: it only says
    brew bundle check --file "$HERE/Brewfile" >&2 || say "the Brewfile is not all installed (a real run installs it)"
elif [ "${BREW_BUNDLE:-1}" != 0 ]; then
    say "Homebrew packages (Brewfile)"
    brew bundle --file "$HERE/Brewfile"
fi

# GNU make, sed and coreutils ahead of Apple's, as setup.sh has them later
for g in make gnu-sed coreutils; do PATH="$HOMEBREW_PREFIX/opt/$g/libexec/gnubin:$PATH"; done
export PATH

# A Python with tomllib (3.11+): Homebrew's. It runs build_stack.py and the venv is made from it.
PY=""
for v in 3.13 3.12 3.11; do
    [ -x "$HOMEBREW_PREFIX/bin/python$v" ] && { PY="$HOMEBREW_PREFIX/bin/python$v"; break; }
done
[ -n "$PY" ] || die "no Homebrew Python 3.11+: brew install python@3.13"

exec "$PY" "$HERE/../../build_stack.py" python="$PY" "$@"
