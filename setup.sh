#!/bin/bash
# setup.sh — Heimdall's environment: source it once per session, in bash. Tracked; it finds its own
# folder, so a clone anywhere works (docs/framework/01_Target.md §5.8).
#
#   source setup.sh                     the default stack, in the machine root ($HEP_MACHINE, ~/Himinbjorg)
#   source <machine>/stacks/<toolkit>/setup.sh    an isolated toolkit's stack (recipes/README.md §6), which
#                                       asks for it through HEP_STACK_REQUEST; the other stack is taken out first
#   launch.sh                           the same from any shell (zsh included): a bash with this loaded
#
# The checkout ($HEP) holds what git has; everything this machine built (the stack, the venv, Heimdall's
# apps, downloads, builds) is in the machine root (docs/audit_3/02_Organisation.md §3).

# bash only: any other shell is turned away here, before anything is changed (docs/audit_3/05_CLI.md §5)
if [ -z "${BASH_VERSION-}" ]; then
    echo "Heimdall's environment needs bash, and this shell is not bash: run launch.sh (beside this setup.sh) from any shell, or start bash and source setup.sh there" >&2
    return 1 2>/dev/null || exit 1
fi

export HEP=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
_hep_default=~/Himinbjorg                                        # (~ is found without $HOME too)
export HEP_MACHINE=${HEP_MACHINE:-$_hep_default}
unset _hep_default
export HEP_STACK=${HEP_STACK_REQUEST-}
unset HEP_STACK_REQUEST
if [ ! -d "$HEP_MACHINE" ]; then
    if [ -e "$HEP/stack" ] || [ -e "$HEP/env/venv" ]; then        # a checkout that still holds its stack
        echo "Heimdall's machine root is now $HEP_MACHINE: this machine's stack is still in $HEP." >&2
        echo "Adopt it once (links and moves only, nothing rebuilt): python3 $HEP/recipes/machine.py adopt" >&2
    else
        echo "no machine root at $HEP_MACHINE: build the stack first (python3 $HEP/recipes/build_stack.py)," >&2
        echo "or set HEP_MACHINE to where it is" >&2
    fi
    return 1 2>/dev/null || exit 1
fi
if [ -n "$HEP_STACK" ]; then
    _hep_base=$HEP_MACHINE/stacks/$HEP_STACK
    if [ ! -d "$_hep_base/stack" ]; then
        echo "no stack '$HEP_STACK' in $HEP_MACHINE/stacks: build it (recipes/README.md §6)" >&2
        unset _hep_base
        return 1 2>/dev/null || exit 1
    fi
else
    unset HEP_STACK
    _hep_base=$HEP_MACHINE
fi
export HEP_INSTALL=$_hep_base/stack HEP_VENV=$_hep_base/venv HEP_APPS=$_hep_base/apps HEP_FORGE=$_hep_base/forge
unset _hep_base
source "$HEP/env/hep_env.sh"                  # the paths, the venv, the helpers; then the machine's machine.sh
return 0 2>/dev/null || true
