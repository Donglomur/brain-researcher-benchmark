# Original spinal-calcium endpoint metrics

This component computes per-neuron Pearson correlation on an already prepared,
uniformly sampled source condition. It retains the five approaches in Figure 4:
raw fluorescence, OASIS, cortical/default CASCADE, glutamatergic-trained CASCADE,
and GABAergic-trained CASCADE. Both spinal models are necessary because the
cross-dataset model is a separate original control. An optional candidate adds
paired correlation differences against the matching spinal model, or default
CASCADE for the separate cortex cohort.

Reproduction and improvement are separate outcomes. With no candidate, the
result contains the five reconstruction method scores. With a candidate for
every neuron, it additionally contains candidate scores and paired differences.
Neither output establishes successful reproduction or improvement: the exact
published baseline vectors, source preparation, numerical parity tolerances and
improvement decision rule have not been recovered or qualified.

## What executes

`metrics.py` uses only the Python standard library:

- `score_neuron` scores one neuron on one fixed operator-selected set of bins.
  It converts CASCADE expected spikes per bin to Hz before absolute-rate
  diagnostics. A Pearson score alone would miss an incorrect factor of 30 at
  the paper's 30 Hz comparison.
- Every method uses identical support. Missing/nonfinite predictions inside
  support are errors; they cannot silently remove difficult bins. Nonfinite
  context outside support is allowed. Constant traces and insufficient support
  have explicit undefined outcomes, not invented zero correlations.
- Normalized L1 and signed bias remain separate diagnostics for calibrated
  rate methods. Raw fluorescence and OASIS retain correlation only because the
  article does not calibrate their amplitudes to spikes. The diagnostic formulas
  are `sum(abs(prediction-target))/sum(target)` and
  `sum(prediction-target)/sum(target)` on the supplied rates.
- `score_condition` requires exactly the operator's frozen neuron identities,
  retains every per-neuron result, and summarizes neurons equally within each
  cohort. It never pools time bins, cell types, sampling rates or noise levels.
  Means and medians are descriptive; undefined counts remain visible. It does
  not calculate a significance test or decide a paper win.

The primary correlation receives the already smoothed target and aligned
prediction unchanged. The component does not resample, add noise, smooth a
second time, optimize a delay, clip outputs, fit a model or infer a support mask.
The current author demo's additional smoothing of error/bias operands is not
silently adopted. Thus the diagnostics here are transparent single-pass
diagnostics; they are **not** qualified numeric reproduction of that demo's
error/bias columns. Primary Pearson is the recoverable original endpoint.

## Operator interface and limits

`Prediction(values, unit)` accepts `hz` or `expected_spikes_per_bin` for the three
CASCADE controls and candidate; raw fluorescence and OASIS use `arbitrary`.
`score_neuron` takes `target_hz`, `controls`, `support`, `sampling_rate_hz` and
optional `candidate`. `controls` has exactly the five keys listed in
`SOURCE_CONTROLS`. `support` has one literal boolean per original bin.

`score_condition` additionally accepts `expected_neurons`, mapping frozen neuron
IDs to `glutamatergic`, `gabaergic` or `cortex`, and `observations`, one object per
neuron containing `neuron_id`, `target_hz`, `controls`, `support`, and optional
`candidate`. Candidate coverage must be complete or absent. Pass each original
condition separately and retain its source configuration alongside the result.
This low-level API intentionally does not accept a claimed paper-condition
label as proof that its arrays have the corresponding sampling, smoothing,
alignment or noise provenance.

For improvement, the operator must choose/freeze controls independently of the
candidate and supply them separately. The API prevents a candidate field from
replacing a control, but it does not authenticate the caller, model training,
bytes, access arm or scientific competence. Reproduction submissions also need
an independent named-algorithm execution audit. The paired paper+data and
paper+data+author-code arms must use identical scientific conditions and be
reported separately; this component does not deliver either arm.

## Primary-source audit

The locally cached article and source were inspected as text; no raw recordings,
electrical targets, historical private solver answers, weights or predictions
were opened. Exact cached-source SHA-256 identities are in `SOURCES.json`.

The [article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12044035/) specifies:

- Figure 4d–f: 30 Hz, standardized noise 7, 21 glutamatergic neurons, 23 GABAergic
  neurons and a separate 80-neuron cortex comparator. Its five-method analysis
  follows dataset-wide systematic delay correction.
- Methods: target Gaussian SDs of 0.4, 0.2, 0.1, 0.1, 0.1, 0.05 and 0.05 seconds
  at 2.5, 5, 10, 15, 20, 25 and 30 Hz, respectively. These are recorded in
  `SOURCE_SIGMA_SECONDS` for operator inspection, not applied to caller arrays.
- Figure 4g–h and Extended Data Figure 4-3: retain both cell types' sampling/noise
  sweeps, and keep the matched-temporal-precision control distinct. This metric
  component does not claim to recover every noise value or its realizations.
- Retrained within-dataset models exclude the held neuron and all its
  recordings. High-rate inhibitory training exclusions need exact recovery;
  assessment membership must not be inferred from a convenient filename glob.

The preserved current source at commit
`1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f` uses a `2,4,6,8` demo noise grid and
announces a later one-timepoint correction. Neither is evidence of the original
paper configuration. Its `*_mini.mat` selection omits four released filenames,
including one excitatory filename, as recorded by the prior source audit. The
article also has an apparent direction inconsistency in its resampling-admission
sentence; exact source-era behavior must be resolved, not guessed here.

The historical local `prospective_native_400ms` condition uses native grids,
no artificial noise and time-weighted metrics. It remains a distinct extension.
This new code does not relabel that prepared data as the original 30 Hz/noise 7
condition, and does not alter any historical definitions or evidence.

## Qualification and verification

This is a software-tested metric component, not a complete executable original
paper benchmark. The full original condition roster, source-era neuron/recording
mapping, alignment/edge masks, noise realizations, exclusions, exact baselines
and paired uncertainty rule remain unresolved. Cortex and the complete sweeps
remain required by the original comparison; small test fixtures are not a
reduced benchmark. No authentic preparation, model execution, empirical score,
reproduction success, improvement or SOTA result is established.

`test_metrics.py` exercises analytical numerical controls, unit mistakes,
missing cross-dataset controls, fixed support, undefined cases, equal-neuron
aggregation, complete identity coverage, distinct reproduction output and
candidate/control separation. Tests use generated small vectors only. During
the parallel construction wave, run them exclusively through its shared
two-slot `test_pool.py`, with one thread and the declared resource limits.
