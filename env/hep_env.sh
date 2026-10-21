#!/bin/bash
# env/hep_env.sh — Heimdall's shell environment (docs/framework/01_Target.md §5.8; docs/06_Internals.md §1).
#
# Sourced by Heimdall's gjallarhorn.sh (the shell function `gjallarhorn`), which sets HEP (Heimdall's folder), HEP_MACHINE (the
# machine root, ~/Himinbjorg) and the loaded stack's HEP_INSTALL, HEP_VENV, HEP_APPS and HEP_FORGE, and
# HEP_BASE when the stack is built on a conda base (docs/conda/). It activates the base (its
# base/activate.sh) or the venv, puts the stack and framework/bin (the `heimdall` command) on PATH, sources the
# machine root's machine.sh, and defines the shell helpers below. The base's lib/ never joins
# LD_LIBRARY_PATH: what was built on it finds it by rpath, and the OS's own programs keep the OS's libraries.
# Safe to source repeatedly: path variables are only ever prepended once, and never get empty elements
# (an empty element means the CWD). `quit` removes exactly what was added here, machine.sh's lines too.

if [ -z "${BASH_VERSION-}" ]; then                # bash only (gjallarhorn.sh says so first; this is for a direct source)
    echo "env/hep_env.sh needs bash: run launch.sh, or bash and then source gjallarhorn.sh" >&2
    return 1 2>/dev/null || exit 1
fi
: "${HEP:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
: "${HEP_MACHINE:=$HOME/Himinbjorg}"
: "${HEP_INSTALL:=$HEP_MACHINE/stack}"
: "${HEP_VENV:=$HEP_MACHINE/venv}"                 # an isolated toolkit's stack has its own (gjallarhorn.sh)
: "${HEP_APPS:=$HEP_MACHINE/apps}"
: "${HEP_FORGE:=$HEP_MACHINE/forge}"
export HEP HEP_MACHINE HEP_INSTALL HEP_VENV HEP_APPS HEP_FORGE
if [ -n "${HEKIT_ROOT-}" ]; then                 # High-Energy's name for the checkout: retired (K15)
    echo "HEKIT_ROOT is retired: Heimdall uses HEP ($HEP)" >&2
    unset HEKIT_ROOT
fi
unset HEP_SETUP                                   # retired: heimdall refresh reloads $HEP/gjallarhorn.sh with $HEP_STACK

_HEP_SCALARS="LHAPDF_DATA_PATH ONNXRUNTIME_DIR GEANT4_DATA_DIR DELPHES_DIR"

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

# _hep_strip_once VAR DIR — remove DIR's first element from VAR (machine.sh may add one that was already
# there: only its own goes); unset VAR when nothing is left.
_hep_strip_once() {
    local cur=":${!1-}:"
    [[ $cur == *":$2:"* ]] || return 0
    cur=${cur/":$2:"/:}
    cur=${cur#:}; cur=${cur%:}
    if [ -n "$cur" ]; then export "$1=$cur"; else unset "$1"; fi
}

# _hep_count LIST ELEM — how many times ELEM is in the :-separated LIST, in _hep_n.
_hep_count() {
    local IFS=: e
    _hep_n=0
    for e in $1; do [ "$e" = "$2" ] && _hep_n=$((_hep_n + 1)); done
    return 0                                     # (a script's set -e: the loop may end on a false test)
}

# _hep_record_path VAR OLD — each element VAR now has more of than OLD had, into _HEP_MACHINE_ADDED.
_hep_record_path() {
    local IFS=: e seen=: now
    for e in ${!1-}; do
        case "$seen" in *":$e:"*) continue ;; esac
        seen="$seen$e:"
        _hep_count "${!1-}" "$e"; now=$_hep_n
        _hep_count "$2" "$e"
        while [ "$now" -gt "$_hep_n" ]; do
            _HEP_MACHINE_ADDED="${_HEP_MACHINE_ADDED:+$_HEP_MACHINE_ADDED
}$1=$e"
            now=$((now - 1))
        done
    done
}

