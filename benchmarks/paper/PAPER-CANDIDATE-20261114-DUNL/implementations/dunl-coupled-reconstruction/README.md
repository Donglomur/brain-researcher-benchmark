# DUNL coupled reconstruction scorer

This package contains the accepted V2 evaluator. Independent review corrected three earlier input defects: nonblocking open before rejecting a FIFO, explicit UTF-8 decoding, and structured refusal of JSON parser `ValueError` (including oversized integer literals). Numerical formulas, cohort rules and scoring tolerances are unchanged.

This component fills the missing numerical relationship between a submitted shared kernel, codes, baseline, logits and reconstructed response. It belongs to the existing `PAPER-CANDIDATE-20261114-DUNL` paper family. It adds **zero benchmark IDs** and does not qualify the paper reproduction or any protected prediction experiment.

The accepted event submission interface checks event times. It does not check the paper's response decomposition. The retained central-endpoint findings explicitly identified this gap: accepting an independently supplied response permits copying the observations while submitting unrelated latent variables. Here every response is recomputed from the same submitted representation before scoring. A sufficiently flexible representation may still interpolate visible observations. This is a reconstruction metric, not evidence of generalization, trained-method lineage or neural understanding.

## Scientific calculation

The selected current-code convention is one shared signed, discrete-unit-L2 kernel `H` with 25 samples on a nominal 5 ms grid, nonnegative codes `x`, and one scalar logit baseline `a` per neuron/trial case. For each complete case:

`eta[t] = a + sum(H[k] * x[t-k])`, with valid indices, stride 1, no padding and output length `len(x)+24`; `p[t] = sigmoid(eta[t])`.

This is the one-channel `conv_transpose1d` orientation in the retained pinned decoder, without reversing the kernel. Both submitted `eta` and `p` must match the recomputation at absolute tolerance `1e-7` plus relative tolerance `1e-6`. Kernel norm tolerance is `1e-6`. Scores use the recomputed values, so tolerated serialization differences cannot improve the score. These tolerances are fixed engineering tolerances, not calibrated historical reproduction tolerances.

The reported normalized-response loss is the mean of `softplus(eta) - y*eta`, calculated with a stable equivalent expression. The implementation does not claim bitwise parity with the source's `log1p(exp(eta))`. It also reports mean squared error on the normalized-response scale. It does not insert a binomial `B` multiplier or combinatorial term, report count likelihood, or relabel `p` as Hz. If original samples are later authenticated as binary 1 ms spikes, expected count per 5 ms is `5p` and rate is `1000p` Hz; that conditional conversion is not performed by this scorer.

All expected cases and code entries, including zeros, are retained. The result reports the mean over all cases/bins and a separately named equal-neuron mean, plus each declared neuron's case count and losses. These are descriptive summaries, not biological confidence intervals. Positive coefficient totals do not match events or reproduce the historical positive-only amplitude histogram. The existing event metric remains separate.

## Inputs and CLI

Python 3.11 and the standard library suffice. No Torch, data download, model or dependency installation is needed for the source controls.

```sh
python3.11 -I -S -B reconstruction.py \
  --owner /absolute/evaluator/owner.jsonl \
  --owner-sha256 EVALUATOR_SELECTED_WHOLE_FILE_SHA256 \
  --submission /absolute/submissions/candidate.jsonl \
  --arm paper_data \
  --output /absolute/evaluator/new-score.json
```

The operator, not the participant, selects the exact owner digest and expected arm (`paper_data` or `paper_data_official_code`). The candidate must name that same arm. This checks labels against the operator's selection; it does not prove actual code-access isolation. Both arms use the same schema and numerical rules.

Each input is strict UTF-8 JSONL, with one header followed by exactly one record for every ordered roster case. Every line, including the last, ends in a newline. Duplicate JSON keys, nonfinite constants, booleans used as numbers, extra fields, extra/missing/reordered cases and incomplete vectors are refused. Refusal produces no successful score. No population is shortened to fit a limit.

The owner header has exactly:

- `schema`: `dunl_reconstruction_owner_v1`.
- `profile`: `unqualified_current_code_reconstruction_v1`.
- `cohort_id`: an opaque identifier; `source_cohort_sha256`: the operator's source-selection pin.
- `kernel_samples=25`, `code_stride=1`, `padding=0`.
- `original_sample_period_us=1000`, `samples_per_bin=5`, `bin_period_us=5000`.
- `baseline_mode`: `scalar_logit_per_case`; `observation_units`: `normalized_sum_of_five_samples`.
- `response_samples`: an integer from 25 through 4096, fixed for the full selected cohort.
- `roster`: the complete ordered list of `{case_id, neuron_id, trial_id}`. Case IDs and neuron/trial pairs must be unique. Each identifier uses 1–80 characters from letters, digits, `_ . : -`.

Each owner case is exactly `{case_id, y}`, where `y` contains all normalized observations in `[0,1]`. This component does not assert that those observations are authenticated binary-count averages or that the roster is biologically complete. It does not create the owner file from authentic data.

