# NEURAL-076: complete visual-feature recovery and hierarchy assessment

These are the current participant instructions for `full-cohort-program-v2`,
bound to the accepted `hierarchy-scorer-v2`. The historical protected package's
TASK.md describes an older scoring endpoint and is not the current objective.

Submit one UTF-8 Python program, at most 131,072 bytes, before query access.
The same program runs afresh for all **five people × ten source brain regions
× thirteen feature families = 650 contexts**. These are not ten folds. Each
invocation receives `--input /case --output /output` and must write exactly
`predictions.npz`. No state persists between contexts. Numerical threads are one.

Each context supplies 1,200 training rows, 500 imagery queries followed by all
1,750 perception queries, and 1,000 fixed feature units. `training.npz` contains
fMRI `x`, paired `features`, category `groups` and `runs`; `queries.npz` contains
`x`, `trial_ids` and `unit_ids`; `bank.npz` supplies the permitted 50-category
feature bank without query-to-category labels. `context.json` names the
person/region/family and 316-voxel limit; `COMPLETE.json` pins those four files.
GIST uses the original identity-only 1,000-of-1,024 selection. All other families
retain their 1,000 units. No smaller panel or outcome-selected units are allowed.

Fit transforms, select at most 316 voxels per output unit and tune exclusively
on training observations. Preserve category groups and exclude any training run
intersecting validation support during tuning. Predict each query pointwise:
no query normalization, transduction, category grouping, cross-condition
adaptation or cross-context state. Process isolation alone cannot certify these
scientific rules; separate procedural review remains required.

Output exactly three C-order nonobject arrays: `features`, a finite float32 or
float64 matrix of shape 2250 × 1000 in original feature units; `trial_ids`, the
exact supplied `<U25` sequence; and `unit_ids`, the exact supplied integer
sequence. Stored or deflated NPZ is allowed. Each archive and its expanded
members must remain within 24 MiB. Extra files, duplicate members, reordered
identities, nonfinite values and incomplete context coverage are invalid.

The operator averages predictions within each instructed category, computes
each unit's signed Pearson correlation across the 50 categories against the
category-feature bank, then averages all 1,000 units. It retains all ten imagery
and all 35 perception repeats per category. Undefined constant correlations
propagate null rather than zero or selective exclusion.

The current primary, separately for each person, is:

`[r(imagery,HVC,cnn7) − r(imagery,HVC,cnn1)] − [r(imagery,LVC,cnn7) − r(imagery,LVC,cnn1)]`.

The report retains all five signed values, their equal-person mean, all 1,300
person/phase/region/family cells, and named secondary contrasts. The old
CNN5–8-minus-CNN1–4 interaction is a secondary. A larger signed hierarchy effect
is **not** automatically a more accurate scientific answer. Null and negative
effects remain valid. No bootstrap, confidence interval, p-value, multiplicity
claim or SOTA qualification is supplied by this route. No-neural and
training-permuted comparator collections require separately frozen execution.

This is agent-built analysis of preprocessed fMRI, not direct or viewer-based
neural understanding. The five-person historical source, public-data/model
exposure, cue carryover, prior run-wide preprocessing and unequal imagery versus
perception repetition counts limit scientific interpretation. Real candidate
performance and runtime feasibility remain unmeasured by these source controls.
