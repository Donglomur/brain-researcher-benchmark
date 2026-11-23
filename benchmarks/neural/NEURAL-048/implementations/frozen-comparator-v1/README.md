# Frozen behavior comparator for NEURAL-048

This operator scorer computes the original equal-worm behavior-minus-neural Bernoulli log-loss contrast using behavior probabilities frozen independently of the candidate. A candidate supplies only `neural_history` and `shifted_neural_history` probabilities. It cannot increase its reported contrast by submitting a worse behavior arm or replacing the comparator while retaining the operator's original pin.

The initial evaluator and historical evidence remain unchanged. Their score accepted three participant-supplied arms, which is useful for descriptive investigation but cannot by itself support an improvement claim. This component adds the concrete fixed-comparator path required by the [current contract](../../understanding.v1.json). It does not establish that a particular baseline is competent, causally constructed, fitted with whole-worm isolation, or frozen before outcomes. No authentic comparator has been produced or admitted here.

## Operator inputs and trust boundary

Use the initial evaluator's operator reference unchanged: complete whole-worm folds, complete episode/observation inventory, post-cutoff dorsal labels, source-manifest binding and shared behavior-history binding. The reference remains private. Source H5/MAT conversion, physical timestamps, worm identities and target/window selection remain unresolved.

`freeze_behavior(reference, predictions, receipt, execution_manifest_sha256)` creates a comparator from already produced operator probabilities. `predictions` contains exactly `{id, behavior}` per observation. The receipt has the original five fields: `split_sha256`, `behavior_history_sha256`, `frozen_recipe_sha256`, `cpu_seconds` and `peak_memory_bytes`. The execution-manifest hash binds the operator's separately retained fitting evidence. It is not validated evidence of competence or execution.

Retain `digest(comparator)` in the independently frozen operator protocol before candidate outcomes. Supply that digest to `score(..., expected_comparator_sha256=...)`. **Never obtain the expected pin from the candidate or recompute it from an untrusted replacement comparator.** Hash checking prevents substitution relative to this independently retained pin; it does not authenticate who selected the comparator or when they selected it. Reference files, comparator files and the expected pin are operator inputs, not candidate-selected CLI arguments.

The candidate object has exactly:

```json
{
  "schema": "neural048-neural-arms/v1",
  "task_id": "NEURAL-048",
  "reference_sha256": "<operator reference digest>",
  "policy_sha256": "<initial evaluator policy digest>",
  "comparator_sha256": "<independently retained comparator digest>",
  "arm_receipts": {
    "neural_history": "<original five-field receipt object>",
    "shifted_neural_history": "<original five-field receipt object>"
  },
  "predictions": [
    {"id": "<observation id>", "neural_history": 0.6, "shifted_neural_history": 0.5}
  ]
}
```

The angle-bracket strings are schema explanations, not usable hashes or receipt objects. Each arm must cover exactly the complete reference observation set. Extra behavior probabilities, labels, unknown IDs, duplicate IDs and incomplete rows fail. Probabilities remain strictly inside `(0, 1)` without clipping. Candidate receipts must bind the same whole-worm split and behavior-history artifact. Hash receipts do not attest actual fitting or feature construction.

## Execution and outputs

First package the independently produced operator behavior probabilities. The
prediction input is a complete JSON list of `{id, behavior}` objects; the receipt
input is the five-field object described above.

```sh
python3 -I -B benchmarks/neural/NEURAL-048/implementations/frozen-comparator-v1/freeze_behavior.py \
  operator-reference.json behavior-probabilities.json operator-receipt.json \
  --execution-manifest-sha256 "$OPERATOR_EXECUTION_SHA256" \
  --output frozen-behavior.json
```

The command reuses `freeze_behavior` validation and creates a complete new file
with private permissions, refusing existing files or symlinks. Its only stdout
payload is `comparator_sha256` and the digest kind. This is the scorer's canonical
JSON digest, **not the SHA-256 of the formatted file bytes**. Retain it in the
independent operator protocol as `OPERATOR_COMPARATOR_SHA256` before candidate
access or outcomes. Packaging a comparator does not prove its fitting history,
competence or prospective freeze time. The input reference and output comparator
remain operator artifacts; do not deliver them to the candidate.

Then score the candidate's neural arms against that retained comparator:

```sh
python3 benchmarks/neural/NEURAL-048/implementations/frozen-comparator-v1/scorer.py \
  operator-reference.json frozen-behavior.json candidate-neural-arms.json \
  --expected-comparator-sha256 "$OPERATOR_COMPARATOR_SHA256" --output report.json
```

The operator must keep the report private where its per-worm/per-episode losses could reveal evaluation outcomes. This component supplies no participant execution sandbox or file-access isolation.

The source-pinned original evaluator performs all probability loss calculations, episode completeness checks, equal-observation within-worm averaging, equal-worm contrast aggregation and paired whole-worm intervals. The output adds absolute equal-worm losses for all three arms, the frozen comparator digest, the comparator execution-manifest digest, and the candidate digest. The original three contrasts, per-worm/per-episode losses, constants diagnostic, one-worm limitation and uncertainty method are retained. Null and negative neural increments remain valid. The new route does not select a recipe, fit a model, or alter uncertainty or target policy.

The arithmetic dependency is pinned to `initial-evaluator-v1/evaluator.py` SHA-256 `cd2dc29f52e4aa79a5dc5b913aad9bef57b08e9bbf74f7c7a463b923c9e03d57`. Changing it requires independent review before this component imports it. `provenance.json` records the unchanged contract and source evidence pins.

## Verification and remaining scope

The task-local tests independently derive the equal-worm loss and paired interval for unequal worm sizes. Adversarial controls cover candidate behavior injection, changed baselines with rebound candidate hashes, provenance mutation, coverage, invalid probabilities, matched-history/split bindings, valid null/negative effects, stable row ordering, copied outputs, strict JSON and the CLI. Test fixtures are invented software examples, never native animal observations or performance results.

The freeze-command controls additionally cover the complete CLI-to-score route,
the canonical digest, private file permissions, existing-path preservation and
failure before output publication. They exercise generated operator examples.

Source authenticity, native data preparation, exact causal lineage, independently competent baseline execution, future-free recipe selection, participant delivery and scientific admission remain open. A fixed baseline removes one source of manipulation; it does not turn a positive contrast into evidence of direct neural understanding or a causal mechanism. The output retains the original unqualified status. No historical task, source evidence or numerical prediction was changed.
