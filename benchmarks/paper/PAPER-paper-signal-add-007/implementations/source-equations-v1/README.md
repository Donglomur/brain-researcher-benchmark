# ICNet original Fig. 4 source-equation scorer

This implementation supplies the missing numerical endpoint for the original
seven-animal, four-sound, two-trial evaluation. It computes equation (3) from
sampled count predictions and equations (4)–(5) from expected-count predictions.
It retains the 28 animal/sound results and individual eligible-unit results.
It does not turn the legacy held-sound training folds into the paper task.

Reproduction and improvement are separate first-class outcomes under the latest
user instruction. This shared numerical component supports both future paths;
neither is evaluated here. The paper+data and paper+data+author-code participant
conditions must use the same prepared panel, scorer and exposure policy with
separate results. Constructing or testing this scorer is not a participant run
in either condition.

`scorer.py` is independently written from the paper equations. It is not copied
from the restricted-license ICNet implementation. The existing registered
runtime and historical records remain unchanged.

## Numerical behavior

For each animal and sound, let `r1,r2` be successive recorded responses and
`p1,p2` be sampled predictions from their respective measurement-time inputs.
Let `e1,e2` be expected counts under those same predictive distributions.

```
correlation_explained_percent = 50 * (corr(r1,p1) + corr(r2,p2)) / corr(r1,r2)
noise_variance = Var(r1-r2) / 2
variance_explained_percent = 100 * (1 - (mean_squared_error - noise_variance)
                                      / (mean_trial_variance - noise_variance))
mean_squared_error = (mean((r1-e1)**2) + mean((r2-e2)**2)) / 2
mean_trial_variance = (Var(r1) + Var(r2)) / 2
```

Fig. 4b flattens all eligible units and time within an animal. Fig. 4d evaluates
each unit across time. The scorer combines centered moments with the contribution
of different unit means, so its flattened result is not an average of per-unit
correlations. Blocks of up to 32 columns keep float64 conversion bounded; NPY
inputs are memory mapped and each animal/sound is processed separately.

Both trial-specific predictions are mandatory. Count observations and sampled
predictions must be nonnegative integers; expected counts may be fractional.
The scorer checks excluded columns for corruption, then applies the same supplied
source mask to all arrays. It never estimates a mask from evaluation outcomes.
Negative and above-100% results are preserved. Constant signals or zero
denominators produce JSON `null` with explicit diagnostics, not a silently
substituted zero or dropped unit. Negative reliability/variance denominators are
reported and flagged. No bootstrap confidence interval or new superiority
decision is inferred from the units.

The paper does not establish the executable variance divisor in the recovered
evidence. `variance_ddof` therefore has no default: 0 and 1 are supported and
recorded. In equation (4), MSE always uses its literal population mean. Use the same explicit divisor for both models in a prospective comparison.
Historical numeric parity still requires the original convention; its absence
does not erase the defined endpoint vector. Pearson correlation and the null
diagnostics above are implementation conventions, not recovered historical
algorithm choices. Neither supported divisor is asserted to be the author default.

## Recovered author interface pitfalls

Pinned ICNet revision `7a631f1779662ee70b1819ac0c9ce0191bcaf158` was inspected as
source only. Its helper does not implement the paper metric equations, so it
does not settle the variance convention or textual aggregation.

- `simulate_model_responses` samples a categorical distribution over counts
  0–4 and overwrites the probabilities before returning. Its returned sample
  cannot also serve as the expected-count input of equation (4). An authorized
  native adapter must retain the distribution to calculate its expectation.
- With `channel_CFs` supplied, the `animal_X` path sorts columns by frequency.
  Original MAT response columns must be joined to predictions explicitly; a
  raw positional comparison after that sort is unsafe.
- The helper docstring says hours, but its arithmetic multiplies `time_input`
  by `1/36000`, and the example labels its input as seconds. Zenodo also supplies
  seconds. The native adapter must follow the arithmetic and trial metadata,
  not multiply the stored seconds by 3,600 again.
