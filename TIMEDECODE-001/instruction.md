# Within-recording modality decoding (TIMEDECODE-001)

Compute two explicitly different auditory-versus-visual decoding estimates from
the original MNE sample recording. This is a **fixed-recipe method control**, not
a numerical reproduction of a paper finding or evidence of generalization to new
people or sessions. Gramfort et al. (2013), §3.3/Figure8/Table3 demonstrates left-only
per-time SVC decoding; this task instead pools left/right stimuli, uses logistic
regression and compares pooled-time with separately fitted per-time models.

## Original inputs and public method

The offline source root is `/app/data/timedecode`. Its `source_manifest.json`
identifies the original OSF version6 archive, both publisher-provided archive
checksums and exact selected member checksums:

- `MEG/sample/sample_audvis_filt-0-40_raw.fif`;
- `MEG/sample/sample_audvis_filt-0-40_raw-eve.fif`;
- `version.txt`.

Check source identity before analysis. This is an already filtered/downsampled
released recording, not untouched high-rate acquisition. Do not fetch data,
substitute a toy cohort, repair samples silently or change the provided files.
No unrestricted recording/image redistribution permission is established.

`/app/method_contract.json` is the complete public estimator, schema, tolerances
and failure contract, including exact metadata fields. Read it before analysis.
The essential choices are:

1. Stimulus codes1/2 are auditory0; codes3/4 are visual1. Preserve every supplied
   original event row and absolute sample index in a selection/rejection ledger.
   Other event codes are recorded but are not classifier observations.
2. Select original gradiometers in source order, excluding original bads. Use
   source SSP only: the supplied vectors cover mag/EEG, so the selected-grad
   projection is identity; do not claim it cleans these gradiometers.
3. Epoch−0.2…0.5s using rounded integer source-sample offsets, inclusive endpoints;
   subtract each channel's epoch baseline mean through time0 inclusive. No added
   detrend, filter, resampling or decimation. Keep native150.15374755859375Hz;
   directly decimating by2 would put Nyquist below the released40Hz low-pass.
4. Reject a target epoch if any selected channel's full-rate peak-to-peak range
   is **strictly greater than4e−10T/m** over the full epoch. Preserve its original
   event identity and measured rejection evidence. Follow the public handling
   of out-of-bounds/annotations/nonfinite inputs. Do not force historical counts.
5. Retain exact native times within0.05…0.45s. Each retained trial has one label.
   Use `StratifiedKFold(5, shuffle=True, random_state=42)` on chronological
   retained trials, not flattened trial-time rows. Reuse this trial-fold mapping
   for **both** estimators and every latency. At least five trials per class
   must survive; otherwise fail explicitly.
6. For each model, fit feature means and population standard deviations on its
   own training observations only (`StandardScaler` constant-feature behavior).
   Fit binary L2 logistic regression with C1 and an unpenalized intercept:
   `sum(logaddexp(0,z)-y*z) + 0.5*sum(w*w)`, where `z=X_standardized@w+b`.
   The public reference uses newton-cholesky, tol1e−10, max_iter100. Equivalent
   converged solvers are acceptable; finite mean-objective gradient infinity
   norm must be≤1e−9. Preserve fitting warnings; do not suppress convergence
   failure. Predict visual1 for signed score>0, auditory0 otherwise.
7. **Pooled:** one model per fold, trained on every analysis-time row from its
   training trials (trial-major/time-minor ordering), evaluated on all time rows
   of held-out trials. **Per-time:** separately fit one model at each latency
   and fold, using training trials at that latency alone. Neither is a
   train-time×test-time temporal-generalization matrix.

The headline is the **unweighted mean of five pooled-model fold accuracies**.
Also report its separately named all-OOF correct/total value. For each per-time
model latency, report both mean-fold and all-OOF accuracy. Unequal fold sizes can
make these summaries differ. Nominal uniform-guessing accuracy0.5 is descriptive,
not a required performance gate. No positive leakage gap or random-sample-split
analysis is required.

## Outputs

Write seven files to `${OUTPUT_DIR}` (default `/app/output`). Exact column/field
names and null conventions are public in `method_contract.json`.

- `source_epochs.csv`: all original event rows, modality, retained/drop status,
  compact retained-trial ID, full-epoch maximum PTP and its channel when defined.
  The `modality` column accepts `0` or `auditory` for event codes1/2, and `1` or
  `visual` for codes3/4, including rejected target epochs. It must be blank for
  non-target events. Numeric integral notation is accepted, but unknown or
  source-inconsistent labels are rejected. This encoding allowance is only for
  this descriptive ledger field; classifier `true_class` and `predicted_class`
  remain numeric0/1 as specified in the public method contract.
- `oof_predictions.csv`: the complete retained trial×time grid for **each**
  estimator, original event identity, native offset/time, true class, trial fold,
  predicted class and signed decision score.
- `per_fold.csv`: five pooled rows and five rows per latency for per-time models;
  keyed by estimator/time/fold, with train/test trial and sample counts, **trial**
  class counts, correct count and accuracy. Pooled `time_index` is blank.
- `decoding_timecourse.csv`: full native analysis grid and the **per-time** model's
  mean-fold `accuracy` and all-OOF `pooled_accuracy`; the latter name denotes its
  aggregation, not the pooled-time classifier.
- `decoding_results.json`: pooled-model headline and all-OOF accuracy, exact
  sample/trial/channel/fold support and class/guessing definitions.
- `run_metadata.json`: source/method file SHA256s; all listed source clock,
  channel/projector/event and epoch-overlap/support fields; honest software
  versions and numerical fit diagnostics. Counts are observations, not targets.
- `findings.md`: a brief actual-result summary distinguishing the estimators and
  the limits below. Wording is not keyword-graded.

Rows/columns may be reordered and harmless extra fields are accepted. Identities,
counts and integer-valued coordinates must match exactly. Signed scores are
compared with atol1e−5+rtol1e−6; reported classes must follow their own score,
including numerically equivalent near-zero decisions. Recompute all statistics
from those submitted decisions. Time tolerance is1e−10s, PTP tolerance is
1e−20+1e−7relative, and accuracy tolerance1e−6. Full scientific details and source
binding are checked; matching an approximate curve shape is insufficient.
Reward is all-or-nothing, not proportional partial credit.

## Interpretation and failure handling

One person/recording does not become a cohort because it has many trials, sensors
or time rows. Whole-trial folds prevent direct same-trial row splitting, but the
source event schedule is strongly structured and some adjacent full epochs and
prior-analysis/next-baseline windows share raw samples. This is **not fully
independent or universally leakage-free validation**. Do not claim a cognitive
onset, hardware comparison, new-person/session/latency generalization, or that a
lower score itself establishes a correct estimator.

For a failed source/precondition/convergence check, exit nonzero and write
parseable `run_metadata.json` and `decoding_results.json` with
`status="failed_precondition"` and a nonempty reason, plus `findings.md`.
Do not overwrite existing evidence or produce a partial grid marked successful.

Sources: [Gramfort et al.2013](https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2013.00267/full),
[King & Dehaene2014](https://doi.org/10.1016/j.tics.2014.01.002),
[MNE sample source documentation](https://mne.tools/1.12/documentation/datasets.html#sample).
