# Human manual-trace agreement

This component computes the original human endpoint described in DREDge's
Extended Data Fig. 2: Pearson correlation between estimated and manually tracked
LFP displacement, separately for Pt01, Pt02 and Pt03. It returns the paired
candidate-minus-author difference for each patient and preserves that ordered
vector. The paper reports rounded correlations 0.98, 0.99 and 0.85; it does not
supply a scalar cohort aggregate or a universal superiority margin.

Reproduction and improvement are separate intended outcomes. A reproduction
evaluation retains the candidate's complete correlation vector and compares it
against authenticated source execution using a separately justified tolerance;
an improvement evaluation retains the paired `delta_r` vector and requires a
separately declared full-cohort decision. Neither tolerance nor decision is
known here. The same packet/support must be used in paired paper+data and
paper+data+author-code conditions; author-code access is a delivery distinction,
not a different endpoint or another task registration.

The existing `initial-evaluator-v1` voltage consistency/fidelity panel remains a
different, prospective diagnostic. Neither that panel nor this computation
establishes a paper win. This component is usable with operator-supplied aligned
traces; recovery and authentication of the original manual references, intervals,
alignment, patient-specific preprocessing and native author outputs remain
necessary before its numbers can be attributed to the original experiment.

The implementation computes correlations without selecting a lag, interpolating,
rescaling coordinates, masking samples, pooling patients or making an independent
sample assumption. Exact frozen time support and recording identity must match
for both methods. Constant traces retain their patient row with null correlation
and null paired difference. Nonfinite values, missing patients, duplicate
identities and incompatible supports are errors. Correlation is invariant to
positive affine changes: good agreement cannot certify displacement amplitude,
offset or physical motion accuracy. No p-value, confidence interval, fidelity
threshold or superiority decision is invented.

## Operator and participant packets

The operator reference is a JSON object with:

- `schema: "dredge-manual-reference/v1"` and
  `task_id: "PAPER-paper-method-add-003"`.
- `alignment_recipe_sha256`: the hash of the separately frozen, source-justified
  preparation/alignment recipe; `author_execution_sha256`: the hash of the
  native author execution receipt. These fields bind declarations and do not
  authenticate their contents by themselves.
- `records`: exactly one object for each of Pt01, Pt02 and Pt03. Each has
  `patient`, `recording_sha256`, strictly increasing `times_s`,
  `manual_displacement_um`, and `author_displacement_um`. All three arrays have
  the same length. Reference arrays stay in operator storage.

`public_support(reference)` produces the prescribed time/recording support and
alignment recipe digest, excluding manual and author displacement values.
`support_sha256(reference)` computes SHA256 of its canonical JSON (sorted keys,
compact separators, normalized float time values). Expose only the prescribed
support to the candidate. The support hash intentionally does not depend on
target values; the separate full-reference byte hash below freezes those values.

The participant JSON object has `schema: "dredge-manual-candidate/v1"`, the same
`task_id`, `support_sha256`, and `records` with `patient`, `recording_sha256`,
`times_s`, and `displacement_um`. Record order may differ; the result is always
Pt01, Pt02, Pt03. Changing the time axis, even by a constant offset, is rejected.
Required source alignment must be recovered and frozen upstream; this interface
does not choose or authorize a new alignment to improve correlation.

Run the operator computation with standard-library Python:

```sh
python3 agreement.py operator-reference.json candidate.json result.json \
  --reference-sha256 FROZEN_SHA256_OF_COMPLETE_OPERATOR_REFERENCE_BYTES
```

The CLI checks the complete reference byte hash and records both input byte
hashes. Existing output files and attempts to overwrite either input are
rejected. `score_packets(reference, candidate)` supplies the same computation as
a Python API; its caller owns the additional full-reference freeze check.
The returned fields are per-patient sample count, `author_r`, `candidate_r` and
`delta_r`, with source recipe/execution digests. Sample counts describe temporal
support, not independent biological replication.

Generated software controls use no recordings, manual traces or author outputs:

```sh
python3 -I -B -m unittest discover -s tests -v
```

The controls distinguish analytically orthogonal and collinear traces, expose
affine invariance and constant-trace failure, retain all three patients, reject
support/identity changes, and exercise a separate frozen-reference CLI packet.
They establish software behavior only. During the parallel build these commands
must run through the shared test pool.

Primary scientific source: [DREDge, Nature Methods (2025), human results and
Extended Data Fig. 2](https://www.nature.com/articles/s41592-025-02614-5).
The registered original source-code revision remains
`evarol/dredge@ed236113a0b6c29b376065440174da6341a1d875`.
