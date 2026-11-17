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
recorded. In equation (4), MSE always uses its literal population mean. Native
source parity must resolve the choice before paper comparison. The mathematical
component is useful under either convention; neither is asserted to be the
author implementation.

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

Remaining gaps are the original reliability-mask identities, exact crop and
measurement-time preparation, source variance convention, the textual per-sound
score reduction, authenticated author checkpoint replay, LNP companion replay,
original development access, stochastic prediction policy and an animal-aware
full-panel improvement decision. The output intentionally has no scalar score or
paper-win decision. It reports `source_equation_component_only`, with native
author reproduction, reproduction evaluation and improvement evaluation false. No source baseline,
scientific improvement, readiness upgrade or SOTA claim is made.