- The example identifies infinite CF entries as low-reliability channels.
  This is a recovery lead for the eligibility mask, not verification of the
  exact 3,476-unit mask. No CF MAT file was downloaded or opened.
- The helper infers output length after removing 2,048 audio context samples;
  the demonstration pads sound to a multiple of 32. These are source mechanics,
  not a verified original evaluation crop or authorization to pad targets.

## Operator interface

Use `score_case` for an already prepared array tuple in this order:
`recorded_trial1`, `recorded_trial2`, `sampled_trial1`, `sampled_trial2`,
`expected_trial1`, `expected_trial2`. Arrays are **time × original units**;
the source MAT layout is animals × time × units. The API requires explicit
Boolean `eligible_mask`, unique ordered `unit_ids` and `variance_ddof`.

The full-panel CLI consumes a local operator manifest plus uncompressed NPYs:

```sh
python scorer.py --manifest /operator/panel.json \
  --input-root /operator/aligned-arrays --output /operator/scores.json
```

Keep the manifest, source arrays, predictions and resulting unit-level report
outside Git. The output path must be new. Run authentic preparation or scoring
only under the project's separate approved native protocol and resource lease.

The input schema is `icnet-source-equations-input/v1`, with these fields:

| Field | Required content |
| --- | --- |
| `variance_ddof` | Explicit integer 0 or 1 |
| `preparation` | SHA256 pins for `source_mask_sha256`, `alignment_protocol_sha256`, `prediction_freeze_sha256`, `measurement_times_sha256`; `mask_origin` = `source_broadband_noise_reliability`; `split` = `original_four_sounds_held_out_from_training` |
| `animals` | Keys `"3"` through `"9"`; each has 512 ordered `unit_ids` and a 512-element Boolean `eligible_mask`; exactly 3,476 eligible units across all animals |
| `cases` | Exactly one entry for every original animal × sound, 28 total |
| Each case | Integer `animal`; `sound`; integer `time_bins`; two `measurement_times_seconds`; `arrays` with all six array roles |
| Each array | `path` relative to the input root and `sha256`; shape `time_bins × 512` |

Sound names are `speech_in_quiet`, `speech_in_noise`, `moving_ripples`, `music`.
The source rate is 24,414.0625/32 neural bins/s. This scorer does not resample,
reorder, crop, pad, align or calibrate observations. The operator must recover
and verify the original crop, measurement times and ordered column identities.
The legacy 22,784-bin convention is not silently imposed as authentic.

The hashes and declarations retain provenance; they do not prove that a supplied
mask, identity list, alignment or candidate history is authentic. Independent
source preparation must establish those facts. Repeated training on any of the
four evaluation responses is incompatible with this same-task endpoint even
if an operator supplies an otherwise valid manifest.

## Evidence and qualification

