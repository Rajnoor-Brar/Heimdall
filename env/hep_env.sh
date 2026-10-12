#!/bin/bash
# env/hep_env.sh — Heimdall's shell environment (docs/framework/01_Target.md §5.8; docs/06_Internals.md §1).
#
# Sourced by Heimdall's setup.sh (alias `load_hep`), which sets HEP (Heimdall's folder), HEP_MACHINE (the
# machine root, ~/Himinbjorg) and the loaded stack's HEP_INSTALL, HEP_VENV, HEP_APPS and HEP_FORGE. It puts
# the stack and framework/bin (the `hep` command) on PATH, activates the venv, and defines the shell
# helpers below.
# Safe to source repeatedly: path variables are only ever prepended once, and never get empty elements
# (an empty element means the CWD). `quit` removes exactly what was added here.

: "${HEP:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
: "${HEP_MACHINE:=$HOME/Himinbjorg}"
: "${HEP_INSTALL:=$HEP_MACHINE/stack}"
: "${HEP_VENV:=$HEP_MACHINE/venv}"                 # an isolated toolkit's stack has its own (setup.sh)
: "${HEP_APPS:=$HEP_MACHINE/apps}"
: "${HEP_FORGE:=$HEP_MACHINE/forge}"
export HEP HEP_MACHINE HEP_INSTALL HEP_VENV HEP_APPS HEP_FORGE
if [ -n "${HEKIT_ROOT-}" ]; then                 # High-Energy's name for the checkout: retired (K15)
    echo "HEKIT_ROOT is retired: Heimdall uses HEP ($HEP)" >&2
    unset HEKIT_ROOT
fi
# The file that sourced this one (Heimdall's setup.sh), re-sourced by hep_refresh
export HEP_SETUP="${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}"

_HEP_SCALARS="LHAPDF_DATA_PATH ONNXRUNTIME_DIR GEANT4_DATA_DIR"

# _hep_prepend VAR DIR — prepend DIR if it exists and is not already present; record the addition.
_hep_prepend() {
    [ -d "$2" ] || return 0
    case ":${!1-}:" in
        *":$2:"*) ;;
        *)  export "$1=$2${!1:+:${!1}}"
            export _HEP_ADDED="${_HEP_ADDED:+$_HEP_ADDED
}$1=$2" ;;
    esac
}

