# Dentate event encoding: initial evaluator v1

[Task implementation note](../../docs/initial-evaluator-v1.md) · [Pinned source provenance](source-provenance.json)

This package implements a complete **prospective within-cell encoding analysis** from a declared JSON export of ErasmusAttn trial fields: source-informed trial normalization, spike/event binning, eye nuisance assembly, paired Poisson model fitting, nested contiguous trial-block validation, and held-out likelihood reporting. It is an implementation component for `PAPER-FIND-ADD-005`, not a scientifically qualified benchmark or a completed paper reproduction. Authentic MATLAB archive import and behavioral decoding remain unresolved.

The source model and this alternative have important differences. The pinned author fitter uses a hierarchical group-lasso category model; this evaluator uses ridge-penalized directional harmonic interactions and includes eye covariates. Its focal contrast is incremental **gap-direction encoding conditional on event, eye, previous-trial direction and subsequent saccade information**. Because subsequent saccade information is available to both encoding models, this is a retrospective conditional encoding endpoint, not an online stimulus or behavior predictor or causal attention estimate. A direct attention contrast has not been frozen.

Runtime: Python 3.10+ and NumPy; no SciPy or MATLAB dependency is used by this package. No dependencies are installed by the evaluator. Input data and official MATLAB code are not bundled.

```sh
python3 evaluator.py --input trial-export.json --output evaluation.json
python3 -m unittest discover -s tests -v
```

An optional `--config config.json` overrides named `Config` fields. Every output records the effective configuration. Defaults are prospective construction choices unless specifically attributed below. These configurations are not interchangeable leaderboard submissions: no grader threshold, protected target, or binary reward is registered.

## Input bridge

Input has `schema: "erasmus-source-trials-json-v1"`, `source_commit: "130f5e64f86bd63980f70bb839c02cd264782aef"`, and a nonempty `cells` array. Each cell contains nonempty string `monkey`, string `cell_id`, and `trials`. These are source names, not generated session identities. The commit field is a declaration, not proof of payload identity. The CLI records the exact input-file SHA256.

Each trial uses these author-field names:

| Field | Interpretation |
| --- | --- |
| `trial_nr` | Unique integer within the animal/cell; chronological order is sorted by this value. |
| `fixon2fixon` | Integer trial duration in ms. |
| `condition_code` | 0 aborted, 1 error, 2 correct, 3 omitted reward, 4 random reward. |
| `SS` | Array of spike times in **seconds**, relative to fixation for task trials. |
| `fix_on`, `cue_start`, `cue_stop`, `c_start`, `c_stop`, `choice_target`, `reward_start` | Scalar event times in **ms**. |
| `saccade_landmarks` | Array in ms; first entry is onset. Empty means unavailable. |
| `gap_direction` | Finite direction in counterclockwise degrees from source north; harmonics use modulo 360. |
| `reward_duration` | Nonnegative duration; zero removes the reward event. |
| `event_presentations` | Nonempty array of nonnegative integer event counts. |
| `n_minus_1` | Original prior-trial object with `condition_code` and `gap_direction`; never recomputed after exclusions. |
| `eyeX`, `eyeY` | One-ms arrays; fixation starts at MATLAB index 4000 (Python index 3999). JSON `null` denotes unavailable samples. |
| `trial_start` | Integer ms, required for condition 4 source normalization before exclusion. |

Other source fields, including `direction_C` and `saccadeAmplitude`, may be present but are not this contrast's predictors. The source data are a MATLAB structure; exporting that structure to the declared JSON format, verifying its schema and matching every source unit/session remain explicit unresolved admission steps. There is no automatic MAT loader or invented session reconstruction. Duplicate trial or animal/cell keys fail. Unknown/malformed numeric input fails; no missing neural observations are fabricated.

## Source-informed assembly

The independent source inspection is pinned in [source-provenance.json](source-provenance.json). Author identities and licenses remain distinct from the prospective model choices.

