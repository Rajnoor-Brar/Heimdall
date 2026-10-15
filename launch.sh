#!/usr/bin/env bash
# launch.sh — Heimdall's environment from any shell (zsh, fish, bash; Linux and macOS): `gjallarhorn`.
#
#   ~/Github/Heimdall/launch.sh                              an interactive bash with gjallarhorn.sh loaded
#   ~/Github/Heimdall/launch.sh --gjallarhorn [title]        the same, in the work dir of that title (zsh's
#                                                            gjallarhorn, which Heimdall writes into ~/.zshrc)
#   ~/Github/Heimdall/launch.sh heimdall run Starter/starter one command in that environment
#   ~/Github/Heimdall/launch.sh --image <name> [--dev] [--gjallarhorn [title] | command…]
#                                                            the same in an Apptainer image (heimdall image)
#
# The environment (gjallarhorn.sh, env/hep_env.sh) is bash. In a bash already, `source gjallarhorn.sh` loads
# it into that shell itself instead. On macOS this runs the base's bash, or Homebrew's (the system's is 3.2).

set -euo pipefail
shell=0 image="" dev=0 title=""
while [ $# -gt 0 ]; do
    case "$1" in
        --gjallarhorn) shell=1; shift ;;
        --image) [ $# -ge 2 ] || { echo "--image takes an image: a name of <machine root>/images, or a .sif" >&2; exit 2; }
                 image=$2; shift 2 ;;
        --dev)   dev=1; shift ;;
        *)       break ;;
    esac
done
if [ "$shell" = 1 ]; then
    [ $# -le 1 ] || { echo "gjallarhorn takes one work dir's title (heimdall recognise --list)" >&2; exit 2; }
    title=${1-}
    set --
fi
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
setup=$here/gjallarhorn.sh
machine=${HEP_MACHINE:-~/Himinbjorg}

# An Apptainer image (V150): its Heimdall and stack, the work dir bound at its own path; a clean environment,
# so this shell's paths never reach it. --dev binds this checkout over the image's /opt/heimdall.
if [ -n "$image" ]; then
    runtime=$(command -v apptainer || command -v singularity) || {
        echo "no apptainer (or singularity) on PATH: the system's (apt install apptainer; module load apptainer)" >&2; exit 127; }
    case "$image" in */*|*.sif) sif=$image ;; *) sif=$machine/images/$image.sif ;; esac
    [ -f "$sif" ] || { echo "no image $sif (heimdall image lists them; heimdall image build makes one)" >&2; exit 1; }
    where=$PWD
    if [ -n "$title" ]; then where=$("$here/framework/bin/heimdall" recognise --path "$title") || exit 1; fi
    binds=(--bind "$where")
    [ "$dev" = 1 ] && binds+=(--bind "$here:/opt/heimdall")
    exec "$runtime" exec --cleanenv "${binds[@]}" --pwd "$where" "$sif" /opt/heimdall/launch.sh "$@"
fi
if [ ! -d "$machine/stack" ]; then
    if [ -e "$here/stack" ] || [ -e "$here/env/venv" ]; then     # a checkout that still holds its stack
        echo "the stack is still in $here: adopt it into $machine once (nothing rebuilt):" >&2
        echo "  python3 $here/recipes/machine.py adopt" >&2
    elif [ "$(uname -s)" = Darwin ]; then
        echo "no stack in $machine: build it first (bash $here/recipes/platforms/mac/build.sh)" >&2
    else
        echo "no stack in $machine: build it first (python3 $here/recipes/build_stack.py)" >&2
    fi
    exit 1
fi

bash=$(command -v bash)
if [ "$(uname -s)" = Darwin ]; then                           # macOS's own bash is 3.2: the base's, else Homebrew's
    bash=$machine/base/.pixi/envs/default/bin/bash
    if [ ! -x "$bash" ]; then
        if ! command -v brew >/dev/null; then
            for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && break; done
        fi
        command -v brew >/dev/null || { echo "no bash 4 or newer: no base in $machine, and no Homebrew (recipes/platforms/mac/README.md)" >&2; exit 1; }
        eval "$(brew shellenv)"
        bash=$HOMEBREW_PREFIX/bin/bash
        [ -x "$bash" ] || { echo "no Homebrew bash: brew install bash" >&2; exit 1; }
    fi
fi

if [ $# -eq 0 ]; then                                         # a shell: your ~/.bashrc, then the stack
    exec "$bash" --rcfile <(printf '[ -f ~/.bashrc ] && source ~/.bashrc\nsource %q %q\n' "$setup" "$title") -i
fi
# one command; "" so that the command's own words are not taken for a work dir's title
exec "$bash" -c 'source "$0" "" >/dev/null && exec "$@"' "$setup" "$@"
