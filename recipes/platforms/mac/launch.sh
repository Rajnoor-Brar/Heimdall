#!/usr/bin/env bash
# recipes/platforms/mac/launch.sh — Heimdall's environment on macOS, from any shell (zsh included):
#
#   recipes/platforms/mac/launch.sh                       # an interactive bash with Heimdall's setup.sh loaded
#   recipes/platforms/mac/launch.sh hep run Starter/starter   # one command in that environment
#
# The environment (env/hep_env.sh) is bash, and macOS's own bash is 3.2: this runs Homebrew's.
# Heimdall is the folder this script sits in, three levels up.

set -euo pipefail
prefix=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
setup=$prefix/setup.sh
machine=${HEP_MACHINE:-$HOME/Himinbjorg}
if [ ! -d "$machine/stack" ]; then
    if [ -e "$prefix/stack" ]; then                                # a checkout that still holds its stack
        echo "the stack is still in $prefix: adopt it into $machine once (nothing rebuilt):" >&2
        echo "  python3 $prefix/recipes/machine.py adopt" >&2
    else
        echo "no stack in $machine: build it first (bash recipes/platforms/mac/build.sh)" >&2
    fi
    exit 1
fi

if ! command -v brew >/dev/null; then
    for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && break; done
fi
command -v brew >/dev/null || { echo "no Homebrew (README step 2)" >&2; exit 1; }
eval "$(brew shellenv)"
bash5=$HOMEBREW_PREFIX/bin/bash
[ -x "$bash5" ] || { echo "no Homebrew bash: brew install bash" >&2; exit 1; }

if [ $# -eq 0 ]; then                                         # a shell: your ~/.bashrc, then the stack
    exec "$bash5" --rcfile <(printf '[ -f ~/.bashrc ] && source ~/.bashrc\nsource %q\nhep_status\n' "$setup") -i
fi
exec "$bash5" -c 'source "$0" && exec "$@"' "$setup" "$@"     # one command