* The paper methods use 25-ms bins; the converter defaults to 50 ms. This package defaults to 25 ms and records overrides.
* Spikes are multiplied by 1000, excluding negative times and times whose MATLAB-style rounded millisecond is at least the trial duration. The bin index follows author `(t == 0) + ceil(t/bin_ms)`: zero is in the first bin, a spike exactly at 25 ms remains in that bin, and 25.001 ms starts the second. Repeated spikes accumulate counts.
* `delay_start = c_stop + 100`; the first saccade landmark defines onset. Error trials reverse current or previous gap direction by 180 degrees to derive saccade direction.
* Missing `n_minus_1` excludes the whole cell. Source exclusions include duration below 1 ms, negative `c_stop` on conditions 1/2, repeated events, empty original or clipped spike trains, current/previous conditions outside 1/2, cue after 1000 ms, missing saccade onset, and adjacent retained events separated by no more than one bin. Every excluded trial/cell is reported.
* **The source's removal of empty-spike trials conditions this retrospective estimand on spike-containing trials.** This is not a whole-recording zero-inclusive forecasting score. The package does not silently replace this source policy.
* Additional prospective quality rules require in-range required event times and complete finite eye support. Eye prefix samples outside the trial can be null. The source pads absent eye samples and invokes an unavailable `rebin` helper; this evaluator excludes incomplete in-trial support, averages each bin explicitly, and uses the actual final partial-bin exposure. Native trailing-bin/NaN equivalence remains unverified.
* Six event kernels match the fitter: fixation, C onset, delay onset, choice-target onset, saccade onset and reward onset. Five progressive cosine `x1.5 off0` functions span 1500 ms; each sampled column is normalized to maximum one, following the pinned formula. Events use source bin placement and each convolution stops at its trial boundary.

## Prospective paired models and evaluation

The reduced model includes six event-kernel sets, mean x/y eye position, previous gap and previous saccade sine/cosine interactions with the fixation kernel, and current saccade sine/cosine interactions with the saccade kernel. The full model adds current gap sine/cosine interactions with C-onset and delay kernels. This fixed harmonic factorization is a new analysis choice; it does not reproduce the author's categorical hierarchy or variable-selection procedure. The choice tests residual directional modulation after specified event/eye/history/movement terms while keeping the paired design tractable and fully auditable. It cannot eliminate unmeasured nuisance variables.

Both models use log-link Poisson counts with log(bin-exposure seconds) as an offset. The intercept is unpenalized; other coefficients receive ridge penalty. Standardization is fitted only to training bins. The average negative Poisson log likelihood (excluding its coefficient-independent factorial constant during optimization) plus half the ridge norm defines the objective. A damped Newton solver requires convergence; it rejects all-zero training targets, nonfinite inputs, singular solves, overflow and nonconvergence rather than issuing a score. Reported likelihoods include `lgamma(y+1)`.

Defaults are five outer contiguous trial blocks and three inner blocks with a one-trial exclusion guard around each held-out block, based on the complete original trial order including subsequently excluded rows. All bins from a trial remain together. Inner training fits its own preprocessing and selects among penalties `[0.01, 0.1, 1.0]` by pooled validation log likelihood per bin; exact ties prefer the larger penalty. Each paired model selects its penalty independently using the same folds. Only outer training is refitted, and each admitted trial receives one outer held-out prediction. Configurations lacking sufficient training trials after guards fail visibly.

The author's response-derived five-trial moving-average baseline is not included: it is computed before validation in the pinned script, whereas this prospective endpoint must not construct test predictors from held-out spikes. The null rate here is estimated solely from outer-training counts and exposures. Author hierarchy, moving-average equivalence, figure modulation indices and MATLAB/SPAMS execution remain separate work.

The primary prospective quantity is `(LL_full - LL_reduced) / total_held_out_spikes`, in **nats per spike**. Both likelihoods score identical admitted outer bins; positive values favor the added directional terms. Total likelihoods, Poisson deviances, deviance explained against the outer-training-rate null, per-fold training indices/scaling/coefficients/penalties, and all outer predictions are retained. A zero denominator is undefined, never silently scored as zero. Descriptive cell means and separate animal summaries are provided without uncertainty or population-generalization claims. They cover admitted input cells only; no complete cohort is inferred from a successful input file.

## Qualification boundary

The paper reports 305 neurons from two macaques (Mi145, Mo160); those are primary-source statements, not a verified acquired population. No authentic data were acquired or evaluated during construction. The generated tests check engineering semantics and leakage controls; they do not establish scientific reproduction, competence, difficulty or a resource envelope for the authentic archive.

Remaining gates include exact direct attention contrast, source population/session mapping, MAT import, independent behavioral decoding, native environment and helper qualification, author-equivalent regularization and hierarchy, figure reference/tolerances, protected evaluation, source-exposure comparison, full data/component rights reconciliation and measured authentic runtime. `scientific_qualification` stays `unknown`, `paper_reproduction_established` stays false, and `benchmark_complete` stays false in every report.

The source basis and field rules are attributed to Sue Ann Koay and the ErasmusAttn_2020 authors, pinned commit `130f5e64f86bd63980f70bb839c02cd264782aef`, whose code license is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The NumPy implementation changes the fitting method, nuisance terms, contrast and validation as described above. No author source files, archive content or license rights for other dependencies are silently incorporated.
