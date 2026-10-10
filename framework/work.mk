# framework/work.mk — a work dir's build (docs/06_Internals.md §15). The work dir's Makefile includes
# it (`include $(HEP)/framework/work.mk`, from framework/templates/work/); `hep build` is `make all`
# there. The rules it shares with Heimdall's Makefile are framework/rules.mk.
#
#   make                        every module program and Rivet plugin
#   make <path>/<X>.exe         compile one source; the output lands where the convention says
#   make <path>/<x>.so          a Rivet plugin (…/Rivet/<x>.so, …/Rivet_<x>.so) or a shared library
#   make clean                  empty build/
#
# Conventions (§5.1):
#   modules/<P>/<X>.cc          → build/<P>/<X>.exe  (-I modules/<P>)
#   modules/<P>/Rivet/<x>.cc    → build/Rivet/Rivet_<x>.so, with <x>.info/.plot/.yoda copied beside it
#   modules/<P>/Rivet_<x>.cc    → the same
#   <dir>/<X>.cc                → build/<dir>/<X>.exe or build/<dir>/lib<X>.so, only when named
# A path with a component starting with `_` is parked: never built by `make all`. Heimdall's
# headers (Module.hh, Kit.hh, Status.hh, …) are on the include path: -I $(HEP)/src.

BUILD    := build
MK       := $(BUILD)

proj_of  = $(word 2,$(subst /, ,$(1)))
out_of   = $(strip \
  $(if $(call is_rivet,$(1)),$(BUILD)/Rivet/Rivet_$(call ana_of,$(1)).so,\
  $(if $(filter modules/%,$(1)),$(BUILD)/$(call proj_of,$(1))/$(basename $(notdir $(1))).exe,\
  $(BUILD)/$(basename $(1)).exe)))
alias_of = $(basename $(1)).exe
incs_of  = $(if $(filter modules/%,$(1)),-I$(CURDIR)/modules/$(call proj_of,$(1)))
goal_src = $(basename $(1)).cc

# `=`, not `:=`: these use rules.mk's helpers, so they are expanded there, once it has defined them
ROOT_CC     = $(call parked,$(wildcard modules/*/*.cc))
RIVET_SRCS  = $(call parked,$(wildcard modules/*/Rivet/*.cc)) $(foreach s,$(ROOT_CC),$(if $(filter Rivet_%,$(notdir $(s))),$(s)))
PROGRAMS    = $(foreach s,$(ROOT_CC),$(if $(filter Rivet_%,$(notdir $(s))),,$(s)))
RIVET_OUT  := $(BUILD)/Rivet

include $(HEP)/framework/rules.mk

ALL := $(foreach s,$(PROGRAMS),$(call out_of,$(s))) $(foreach s,$(RIVET_SRCS),rivet_$(call ana_of,$(s)))

.PHONY: all clean configure list
all: $(ALL)
configure:
	$(HEP)/env/flags.sh $(FLAGS_MK)
list:
	@printf '%s\n' $(ALL)
clean:
	rm -rf $(BUILD)

-include $(wildcard $(BUILD)/deps/*.d)
