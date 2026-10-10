# Makefile — Heimdall's own build: the framework's apps and the C++ tests (docs/06_Internals.md §15).
# `hep build --framework` is `make all` here. A work dir's build is framework/work.mk; the rules
# both share are framework/rules.mk.
#
#   make                        every app, and Herwig's repository
#   make src/<X>.exe            compile one source; the output lands where the convention says
#   make tests                  build the C++ tests       make test   build and run them, then pytest
#   make clean                  remove the apps and the build's intermediates (never the stack's builds)
#
# Conventions (§5.1):
#   src/App_<X>.cc              → framework/Apps/App_<X>.exe
#   src/Apps/<X>/main.cc        → framework/Apps/<X>.exe      (the folder's other files are headers it includes)
#   tests/cxx/<X>.cc            → forge/tests/<X>.exe
#   <dir>/<X>.cc                → forge/make/<dir>/<X>.exe or forge/make/<dir>/lib<X>.so, only when named
# Intermediates (flags.mk, flags.log, deps/) are in forge/make/. With an isolated toolkit's stack
# loaded ($HEP_STACK), framework/Apps/ is stacks/<toolkit>/Apps/ and forge/ is stacks/<toolkit>/forge/:
# the apps are linked against that stack.

HEP      ?= $(CURDIR)
STACK    := $(if $(HEP_STACK),stacks/$(HEP_STACK)/,)
APPS     := $(if $(STACK),$(STACK)Apps,framework/Apps)
FORGE    := $(STACK)forge
MK       := $(FORGE)/make

out_of   = $(strip \
  $(if $(filter src/App_%.cc,$(1)),$(APPS)/$(basename $(notdir $(1))).exe,\
  $(if $(filter src/Apps/%/main.cc,$(1)),$(APPS)/$(notdir $(patsubst %/,%,$(dir $(1)))).exe,\
  $(if $(filter tests/cxx/%,$(1)),$(FORGE)/tests/$(basename $(notdir $(1))).exe,\
  $(MK)/$(basename $(1)).exe))))
alias_of = $(if $(filter src/Apps/%/main.cc,$(1)),$(patsubst %/,%,$(dir $(1))).exe,$(basename $(1)).exe)
incs_of  = $(if $(filter src/Apps/%,$(1)),-I$(dir $(1)))
goal_src = $(if $(filter src/Apps/%.exe,$(1)),$(1:.exe=)/main.cc,$(basename $(1)).cc)

APP_SRCS   := $(wildcard src/App_*.cc) $(wildcard src/Apps/*/main.cc)
TEST_SRCS  := $(wildcard tests/cxx/*.cc)
PROGRAMS   := $(APP_SRCS) $(TEST_SRCS)
RIVET_SRCS :=
RIVET_OUT  := $(MK)/Rivet

include framework/rules.mk

ALL   := $(foreach s,$(APP_SRCS),$(call out_of,$(s)))
TESTS := $(foreach s,$(TEST_SRCS),$(call out_of,$(s)))

# Herwig's repository (framework/tools/herwig): its own install made none, because its defaults need
# the CT14lo/CT14nlo PDF sets (L15). Built here, never in the stack; a failure warns and leaves no file.
HERWIG := $(shell command -v Herwig 2>/dev/null)
ifneq ($(HERWIG),)
HERWIG_HOME := $(patsubst %/bin/Herwig,%,$(HERWIG))
$(APPS)/Herwig/HerwigDefaults.rpo: $(HERWIG)
	@mkdir -p $(@D)
	@cd $(@D) && if Herwig init -L$(HERWIG_HOME)/lib/Herwig -i$(HERWIG_HOME)/share/Herwig \
	    --repo=$(abspath $@) defaults/HerwigDefaults.in > init.log 2>&1; then echo "── $@"; \
	  else rm -f $(abspath $@); echo "warning: Herwig's repository was not built: $$(tail -1 init.log)"; fi
ALL += $(APPS)/Herwig/HerwigDefaults.rpo
endif

.PHONY: all tests test test-slow clean configure list schema docs
all: $(ALL)
tests: $(TESTS)
test: all tests
	@set -e; for t in $(TESTS); do echo "── $$t"; $$t; done
	python3 -m pytest -q -m "not slow"
test-slow: all
	python3 -m pytest -q -m slow
configure:
	env/flags.sh $(FLAGS_MK)
list:
	@printf '%s\n' $(ALL) $(TESTS)
schema:                         # framework/schema/run.schema.json from run.toml (V55)
	cd framework && python3 -m runner.schema
docs:                           # the manual's generated blocks, from the schema, base.toml and the CLI (V91)
	cd framework && python3 -m runner.docs
clean:
	rm -rf $(APPS) $(MK) $(FORGE)/tests

-include $(wildcard $(MK)/deps/*.d)