The source is [Drakopoulos et al., Nature Machine Intelligence, 2025](https://www.nature.com/articles/s42256-025-01104-9),
Methods “Predictive power metrics”, equations (3)–(5), and Fig. 4b,d.
[Zenodo 12636772 v1](https://zenodo.org/records/12636772) identifies animals 3–9,
the four sounds, both trials and measurement-time metadata. Exact cached-evidence
hashes are in `source-pins.json`.

`test_scorer.py` uses generated count matrices only and checks the literal
equations against an independent Python `statistics` implementation, flattening
versus averaging, both variance conventions, trial/expected-count separation,
masking, alignment and unit mismatch controls, undefined values, complete panel
coverage and payload failures. These checks cannot establish model accuracy.

The accepted retained-source adjudication establishes the Fig. 4d time-only
per-MUA explained-correlation and explained-variance vector, both higher-is-better,
for the same units compared with a single-layer Poisson LNP. Fig. 4b separately
flattens eligible units and time within each animal. A universal scalar is not
required. Historical textual summaries, source boxplot implementation details
and exact stochastic replay remain separate reconciliation questions. The panel
report now carries this endpoint binding; numerical Eq. 3–5 kernels are unchanged.

Actual masks and original time/crop joins, authentic ICNet and LNP fits/rates,
source-reference predictions, development access, model selection and protected
exposure remain gates. A prospective comparison must state its common variance
divisor and stochastic policy. Historical numeric parity additionally requires
original conventions. The component makes no reproduction or improvement decision.

## Poisson LNP comparison

`lnp_comparison.py` adds a partial route from externally supplied LNP rates to the
same source metrics. It does not train the LNP, construct its acoustic features,
or authenticate a rate as the output of an original fit. The source comparator
has one convolutional layer (512 filters, size 64, stride 1, no bias), exponential
activation, a 96-band log-Mel/sigmoid front end and L2 factor 1e-5. Exact retained
source locators and the Methods Fig. 3d versus Results Fig. 4d citation conflict
are preserved in `source-pins.json` and the accepted adjudication.

The source LNP has no ICNet time module. A single rate matrix for a given animal
and sound is used as the expected count in both repeated trials. Two genuine
Poisson count draws use separately declared seeds. Counts retain int64 support;
they are never clipped to 0–4, normalized as five categories or cast through the
original int8 categorical adapter. PCG64/NumPy sampling is an explicit prospective
choice. It is not historical TensorFlow sampling or source-author seed recovery.
The underlying NumPy Poisson generator rejects rates beyond its numeric range.

`compare_case` accepts the six aligned arrays used by `score_case` plus the LNP
rate matrix, original mask/IDs, a common explicit `variance_ddof`, and two LNP
trial seeds. Its full same-unit vector preserves both models' metric values,
intermediates and diagnostics, with ICNet-minus-LNP differences in percentage
points. Undefined values remain present. The separate flattened output is
labelled as a Fig. 4b companion; flattened LNP values are a derived companion,
not a claim that the paper directly compared LNP in Fig. 4b.

The full-panel API consumes schema `icnet-fig4-lnp-comparison-input/v1`:

- `icnet_panel`: the existing complete `icnet-source-equations-input/v1` manifest.
- `lnp.model_sha256_by_animal`: one declared model hash for each animal 3–9.
- `lnp.training_split_evidence_sha256`: declared original training-split evidence.
- `lnp.sampling`: `prospective_NumPy_PCG64_Poisson_two_explicit_trial_seeds`.
- `lnp.cases`: all 28 animal/sound cases, each with `animal`, `sound`, `time_bins`,
  `rates` (relative NPY path/SHA256) and `trial_seeds` (two required integers).

LNP rates must align with all 512 original columns and the declared temporal
support. The same observed trials, source mask and unit identities feed both
models. Hashes bind rate bytes and preserve model/evidence declarations; the
module does not verify the model architecture, training split or authentic joins.
Full source temporal support remains an external gate, as in the existing scorer.

A future admitted run uses `python lnp_comparison.py --manifest PANEL.json
--input-root OPERATOR_ROOT --output NEW_REPORT.json`. The output contains all
four sounds, seven animals and 3,476 units per sound, plus distinct flattened
companions. Units remain nested within animals. No bootstrap or inferential
superiority decision is implemented. ICNet exceeding LNP reproduces the paper's
comparator contrast; it cannot establish that a candidate improves over ICNet.
Candidate improvement still requires comparison with the authentic ICNet baseline
under the separately admitted full-vector uncertainty and exposure policy.

The [candidate comparison interface](CANDIDATE_COMPARISON.md) supplies that paired
numerical route from two complete, matched prediction panels. It retains each
model's frozen outputs and full per-unit/per-animal differences. It does not
authenticate the source baseline or implement the scientific improvement decision.

The source's early/late sampled-count RMSE and probability log-likelihood belong
to Figs. 1–3 and are not calculated by this Fig. 4 component. A missing likelihood
log base cannot block the defined Fig. 4 vector. Historical printed-summary
reduction and source plotting conventions likewise remain separate from the
ability to retain granular endpoint values.