The candidate header has exactly `schema=dunl_reconstruction_submission_v1`, `context_id`, `arm`, `kernel` (25 numbers), and `method_manifest_sha256` (a declared lineage pin, not independently verified). `context_id` is SHA-256 of the owner header serialized with sorted keys, compact separators, UTF-8 and no nonfinite numbers; the exported `context_id(header)` function implements this. It depends only on the header, never target values. The owner header must contain only approved opaque/public metadata before any participant delivery.

Each candidate case is exactly `{case_id, code, baseline, eta, p}`. `code` has `response_samples-24` nonnegative entries; `eta` and `p` have `response_samples` entries. `baseline` is scalar. Numeric magnitudes are bounded by `1e12`; `p` is in `[0,1]`. Kernel scale cannot be traded against code scale because the kernel has unit norm.

`score_streams(owner_binary_stream, submission_binary_stream, evaluator_owner_sha256, evaluator_expected_arm)` is the pure streaming interface. The CLI additionally refuses symlink inputs, checks regular bounded files and unchanged open-file identity, and exclusively creates a mode-0600 result. It never runs or imports candidate code. Standard output contains only completion status; full numerical results stay in the operator's output file. The file interface is not a sandbox, an access-control system, a held-feedback policy or a crash-atomic publishing guarantee. Keep the evaluator workspace and all detailed scores outside participant access.

Limits are 256 KiB per line, 128 MiB per complete input, at most 4096 cases, and at most 1,000,000 response values across the complete roster (at most 25,000,000 convolution summands). Inputs are parsed one case at a time. The result has a 256 KiB cap. These source limits are not a measured full-cohort runtime or permission for an authentic run. An incompatible authentic cohort requires a separately reviewed capacity revision, never dropped rows.

## Evidence and remaining work

The scientific relation follows the retained current official source at commit `23a34f40b122c3ccf3715995f0dd19fcbbcb46a2`: [decoder](https://github.com/btolooshams/dunl-compneuro/blob/23a34f40b122c3ccf3715995f0dd19fcbbcb46a2/dunl/model.py), [whisker configuration](https://github.com/btolooshams/dunl-compneuro/blob/23a34f40b122c3ccf3715995f0dd19fcbbcb46a2/config/whisker_config.yaml), and [loss](https://github.com/btolooshams/dunl-compneuro/blob/23a34f40b122c3ccf3715995f0dd19fcbbcb46a2/dunl/lossfunc.py). `PROVENANCE.json` records the official source identity and accepted evaluator/test hashes. It contains no dataset, private binding, review transcript or local history.

The paper's ten included neurons, current eleven-channel allocation artifact, original trial identities/splits, resolved group-model exporter, checkpoint provenance, supplement and actual units remain unresolved. This component chooses neither a fabricated eleventh neuron nor a silently repaired ten-neuron cohort. It accepts an explicitly operator-selected roster and marks authentic completeness, historical runtime parity, training lineage, protected prediction and scientific qualification **false** in every score.

The next scientific step is an independently reviewed authentic cohort/role and exporter join, then complete native decoder parity and competent analytic-kernel/PSTH/learned-kernel comparisons under equal information. A protected response-prediction experiment needs its own masked-observation protocol; the present fully observed reconstruction must not be promoted into that claim.

For a direct development check, run the generated implementation controls with:

```sh
python3.11 -I -S -B test_reconstruction.py
```

The full-roster fixture contains **invented** 10×50 cases with only 27 response bins and three code bins per case. It exercises all declared cases and identities, not authentic trial geometry or all paper data. Controls also cover independent convolution/loss calculations, uncoupled copied responses, rescaling, numerical extremes, omission/order/duplicates, units, target-independent context identity, operator-selected arms, safe file refusal and create-only output. Passing them is implementation evidence only.

## Verified package checks

The six-file package is relocatable and needs no files from the original authoring workspace. `SOURCE_MANIFEST.json` lists the exact bytes and SHA-256 of all five other package members. For an authenticated check, select the manifest size and SHA-256 from the reviewed release/CI configuration, then run:

```sh
python3.11 -I -S -B verify_and_test.py \
  --manifest-bytes "$REVIEWED_MANIFEST_BYTES" \
  --manifest-sha256 "$REVIEWED_MANIFEST_SHA256"
```

The release CI additionally verifies the launcher itself against a separately pinned hash before executing those exact checked bytes. A manifest hash computed from an untrusted local copy is not an independent release trust anchor. Do not refresh pins automatically to make a changed package pass.

Verification rejects missing/extra members, symlinks, nonregular files, duplicate manifest keys and byte/hash mismatches. After checking every member, the launcher copies the captured evaluator/test bytes into a fresh private temporary directory and invokes the 18 generated checks there with isolated Python and bytecode writing disabled. It never imports tests from the original directory or its cache. The child has a 60-second deadline and must execute exactly 18 successful tests, with zero skips, expected failures or unexpected successes. Expected stdout reports source authentication only; unittest prints the generated control outcomes. A nonzero exit means refusal, failed tests or incomplete controls.

This source consistency check does not establish authenticity of external neural inputs, a sandbox against a hostile same-user process, measured production resource fit or scientific readiness. Test output and temporary fixtures contain invented values only.
