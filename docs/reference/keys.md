---
id: keys
summary: every setting in one line each, for grep: key, type, default
code: framework/schema, src/Apps/Paint/base.toml, recipes/settings.toml
generated: true
---

# Every key

`key | type | default`. Generated. What each does: `heimdall explain <key>`, or its settings page.

```
file.master | string | -
file.import | string or list of strings or tables | -
file.drop | list of strings | -
file.vars | table | -
file.meta | table | -
file.schema | integer | -
errand.name | string | required
errand.assignment | string | required
errand.run | string | -
errand.serial | integer | -
errand.events | integer | -
errand.threads | integer | 1
errand.parallelism | integer or string | 1
errand.library | true or false or string | false
errand.plot | true or false or list of strings | true
errand.stats | true or false or list of strings | true
errand.description | string | -
errand.tag | string | -
errand.sweep_runs | true or false or list of strings | false
errand.notify | string | "none"
errand.chain | list | -
errand.vary | list | -
errand.plot_points | list of strings | -
errand.combine | list of strings | -
errand.pre | list | -
errand.post | list | -
errand.generate_cards | list of strings | -
errand.seed | string or integer | "identity"
errand.commands | list | -
cfgs.<name>.extends | string | -
cfgs.<name>.serial | integer | -
cfgs.<name>.name | string | -
cfgs.<name>.folder | string | -
cfgs.<name>.title | string | -
cfgs.<name>.description | string | -
cfgs.<name>.tag | string | -
cfgs.<name>.events | integer | -
cfgs.<name>.threads | integer | -
cfgs.<name>.parallelism | integer or string | -
cfgs.<name>.library | true or false or string | -
cfgs.<name>.plot | true or false or list of strings | -
cfgs.<name>.stats | true or false or list of strings | -
cfgs.<name>.vary | list | -
cfgs.<name>.plot_points | list of strings | -
cfgs.<name>.combine | list of strings | -
cfgs.<name>.chain | list | -
cfgs.<name>.generate_cards | list of strings | -
cfgs.<name>.pre | list | -
cfgs.<name>.post | list | -
cfgs.<name>.fixed | table | -
cfgs.<name>.vars | table | -
cfgs.<name>.data | table | -
cfgs.<name>.cluster | table | -
cfgs.<name>.seed | string or integer | "identity"
quantities.<q>.shape | string or list | -
quantities.<q>.to | string or table | -
quantities.<q>.format | string | -
quantities.<q>.description | string | -
quantities.<q>.exclude | list | -
quantities.<q>.points | list | -
quantities.<q>.fixed | string or integer or number | -
quantities.<q>.fields | table | -
tools.<name>.uses | string | -
tools.<name>.card | string or list | -
tools.<name>.input | string or list | -
tools.<name>.output | string or list | -
tools.<name>.timeout | number | -
tools.<name>.stall_after | number | -
tools.<name>.status | string | -
tools.<name>.filters | string | -
tools.<name>.executable | string | -
tools.<name>.arguments | list | -
tools.<name>.consumes | list of strings | -
tools.<name>.config | table | -
tools.<name>.streamable | true or false | -
tools.<name>.consumes_events | true or false | -
tools.<name>.settings | table | -
tools.<name>.cores | integer | -
tools.<name>.shards | integer | 1
tools.<name>.keep | true or false | true
plot.backend | string or list of strings | "root"
plot.formats | list of strings | ["pdf"]
plot.band | list of strings | -
plot.objects | list of strings | -
plot.ratio | true or false | false
plot.y_gutter | number | 0.5
plot.x_gutter | number | -
plot.x_range | list of numbers or strings | -
plot.y_range | list of numbers or strings | -
plot.logy | true or false | -
plot.logx | true or false | -
plot.logz | true or false | -
plot.auto_range | true or false | true
plot.normalise | string or true or false | false
plot.void_empty | true or false | false
plot.use_data | true or false | true
plot.min_entries | integer | 0
plot.range_pad | integer | 0
plot.sets | list of integers or strings or lists or tables or table | -
plot.looks | table | -
plot.across | table | -
plot.across_from | table | -
plot.draw | list of strings | -
plot.split | integer | -
plot.statistics | true or false | true
plot.legend_statistic | string | "none"
plot.root_style | string | -
plot.title | string | -
plot.title_left | string | -
plot.title_right | string | -
plot.legend_header | string | -
plot.data | table | -
plot.style | table | -
plot.figures | table | -
plot.figures.<name>.class | string | "defined"
plot.figures.<name>.type | string | -
plot.figures.<name>.name | string | -
plot.figures.<name>.objects | list of strings | -
plot.figures.<name>.statistic | string | -
plot.figures.<name>.weight | number | -
plot.figures.<name>.sort | true or false | false
plot.figures.<name>.op | string | -
plot.figures.<name>.x | string | -
plot.figures.<name>.y | string | -
plot.figures.<name>.pages | list of strings | -
plot.figures.<name>.columns | integer | -
plot.figures.<name>.over | list of strings | -
plot.figures.<name>.configurations | list of strings | -
plot.figures.<name>.labels | list of strings | -
plot.figures.<name>.x_label | string | -
plot.figures.<name>.y_label | string | -
plot.figures.<name>.style | table | -
plot.data.file | string | -
plot.data.legend | string | "Data"
plot.data.map | table | -
plot.across_from.runs | list of strings | ["*"]
plot.across_from.prefer | string | "last"
plot.across_from.ignore | list of strings | -
stats.sets | list of strings | -
stats.objects | list of strings | -
stats.reference | string or table | -
stats.normalise | string or true or false | -
stats.void_empty | true or false | -
stats.min_entries | integer | -
stats.auto_range | true or false | -
stats.range_pad | integer | -
stats.metrics | list of strings | -
stats.centres | string | "mid"
score.metrics | list of strings or table | -
score.normalise | string | "thresholds"
score.thresholds | table | -
score.weights | table | -
score.weights_by | string | "equal"
score.mean | string | "rms"
score.by | string or list of strings | -
score.baseline | string or table | -
score.veto | number | -
score.aggregate | string | "rms"
score.dominated | true or false | false
score.head_to_head | string | -
report.title | string | -
report.subtitle | string | -
report.from | list of strings | -
report.output | string | -
report.template | string | -
report.section | list of tables | -
report.tools | list of strings | -
report.font | string | "sans"
report.size | number | 9.5
report.accent | string | "#2a78d6"
report.contents | true or false | true
report.columns | integer | 2
report.method | true or false | true
report.context | string | "first"
report.section.title | string | required
report.section.note | string | -
report.section.from | list of strings | -
report.section.pages | list of strings | -
report.section.set | string | "totality"
report.section.cells | list of strings | -
report.section.backend | string or list of strings | -
report.section.layout | string | "pages"
report.section.columns | integer | -
report.section.label | string | "folder"
report.section.optional | true or false | false
report.section.compare | list of strings | -
report.section.stats | list of strings | -
report.section.bars | list of strings | -
report.section.files | list of strings | -
report.section.tools | list of strings | -
report.section.hide | list of strings | -
report.section.plot | table | -
cluster.scheduler | string | "slurm"
cluster.time | string | -
cluster.partition | string | -
cluster.account | string | -
cluster.qos | string | -
cluster.constraint | string | -
cluster.gres | string | -
cluster.memory | string | -
cluster.cpus | integer | 0
cluster.max_running | integer | 0
cluster.mail | string | -
cluster.setup | list of strings | []
cluster.image | string | -
cluster.sbatch | list of strings | []
cluster.pre | table | -
cluster.finish | table | -
tools.merge.equivalent | flag | true
tools.rivet.analyses | list | required
tools.rivet.options | table | -
tools.yd2rt.select | list | -
style.page.size | list | [4.67, 4.21]
style.page.dpi | integer | 300
style.page.font | string | "serif"
style.page.margins.left | number | 0.16
style.page.margins.right | number | 0.032
style.page.margins.top | number | 0.066
style.page.margins.bottom | number | 0.11
style.text.title | number | 10.0
style.text.labels | number | 8.0
style.text.legend | number | 9.0
style.text.header | number | 9.0
style.text.page_title | number | 12.0
style.text.corner | number | 9.0
style.curves.palette | list | ["#EE3311", "#3366FF", "#109618", "#FF9900", "#990099"]
style.curves.width | number | 1.0
style.curves.errors | string | "bars"
style.data.colour | string | "kBlack"
style.data.marker | integer | 20
style.data.marker_size | number | 2.0
style.data.x_bars | true or false | true
style.axes.tick_length | number | 6.0
style.axes.ticks_all_sides | true or false | true
style.axes.titles_at_ends | true or false | true
style.axes.title_offset | list | [1.0, 1.55]
style.axes.label_offset | number | 2.5
style.legend.position | string | "top-right"
style.legend.inset | list | [5.0, 5.0]
style.legend.spacing | number | 1.2
style.legend.symbol | number | 16.0
style.legend.gap | number | 5.0
style.ratio.heights | list | [2.0, 1.0]
style.ratio.range | list | [0.5, 1.5]
style.ratio.limits | list | [0.0, 3.0]
style.ratio.divisions | integer | 512
style.ratio.decimals | true or false | true
style.ratio.gap | number | 0.0
stack.machine | string | ""
stack.base | string | "conda"
stack.base_python | string | "3.12"
stack.base_gcc | string | "15"
stack.base_packages | list | []
stack.base_pypi | list | []
stack.packages | string | "core"
stack.cores | integer | 0
stack.root_cores | integer | 0
stack.cxx_std | integer | 17
stack.opt_flags | string | "-O2"
stack.python | string | "python3"
stack.system | true or false | true
stack.graphics | string | "ON"
stack.geant4_data | string | "ON"
stack.cuda_arch | string | "native"
stack.setup_extra | list | []
stack.verify | true or false | true
stack.shell_rc | true or false | true
stack.python_packages | list | (a long list)
stack.ufo_models | list | []
stack.openloops_processes | list | ["ppllj"]
stack.pdf_sets | list | (a long list)
stack.apt_packages | list | (a long list)
stack.env.CXXFLAGS | string | "{cxxflags}"
stack.env.VIRTUAL_ENV | string | "{venv}"
stack.env.LHAPDF_DATA_PATH | string | "{dir_lhapdf}/share/LHAPDF"
```
