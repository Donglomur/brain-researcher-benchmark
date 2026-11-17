# DoSEI ordinal responsiveness and paired diagnostics

This standard-library component scores observed bedside responsiveness on the DoSEI task. It supplies a conditional evaluator, not a clinically validated benchmark or a native EEG preprocessing pipeline. Both scientific implementations are preserved byte-for-byte from their reviewed sources. No clinical data, original annotations, genuine person identifiers, predictions, target answers or trained models are distributed.

The declared scope is all171recordings,7328original MOAAS assessment slots and1129separate state-of-consciousness transitions. These are reported source counts enforced as logical scope, not an independently authenticated census.171recordings must never be treated as171proven biological people. The evaluator must supply a complete original recording-to-person mapping, original assessment/event census and frozen eligibility policy. The number of biological people is explicit; grouped outer folds must respect repeated procedures. Authentic versions of these operands remain unresolved.

## Primary score

The released ordered MOAAS categories are1,2,3,4,5. The primary report describes original0/1 merged into1 and5/6 into5. This scorer consumes already authenticated released categories; it neither guesses raw-scale recoding nor substitutes binarySoC. It uses prospective normalized ranked probability score (RPS): sum the four squared cumulative-probability errors and divide by4. Average eligible assessments within each biological person, then equally across people. This prospective RPS is not an author-reported benchmark result.

Every original slot stays in the report. Label/window/timing/artifact dispositions are frozen before outcomes. A slot is evaluable only when the label is valid, the input window complete, timing verified and artifact disposition included. That conjunction is an explicit evaluator interface rule, not a claimed producer QC rule. Missing and ambiguous labels stay null; incomplete or excluded cases remain in coverage. Missing or failed evaluable predictions refuse the entire submission. If any person has no evaluable assessments, the full-person primary is undefined rather than silently averaging a favorable subset.

Predictions are five exact decimal strings in category order, each in[0,1] with at most18decimal places and exact sum1. No clipping or renormalization. RPS and aggregation use exact rational arithmetic; report numerator/denominator strings are authoritative, floats are display approximations. SoC transitions are separately counted and are never additional ordinal targets.

## Paired diagnostic

For each frozen transform, compare transformed-minus-original RPS on exactly the same supported eligible case IDs within each person. Average those paired differences within person, then equally across people with support. Finally equally average available transform means. List every unsupported person and retain every unavailable transform; an unavailable transform is not assigned zero. If none are available, the diagnostic is null. The complete original score stays separate for every arm and retains its full natural coverage.

All arms must bind identical original packet-set receipts, transform lists, map hashes and per-case transformed packet hashes/support. Target-category coverage is computed after map and prediction admission. This verifies equality of supplied logical values; it does not independently authenticate physical packets. Different map hashes or a nonidentity receipt do not prove actual nonidentity/distinctness. No native shuffle schedule, within-person donor map, clock alignment, boundary integrity, mask invariance or waveform conversion is supplied. Those source-dependent prerequisites remain held. A single supplied session per recording is a prospective interface constraint; do not collapse genuine source sessions merely to pass it.

The map schema admits only declared channel/temporal shuffle families and excludes label/dose/clinical columns. Real target-free provenance and pre-outcome freezing still require an independent evaluator. The diagnostic is descriptive and support-limited, with no permutation p-value, exchangeability, causal, consciousness or treatment claim.

## Running the interfaces

Python3.11 standard library is sufficient for this software component. From this component directory:

```sh
python3 -I -S -B dosei_score.py \
  --policy POLICY.json --expected-policy-sha256 POLICY_SHA \
  --predictions PREDS.json --expected-predictions-sha256 PREDS_SHA \
  --targets TARGETS.json --expected-targets-sha256 TARGETS_SHA \
  --output FRESH_PRIMARY.json

python3 -I -S -B dosei_paired.py --primary-source dosei_score.py \
  --policy POLICY.json --expected-policy-sha256 POLICY_SHA \
  --maps MAPS.json --expected-maps-sha256 MAPS_SHA \
  --predictions PAIRED_PREDS.json --expected-predictions-sha256 PREDS_SHA \
  --targets TARGETS.json --expected-targets-sha256 TARGETS_SHA \
  --output FRESH_PAIRED.json
```

The placeholder operands are not distributed. PRIMARY_INTERFACE.json and PAIRED_INTERFACE.json specify their strict fields. Expected hashes are required external values and bind chosen bytes, not clinical truth or authority. Both CLIs admit all required predictions before opening protected targets; the bytes callables already receive caller-owned targets and are not sandboxes. Outputs require a fresh file; write failure can leave a partial file. The primary software dependency of the paired CLI is exact-byte/hash checked before loading.

Primary format caps:4MiBpolicy,2MiBpredictions,1MiBtargets,4MiBoutput. Paired caps:8arms,32transforms;4MiBpolicy,32MiBmaps,64MiBpredictions,1MiBtargets,32MiBoutput. Exceeding a cap refuses the complete input; no truncation. These are format ceilings, not RAM/CPU guarantees. Maximum-format inputs have not been resource-qualified; authentic execution requires separate bounded lifecycle and memory planning. Inputs and reports are materialized in memory.

## Checks and remaining work

`python3 -I -S -B test_delivery.py` checks relocation, exact runtime source pins, the complete test inventory, CLI help and refusal before missing-input access. It does not execute accepted numerical suites. The package retains14primary author tests,9paired author tests and two independent5-test suites (33total), with their helper/test bodies unchanged. Their only relocation edits are local software paths and removal of private evidence-writing launch harnesses. To run these generated numerical checks deliberately, invoke test_dosei.py, test_paired.py, test_primary_independent.py or test_paired_independent.py. Their fixtures are visibly invented full-scope metadata, not real clinical data or physiological references.

Authentic person/event/assessment lineage, original30-second causal two-channel125Hz EEG packets, rights, clinical QC, native transformations, protected training/tuning, physiological comparator competence, secondary ordinal reporting/calibration and group-aware uncertainty remain unresolved. This package adds no task, ready benchmark or scientific/model result. Official technical-report/release/code references and interpretation are in PROVENANCE.json.
