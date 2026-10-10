# framework/rules.mk — what Heimdall's Makefile and a work dir's (framework/work.mk) share
# (docs/06_Internals.md §15): the flags cache, linking by `// requires:`, and the rule templates.
#
# The includer sets, before including this file:
#   MK          where flags.mk, flags.log and deps/ go
#   PROGRAMS    the sources compiled to programs by convention     RIVET_SRCS   the Rivet plugins' sources
#   RIVET_OUT   where Rivet plugins go
#   out_of      a source's output       alias_of   its short target     incs_of   its own -I flags
#   goal_src    the source of a goal named on the command line (<path>/<X>.exe, <path>/<x>.so)
#
# Linking (§5.2): a source names its libraries in a `// requires: pythia8 hepmc3 …` line near the
# top (`none` for none; a trailing `(…)` is a note). Without the line it gets every library that
# was found. Including "Module.hh" adds hepmc3 and toml. Flags come from $(MK)/flags.mk (§5.3).

ifndef HEP
  $(error HEP is not set: load Heimdall's environment first (source <Heimdall>/setup.sh))
endif

SHELL := /bin/bash
.DEFAULT_GOAL := all
.SUFFIXES:
.DELETE_ON_ERROR:

CXX      ?= g++
CXXFLAGS ?= -O2
# The loaded stack's C++ standard, as recipes/build_stack.py built it: an isolated toolkit's may be 20
CXX_STD  := $(or $(shell cat $(HEP_INSTALL)/.stamps/cxx_std 2>/dev/null),17)
BASE      = -std=c++$(CXX_STD) $(CXXFLAGS) -I $(HEP)/src

# ── flags: probed once, rewritten only when what they depend on changes (L22) ──────────────────
FLAGS_MK := $(MK)/flags.mk
ifneq ($(wildcard $(FLAGS_MK)),)
  include $(FLAGS_MK)
endif
FLAGS_KEY_NOW := $(shell $(HEP)/env/flags.sh --key)
ifneq ($(FLAGS_KEY),$(FLAGS_KEY_NOW))
  $(shell $(HEP)/env/flags.sh $(FLAGS_MK))
  include $(FLAGS_MK)
endif
# KNOWN (every library a source may require) is env/stack.toml's, written into $(FLAGS_MK) (V78).
# Every output depends on $(FLAGS_MK): a re-probe (another stack loaded, a tool moved) rebuilds them.

open     := (
req_line  = $(shell sed -n 's#^[[:space:]]*//[[:space:]]*requires:[[:space:]]*##p' $(1) | head -n1 | sed 's#[[:space:]]*$(open).*##')
uses_kit  = $(if $(shell grep -ls 'include[[:space:]]*"Module.hh"' $(1)),hepmc3 toml)
libs_of   = $(sort $(call uses_kit,$(1)) $(filter-out none,$(or $(call req_line,$(1)),$(FOUND))))
lib_flags = $(if $(filter $(2),$(FOUND)),$(FLAGS_$(2)),$(error $(1): requires '$(2)', $(if \
              $(filter $(2),$(KNOWN)),which env/flags.sh did not find (see $(FLAGS_MK)),\
              which is not a known library (known: $(KNOWN)))))
flags_of  = $(foreach l,$(call libs_of,$(1)),$(call lib_flags,$(1),$(l)))

# ── naming ──────────────────────────────────────────────────────────────────────────────────────
parked   = $(foreach s,$(1),$(if $(findstring /_,/$(s)),,$(s)))
is_rivet = $(or $(findstring /Rivet/,$(1)),$(filter Rivet_%,$(notdir $(1))))
ana_of   = $(patsubst Rivet_%,%,$(basename $(notdir $(1))))
lib_of   = $(MK)/$(patsubst ./%,%,$(dir $(1)))lib$(basename $(notdir $(1))).so
side_of  = $(firstword $(wildcard $(dir $(1))$(call ana_of,$(1)).$(2) $(dir $(1))Rivet_$(call ana_of,$(1)).$(2)))
depfile  = $(MK)/deps/$(subst /,__,$(1)).d

# Sources named on the command line, including ones outside the conventions (generator_comparison.cc)
GOALS      := $(filter %.exe %.so,$(MAKECMDGOALS))
$(foreach g,$(GOALS),$(if $(wildcard $(call goal_src,$(g))),,$(error $(g): no source $(call goal_src,$(g)))))
GOAL_SRCS  := $(foreach g,$(GOALS),$(call goal_src,$(g)))
SO_GOALS   := $(foreach g,$(filter %.so,$(GOALS)),$(if $(call is_rivet,$(g)),,$(call goal_src,$(g))))

EXE_SRCS   := $(sort $(PROGRAMS) $(foreach s,$(GOAL_SRCS),$(if $(call is_rivet,$(s)),,$(if $(filter $(s),$(SO_GOALS)),,$(s)))))
RIVETS     := $(sort $(RIVET_SRCS) $(foreach s,$(GOAL_SRCS),$(if $(call is_rivet,$(s)),$(s))))

# ── rules ───────────────────────────────────────────────────────────────────────────────────────
define exe_rule
$(call out_of,$(1)): $(1) $(FLAGS_MK)
	@mkdir -p $$(@D) $(MK)/deps
	$$(CXX) $$(BASE) $(call incs_of,$(1)) -MMD -MP -MF $(call depfile,$(1)) $(1) -o $$@ $$(call flags_of,$(1))
.PHONY: $(call alias_of,$(1))
$(call alias_of,$(1)): $(call out_of,$(1))
endef

define so_rule
$(call lib_of,$(1)): $(1) $(FLAGS_MK)
	@mkdir -p $$(@D) $(MK)/deps
	$$(CXX) $$(BASE) -fPIC -shared $(call incs_of,$(1)) -MMD -MP -MF $(call depfile,$(1)) $(1) -o $$@ $$(call flags_of,$(1))
.PHONY: $(basename $(1)).so
$(basename $(1)).so: $(call lib_of,$(1))
endef

# A Rivet plugin, and its .info/.plot/.yoda as real targets so an edit re-copies them (00/B44).
# rivet-build gets the shared-header paths (L20) and, when the .info says `Requires: ONNX`, ONNX. It runs a
# make of its own, so its line starts with `+`: that make shares our -j job slots. `sed -i.tmp` and
# the rm, not `sed -i`: BSD sed (macOS) takes no bare -i.
define side_rule
$(RIVET_OUT)/$(call ana_of,$(1)).$(2): $(call side_of,$(1),$(2))
	@mkdir -p $$(@D)
	cp $$< $$@
endef
define rivet_rule
$(RIVET_OUT)/Rivet_$(call ana_of,$(1)).so: $(1) $(FLAGS_MK)
	@mkdir -p $$(@D) $(MK)/deps
	+rivet-build $$(abspath $$@) $(abspath $(1)) -I$(HEP)/src $(call incs_of,$(1)) \
	    -MMD -MP -MF$(abspath $(call depfile,$(1))) \
	    $(if $(shell grep -ls 'Requires:.*ONNX' $(call side_of,$(1),info) /dev/null),$$(FLAGS_onnx))
	@sed -i.tmp '1s|^[^:]*:[[:space:]]*[^[:space:]]*\.cc|$$@:|' $(call depfile,$(1)) && rm -f $(call depfile,$(1)).tmp
$(foreach e,info plot yoda,$(if $(call side_of,$(1),$(e)),$(eval $(call side_rule,$(1),$(e)))))
.PHONY: $(basename $(1)).so rivet_$(call ana_of,$(1))
$(basename $(1)).so rivet_$(call ana_of,$(1)): $(RIVET_OUT)/Rivet_$(call ana_of,$(1)).so $(foreach e,info plot yoda,$(if $(call side_of,$(1),$(e)),$(RIVET_OUT)/$(call ana_of,$(1)).$(e)))
endef

$(foreach s,$(EXE_SRCS),$(eval $(call exe_rule,$(s))))
$(foreach s,$(SO_GOALS),$(eval $(call so_rule,$(s))))
$(foreach s,$(RIVETS),$(eval $(call rivet_rule,$(s))))
