# Complete original rat GLM and geometry producer

This additive implementation closes the missing source-production route for
`PAPER-paper-method-add-006`. It fits all **108 basis configurations**, all ten
Poisson regularization candidates and ten contiguous folds for every eligible
unit across **eight rats × eight sessions × two regions**. It also produces
the raw-activity geometry, empirical/theoretical readouts, GLM participation
ratios, complete learning/behavior arrays and original mixed-effects trends.

**Status:** source implemented and tested with generated controls. No authentic
full-grid fit, authentic readout/trend fit, candidate attempt, paper reproduction,
improvement or SOTA result is established by this component. The full-run resource
cost is unmeasured. Authentic execution needs its own admitted compute/storage
protocol; these instructions are not evidence that such a run occurred.

## Source and preserved scope

The [primary paper](https://doi.org/10.1038/s41593-025-02183-y) defines the scientific scope.
The inspected author revision is `9674a6cb0c39926d70746024ce17de35f87df8f9`.
Author `fit-GLMs-rat.py`, `rat_utils.py`, `process_rats.py`,
`run-pfc-hp-analysis-rats.py`, `utils.py` and the retained figure cells define
the operations. This code reimplements the algorithms and reuses the existing
benchmark's numerical kernels; it does not vendor the unlicensed author files.

The explicit current animal order is KL8, ER1, JS34, JS14, JS17, JS21, JS15, ZT2.
Each contributes eight retained sessions and CA1/PFC. Source geometry used an
unsorted file glob, so this declared order is not an authenticated historical
random realization. DANDI version `000978/0.240511.0307` and the selected-field
source inputs remain unchanged. The cached nine HDF5 selections are 458,747,136
bytes, not complete copies of the 322.98 GB source archive. This producer reuses
the already prepared 128 regional packets; it does not rebuild the NWB parser.

`native_inputs.py` validates the full roster and byte/SHA256-bound numeric
packets, retaining actual asset IDs, source epochs, unit IDs, bin times and trial
IDs. The old design's `units`, `unit_ids` and `strict_columns` describe a separate
prospective training filter and **do not select native units**. Native units come
from the complete packet arrays and the source's own rate mask.

The optional frozen `TRIAL_COVERAGE.json` receipt binds all 128 complete original
trial sets. Its SHA256 is
`82cf82f172ebbe00908517f6bef429f30eb0ec3904f225da9e761aa3282f473d`.
It binds original DESIGN SHA256
`fd4904ed7a96fb57b32eee36c50e859f1c69fd16c0614f5ff60a6985d8bb3da4`;
the independently recorded unchanged-packet successor DESIGN.v2 is
`5ff7542d9d78aee6f86a4d97fa8e535882c3b582ac45aba5b4fdb5c026bde403`.
The loader checks the receipt, every case, loaded packet pin, distinct-trial
count and within-trial correctness. This permits the original equal-trial mean,
rather than a duration-weighted mean of bins. Without that proof, behavior is
explicitly unavailable. The older PREPARATION001 source hash alone does not pin
the subsequently added complete-trial guard. Authentic anatomical/epoch mapping
still needs independent qualification against the selected NWB fields.

## What runs

`glm_search.py` enumerates 13,824 source-coordinate jobs. Each uses the exact
product order `(5,10,15) × (3,6,12) × (10,50,100,150) × (10,40,80)`,
`np.logspace(-.5,2,10)` alphas and unshuffled ten-fold sklearn CV. Recorded speed
is strictly greater than 4 cm/s, firing rate strictly greater than 0.1 Hz in
500 ms bins, and basis-center count strictly greater than 20. Position is centered
separately within each eligible session; basis centers pool all eight sessions
for that rat. Gaussian covariates are standardized on the whole eligible session.
These are the source exposures, not train-only or protected transforms.

Each unit uses actual `GridSearchCV(PoissonRegressor(), error_score='raise')`.
Refit is exactly **nanmean then ordinary argmax**, including its unusual all-NaN
alpha behavior; it is not replaced by finite-only or `nanargmax` selection.
Fold statistics count non-NaN values, preserving infinities. Fit/scoring errors
abort and leave failures visible; convergence warnings are recorded without
being silently changed into errors. Execution is serial, retaining the estimator
defaults (`lbfgs`, 100 iterations, tolerance `1e-4`).

The source's `xhat` is the selected-alpha refit on all eligible rows. That remains
`predictions`. Ten additional selected-alpha refits produce `oof_predictions` for
the existing scorer. Those extra predictions still have all-fold hyperparameter
selection and full-session preprocessing exposure. They are not historical saved
source predictions, nested CV, or independent held-out performance. Fit counts
are explicit: 101 source fits plus ten OOF extension fits per unit/configuration.

The finalizer requires all 13,824 jobs. It emits all 216 region/configuration
scores using the source `nanmean` of 64 ordinary per-unit session means. The
active figure code fixes basis `(10,3,100,40)`; its across-basis winner-selection
lines are commented out. The implementation therefore exports the entire search
and its scores but invents no historical winner. Regional 0.29/0.25 D² anchors
remain supporting results, not the primary biological success criterion.

`geometry_results.py` preserves the separate geometry speed mask: norm of the
derived velocity components strictly greater than 4. It retains 19 neurons in
both regions, 500 observations, 300 training observations, 500 Gaussian teacher
tasks and 500 repetitions. The complete panel has 64,000 geometry jobs.
Task-balance filtering sees all 500 observations, including eventual test rows.
Raw activity supplies the geometry and readouts; full-row GLM predictions supply
the expected-count participation ratio. They are not conflated.

The named current stochastic route is `current_serial_seeded_v1`. All seed,
teacher, training, row and unit identities are recorded; classifier seeds are
derived without consuming the main region RNG. The exact recipe is in
[RNG_POLICY.json](RNG_POLICY.json). The literal `source_random_state_none`
callable remains separate. Historical parallel-worker RNG parity is false.
Reference and candidate comparisons must reuse the same frozen task/seed
manifest; a candidate cannot redraw tasks after observing its results.

Complete reduction preserves the 500×8×8 readout/geometry arrays per region,
raw/expected participation ratios, session trajectories and descriptive
behavior/theory Pearson R². Eight rats remain eight independent animals; 64
sessions are repeated observations. A separate `trends` operation implements
all 14 original random-intercept linear/quadratic MixedLM fits, default `.fit()`
options and the original joint 24-test BH correction at alpha .01. Larger effects
or smaller p-values are not defined as scientific improvement.

## Saved artifacts and entry points

`producer.py` binds every checkpoint to the source code, input design, runtime,
grid, alpha bytes, cohort and stochastic policy. It stores typed numeric/string
arrays with JSON metadata, rejects object/pickle payloads, records nonfinite
source statistics explicitly, checks expanded as well as retained byte limits,
and refuses to overwrite existing output. Complete checkpoints can resume only
with identical bindings. Geometry checkpoints also enforce the exact continuing
MT19937 state. Partial/incomplete output remains incomplete and is not skipped.

The GLM/readout runtime is deliberately frozen to NumPy 2.2.6, SciPy 1.15.3 and
scikit-learn 1.6.1. The specified current MixedLM backend requires
statsmodels 0.14.5, pandas 2.2.3 and patsy 1.0.1; the author did not pin its
historical statsmodels runtime. Wheel-lock verification and the actual hosted
numerical control are separate admission steps. No local installation is
performed by this component.

From this directory, `python -B producer.py plan` describes the full scope without
loading inputs or fitting. The explicit future operations are:

- `glm`: all 13,824 jobs, or a numbered checkpoint range using `--start/--stop`.
- `geometry`: the full 64,000-job current seeded route, with state-bound resume.
- `reduce`: require the complete GLM and geometry trees; emit full figure arrays.
- `trends`: consume that full reduced panel; fit all 14 source trends and BH family.
- `oof`: export all 64 paired-region sessions for an explicitly chosen basis.

Execution operations require `--prepared-directory`, `--design`,
`--design-sha256`, `--output` and `--max-result-bytes`; behavior additionally
requires `--trial-coverage`. Reduction requires `--glm-directory`,
`--geometry-directory` and an explicitly frozen `--glm-pr-seed`, because the
original figure's PR draws were unseeded. Trends require `--panel-result`;
OOF requires `--glm-directory` and `--basis-index`.

OOF export emits `REFERENCE.json`, `AUTHOR.json` and safe numeric prediction
files accepted directly by `../oof-prediction-replay-v2/replay.py`. A candidate
must supply its own aligned prediction manifest. The retained scorer preserves
per-unit/fold D² and explicit undefined-fold statuses, with `population_d2=null`;
this producer does not invent an unresolved regional/null-unit aggregation.

## Controls and limits

Generated controls exercise independent actual sklearn alpha-search/full-refit/
OOF numerical parity; source NaN/tie/infinity/error/warning handling; all 108
configurations and all 128 cells; native identity and malformed-array refusal;
complete 64-session export into the existing scorer; real generated SVC readouts;
seed-stream isolation; original PR/geometry formulas; and full-panel/trend/FDR
construction. Mocked large-panel dispatch and MixedLM-call controls are labelled
as such; they do not substitute for genuine numerical seams.

Run the ordinary generated suite with
`python -B -m unittest discover -s tests -v` in the compatible existing environment.
The required, separate native suite is
`python -B -m unittest discover -s native_tests -p test_mixedlm.py -v`.
It uses real MixedLM on a generated eight-rat/eight-session panel and an independent
balanced-design OLS oracle; a missing dependency fails instead of skipping. Its
hosted execution is separate from the local generated checks and must be observed
before claiming that seam passed. Neither suite reads original signals.

Remaining scientific limits include the paper's CA1 24-neuron versus active-code
19-neuron discrepancy, 0.48 versus caption 0.49 behavior/readout R², unrecovered
historical file/RNG/runtime identity, source null-unit regional aggregation,
independent NWB identity qualification, public-data exposure/rights and authentic
comparator execution. Passing CI does not remove these limits or establish
benchmark readiness, reproduction, improvement or a broader SOTA result.
