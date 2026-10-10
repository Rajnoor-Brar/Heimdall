# recipes/toolkits.d/: your own toolkits

Any `*.toml` here is read with [../toolkits.toml](../toolkits.toml)'s presets, in the same format,
and its toolkits are used the same way: `python3 recipes/build_stack.py packages=@<name>`. A name
that a preset or another file already uses is refused, so a custom toolkit never silently replaces
one. Commit the files you want on every machine; leave the others untracked.

[example.toml.sample](example.toml.sample) shows every key; copy it to `<name>.toml` and edit it.
