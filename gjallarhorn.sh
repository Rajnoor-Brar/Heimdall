#!/bin/bash
# gjallarhorn.sh — Heimdall's environment: source it once per session, in bash. Tracked; it finds its own
# folder, so a clone anywhere works (docs/framework/01_Target.md §5.8).
#
#   source gjallarhorn.sh               the default stack, in the machine root ($HEIMDALL_MACHINE, ~/Himinbjorg)
#   source gjallarhorn.sh <title>       and then cd to the work dir recorded under that title (heimdall
#                                       recognise); `gjallarhorn [title]`, the shell function Heimdall's
#                                       build writes into ~/.bashrc and ~/.zshrc, is this (bifrost --shell)
#   source <machine>/stacks/<toolkit>/gjallarhorn.sh
#                                       an isolated toolkit's stack (recipes/README.md §6), which asks for it
#                                       through HEIMDALL_STACK_REQUEST; the other stack is taken out first
#   launch.sh                           the same from any shell (zsh included): a bash with this loaded
#
# The checkout ($HEIMDALL) holds what git has; everything this machine built (the base or the venv, the stack,
# Heimdall's apps, downloads, builds) is in the machine root (docs/audit_3/02_Organisation.md §3).

# bash only: any other shell is turned away here, before anything is changed (docs/audit_3/05_CLI.md §5)
if [ -z "${BASH_VERSION-}" ]; then
    echo "Heimdall's environment needs bash, and this shell is not bash: run launch.sh (beside this gjallarhorn.sh) from any shell, or start bash and source gjallarhorn.sh there" >&2
    return 1 2>/dev/null || exit 1
fi

export HEIMDALL=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
_heimdall_default=~/Himinbjorg                                        # (~ is found without $HOME too)
export HEIMDALL_MACHINE=${HEIMDALL_MACHINE:-$_heimdall_default}
unset _heimdall_default
export HEIMDALL_STACK=${HEIMDALL_STACK_REQUEST-}
unset HEIMDALL_STACK_REQUEST
if [ ! -d "$HEIMDALL_MACHINE" ]; then
    if [ -e "$HEIMDALL/stack" ] || [ -e "$HEIMDALL/env/venv" ]; then        # a checkout that still holds its stack
        echo "Heimdall's machine root is now $HEIMDALL_MACHINE: this machine's stack is still in $HEIMDALL." >&2
        echo "Adopt it once (links and moves only, nothing rebuilt): python3 $HEIMDALL/recipes/machine.py adopt" >&2
    else
        echo "no machine root at $HEIMDALL_MACHINE: build the stack first (python3 $HEIMDALL/recipes/build_stack.py)," >&2
        echo "or set HEIMDALL_MACHINE to where it is" >&2
    fi
    return 1 2>/dev/null || exit 1
fi
if [ -n "$HEIMDALL_STACK" ]; then
    _heimdall_base=$HEIMDALL_MACHINE/stacks/$HEIMDALL_STACK
    if [ ! -d "$_heimdall_base/stack" ]; then
        echo "no stack '$HEIMDALL_STACK' in $HEIMDALL_MACHINE/stacks: build it (recipes/README.md §6)" >&2
        unset _heimdall_base
        return 1 2>/dev/null || exit 1
    fi
else
    unset HEIMDALL_STACK
    _heimdall_base=$HEIMDALL_MACHINE
fi
export HEIMDALL_INSTALL=$_heimdall_base/stack HEIMDALL_APPS=$_heimdall_base/apps HEIMDALL_FORGE=$_heimdall_base/forge
if [ -f "$_heimdall_base/base/activate.sh" ]; then        # a conda base (docs/conda/): it is the Python environment too
    export HEIMDALL_BASE=$_heimdall_base/base/.pixi/envs/default
    export HEIMDALL_VENV=$HEIMDALL_BASE
else                                                 # base = "system": a venv
    unset HEIMDALL_BASE
    export HEIMDALL_VENV=$_heimdall_base/venv
fi
unset _heimdall_base
source "$HEIMDALL/env/heimdall_env.sh"                  # the base (or venv), the paths, the helpers; then machine.sh
# A title: go to the work dir recorded under it (an unknown one is said, and the environment stays loaded)
if [ -n "${1-}" ]; then
    _heimdall_where=$(command heimdall recognise --path "$1") && cd "$_heimdall_where" || {
        unset _heimdall_where; return 1 2>/dev/null || exit 1; }
    unset _heimdall_where
fi
return 0 2>/dev/null || true