# _hep_source_recorded FILE — source FILE (machine.sh: setup_extra's lines, a `module load` …; the base's
# activate.sh) and record
# what it changed, so quit takes it out again: each element it added to a *PATH* variable, and every
# other exported variable's value before (_HEP_MACHINE_ADDED, _HEP_RESTORE).
_hep_source_recorded() {
    local _hep_names _hep_v _hep_old _hep_q
    _hep_names=$(compgen -e)
    for _hep_v in $_hep_names; do
        printf -v "_hepm_$_hep_v" '%s' "${!_hep_v}"
    done
    source "$1"
    for _hep_v in $(compgen -e); do
        case "$_hep_v" in _HEP_*|HEP_*|PWD|OLDPWD|SHLVL|_) continue ;; esac
        _hep_old="_hepm_$_hep_v"
        if [[ $'\n'"$_hep_names"$'\n' == *$'\n'"$_hep_v"$'\n'* ]]; then
            [ "${!_hep_old}" = "${!_hep_v}" ] && continue
            case "$_hep_v" in
                *PATH*) _hep_record_path "$_hep_v" "${!_hep_old}" ;;
                *)      printf -v _hep_q '%q' "${!_hep_old}"
                        _HEP_RESTORE="${_HEP_RESTORE-}export $_hep_v=$_hep_q"$'\n' ;;
            esac
        else
            case "$_hep_v" in
                *PATH*) _hep_record_path "$_hep_v" "" ;;
                *)      _HEP_RESTORE="${_HEP_RESTORE-}unset $_hep_v"$'\n' ;;
            esac
        fi
    done
    for _hep_v in $_hep_names; do                  # what it unset comes back
        case "$_hep_v" in _HEP_*|HEP_*|PWD|OLDPWD|SHLVL|_) ;; *)
            if [ -z "${!_hep_v+set}" ]; then
                _hep_old="_hepm_$_hep_v"
                printf -v _hep_q '%q' "${!_hep_old}"
                _HEP_RESTORE="${_HEP_RESTORE-}export $_hep_v=$_hep_q"$'\n'
            fi ;;
        esac
        unset "_hepm_$_hep_v"
    done
    export _HEP_MACHINE_ADDED _HEP_RESTORE
}

# _hep_unload: take the environment out (machine.sh's lines, the venv, the path elements, the scalars),
# keeping which stack is asked for. quit and a switch to another stack use it.
_hep_unload() {
    local venv=${VIRTUAL_ENV-} path=$PATH var dir saved
    while IFS='=' read -r var dir; do              # machine.sh's first (it came last): each element once
        [ -n "$var" ] && _hep_strip_once "$var" "$dir"
    done <<< "${_HEP_MACHINE_ADDED-}"
    [ -n "${_HEP_RESTORE-}" ] && eval "$_HEP_RESTORE"
    if declare -F deactivate >/dev/null; then    # the prompt and PYTHONHOME; but it also puts PATH back as it was
        path=$PATH                               # at activation, losing what was added since: keep today's
        deactivate
        export PATH=$path
    fi                                           # (a child shell inherits the venv's variables, not deactivate)
    [ -n "$venv" ] && _hep_strip PATH "$venv/bin"
    unset VIRTUAL_ENV VIRTUAL_ENV_PROMPT
    while IFS='=' read -r var dir; do
        [ -n "$var" ] && _hep_strip "$var" "$dir"
    done <<< "${_HEP_ADDED-}"
    for var in $_HEP_SCALARS; do
        saved="_HEP_SAVED_$var"
        if [ -n "${!saved-}" ]; then export "$var=${!saved}"; else unset "$var"; fi
        unset "$saved"
    done
    unset HEP_ENV_LOADED _HEP_ADDED _HEP_MACHINE_ADDED _HEP_RESTORE
    hash -r
}

# --- routine commands ---
# quit: leave the environment. Everything gjallarhorn.sh and machine.sh added goes; HEP and HEP_MACHINE stay
# (where Heimdall and the machine root are, for `source $HEP/gjallarhorn.sh`). A no-op when not loaded.
quit() {
    if [ -z "${HEP_ENV_LOADED-}" ]; then
        echo "Heimdall's environment is not loaded"
        return 0
    fi
    _hep_unload
    unset HEP_STACK HEP_INSTALL HEP_VENV HEP_BASE HEP_APPS HEP_FORGE
}
# heimdall_refresh: quit, then the same stack again (an isolated toolkit's included), from scratch.
heimdall_refresh() {
    local stack=${HEP_STACK-}
    quit >/dev/null
    export HEP_STACK_REQUEST=$stack
    source "$HEP/gjallarhorn.sh" ""
}
# heimdall: the program (framework/bin/heimdall), except what changes this shell itself, which a program
# cannot: `heimdall refresh`, `heimdall quit` and `heimdall cd`.
heimdall() {
    case "${1-}" in
        refresh|quit)
            [ $# -eq 1 ] || { echo "heimdall $1: takes no arguments" >&2; return 2; }
            if [ "$1" = refresh ]; then heimdall_refresh; else quit; fi ;;
        cd)
            shift
            heimdall_cd "$@" ;;
        *)
            command heimdall "$@" ;;
    esac
}
# heimdall cd PROJECT [configs|modules|results|records|logs] — cd into a project folder of the current work dir.
heimdall_cd() {
    [ -n "${1-}" ] || { echo "usage: heimdall cd PROJECT [configs|modules|results|records|logs]" >&2; return 2; }
    local work
    work=$(command heimdall where --work) || return 2
    cd "$work/${2:-configs}/$1"
}
# heimdall_status: the loaded stack's packages, from their recipes (`heimdall stack status`; kept for a release).
heimdall_status() { command heimdall stack status "$@"; }

