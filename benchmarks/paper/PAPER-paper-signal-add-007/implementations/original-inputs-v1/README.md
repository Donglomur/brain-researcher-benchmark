# ICNet original inputs and complete prediction interface

This component connects the original public evaluation files to the preserved
[source-equation scorer](../source-equations-v1/README.md). It supplies actual MAT
intake, public/evaluator projections, a complete probability-stream adapter, and
the private scoring join. It preserves seven animals, four sounds, both trials,
all 512 original columns and the required 3,476-unit source mask. These are 28
animal/sound cases within one paper task, not 28 animals or new benchmarks.

The original four sounds are evaluation material. The two response trials are
not a train/test split. Neither response array is supplied to the predictor.
Original development inputs, paper-era mask/crop correspondence, competent author
and LNP replay remain separate requirements. The source-defined Fig. 4b/4d
endpoint vectors do not require a universal scalar; historical textual-summary
reconciliation is a separate reporting question.
This component does not establish a reproduced finding, an improvement, or SOTA.

## What was recovered

The [original versioned release](https://zenodo.org/records/12636772) contains
`IC_data_trial1.mat` and `IC_data_trial2.mat` (326,661,096 bytes each), and
`sound_data.mat` (11,665,880 bytes). Publisher sizes and MD5 identities are fixed
in `source.py`; complete acquisitions additionally receive SHA256 identities.

Bounded original-file range inspection recovered every top-level directory entry:

| File | Actual arrays |
| --- | --- |
| Each response trial | Four signed-int8 arrays, shape **7 × 22,784 × 512**; float64 measurement times **7 × 4** and characteristic frequencies **7 × 512**; int64 animal IDs **1 × 7**; float64 scalar sampling rate |
| Sounds | Four float32 arrays, shape **1 × 729,088**, and a float64 scalar sampling rate |

These are **uncompressed little-endian MATLAB v5 numeric variables**, not HDF5 or
a nested MATLAB structure. The publisher prose says seven fields; the actual
trial files have eight variables. The exact released extent is 29.86344448
seconds, with 32 audio samples per neural bin. The description's nominal
30 seconds is not a reason to pad, crop or resample these arrays. Header recovery
alone does not establish their historical preprocessing origin or metadata values.

The exact three complete files were subsequently found in the existing source
cache and reauthenticated without another download. Bounded numeric metadata
inspection found identical CF matrices in both trials: 3,476 positive finite
frequencies and 108 **negative-infinity** exclusion markers. The loader retains
those markers unchanged and rejects positive infinity, NaN and nonpositive
finite frequencies. Neither recorded neural values nor audio samples were
numerically processed during that metadata inspection. The unlabeled
measurement-time columns still need an original evaluation-code mapping.

The source loader reads only bounded MAT metadata and memory-maps the fixed
numeric payload offsets in MATLAB column-major order. It refuses compressed,
complex, sparse, logical, object, unknown, missing and dimension-mismatched
variables. Whole-file identity is checked before any numeric preparation. Counts
must be nonnegative; observed counts are not arbitrarily capped at four merely
because the model distribution has five categories.

## Prepare the source panel

Use Python 3.11+ and NumPy. No SciPy, TensorFlow, checkpoint or author code is
needed for preparation. Original source inputs and generated outputs stay outside
Git. The preparation policy is an operator-reviewed JSON document:

```json
{
  "schema": "icnet-original-preparation-policy/v1",
  "measurement_time_sound_order": [
    "speech_in_quiet", "speech_in_noise", "moving_ripples", "music"
  ],
  "mask_policy": "finite_source_characteristic_frequencies",
  "mask_evidence_sha256": "SHA256_OF_INDEPENDENT_MASK_EVIDENCE",
  "alignment_review_sha256": "SHA256_OF_INDEPENDENT_ALIGNMENT_REVIEW"
}
```

The placeholders are not valid input hashes. These references identify required
review evidence; a correctly shaped digest does not authenticate that evidence.
`measurement_time_sound_order` must explicitly name the sound occupying each
successive source time column. Any exact permutation of the four names can be
represented; the producer uses that mapping when joining each sound's two times.
The order shown above is illustrative, not independently verified source metadata.
There is no default ordering or automatic inference from field-list order.
The finite-CF mask interpretation comes from the pinned author's example, which
identifies infinite CFs as low-reliability channels; the release stores these
as negative infinity. Both trial CF arrays must
agree, and the selected population must contain exactly 3,476 units. Count
agreement alone does not independently establish broadband-noise reliability.
The operator must resolve measurement-time column order and historical alignment
before interpreting a paper comparison. No mask is estimated from evaluation
responses.

```sh
python source.py --source-root /operator/original-mat \
  --policy /operator/preparation-policy.json \
  --output-root /operator/workspace/prepared
```

All four complete sounds are exported once in physical calibrated Pa. Public
material also contains original animal/column IDs, CFs and both trial-specific
measurement times in **seconds**. The files are readonly after complete writing.
Private material holds both recorded response arrays and the reference manifest.
The destination is new and private; incomplete failures are retained without a
completed reference manifest. Directories separate data roles, but do not isolate
an untrusted process running under the same operating-system account.

Preparation pins the actual bytes and fixed geometry, preserves every original
column, and emits all 28 cases. The two paper-access conditions must use the
same exported public data; giving official code is a separate delivery condition.
This component does not itself create the paired code distribution or an agent
episode.

## Supply predictions without discarding probabilities

`predictions.py` accepts a trusted operator predictor module exporting
`predict(request)`. It invokes that function once for every animal/sound/trial:
56 calls with the complete original support. Each request contains:

- Readonly calibrated `audio_pa`, `fs_audio` and `fs_neural`.
- Original `animal`, `sound`, `trial`, and `measurement_time_seconds`.
- Readonly `characteristic_frequencies_hz`, ordered `unit_ids`, `time_bins`, and
  `maximum_block_bins` (1,024).

The callable yields dictionaries containing only `start_bin`, `probabilities`
and `column_indices`. Each probability block has shape **time × 512 × 5**, with
float32/float64 categorical probabilities for counts 0–4. Blocks must cover every
bin exactly once in order. `column_indices` is the exact permutation identifying
the original MAT column represented by each output column; it cannot be inferred
uniquely from CF values because frequencies may tie. Column order must remain
consistent across a trial.

The adapter restores original columns, computes expected counts from the full
distribution, and independently samples categorical counts. Both arrays are
retained for each trial. Its required explicit seed uses NumPy PCG64, with a
stable per-case/trial seed and row-major draws; changing block size does not
change samples. This is a declared sampling implementation, **not bitwise
TensorFlow sampling parity** or a recovered historical random seed. Rows may
deviate from unit mass by at most eight input-dtype epsilons; accepted rows are
normalized to remove storage/accumulation roundoff. Logits are not probabilities.

```sh
python predictions.py --public-manifest /operator/workspace/prepared/public/panel.json \
  --predictor /operator/reviewed_predictor.py \
  --predictor-sha256 EXACT_REVIEWED_SOURCE_SHA256 --seed 7321 \
  --output-root /operator/workspace/predictions
```

The CLI compiles exactly the verified predictor source bytes. Its transitive
dependencies and model execution still require operator qualification. The
predictor is trusted code, with host privileges; this is not protected candidate
execution. No model, weights, API client, arbitrary default context padding or
author inference implementation is bundled. The pinned author helper discards
probabilities when it samples; its returned sample alone cannot satisfy this
interface. A qualified author bridge must expose the pre-sampling distributions,
preserve the two measurement times, and establish original context alignment.

## Expose the author model probability output

The [explicit-context author bridge](AUTHOR_BRIDGE.md) supplies a source-documented
connection from an operator-supplied model to this probability-stream interface.
It preserves original decoder columns, both measurement times and the complete
output support. It requires explicit preceding waveform context and external
alignment evidence; no demo padding policy is selected automatically. Its
generated controls do not qualify the checkpoint, TensorFlow execution, context
policy or an original-author numerical replay.

## Join and score privately

Only after a complete prediction manifest exists does the separate grading stage
read private response files. It requires the exact same public-panel hash,
complete 28-case/two-trial identities, original columns, source mask, times and
array pins. It creates a private manifest in memory and calls the byte-pinned,
`source-equations-v1/scorer.py` with unchanged Eq. 3–5 numerical kernels and an
updated source endpoint binding; no large array copies are needed.

```sh
python grade.py --public-manifest /operator/workspace/prepared/public/panel.json \
  --private-reference /operator/workspace/prepared/private/reference.json \
  --predictions /operator/workspace/predictions/predictions.json \
  --workspace-root /operator/workspace --variance-ddof 0 \
  --output /operator/workspace/metrics.json
```

`--variance-ddof` is mandatory. The example's zero is not a recovered author
choice; both original supported conventions remain explicit. The output retains
all animal/sound and unit metrics, negative/above-100 values and undefined-value
diagnostics. It has no invented pooled scalar or paper-win decision. Public
evaluation targets were already released; local separation does not create an
unexposed holdout.

## Validation scope

Generated controls exercise actual MAT parsing and full original-geometry source
preparation, source identity/clock/type failures, public/private roles,
probability-column restoration, expectation/sampling, and complete orchestration.
Reduced-time generated prediction controls retain all animals/sounds/trials and
are reported separately from the full-size intake control. They do not run an
author model, use authentic numeric payloads, or establish scientific qualification.
The single full-size generated preparation pass preceded the source-backed
CF-marker correction and used positive-infinity exclusions. Its earlier source
pins are preserved. The corrected negative-infinity revision passed ten affected
small controls, including the complete case/trial prediction-to-score join;
the large fixture was not repeated. The full-size test requires an explicit
`ICNET_FIXTURE_ROOT` and a separate 1,536 MiB artifact budget.
Two focused controls subsequently verify explicit nonidentity time-column mapping
and refuse missing, duplicate or foreign sound identities.
See `SOURCE.json` and `TESTING.json` for exact source dependencies and observed
test evidence. Historical contracts and earlier test evidence remain unchanged. The current
scorer reporting and its live dependency pins are updated; Eq. 3–5 numerical
kernels remain unchanged.

## Distinct LNP rate route

This categorical transport retains its five count classes and original dtype
contract. It must not be relabelled as the paper's Poisson LNP. The separate
`source-equations-v1/lnp_comparison.py` accepts external LNP rates, samples
unbounded int64 Poisson counts under explicit prospective seeds, and compares
the same per-MUA Eq. 3–5 vectors while retaining flattened companions. It does
not fit or authenticate LNP rates, recover historical sampling, or qualify a
source baseline. The same prepared observations, unit mask, original columns
and temporal support remain required. ICNet-minus-LNP results describe the
original comparator contrast; candidate improvement over ICNet is separate.
