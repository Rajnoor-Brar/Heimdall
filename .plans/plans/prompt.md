# Plotting 

## Axes
quantity axes may be assigned one of three role
1. Curve : Filters points for curves in plot
2. Page  : Filters points to make up the pages in a set.
3. Merged: Merge points into single point (look into and see if 'combine' is same concept as this or what)

```toml
[plot.sets.<set>]
pages = [{ generator = "sh3" , beampolarisation = "all"}, {generator="py8", qed_ledpton="all"}]
curves = {energies = "all"}
merge = [{events = "all"}, {pdfs = {list=["pdf1","pdf2","pdf2"], label = "Combined Pdfs", tag="combpdf} }]
 }
```
for all other points axes being same, with only difference being pdf value, the points with listed value merge into one point combpdf.

all merge quantities in merge = [] apply on top of each other like point with any events count AND pdf among <list>, become one point.
for merge = {<quantity> = "all"}, the quantity simply vanishes as axis for plotting purposes (except for note keeping, these points were merged and so)

plot.sets.<set>.merge.mean_type = <"linear","geometric","trimmed_linear","trimmed_geo","rms","wasserstien" etc>

more details on supportable mean type in mean_types.md



# Comparisons, Scoring and ranking

Each plot should hold a weight, by default =1, or set via plot.figures settings; or simply provided as list in plot.sets.<set>.plot_weights =[]

weight can be any positive real value acting as ratio of weight among plots, normalised to 0-1 range when using in the backend.

instead of simple average when determining metric for a point, ability to select mean_type for mean types something like
<set>.plot_mean = 

Options to have stats be shown per axes, like stats for PDFs only with other axes all merged to leave pdf only points for comparison.

Aggregate Scoring across points and pages to be based on actual scoresof metrics, not scores given to local ranks or win rates.

several options for combining of metrics for grand scoring in scoring_fairness.md

We could end up requiring to reorganize or restructure toml options and their nesting.

Ability to quick compare runs on non point basis such as baseline configurations.

## Across comparisons

1. for runs with different axes of variations. how can we do proper comparisons in reports and such. untangle the runs into all axial variations and treat those axes as fixed or varied values in other runs
2. for runs/stats with same name in reports and stats, ability to distinguish them, for one, we can prefix with serial number of the run


# Proposal for discussion on feasebility : Dedicated Statistics Backend
A dedicated modules/backend for data, statistics and scoring related computation only, or separation/decoupling of statistics and data backends from plot.


# Improvement to Terminal watch and runs UI, with some colors, and <A>/<E> location in results/records
reorganise to
  [<i>] <machine_name> | <work_dir> | <config>
      <time of start>   ·  <current duration>
      <A/E> · <run>
      <state> · <jobs running>  ·  <done/total>
      pid <pid> : heimdall watch --pid <pid> · heimdall stop --pid <pid>
      log <log_path>

with some coloring
possibly have log path be clickable to open it in system default app
and watch/stop/resume(for paused)/rerun(for failed) line be clickable and execute the line (with additional "--prompt-user" flag for stop, requiring user to type "stop", same for "rerun" and "resume", or any other to cancel and not do the action)

runs when run plain to with --5 etc flags, would always categorize runs "running", "paused" , "failed, "cancelled", "completed", either we group them, list them by recency with corresponding label

# Ability to alter parallelism/running jobs in ongoing runs

something like "heimdall runs -i 2 --set-jobs 8"
if new count is higher, new jos dispatch, if lower existing jobs are waited out

# Points library

##  <Assigment>/<Errand>/<Run>/<point>

points stored in <results|records>/<Assignment>/library/<point>
<point> is not named by varied quantities. a point's is a unique randrom UUID. For example a point with 10M and nnpdf23 in run with varied event counts is same as one in varied pdfs runs. A point remains same if all the final configs and configuration states are identical (except some selected exceptions, such as seed values and so)

a jsonl (eg library/points.jsonl) may be used to index UUIDs to identities and configurations

<[run].points | run.cfgs.<cfg>.points>.to_library = True | False | "Only" | "Overwrite"
with "only", a run is just a phantom construct, and all points go to library with the run itself being as good as having never run
with overwrite, contributed points overwrites existing points instead of using and skipping over.

points.from_library = True | False (whether to use points from library)

# other
1. just use 'himinbjorg' instead of 'machine_root'
2. rethink the purpose of heimdall tag/log
3. Also lets get to solving and clearing ISSUES.md