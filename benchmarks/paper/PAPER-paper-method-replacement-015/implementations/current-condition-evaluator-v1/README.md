# Spinal current-source eligible-record comparison

This additive evaluator implements **`current_source_noise7_eligible_v1`**. It uses the unchanged, authenticated current-source bank: **132 source recording rows, 116 noise-eligible recordings, all 44 neurons** (21 glutamatergic / 23 GABAergic). The 16 source exclusions remain in every comparison report. Eligibility is fixed from input noise before prediction inspection.

The original `source-condition-primitives-v1` producer, all-record adapter, and authentic preparation receipt remain unchanged. Their blanket 132-record refusal is not applied to this separate condition. The adopted eligibility follows the pinned author function: native noise above the requested level produces zero replicas, and only eligible recordings are appended. Unknown preparation failures are not permitted exclusions.

This current-source comparison is **not historical Figure 4 replication**. The original noise realization, optimized alignment/OASIS smoothing, high-rate training exclusions, multi-record aggregation, complete sweeps and 80-neuron cortical comparison remain unresolved. An executable scorer also does not establish that model references are qualified or that a candidate improves the paper.

## Frozen scope and scientific behavior

`CASE_ROSTER.json` contains only source identities, input-derived eligibility and array geometry from the already prepared bank. It has no target values or event counts. The public loader pins this roster and the operator `BANK.json` by SHA256. It does not accept an alternative roster or a new random realization through the CLI. The bank pin is `33085162e9ba9ea64ef9862f681ec6f43c7065256b89430c313e5ac0dab5c726`. Scientific adoption is recorded by SHA256 `55494d44fd04093429051caad11f16396d32edee8302888d14f785b05efeec78`; its independent eligibility review is `96e006b10eec3aefef576a62ddd6b540141fbbd2673251eb381b12fbe5fd48ba`.

The bank uses nominal 30 Hz, requested standardized noise 7, target Gaussian sigma 50 ms, and the frozen per-record noise stream. Additional model-specific temporal shift is zero. Every method uses the same bank observations, full original vector lengths, original recording boundaries, and fixed 32-bin context margin at each end. Neither candidate files nor model failures can define a new mask, time shift or smoothing choice.

Within a neuron, eligible recordings are joined in their frozen original order; their fixed supported bins enter the unchanged `original-endpoint-metrics-v1` kernel. Every neuron is reported, followed by separate equal-neuron summaries for the two original cohorts. This is an explicitly adopted **current** aggregation rule, not recovered historical multi-record aggregation. Undefined correlations remain visible alongside expected/defined/undefined denominators.

Five original controls remain required: raw fluorescence (fixed directly by the bank), OASIS, default/cortical CASCADE, glutamatergic CASCADE and GABAergic CASCADE. An optional candidate must cover all 116 eligible recordings. The existing kernel supplies per-neuron correlation and rate diagnostics, plus paired candidate-minus-own-cohort-reference correlation differences. OASIS/raw amplitude is arbitrary; rate methods use Hz or expected spikes per nominal bin. No hidden amplitude calibration, double smoothing, significance threshold or binary reproduction margin is introduced.

All original recordings of a held neuron, including noise-ineligible recordings, must stay excluded from its training. The source producer's existing exclusion helper preserves that rule. This evaluator does not train models or prove their training membership. Source-compatible configurations, training provenance and source-qualified held-neuron references remain required construction work. A model's provenance note is unverified text; it cannot mark a reference qualified.

## File interface and execution

Only NumPy and the Python standard library are needed for this evaluator. Generated controls were run with Python 3.11 and NumPy 2.4.6. No SciPy, model library, installation, network access or authentic data is required for its generated suite:

```sh
python -B -m unittest discover -s benchmarks/paper/PAPER-paper-method-replacement-015/implementations/current-condition-evaluator-v1 -p 'test_*.py' -v
```