# _hep_strip VAR DIR — remove every DIR element from VAR; unset VAR when nothing is left.
_hep_strip() {
    local cur=":${!1-}:"
    while [[ $cur == *":$2:"* ]]; do cur=${cur//":$2:"/:}; done
    cur=${cur#:}; cur=${cur%:}
    if [ -n "$cur" ]; then export "$1=$cur"; else unset "$1"; fi
}

# --- routine commands ---
# quit: leave the environment. Removes the path elements added above, restores the scalars, deactivates
# the venv. Stays defined, and is a no-op when the environment is not loaded.
quit() {
    if [ -z "${HEP_ENV_LOADED-}" ]; then
        echo "HEP env not loaded"
        return 0
    fi
    local venv=${VIRTUAL_ENV-} path=$PATH
    if declare -F deactivate >/dev/null; then    # the prompt and PYTHONHOME; but it also puts PATH back as it was
        deactivate                               # at activation, losing what was added since: keep today's
        export PATH=$path
    fi                                           # (a child shell inherits the venv's variables, not deactivate)
    [ -n "$venv" ] && _hep_strip PATH "$venv/bin"
    unset VIRTUAL_ENV VIRTUAL_ENV_PROMPT
    local var dir saved
    while IFS='=' read -r var dir; do
        [ -n "$var" ] && _hep_strip "$var" "$dir"
    done <<< "${_HEP_ADDED-}"
    for var in $_HEP_SCALARS; do
        saved="_HEP_SAVED_$var"
        if [ -n "${!saved-}" ]; then export "$var=${!saved}"; else unset "$var"; fi
        unset "$saved"
    done
    unset HEP_ENV_LOADED _HEP_ADDED HEP_STACK
    hash -r
}
hep_refresh() {
    local setup="${HEP_SETUP:-$HEP/setup.sh}"
    quit >/dev/null
    source "$setup"
}
# hep: the command (framework/bin/hep), except `hep refresh`, which reloads this shell's environment and
# so must run in the shell itself (a program cannot change its parent's variables).
hep() {
    if [ "${1-}" = refresh ]; then
        shift
        [ $# -eq 0 ] || { echo "hep refresh: takes no arguments" >&2; return 2; }
        hep_refresh
    else
        command hep "$@"
    fi
}
# hep_status: the loaded stack's packages, from their recipes (`hep status --stack`).
hep_status() { command hep status --stack "$@"; }

hep_stash()   { cd "$HEP_MACHINE/forge/downloads"; }   # the downloads (stash/ before the machine root)
hep_forge()   { cd "$HEP_FORGE"; }
hep_stack()   { cd "$HEP_INSTALL"; }
# hep_cd PROJECT [configs|modules|results|output] — cd into a project folder of the current work dir.
hep_cd() {
    [ -n "${1-}" ] || { echo "usage: hep_cd PROJECT [configs|modules|results|output]"; return 2; }
    local work
    work=$(hep where --work) || return 2
    cd "$work/${2:-configs}/$1"
}
hep_help() {
    cat << HLP
hep run | plot | watch | build | make   the framework (hep --help)
HEP environment commands:
  hep_status             the loaded stack: each package, its release and state (hep status --stack)
  hep refresh            reload the environment from scratch (also hep_refresh)
  quit                   leave the HEP environment (restores paths, deactivates venv)
  hep_cd PROJECT [DIR]   cd to <work dir>/DIR/PROJECT (DIR: configs|modules|results|output)
  hep_stash              cd to the machine root's downloads
  hep_forge              cd to the machine root's builds in progress
  hep_stack              cd to the stack (the installs)
  hep_help               this message
HLP
}

# Guard against double-sourcing. A child shell inherits the variables but not the functions defined
# above, so it only needs this file for the functions.
if [ -n "${HEP_ENV_LOADED-}" ]; then
    [[ $- == *i* ]] && echo "HEP env already loaded — $HEP (hep_help for commands)"
    return 0
fi

# Activate the Python venv
source "$HEP_VENV/bin/activate"

# The stack's install folders: every shipped recipe's (env/packages.sh, generated from recipes/toolkits/),
# and what this stack's builds made (a machine toolkit's own recipes); only folders that are there count.
source "$HEP/env/packages.sh"
[ -f "$HEP_INSTALL/.stamps/folders" ] && _HEP_PACKAGES="$_HEP_PACKAGES $(< "$HEP_INSTALL/.stamps/folders")"
_hep_pyver=$("$HEP_VENV/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
for pkg in $_HEP_PACKAGES; do
    _hep_prepend PATH              "$HEP_INSTALL/$pkg/bin"
    _hep_prepend LD_LIBRARY_PATH   "$HEP_INSTALL/$pkg/lib"
    _hep_prepend LD_LIBRARY_PATH   "$HEP_INSTALL/$pkg/lib64"
    _hep_prepend PYTHONPATH        "$HEP_INSTALL/$pkg/lib/python$_hep_pyver/site-packages"
    _hep_prepend CMAKE_PREFIX_PATH "$HEP_INSTALL/$pkg"
    _hep_prepend PKG_CONFIG_PATH   "$HEP_INSTALL/$pkg/lib/pkgconfig"
done
# ROOT and Pythia install their Python modules into lib/ (import ROOT, import pythia8)
_hep_prepend PYTHONPATH "$HEP_INSTALL/root/lib"
_hep_prepend PYTHONPATH "$HEP_INSTALL/pythia8/lib"
unset pkg _hep_pyver _HEP_PACKAGES
# framework/bin last, so it sits in front of everything, including the venv's bin/: the `hep` command
# is framework/bin/hep.
_hep_prepend PATH "$HEP/framework/bin"

for _hep_var in $_HEP_SCALARS; do
    export "_HEP_SAVED_$_hep_var=${!_hep_var-}"
done
unset _hep_var
export LHAPDF_DATA_PATH="$HEP_INSTALL/LHAPDF/share/LHAPDF"
# Geant4 11 finds every data set under one directory (what its geant4.sh exports)
[ -d "$HEP_INSTALL/geant4/share/Geant4/data" ] && export GEANT4_DATA_DIR="$HEP_INSTALL/geant4/share/Geant4/data"
export ONNXRUNTIME_DIR="$HEP_INSTALL/onnxruntime"
# RIVET_ANALYSIS_PATH is deliberately not set: the rivet tool sets build/Rivet per run.
export HEP_ENV_LOADED=1
hash -r

[[ $- == *i* ]] && echo "HEP env loaded — $HEP${HEP_STACK:+ (stack: $HEP_STACK)} (hep_status for versions, hep_help for commands)"
return 0