heimdall_stash()   { cd "$HEP_MACHINE/forge/downloads"; }   # the downloads (shared by every stack)
heimdall_forge()   { cd "$HEP_FORGE"; }
heimdall_stack()   { cd "$HEP_INSTALL"; }
heimdall_help() {
    cat << HLP
heimdall run | plot | watch | build | stack | …   every command (heimdall help; heimdall help <command>)
In this shell:
  heimdall refresh           reload the environment from scratch, the same stack (also heimdall_refresh)
  heimdall quit              leave it: paths, the base (or venv) and machine.sh's lines as before (also quit)
  heimdall cd PROJECT [DIR]  cd to <work dir>/DIR/PROJECT (DIR: configs|modules|results|records|logs; also heimdall_cd)
  heimdall_status            the loaded stack: each package, its release and state (heimdall stack status)
  heimdall_stash             cd to the machine root's downloads
  heimdall_forge             cd to the loaded stack's builds in progress
  heimdall_stack             cd to the loaded stack (the installs)
  heimdall_help              this message
HLP
}

# Loaded already? HEP_ENV_LOADED names the stack that is (a child shell inherits it, and its paths, but
# not the functions above: it needs this file only for them). Another stack's environment is taken out
# first, so two stacks never share PATH (an isolated toolkit's C++20 beside the C++17 one).
if [ -n "${HEP_ENV_LOADED-}" ]; then
    if [ "$HEP_ENV_LOADED" = "$HEP_INSTALL" ]; then
        [[ $- == *i* ]] && echo "Heimdall's environment already loaded — $HEP${HEP_STACK:+ (stack: $HEP_STACK)} (heimdall_help for commands)"
        return 0
    fi
    _hep_unload
fi

# The base (conda: its compilers, libraries and Python; recorded, so quit takes it out), or the venv
if [ -n "${HEP_BASE-}" ]; then
    _hep_source_recorded "${HEP_BASE%/.pixi/envs/default}/activate.sh"
else
    source "$HEP_VENV/bin/activate"
fi

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
# MadGraph's loop libraries (Ninja, COLLIER, shared): its MadLoop programs link them without a run path
_hep_prepend LD_LIBRARY_PATH "$HEP_INSTALL/madgraph/HEPTools/lib"
unset pkg _hep_pyver _HEP_PACKAGES
# framework/bin last, so it sits in front of everything, including the venv's bin/: the `heimdall` command
# is framework/bin/heimdall.
_hep_prepend PATH "$HEP/framework/bin"

for _hep_var in $_HEP_SCALARS; do
    export "_HEP_SAVED_$_hep_var=${!_hep_var-}"
done
unset _hep_var
# Each where the stack has it, else where a ready-made one is (in the base, from conda-forge)
if [ -d "$HEP_INSTALL/LHAPDF" ] || [ -z "${HEP_BASE-}" ]; then
    export LHAPDF_DATA_PATH="$HEP_INSTALL/LHAPDF/share/LHAPDF"
else
    export LHAPDF_DATA_PATH="$HEP_BASE/share/LHAPDF"
fi
# Geant4 11 finds every data set under one directory (what its geant4.sh exports)
[ -d "$HEP_INSTALL/geant4/share/Geant4/data" ] && export GEANT4_DATA_DIR="$HEP_INSTALL/geant4/share/Geant4/data"
if [ -d "$HEP_INSTALL/onnxruntime" ] || [ -z "${HEP_BASE-}" ]; then
    export ONNXRUNTIME_DIR="$HEP_INSTALL/onnxruntime"
else
    export ONNXRUNTIME_DIR="$HEP_BASE"
fi
[ -n "${HEP_BASE-}" ] && [ ! -d "$HEP_INSTALL/delphes" ] && [ -f "$HEP_BASE/include/classes/DelphesClasses.h" ] \
    && export DELPHES_DIR="$HEP_BASE"
# RIVET_ANALYSIS_PATH is deliberately not set: the rivet tool sets build/Rivet per run.

# This machine's lines (macOS: DYLD_LIBRARY_PATH and the GNU tools; a cluster: module load …), last, and
# recorded, so quit and refresh take them out instead of piling them up.
[ -f "$HEP_MACHINE/machine.sh" ] && _hep_source_recorded "$HEP_MACHINE/machine.sh"
export HEP_ENV_LOADED=$HEP_INSTALL
hash -r

[[ $- == *i* ]] && echo "Heimdall's environment loaded — $HEP${HEP_STACK:+ (stack: $HEP_STACK)} (heimdall_status for versions, heimdall_help for commands)"
return 0
