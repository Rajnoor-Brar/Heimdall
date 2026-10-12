#!/usr/bin/env bash
# launch.sh — Heimdall's environment from any shell (zsh, fish, bash; Linux and macOS): `load_hep`.
#
#   ~/Github/Heimdall/launch.sh                            an interactive bash with setup.sh loaded (exit leaves it)
#   ~/Github/Heimdall/launch.sh hep run Starter/starter    one command in that environment
#   alias load_hep="$HOME/Github/Heimdall/launch.sh"       in ~/.zshrc or ~/.bashrc
#
# The environment (setup.sh, env/hep_env.sh) is bash. In a bash already, `source setup.sh` loads it into
# that shell itself instead. On macOS this runs Homebrew's bash (the system's is 3.2).

set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
setup=$here/setup.sh
machine=${HEP_MACHINE:-~/Himinbjorg}
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
if [ "$(uname -s)" = Darwin ]; then
    if ! command -v brew >/dev/null; then
        for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$("$b" shellenv)" && break; done
    fi
    command -v brew >/dev/null || { echo "no Homebrew (recipes/platforms/mac/README.md step 2)" >&2; exit 1; }
    eval "$(brew shellenv)"
    bash=$HOMEBREW_PREFIX/bin/bash
    [ -x "$bash" ] || { echo "no Homebrew bash: brew install bash" >&2; exit 1; }
fi

if [ $# -eq 0 ]; then                                         # a shell: your ~/.bashrc, then the stack
    exec "$bash" --rcfile <(printf '[ -f ~/.bashrc ] && source ~/.bashrc\nsource %q\n' "$setup") -i
fi
exec "$bash" -c 'source "$0" >/dev/null && exec "$@"' "$setup" "$@"     # one command
