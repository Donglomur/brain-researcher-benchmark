# Complete held-out trajectory evaluation

This package restores an executable scorer for the complete existing NEURAL-067 prediction panel: 14 runs, seven source sessions, four information arms, 34,490 full rows per arm, and seven ordered outputs. It contains no recordings, targets, fitted model, or participant runtime. Its generated controls do not qualify a benchmark or establish an agent result.

The authoritative task and its history remain unchanged. This package is an integration proposal for the current contract's missing evaluator. The legacy runtime declaration still describes a different, unqualified execution route.

## Endpoint and source identity

`scorer.py` fixes the exact run order and counts from the recovered historical **public** `design.json`, SHA-256 `73cdfd5d8760ad456251877d458a257af8f0100d5c73f95f965a0f9dda5b2028`. Its query runs map to official `S6` through `S12`, each with two sets. The mapping comes from FALCON `config.py`; held-out membership and the estimator come from `evaluator.py`, both at source commit `770c9b9597b8f58bf67b5a9ec6401ef705a2cb0f`. See `sources.json` for exact pins. These are recovered source declarations, not fresh validation of any NWB payload or prepared array.

The scorer validates every prediction before invoking its operator target callback. It requires the complete four-arm panel in fixed arm/run order and exact full-run row IDs `0..n_rows-1`, seven finite numeric outputs, and the source coordinate order `tx, ty, tz, rx, g1, g2, g3`. It refuses extra fields, missing or duplicate blocks, reordered rows, nonfinite values, and booleans used as numbers. A numerical artifact's claimed row IDs cannot prove it was generated causally.

After validating targets and strict boolean masks, the scorer applies each source mask, pools both sets **within the same session**, computes seven-output variance-weighted R², and averages the seven session scores equally. It does not average run scores or coordinate scores. The standard deviation uses divisor seven and is descriptive session variation, not a confidence interval or independent-person uncertainty. The complete original query panel has no held-in evaluation runs; these are reported as absent rather than combined with later sessions. Training remains the original 13 early runs and is outside this scorer.

The historical scorer's force-finite constant convention is intentionally not imported into the revised contract: each constant coordinate has `null` R² and an explicit disposition. Its weight is zero when other coordinates vary. If all seven coordinates are constant, the session score is `null`; any undefined session makes the overall score and corresponding paired contrast `null` without dropping that session. This is a disclosed deviation from the official evaluator's default force-finite edge case, required by the current task's failure policy. Zero or one selected row, nonconstant variance underflow, overflow, and nonfinite defined metrics are rejected. SSE remains ordinary finite floating-point arithmetic; arbitrary precision and bitwise scikit-learn equivalence are not claimed.

The reported paired differences preserve `neural_clock minus clock` and `neural_clock minus shifted_neural_clock`. Source velocity labels are attempted open-loop supervision, in the historical design's stored source-position increments per 20-ms sample; no SI conversion or executed-motion interpretation is introduced.

## Operator interface

Python's standard library is sufficient. Run the complete scorer with:

```sh
python3 scorer.py --submission predictions.json --targets operator-targets.json --output grade.json
```

The output must be a new file. The target bundle stays operator-owned; the command is not a sandbox, participant launcher, source authenticator, or privacy boundary. No path, digest, or target in this example refers to an existing private artifact. Preparation must bind masks and target bytes to authenticated NWB sources before real scoring.

A submission has exactly these fields:

```text
schema: "neural067_session_predictions_v1"
contract_sha256: scorer.CONTRACT_SHA256
columns: ["tx", "ty", "tz", "rx", "g1", "g2", "g3"]
entries: 56 objects in scorer.ARMS then scorer.QUERY order
  arm, run, session: exact identities from the module
  row_ids: [0, ..., n_rows-1]
  prediction: n_rows by 7 finite numbers, including unmasked rows
```

The private target bundle has exactly `schema: "neural067_session_targets_v1"`, the same `contract_sha256`, and `runs`, a mapping with exactly the 14 run IDs. Each value has exactly `run`, `session`, `row_ids`, `velocity` (full rows by seven), and `eval_mask` (full rows of literal JSON booleans). The API alternative is `grade(submission, load_target)`, whose callback returns that run's target object. The CLI reads no target bundle until complete public prediction admission succeeds. Returned reports contain aggregate errors and scores, never trajectory labels.

`CONTRACT_SHA256` identifies this scorer's roster and numerical contract. It is deliberately different from the legacy design hash; old predictions require an explicit conversion, not silent compatibility. This scorer does not validate calibration provenance, source data authenticity, submitted program freezing, trial timing, or NEURAL-067/068 exposure separation.

## Access conditions and remaining qualification

The four information arms are **not** the four access modes. The same strict prediction endpoint can score a separately controlled response artifact, but this package delivers none of the participant modes:

| Access mode | Still required |
| --- | --- |
| Direct observation | Complete fixed permitted observation packet and response collection without execution |
| Typed viewer | Task renderer, restrictive actions, complete case collection and target isolation |
| Tool assisted | Case-local investigation with fixed input/compute entitlement and no outcome feedback |
| Frozen program | Pre-query code/recipe freeze, complete causal transport and matched calibration |

The report always states that causal execution and access mode are unverified. It cannot establish unaided interpretation, official hidden challenge performance, motor mechanism, or human-population generalization. Source terms/redistribution conflict, invalid draft schema, source timing/mask authentication, original panel exposure, complete participant delivery and genuine comparator qualification remain unresolved. No private historical target, neural array, model, prediction, or answer was read to construct this package.

The beside-source controls use generated values on the complete declared row geometry and small exact arithmetic examples. They verify masking, within-session pooling, equal session weighting, weighted channels, undefined constants, strict identity and callback ordering. Run them through the project test pool, not as a native scientific workload.