Run checks through the research program's shared bounded pool. No authentic model fitting, inference or scoring was performed to construct this successor.

The operator supplies the private bank and independently freezes a reference manifest SHA. Candidate files cannot select or replace that reference. A future admitted evaluation uses:

```sh
python -B benchmarks/paper/PAPER-paper-method-replacement-015/implementations/current-condition-evaluator-v1/evaluate.py \
  --bank /operator/private/frozen-bank \
  --references /operator/references \
  --reference-manifest-sha256 OPERATOR_FROZEN_SHA256 \
  --candidate /participant/predictions \
  --candidate-manifest-sha256 CANDIDATE_ARTIFACT_SHA256 \
  --output /operator/private/comparison.json
```

Omit both candidate arguments to compute reference-only descriptive results. Output must not already exist and is written with mode 0600 after every required input has succeeded. The evaluator reports current-condition metrics, not an automatic paper reproduction or SOTA decision.

Each prediction directory has a `PREDICTIONS.json` manifest and one ordinary `numpy.savez` archive per eligible recording. Reference and candidate directories have separate role-bound manifests. The complete schema is:

```json
{
  "schema": "spinal_current_prediction_bundle_v1",
  "role": "operator_reference",
  "condition_id": "current_source_noise7_eligible_v1",
  "bank_manifest_sha256": "33085162e9ba9ea64ef9862f681ec6f43c7065256b89430c313e5ac0dab5c726",
  "methods": {
    "oasis": "arbitrary",
    "default_cascade": "expected_spikes_per_bin",
    "glutamatergic_cascade": "hz",
    "gabaergic_cascade": "hz"
  },
  "recordings": [
    {
      "recording_id": "ds40_01/recording-000",
      "payload": {"path": "prediction-000.npz", "bytes": 12345, "sha256": "FILE_SHA256"}
    }
  ],
  "provenance_note": "Operator description; not proof of reference qualification"
}
```

The example shows one row for readability; exactly all 116 eligible IDs are required, with the actual byte lengths and hashes. Each reference NPZ contains exactly the four method-named arrays, each matching its recording's complete bin count. Candidate manifests instead use role `candidate`, methods `{"candidate":"hz"}` (or `expected_spikes_per_bin`), and NPZ files containing only `candidate`. The raw fluorescence control cannot be submitted or replaced. No manifest fields for targets, masks, alignment or a replacement reference are accepted.

Vectors may use ordinary real NumPy floating/integer dtypes of at most eight bytes; complex, Boolean and object prediction arrays are rejected. Nonfinite predictions inside fixed scored support fail, while nonfinite unused context positions do not change the support. Predictions for omitted eligible records or extra source-excluded records fail. Candidate coverage is all eligible recordings or none.

## Bounded file handling and limits

Manifests are duplicate-key-free finite JSON objects of at most 1 MiB. Payloads use canonical relative regular paths with no symlink components. Each archive is read once into immutable bytes, checked against the frozen pin, and decoded from those same bytes. Per-bank/reference/candidate payload totals are limited to 32 MiB. One neuron's vectors are assembled at a time; scientific records are not silently truncated to meet memory limits.

The NPZ contract deliberately requires ordinary, unencrypted `ZIP_STORED` archives with one to five exact members. Before constructing `ZipFile`, the reader checks the ordinary ZIP end directory, declared entry count, directory size and exact extent. Archive comments, multidisk files and ZIP64 **end directories** are rejected; the local ZIP64 headers normally emitted by `numpy.savez` are supported. Each NPY has a bounded header, unique header keys, a one-dimensional exact integer shape, a permitted dtype, and an exact payload extent checked before array decoding. Pickle is never used.

These checks are a bounded artifact interface, not a process sandbox. Protected observation-only material delivery, isolated participant execution and executable qualified reference production remain separate work. The operator bank contains targets and must not be given to assessment participants. The public roster and comparison receipts do not change those access rules.
