"""The tests' machine root is a shadow (conftest.py): the live machine.toml and recipes.toml decide nothing."""

from __future__ import annotations

import os
from pathlib import Path

from runner import paths


def test_the_machine_root_is_the_shadow_in_scratch():
    root = paths.machine_root()
    assert root.parent.name == "scratch" and root.name == "machine"
    assert paths.machine_settings() == {}                                    # the template is all comments
    assert (root / "recipes.toml").is_file()


def test_the_built_parts_are_the_real_ones():
    root = paths.machine_root()
    for name in ("HEIMDALL_APPS", "HEIMDALL_INSTALL", "HEIMDALL_FORGE"):
        assert Path(os.environ[name]).resolve() != root.resolve()            # pinned, not derived from the shadow
    for name in ("stack", "base", "apps"):
        link = root / name
        if link.exists() or link.is_symlink():
            assert link.is_symlink(), f"{name} is linked, not copied"
