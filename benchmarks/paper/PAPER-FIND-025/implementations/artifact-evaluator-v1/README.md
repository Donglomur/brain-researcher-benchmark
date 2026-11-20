# FIND025 artifact evaluator, version 1

This component computes the existing movement-prediction, binary-decoding and onset metrics from authenticated candidate bytes and separate operator operands. It extends the preserved [submission comparison implementation](../submission-comparison/CONTRACT.md), whose previous numerical interface accepted evaluator-declared scalar records. It does not prepare authentic data, resolve the paper/code discrepancies, run MATLAB, or establish an improved paper result.

## Operator API

`evaluate_submissions(plan, submissions, payloads, operator_operands)` accepts decoded objects from a trusted bounded operator interface. Use this batch function to compare runs: every supplied candidate and author-baseline run receives exactly the same operator target/support bundle. `evaluate_submission(...)` is a convenience for one run and does not independently establish pairing with another call.

- `plan` and `submissions` use the unchanged predecessor schemas. All sixteen output groups remain assigned. Missing, failed, undefined and abstained records retain their original denominators.
- `payloads` maps `(run_id, kind, logical_id, sha256)` tuples to `bytes`. These are in-memory keys, never paths. All referenced artifacts are hash-checked before numerical decoding; unknown supplied keys are rejected. Missing or changed artifacts are held. Extra ancillary artifacts must also authenticate.
- `operator_operands` has exactly `schema: "find025_operands_v1"`, `plan_sha256`, and a `cases` list. Each supplied numerical case has exactly `case_id`, complete `identity`, ordered unique `row_ids`, `target_values`, `times`, `delay_onset`, `representation`, and `preparation_id`.
- Each numerical artifact has strict UTF-8 JSON containing exactly `schema: "find025_prediction_vector_v1"`, `row_ids`, and `values`. Candidate truth, self-scores and extra fields are rejected. Row identity and order must match the operator exactly; no intersection, sorting, dropped rows, imputation or prediction calibration occurs.

`identity` must equal the assigned predecessor identity in full. `preparation_id` references the operator-held derivation of the admitted support and transformation. It is an assertion requiring independent provenance review; a string or digest cannot certify its scientific correctness. Candidate values and operator targets are finite numbers with magnitude at most 1e100; booleans are rejected. Signed variance explained and squared correlation now rescale finite vectors before centering and squaring: tiny nonconstant operands such as `[0, 1e-200, 2e-200]` no longer become undefined merely through square underflow. Positive scales cancel from the unchanged formulas. True constancy remains undefined, negative signed scores survive, and no rows or target values are replaced. Decoding requires the exact -1/+1 class dictionary.

The output contains authenticating and scoring audits, predecessor-shaped evaluator records, and the unchanged descriptive comparison report. It does not return target values, timestamps or row IDs. Operator bundle digests are content bindings, not custody or provenance proofs. Treat the whole evaluation result as operator evidence: a digest of a low-entropy target is not an access-control mechanism.

## Metric-specific operands

| Metric | Operator representation and values | Computation |
|---|---|---|
| `binary_accuracy_v1` | `assigned_rows`; exact held -1/+1 `target_values`; null times/onset | Fraction correct on all assigned rows |
| `signed_variance_explained_v1` | `assigned_rows`; exact `target_values`; null times/onset | Signed 1−SSE/SST; negative values remain negative |
| `pearson_squared_paired_vector_v1` | Same rows, targets and preparation as protected signed VE | Squared centered Pearson correlation, without refitting scale/intercept |
| `pearson_squared_delay_trialmeans_git003835_v1` | `delay_trialmeans`; independently admitted delay trial means; null times/onset | Historical squared correlation on those trial means |
| `first_strict_90pct_latency_v1` | `oriented_smoothed_prego_trace`; null targets; strictly increasing `times`, numeric `delay_onset` | First sample strictly above 90% of trace maximum, minus delay onset |

Historical corr² is not computed from pointwise predictions by an invented reduction. The operator must first prepare and adjudicate the exact trial means, condition order and source window. For protected movement panels, both metric cases must supply identical actual target vectors, ordered rows and preparation references, and the predecessor requires the same prediction descriptor. The batch API uses that one bundle across arms and baseline/candidate roles. This is an independently authored protected extension; it is not the original paper split.

Four artifact-only groups authenticate submitted bytes without a scalar. The two normalized-variance groups retain their artifacts and report `unsupported`: covariance/basis/eigenvalue/denominator realization remains unresolved. This component does not introduce a replacement formula. Constant targets/correlation inputs and no strict onset crossing produce explicit undefined outcomes. Malformed prediction JSON produces failed records. Missing scientific operands produce held cases.

All unresolved plan obligations and predecessor identity/execution admission checks remain enforced. Paper mode may retain individual arithmetic but its comparisons retain the final-paper adjudication hold, `paper_pass: null`, `scientifically_qualified: false` and `execution_ready: false`. No inference, effect threshold or aggregate superiority rule is added.

## Resource and trust boundary

The fixed ingestion ceilings are 4 MiB per artifact, 64 MiB total candidate payload bytes and 100,000 rows per vector. These are software resource limits, not source-paper cohort choices. An oversized case is rejected in full; never shorten the scientific support to pass. Authentic operator preparation must verify that the entire resolved panel fits, or select a reviewed successor format before execution.

The API assumes a trusted host and already-bounded plan/submission/operand objects. It is not a network JSON parser, process sandbox, isolation mechanism or target custodian. No candidate file path, pickle, array container, model or executable is loaded. The executable dependencies are the unchanged predecessor submission contract and the local scale-stable arithmetic successor, pinned in [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json). The original `submission-comparison/metric_primitives.py` remains byte-exact; the maintained evaluator explicitly selects `metric_primitives_v2.py`. Historical source, contracts and canonical task files are unchanged.

## Source and qualification

The original source is [Hasnain and Birnbaum et al., Nature Neuroscience](https://www.nature.com/articles/s41593-024-01859-1), with the [author analysis archive](https://zenodo.org/records/13941415) and [pinned GitHub analysis source](https://github.com/economolab/HasnainBirnbaum2024/tree/0038351ee773c2aee8758b3d74b0c9bf2991f543). The retained official source explicitly distinguishes delay-trial-mean corr² in `Scatter_ModelPred_TrueCDTrialType.m` from signed 1−SSE/SST in `getR2.m`. Source hashes and exact dependency roles are recorded in the manifest. No upstream MATLAB body is redistributed.

The final-paper versus released-code cohort, model, trial/condition identity, temporal support, preprocessing and baseline mapping remain unresolved. This implementation follows the retained API decision for already-adjudicated operands. It does not solve those source questions. Generated checks use wholly invented vectors and symbolic participants. Zero authentic input preparation, author inference, candidate trials, paper wins or current-SOTA comparisons are claimed.

The task-local control entry point is `test_artifact_evaluator.py`. Run it only through the shared reviewed lightweight test pool during parallel construction, with one thread, at most 1 GiB declared RAM and at most 180 seconds. It exercises positive arithmetic and counterexamples for target injection, hash tampering, wrong rows, invalid JSON, metric-specific reductions, common-vector pairing, constancy, missing cases and preserved paper/execution holds. Actual results and measured costs are retained in the external handoff.

The additional `test_numeric_scale.py` controls cover finite scaling invariance, negative signed VE, constant/malformed input refusal, the actual paired artifact evaluator path, and failed predictions retained in the full assignment denominator. These generated controls do not change scientific readiness.
