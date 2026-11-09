#!/bin/bash
# env/heimdall_env.sh — Heimdall's shell environment (doc:layout; doc:layout).
#
# Sourced by Heimdall's gjallarhorn.sh (the shell function `gjallarhorn`), which sets HEIMDALL (Heimdall's folder), HEIMDALL_MACHINE (the
# Himinbjorg, ~/Himinbjorg) and the loaded stack's HEIMDALL_INSTALL, HEIMDALL_VENV, HEIMDALL_APPS and HEIMDALL_FORGE, and
# HEIMDALL_BASE when the stack is built on a conda base (doc:base). It activates the base (its
# base/activate.sh) or the venv, puts the stack and framework/bin (the `heimdall` command) on PATH, sources the
# Himinbjorg's machine.sh, and defines the shell helpers below. The base's lib/ never joins
# LD_LIBRARY_PATH: what was built on it finds it by rpath, and the OS's own programs keep the OS's libraries.
# Safe to source repeatedly: path variables are only ever prepended once, and never get empty elements
# (an empty element means the CWD). `quit` removes exactly what was added here, machine.sh's lines too.

if [ -z "${BASH_VERSION-}" ]; then                # bash only (gjallarhorn.sh says so first; this is for a direct source)
    echo "env/heimdall_env.sh needs bash: run launch.sh, or bash and then source gjallarhorn.sh" >&2
    return 1 2>/dev/null || exit 1
fi
: "${HEIMDALL:=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
: "${HEIMDALL_MACHINE:=$HOME/Himinbjorg}"
: "${HEIMDALL_INSTALL:=$HEIMDALL_MACHINE/stack}"
: "${HEIMDALL_VENV:=$HEIMDALL_MACHINE/venv}"                 # an isolated toolkit's stack has its own (gjallarhorn.sh)
: "${HEIMDALL_APPS:=$HEIMDALL_MACHINE/apps}"
: "${HEIMDALL_FORGE:=$HEIMDALL_MACHINE/forge}"
export HEIMDALL HEIMDALL_MACHINE HEIMDALL_INSTALL HEIMDALL_VENV HEIMDALL_APPS HEIMDALL_FORGE
if [ -n "${HEKIT_ROOT-}" ]; then                 # High-Energy's name for the checkout: retired (K15)
    echo "HEKIT_ROOT is retired: Heimdall uses HEIMDALL ($HEIMDALL)" >&2
    unset HEKIT_ROOT
fi
unset HEP_SETUP                                   # retired: heimdall refresh reloads $HEIMDALL/gjallarhorn.sh with $HEIMDALL_STACK
# Heimdall's names before they moved: a shell loaded with them is left with today's alone
unset HEP HEP_MACHINE HEP_INSTALL HEP_BASE HEP_STACK HEP_STACK_REQUEST HEP_VENV HEP_APPS HEP_FORGE HEP_WORK HEP_CONFIGS \
      HEP_RESULTS HEP_RECORDS HEP_CACHE HEP_REPORTS HEP_RUNS HEP_WORKDIRS HEP_ENV_LOADED HEP_CONTEXT HEP_STATUS_FD \
      HEP_MAKELIBS_JOBS HEP_DETACH HEP_CLUSTER_JOB HEP_BUILD_SH HEP_PLAIN

_HEIMDALL_SCALARS="LHAPDF_DATA_PATH ONNXRUNTIME_DIR GEANT4_DATA_DIR DELPHES_DIR"

# _heimdall_prepend VAR DIR — prepend DIR if it exists and is not already present; record the addition.
_heimdall_prepend() {
    [ -d "$2" ] || return 0
    case ":${!1-}:" in
        *":$2:"*) ;;
        *)  export "$1=$2${!1:+:${!1}}"
            export _HEIMDALL_ADDED="${_HEIMDALL_ADDED:+$_HEIMDALL_ADDED
}$1=$2" ;;
    esac
}

