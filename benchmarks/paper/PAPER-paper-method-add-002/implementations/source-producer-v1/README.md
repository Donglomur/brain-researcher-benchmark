# Original Churchland source producer

This component produces the inputs and numerical result family consumed by the
existing [source endpoints](../source-endpoints-v1/README.md). It implements the
original Churchland analysis: complete preprocessing, named factor and partial
reconstruction outputs, raw and reconstructed trajectory decoding, the separate
condition-average control, and Figure 2 component diagnostics. It does not use
the earlier 200-case conditional-position programme as evidence of the original
paper's results.

The full primary article was reviewed for this construction: [Nature Neuroscience,
DOI 10.1038/s41593-024-01626-2](https://doi.org/10.1038/s41593-024-01626-2),
PMC11537991, cached XML SHA256
`44928c44a2f737e6b9c0e4528be9d8cdf396283a5575f50f71dec543e6033710`.
The previous endpoint review's missing-paper limitation is historical. This new
review does not retroactively change what that earlier review inspected.
Author analysis revision is `62b0ca1267fe9d615111a193080577eda601687e`.
The implementation is original; author code is not copied into this directory.

## Complete original inputs

`load_originals` authenticates the six exact numeric NPY files before decoding:
265 straight and 246 curved neural trials, movement, target angle, target position
and condition. All 511 trials, 182 neurons and 150 source bins remain. Source
file sizes total 112,845,920 bytes; exact SHA256/shape pins are embedded in
`ORIGINALS`. It refuses symlink files, wrong hashes/shapes, nonnumeric/pickled
arrays and source changes during reading. Array positions are not authenticated
biological trial identifiers. All observations come from one monkey J session.

`prepare_arrays` assembles straight then curved trials and applies the notebook's
preprocessing: count × 100, Gaussian sigma 2 bins along time with reflect edges
and truncate 4, then each neuron's full-experiment minimum subtraction and range
division. Final data are float32 in `[trial,neuron,time]`; normalization constants
are retained. No fold-specific normalization is substituted. All trials have
been exposed during representation preparation; a later decoder split cannot
make representation fitting an unseen-trial experiment. A constant neuron fails
explicitly instead of disappearing or receiving invented values.

The only CLI operation is complete private array preparation:

```sh
python3 -I -B producer.py --inputs /operator/originals --output /operator/new-preparation
```

It uses a fresh directory, keeps all outputs private and writes a completion
receipt with original and derived hashes. It performs no decoder fitting, model
optimization, scientific scoring or candidate attempt. Authentic preparation
requires its separately reviewed resource protocol; merely shipping this CLI
is not evidence that it ran.

## Factor and reconstruction producer

`materialize_model` accepts an explicit model callback, seed, optimizer
configuration, mask identity and reference identity. It does not supply a trained
model, recovered historical checkpoint or qualified fitting runtime. Callback
outputs must be complete named factor arrays with the source rank roster.
Mutable callback configurations are deep copies; callbacks cannot rewrite the
rank check by mutating a nested configuration.

| Named model | Required output |
| --- | --- |
| `raw` | Complete preprocessed tensor |
| `neuron_nmf12` | 12 neuron-slicing components |
| `trial_nmf12` | 12 trial-slicing components |
| `tca12` | 12 nonnegative CP components |
| `mixed_slice12_1` | 12 trial-slicing and one time-slicing component |
| `lfads` | Independently supplied complete output and provenance; currently unavailable |

Rank axes are explicitly **trial, neuron, time**. The source `[12,0,1]` is the
paper's neuron/trial/time `(0,12,1)`. Each exported slice family contains a vector
and a matrix over the other two axes. Outer products reconstruct the native
tensor; sums and arbitrary explicitly selected components use the same arithmetic.
The mixed model produces full, trial-only and time-only reconstructions separately.
Figure 2e's successful mixed movement readout uses the **trial-only** partial
reconstruction. A generic author `1201` object does not identify that choice.

Factors must already be exported as nonnegative values. The author transforms
each latent factor with absolute value before its product; rectifying a summed
reconstruction is not equivalent. No SVD, rotation or guessed gauge is applied:
the paper's hierarchical uniqueness procedure is explicitly for unconstrained
sliceTCA, whereas Figure 2 is nonnegative. Component order, scaling, decomposition
between types and historical identities remain unresolved.

`mixed_optimizer_recipe` records the released notebook's three 149-update phases
(447 updates), learning rate 0.02, omitted-entry fractions 0.8/0.4/0.2, mask refresh
every 20 updates, reset Adam/seed per phase, and seed roster 0–9. Its separate
`paper_described450` route changes the phase counts to the paper-described 150;
this is a declared configuration variant, not proof of a complete historical
paper recipe. The source notebook's six-item result unpacking disagrees with the
pinned seven-item return and can mistake loss history for final MSE. Named
callback outputs avoid inheriting that ambiguous tuple interpretation.

## Original decoding and condition-average paths

`fit_linear`, `fit_velocity`, `predict_positions` and `repeated_decoding` construct
actual predictions rather than only accepting precomputed tensors. Every call
must declare `source_code_ridge1` or `paper_ols0`. Source ridge alpha 1 penalizes
the appended constant as well as neural coefficients. OLS uses least squares.
The functions are executable numerical producers; no authentic fitting is implied
by their presence or by generated numerical tests.

The original neural `[55:-15]` and movement `[65:-5]` slices give 80 bins with a
ten-bin/100-ms lag. Train on 79 adjacent displacements, then integrate from the
true initial held-out hand position. The existing scorer retains coordinate-wise
centering and pools XY residuals within each trial. All five folds and twenty
repeats remain: 5,300 straight test occurrences and 4,900 curved occurrences.
One curved trial stays in training throughout each repetition. Folds/repeats are
dependent; they are not additional animals or independent uncertainty samples.

`condition_average_control` follows its distinct released route: split first,
average neural and movement observations within each angle separately in each
half, fit on one half and reverse orientation. It preserves twenty cumulatively
composed permutations and the global MT19937 state left after the final curved
single-trial call. Each straight orientation trains on 132 and tests on 133
trials, so its middle permuted trial is held out twice and trained on neither
side in that repetition. Curved halves are 123/123. This yields condition-wise,
not single-trial, scores. A condition missing from one half fails explicitly.
The whole-dataset averaging helper is not substituted for this control.

The result family retains source helper population SD and separately named
descriptive SEM conventions with ddof 0 and 1. The Figure 2 caption says SEM,
but the inspected helper's SD return is not what the plotting call consumes.
The plotting aggregation itself is absent from the inspected cache. Neither
SEM convention is asserted to reproduce the historical bars or provide a
confidence interval.

## Component results and paper/code differences

`component_results` exports trial weights, neuron×time slices, peak-bin ordering,
the preparatory time profile and trial×neuron slice, explicitly condition-ordered
correlation matrices and target projections. `preparatory_subspace` supplies the
released Figure 2h LDA-plus-target-regression axes and a separately named
whole-span orthogonal option. No plot display normalization or x-axis compression
is applied to scientific tensors or scores.

| Question | Released route | Preserved paper/source limit |
| --- | --- | --- |
| Physical decoding window | Exact 80-bin indexed support | Methods describe −250 to +450 ms; those indices are not silently relabelled |
| Region correlations | Columns 0:92 and 92:182, explicitly labelled source groups | Paper says M1=90/PMd=92; a biological neuron-region map remains unavailable |
| Target projection | Same-stratum ridge on raw time-slice factor matrix | Paper describes OLS on −0.75 to 0 s averaged partial activity and fivefold decoding |
| Paper partial-average target route | OLS on `mean(time_factor[explicit_bins]) * slice` | Caller must supply bins; physical binding and historical crossvalidation remain unqualified |
| Preparatory axes | In-sample LDA plus no-intercept target regression; optional orthogonal basis of their whole span | Not equated to the paper's target axes orthogonalized to curvature |
| Factor gauge | Preserve supplied factors | Ridge target projection can change under reciprocal factor scaling even when reconstruction is identical |

For correlations, the source condition order is
`20,22,10,34,18,39,32,5,37,35,26,31`, separately within reach type. It is not
numeric condition sorting. Target projections center target positions over all
511 trials before stratifying, as the released code does. Source region groups
are emitted only with the explicit `source_code_92_90` route; selecting
`paper_counts_unbound` emits whole-population correlations without inventing
region membership.

`source_result_family` connects all available models, named mixed partials, raw
condition averaging, components and preparatory axes to the existing endpoints.
It lists every missing required comparator, including LFADS. Missing references
never become fabricated model outputs. `score_reconstruction_cell` connects an
explicit original-shape target, reconstruction, fixed training mask and cut to
the original blocked root-error scorer. Original masks, rank grids, seed outcomes
and full numerical curves remain external requirements, separate from stochastic
optimization masks. Figure 4's different-dataset PCA/FA controls are not added
to this Churchland comparison.

Dependencies are NumPy and SciPy; the optional preparatory-subspace function also
uses scikit-learn. No dependency is installed by this component. The adjacent
`source-endpoints-v1/endpoints.py` is hash-pinned and must remain present. Source
readiness, actual original finding reproduction and improvement are separate:
no model callback, input receipt or successful unit test establishes a paper win.

## Verification commands

From this component directory, run the generated controls with:

```sh
python3 -m unittest discover -s tests -v
```

An optional, separate comparison executes only hash-pinned, named author
functions on generated numeric arrays. It requires an existing source cache,
fits linear decoders only on generated data, and never imports the author
repository, opens authentic data, downloads a file or fits a decomposition:

```sh
python3 tests/compare_author.py \
  --author-source-dir /existing/pinned/source-scope-v1 \
  --output /operator/new-generated-author-comparison.json
```

The numerical comparison preserves all 511 generated trial positions and the
full twenty-repeat/five-fold and two-half schedules, with a smaller feature
dimension for bounded validation. It checks equations and source scheduling;
it does not reproduce the paper's empirical scores or validate a historical fit.

[Validation receipt](VALIDATION.json): 18 generated controls passed. The pinned
author comparison matched the complete repeated single-trial R² arrays within
3.6×10⁻¹⁵ and the distinct condition-average arrays within 1.1×10⁻¹⁴. Source and
numerical reviewers separately accepted this implementation. These are generated
numerical compatibility results; authentic preparation, reference fitting and
empirical paper scores are not established by this receipt.

## Authentic input preparation

The separately admitted input-only operation subsequently completed once on
2026-11-17. It authenticated all six originals and prepared all 511 trials,
182 neurons and 150 bins in 0.620 seconds, with 506,609,664 bytes peak child RSS.
No decoder, decomposition, scientific score or candidate was run. A separate
saved-artifact audit verified hashes, complete array support, source row order,
finiteness and every neuron's normalized minimum/maximum. The private outputs
remain outside Git.

[Authentic preparation receipt](AUTHENTIC_PREPARATION.json) distinguishes exact
retained size (57,055,115 bytes), allocated filesystem size and the conservative
58,103,691-byte logical-write charge. The latter includes a stated 1 MiB allowance
for NPZ/header rewrites; cumulative and physical I/O were not directly measured.
The operation used a 150-second total pool deadline including queue time, the
narrower bound established by root admission. This closes authentic input
preparation while the model/reference and paper/code qualification limits above
remain unchanged.
