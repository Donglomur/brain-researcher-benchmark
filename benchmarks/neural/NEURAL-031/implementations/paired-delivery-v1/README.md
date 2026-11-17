# NEURAL-031: complete paired public delivery

This source recovers the missing portable preparation and delivery step for the
existing spine-growth prediction endpoint. It prepares the original 20 outer
folds into all 40 baseline/neural contexts, exports one context, and collects all
40 predictions for the unchanged `../ratio-scoring-v1` scorer. It never executes
a participant program or opens private query targets.

The historical projection exists: its sealed manifest pins 40 pairs of public
NPZ and JSON files. `SOURCE_INPUTS.json` contains the complete original and paired
content identities, without private storage locations or payloads. During this
source recovery, all 60 NPZ files were checked by file metadata only; their
contents were not opened. Small manifests and the public support JSON were
authenticated. This is not a new authentic preparation or model evaluation.

## Scientific contract

The original panel remains 27 source members, 20 mice, 1,143 source rows, 774
baseline-defined requests and 731 observed follow-up ratios. Each mouse is held
out once, with all its compartments together. All 774 rows require predictions
in each information condition, including 43 rows with unavailable targets.

The target is follow-up volume divided by baseline volume, dimensionless. A
ratio of one means no change. An observed zero is retained; missing targets are
not zeros. This is a baseline-defined prediction cohort, distinct
from the paper's retrospective stable-at-both-visits cohort and pooled
correlation analysis. It is not an exact reproduction of that paper statistic.

| Access | Baseline | Neural |
| --- | --- | --- |
| Common predictors | Baseline volume, basal indicator, local and coincident missingness | Identical common predictors |
| Neural measurements | Physically absent | Local normalized coactivity and normalized dendrite coincidence |
| Training data | The other 19 whole mice, including their available ratio labels | Identical rows and labels |
| Query answers or follow-up metadata | Absent | Absent |
| Prediction time | After the complete Early recording | Same |

Missingness is shared between conditions. Nonfinite activity values become NaN
in the neural view; no activity-valued buffer enters the baseline archive.
`projection031.py` recovers the original projection functions without changing
their operations. Preparation checks cross-fold predictor, label, row and mouse
consistency before writing any output, then requires byte identity with every
retained public artifact and the original support file.

This route measures agent-built analysis or a submitted prediction program on
processed neural measurements. It is neither native waveform interpretation nor
a viewer condition. Whole-mouse cross-validation yields overlapping training
sets, not 20 independent experiments. The existing scorer reports equal-mouse
baseline MAE minus neural MAE, both absolute arms, no-change and training-median
controls, unavailable-target counts, and compartment/baseline-new strata. Zero or negative gain is valid.
A gain alone does not establish causation, native understanding or new SOTA.

## Operator commands

Run from this directory with Python and NumPy already available. All paths below
are operator-selected locations; output directories must not exist. The original
root must contain `public/fold00/data.npz` through `public/fold19/manifest.json`.
The paired store contains `support.json` and `public/foldNN/{baseline,neural}`.

```sh
python -I -B delivery.py prepare --original-root ORIGINAL_ROOT --output NEW_PAIRED_STORE
python -I -B delivery.py export --store-root PAIRED_STORE --fold 0 --view baseline --output NEW_CONTEXT_INPUT
python -I -B delivery.py collect --store-root PAIRED_STORE --predictions-root CAPTURED_OUTPUTS --output NEW_COLLECTION
```

An existing, authenticated historical paired store can be used directly with
`export`; a new projection is not required. `export` reads only the selected
archive and manifest, plus the public support. Its new directory contains
exactly `data.npz` and `manifest.json`. It returns an operator receipt on stdout,
including the two content pins. Do not send the operator receipt, store root,
full support, other context exports or host access to a participant.

**Forty fresh participant realms are required.** Another held-out fold's
training labels include the current mouse's answers. Giving one persistent
agent or process multiple contexts would invalidate the original experiment.
Freeze the same participant source and method before all contexts. An isolated
program's original invocation is:

```sh
python -I -B /program/submission.py --input /input/data.npz --manifest /input/manifest.json --output /output/predictions.json
```

Only that context's two files and the frozen program belong in its read-only
mounts; only its output is writable. Preserve the original 480-second absolute
candidate batch deadline, including all 40 setups, executions, captures and
removals; do not turn it into 480 seconds per context. The original candidate
limits are 3 GiB RAM and 1.75 CPU. No arbitrary per-context 8/12-second cutoff is
introduced. Same-source enforcement, no-network execution, fresh-process state,
image inventory review, cleanup and independent output capture require a
separately qualified runner. **These utilities do not provide that sandbox**,
and `collect` does not certify program identity, elapsed time or execution
provenance. Do not use an unrestricted host process as a substitute.

Captured output layout is exactly 20 `foldNN` directories, each containing
`baseline/predictions.json` and `neural/predictions.json`. No extra output files
are allowed. Each prediction uses the existing schema
`neural031_ordinary_prediction_v1`, binds its exact input manifest, and contains
every ordered row ID with a finite nonnegative ratio prediction. The collector
rejects absent, additional, swapped or reordered contexts/rows and mismatched
manifest identities. It writes `submission.json` and `support.json` only after
the complete bundle passes the existing endpoint validator.

Pass those files to the existing `ratio-scoring-v1/score.py` operator CLI with
the independently pinned `neural031_ratio_targets_v1` JSON. The retained
historical private NPZ is **not** that JSON: its authentic, reviewed target
conversion remains a separate operator preparation step. No target conversion
or target reads occur here. The scorer validates all predictions before opening
the target file. Nothing in this delivery source changes its metric or declares
the registered runtime ready.

## Failures, bounds and checks

Every authentic CLI route uses the committed content roster. Inputs are bounded
regular files with exact hashes; symlink components beneath input roots are
rejected. Preparation validates all 20 original contexts and all expected output
pins before creating its output directory. A different serializer that changes
NPZ bytes fails; this is not permission to silently re-pin the source. Output
writes are exclusive and bounded: 16 MiB preparation, 272 KiB single export,
6.125 MiB collection. An interrupted write can leave an incomplete directory;
retain it for diagnosis and use a new output directory, never resume or merge it
into an accepted store. A valid pinned support and all required file identities
are needed for later use.

```sh
python -I -B test_delivery.py
```

Ten generated controls exercise the full 20-mouse/774-request/40-context shape,
physical neural-value removal with shared missingness, complete export and
collection, the unchanged scorer join, inconsistent training labels/predictors,
wrong identities, missing/reordered/extra outputs, symlinks and overwrite
rejection. All observations, labels and predictions in these controls are
generated; no model is called. The initial suite took 0.848 seconds wall time,
0.675 seconds child CPU, and 60,375,040 bytes peak child RSS in the bounded test
pool. It wrote 5,281,268 fixture bytes cumulatively and removed its fixtures.
Those are software-control measurements, not an authentic-preparation or
candidate-runtime estimate.

Remaining work before an authentic scored program study is concrete: qualify
the isolated 40-context runner and frozen program boundary, prepare the original
private target JSON under its reviewed conversion, freeze the scientific
comparison and model budget, then run and capture every original context. The
source recovery, pins and generated checks do not satisfy those steps.