# _heimdall_strip VAR DIR — remove every DIR element from VAR; unset VAR when nothing is left.
_heimdall_strip() {
    local cur=":${!1-}:"
    while [[ $cur == *":$2:"* ]]; do cur=${cur//":$2:"/:}; done
    cur=${cur#:}; cur=${cur%:}
    if [ -n "$cur" ]; then export "$1=$cur"; else unset "$1"; fi
}

# _heimdall_strip_once VAR DIR — remove DIR's first element from VAR (machine.sh may add one that was already
# there: only its own goes); unset VAR when nothing is left.
_heimdall_strip_once() {
    local cur=":${!1-}:"
    [[ $cur == *":$2:"* ]] || return 0
    cur=${cur/":$2:"/:}
    cur=${cur#:}; cur=${cur%:}
    if [ -n "$cur" ]; then export "$1=$cur"; else unset "$1"; fi
}

# _heimdall_count LIST ELEM — how many times ELEM is in the :-separated LIST, in _heimdall_n.
_heimdall_count() {
    local IFS=: e
    _heimdall_n=0
    for e in $1; do [ "$e" = "$2" ] && _heimdall_n=$((_heimdall_n + 1)); done
    return 0                                     # (a script's set -e: the loop may end on a false test)
}

# _heimdall_record_path VAR OLD — each element VAR now has more of than OLD had, into _HEIMDALL_MACHINE_ADDED.
_heimdall_record_path() {
    local IFS=: e seen=: now
    for e in ${!1-}; do
        case "$seen" in *":$e:"*) continue ;; esac
        seen="$seen$e:"
        _heimdall_count "${!1-}" "$e"; now=$_heimdall_n
        _heimdall_count "$2" "$e"
        while [ "$now" -gt "$_heimdall_n" ]; do
            _HEIMDALL_MACHINE_ADDED="${_HEIMDALL_MACHINE_ADDED:+$_HEIMDALL_MACHINE_ADDED
}$1=$e"
            now=$((now - 1))
        done
    done
}

# _heimdall_source_recorded FILE — source FILE (machine.sh: setup_extra's lines, a `module load` …; the base's
# activate.sh) and record
# what it changed, so quit takes it out again: each element it added to a *PATH* variable, and every
# other exported variable's value before (_HEIMDALL_MACHINE_ADDED, _HEIMDALL_RESTORE).
_heimdall_source_recorded() {
    local _heimdall_names _heimdall_v _heimdall_old _heimdall_q
    _heimdall_names=$(compgen -e)
    for _heimdall_v in $_heimdall_names; do
        printf -v "_heimdallm_$_heimdall_v" '%s' "${!_heimdall_v}"
    done
    source "$1"
    for _heimdall_v in $(compgen -e); do
        case "$_heimdall_v" in _HEIMDALL_*|HEIMDALL_*|PWD|OLDPWD|SHLVL|_) continue ;; esac
        _heimdall_old="_heimdallm_$_heimdall_v"
        if [[ $'\n'"$_heimdall_names"$'\n' == *$'\n'"$_heimdall_v"$'\n'* ]]; then
            [ "${!_heimdall_old}" = "${!_heimdall_v}" ] && continue
            case "$_heimdall_v" in
                *PATH*) _heimdall_record_path "$_heimdall_v" "${!_heimdall_old}" ;;
                *)      printf -v _heimdall_q '%q' "${!_heimdall_old}"
                        _HEIMDALL_RESTORE="${_HEIMDALL_RESTORE-}export $_heimdall_v=$_heimdall_q"$'\n' ;;
            esac
        else
            case "$_heimdall_v" in
                *PATH*) _heimdall_record_path "$_heimdall_v" "" ;;
                *)      _HEIMDALL_RESTORE="${_HEIMDALL_RESTORE-}unset $_heimdall_v"$'\n' ;;
            esac
        fi
    done
    for _heimdall_v in $_heimdall_names; do                  # what it unset comes back
        case "$_heimdall_v" in _HEIMDALL_*|HEIMDALL_*|PWD|OLDPWD|SHLVL|_) ;; *)
            if [ -z "${!_heimdall_v+set}" ]; then
                _heimdall_old="_heimdallm_$_heimdall_v"
                printf -v _heimdall_q '%q' "${!_heimdall_old}"
                _HEIMDALL_RESTORE="${_HEIMDALL_RESTORE-}export $_heimdall_v=$_heimdall_q"$'\n'
            fi ;;
        esac
        unset "_heimdallm_$_heimdall_v"
    done
    export _HEIMDALL_MACHINE_ADDED _HEIMDALL_RESTORE
}

# _heimdall_unload: take the environment out (machine.sh's lines, the venv, the path elements, the scalars),
# keeping which stack is asked for. quit and a switch to another stack use it.
_heimdall_unload() {
    local venv=${VIRTUAL_ENV-} path=$PATH var dir saved
    while IFS='=' read -r var dir; do              # machine.sh's first (it came last): each element once
        [ -n "$var" ] && _heimdall_strip_once "$var" "$dir"
    done <<< "${_HEIMDALL_MACHINE_ADDED-}"
    [ -n "${_HEIMDALL_RESTORE-}" ] && eval "$_HEIMDALL_RESTORE"
    if declare -F deactivate >/dev/null; then    # the prompt and PYTHONHOME; but it also puts PATH back as it was
        path=$PATH                               # at activation, losing what was added since: keep today's
        deactivate
        export PATH=$path
    fi                                           # (a child shell inherits the venv's variables, not deactivate)
    [ -n "$venv" ] && _heimdall_strip PATH "$venv/bin"
    unset VIRTUAL_ENV VIRTUAL_ENV_PROMPT
    while IFS='=' read -r var dir; do
        [ -n "$var" ] && _heimdall_strip "$var" "$dir"
    done <<< "${_HEIMDALL_ADDED-}"
    for var in $_HEIMDALL_SCALARS; do
        saved="_HEIMDALL_SAVED_$var"
        if [ -n "${!saved-}" ]; then export "$var=${!saved}"; else unset "$var"; fi
        unset "$saved"
    done
    unset HEIMDALL_ENV_LOADED _HEIMDALL_ADDED _HEIMDALL_MACHINE_ADDED _HEIMDALL_RESTORE
    hash -r
}

# --- routine commands ---
# quit: leave the environment. Everything gjallarhorn.sh and machine.sh added goes; HEIMDALL and HEIMDALL_MACHINE stay
# (where Heimdall and Himinbjorg are, for `source $HEIMDALL/gjallarhorn.sh`). A no-op when not loaded.
quit() {
    if [ -z "${HEIMDALL_ENV_LOADED-}" ]; then
        echo "Heimdall's environment is not loaded"
        return 0
    fi
    _heimdall_unload
    complete -r heimdall 2>/dev/null
    unset HEIMDALL_STACK HEIMDALL_INSTALL HEIMDALL_VENV HEIMDALL_BASE HEIMDALL_APPS HEIMDALL_FORGE
}
# heimdall_refresh: quit, then the same stack again (an isolated toolkit's included), from scratch.
heimdall_refresh() {
    local stack=${HEIMDALL_STACK-}
    quit >/dev/null
    export HEIMDALL_STACK_REQUEST=$stack
    source "$HEIMDALL/gjallarhorn.sh" ""
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
# heimdall cd ASSIGNMENT [configs|modules|results|records|logs] — cd into an assignment's folder of the current work dir.
heimdall_cd() {
    [ -n "${1-}" ] || { echo "usage: heimdall cd ASSIGNMENT [configs|modules|results|records|logs]" >&2; return 2; }
    local work
    work=$(command heimdall where --work) || return 2
    cd "$work/${2:-configs}/$1"
}
# TAB completion for `heimdall` (env/complete.bash), here and not after the early return below: `complete` specs are not inherited.
[ -r "$HEIMDALL/env/complete.bash" ] && source "$HEIMDALL/env/complete.bash"
# heimdall_status: the loaded stack's packages, from their recipes (`heimdall stack status`; kept for a release).
heimdall_status() { command heimdall stack status "$@"; }

heimdall_stash()   { cd "$HEIMDALL_MACHINE/forge/downloads"; }   # the downloads (shared by every stack)
heimdall_forge()   { cd "$HEIMDALL_FORGE"; }
heimdall_stack()   { cd "$HEIMDALL_INSTALL"; }
heimdall_help() {
    cat << HLP
heimdall run | plot | watch | build | stack | …   every command (heimdall help; heimdall help <command>)
In this shell:
  heimdall refresh           reload the environment from scratch, the same stack (also heimdall_refresh)
  heimdall quit              leave it: paths, the base (or venv) and machine.sh's lines as before (also quit)
  heimdall cd A [DIR]        cd to <work dir>/DIR/A, an assignment's (DIR: configs|modules|results|records|logs; also heimdall_cd)
  heimdall_status            the loaded stack: each package, its release and state (heimdall stack status)
  heimdall_stash             cd to Himinbjorg's downloads
  heimdall_forge             cd to the loaded stack's builds in progress
  heimdall_stack             cd to the loaded stack (the installs)
  heimdall_help              this message
HLP
}

# Loaded already? HEIMDALL_ENV_LOADED names the stack that is (a child shell inherits it, and its paths, but
# not the functions above: it needs this file only for them). Another stack's environment is taken out
# first, so two stacks never share PATH (an isolated toolkit's C++20 beside the C++17 one).
if [ -n "${HEIMDALL_ENV_LOADED-}" ]; then
    if [ "$HEIMDALL_ENV_LOADED" = "$HEIMDALL_INSTALL" ]; then
        [[ $- == *i* ]] && echo "Heimdall's environment already loaded — $HEIMDALL${HEIMDALL_STACK:+ (stack: $HEIMDALL_STACK)} (heimdall_help for commands)"
        return 0
    fi
    _heimdall_unload
fi

# The base (conda: its compilers, libraries and Python; recorded, so quit takes it out), or the venv
if [ -n "${HEIMDALL_BASE-}" ]; then
    _heimdall_source_recorded "${HEIMDALL_BASE%/.pixi/envs/default}/activate.sh"
else
    source "$HEIMDALL_VENV/bin/activate"
fi

# The stack's install folders: every shipped recipe's (env/packages.sh, generated from recipes/toolkits/),
# and what this stack's builds made (a machine toolkit's own recipes); only folders that are there count.
source "$HEIMDALL/env/packages.sh"
[ -f "$HEIMDALL_INSTALL/.stamps/folders" ] && _HEIMDALL_PACKAGES="$_HEIMDALL_PACKAGES $(< "$HEIMDALL_INSTALL/.stamps/folders")"
_heimdall_pyver=$("$HEIMDALL_VENV/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
for pkg in $_HEIMDALL_PACKAGES; do
    _heimdall_prepend PATH              "$HEIMDALL_INSTALL/$pkg/bin"
    _heimdall_prepend LD_LIBRARY_PATH   "$HEIMDALL_INSTALL/$pkg/lib"
    _heimdall_prepend LD_LIBRARY_PATH   "$HEIMDALL_INSTALL/$pkg/lib64"
    _heimdall_prepend PYTHONPATH        "$HEIMDALL_INSTALL/$pkg/lib/python$_heimdall_pyver/site-packages"
    _heimdall_prepend CMAKE_PREFIX_PATH "$HEIMDALL_INSTALL/$pkg"
    _heimdall_prepend PKG_CONFIG_PATH   "$HEIMDALL_INSTALL/$pkg/lib/pkgconfig"
done
# ROOT and Pythia install their Python modules into lib/ (import ROOT, import pythia8)
_heimdall_prepend PYTHONPATH "$HEIMDALL_INSTALL/root/lib"
_heimdall_prepend PYTHONPATH "$HEIMDALL_INSTALL/pythia8/lib"
# MadGraph's loop libraries (Ninja, COLLIER, shared): its MadLoop programs link them without a run path
_heimdall_prepend LD_LIBRARY_PATH "$HEIMDALL_INSTALL/madgraph/HEPTools/lib"
unset pkg _heimdall_pyver _HEIMDALL_PACKAGES
# framework/bin last, so it sits in front of everything, including the venv's bin/: the `heimdall` command
# is framework/bin/heimdall.
_heimdall_prepend PATH "$HEIMDALL/framework/bin"

for _heimdall_var in $_HEIMDALL_SCALARS; do
    export "_HEIMDALL_SAVED_$_heimdall_var=${!_heimdall_var-}"
done
unset _heimdall_var
# Each where the stack has it, else where a ready-made one is (in the base, from conda-forge)
if [ -d "$HEIMDALL_INSTALL/LHAPDF" ] || [ -z "${HEIMDALL_BASE-}" ]; then
    export LHAPDF_DATA_PATH="$HEIMDALL_INSTALL/LHAPDF/share/LHAPDF"
else
    export LHAPDF_DATA_PATH="$HEIMDALL_BASE/share/LHAPDF"
fi
# Geant4 11 finds every data set under one directory (what its geant4.sh exports)
[ -d "$HEIMDALL_INSTALL/geant4/share/Geant4/data" ] && export GEANT4_DATA_DIR="$HEIMDALL_INSTALL/geant4/share/Geant4/data"
if [ -d "$HEIMDALL_INSTALL/onnxruntime" ] || [ -z "${HEIMDALL_BASE-}" ]; then
    export ONNXRUNTIME_DIR="$HEIMDALL_INSTALL/onnxruntime"
else
    export ONNXRUNTIME_DIR="$HEIMDALL_BASE"
fi
[ -n "${HEIMDALL_BASE-}" ] && [ ! -d "$HEIMDALL_INSTALL/delphes" ] && [ -f "$HEIMDALL_BASE/include/classes/DelphesClasses.h" ] \
    && export DELPHES_DIR="$HEIMDALL_BASE"
# RIVET_ANALYSIS_PATH is deliberately not set: the rivet tool sets build/Rivet per run.

# This machine's lines (macOS: DYLD_LIBRARY_PATH and the GNU tools; a cluster: module load …), last, and
# recorded, so quit and refresh take them out instead of piling them up.
[ -f "$HEIMDALL_MACHINE/machine.sh" ] && _heimdall_source_recorded "$HEIMDALL_MACHINE/machine.sh"
export HEIMDALL_ENV_LOADED=$HEIMDALL_INSTALL
hash -r

[[ $- == *i* ]] && echo "Heimdall's environment loaded — $HEIMDALL${HEIMDALL_STACK:+ (stack: $HEIMDALL_STACK)} (heimdall_status for versions, heimdall_help for commands)"
return 0
