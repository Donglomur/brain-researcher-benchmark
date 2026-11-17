# Participant-weighted ordinal training prior

This component implements the required training-prior comparator for the existing observed bedside responsiveness task. For each outer fold it averages each training person's empirical five-category distribution, then predicts that fixed distribution for every evaluable held-out assessment. It emits the existing `dosei_predictions_v1` format without changing the primary or secondary scorer. It does not estimate a physiological feature model or reproduce the author's binary SoC classifier.

The target stays the released ordered MOAAS categories 1–5 at original bedside assessments. All 171 recordings, 7,328 assessment slots and 1,129 separate SoC transitions remain mandatory through the byte-pinned original policy validator. Those counts are inherited source-reported scope, not a newly verified clinical census. Biological person identities come from that externally authenticated policy, never recording names. Repeated recordings of one person contribute to that person's distribution together.

## Estimator and numerical transport

For training person p with n_p eligible assessments, let c_pk be that person's number in released category k. With P training people, the prior is q_k = (1/P) sum_p c_pk/n_p. All calculation uses exact rational arithmetic. The primary scorer gives equal weight to people and then equal weight to their evaluable assessments; this prior follows the same weighting. Pooling every assessment would instead let a person's assessment frequency determine their weight. The pointwise empirical CDF mean also minimizes the participant-weighted training RPS among constant predictions.

Eligibility is the unchanged primary-policy conjunction of valid label, complete window, verified timing and included artifact disposition. The explicit prospective recipe uses only those eligible outer-training assessments. It performs no smoothing, tuning or outcome-dependent selection. A training person without eligible support refuses that fold; the code neither drops that person nor invents a prior. Every held-out slot remains, with `not_evaluable` and null probabilities where the primary policy requires it.

Many exact priors have repeating decimals. The original scorer requires five decimal strings with at most 18 fractional places and exact sum one. This component scales each q_k by 10^18, floors all coordinates, and distributes the remaining integer units to the largest fractional remainders, breaking ties by ascending category. Each coordinate differs from its exact value by less than 10^-18. The fold bundle retains exact numerator/denominator values and the transported probabilities. Scoring uses the transported values; it does not pretend they are the unrounded rationals. No submitted model probabilities are renormalized.

## Fold inputs and output

The unchanged complete policy is evaluator-owned and contains no category values. Each fold receives a separate `dosei_prior_training_v1` JSON object with exactly these fields:

```json
{
  "schema": "dosei_prior_training_v1",
  "task": "clinical-dosei-responsiveness",
  "policy_sha256": "external SHA256 of the complete policy bytes",
  "outer_fold": "the declared fold ID",
  "assessments": [
    {"assessment_id": "an eligible outer-training assessment ID", "category": 1}
  ]
}
```

The row set must equal all and only that fold's eligible outer-training assessments. Held-out rows, missing rows, duplicate rows, nonevaluable rows, extra fields, binary/invalid categories and changed policy hashes are refused. The code never reads a full target bundle to select training labels. A trusted evaluator must export each fold's input under the protected split; this library cannot establish exporter isolation or source truth. Per-person category counts and training-label hashes in fit bundles are evaluator audit material, not participant packet metadata.

`fit_artifacts` returns a `dosei_prior_fold_v1` bundle with the policy/training/source hashes, explicit recipe, per-training-person counts, exact prior, decimal prior and complete held-out prediction rows. `merge_artifacts` verifies one hash-bound bundle per declared outer fold, recomputes the prior from the audit counts, checks those counts against eligible policy support, and verifies every held-out row against the constant prior or frozen null. It returns the complete unchanged primary prediction schema in policy order. Merge takes no label artifact. Receipt equality and count consistency do not prove that a claimed training distribution came from authentic labels.

## Running

Python 3.11 standard library is sufficient. From this directory, fit each fold using external evaluator operands:

```sh
python3 -I -S -B dosei_prior.py fit \
  --primary-source ../ordinal-and-paired/dosei_score.py \
  --policy POLICY.json --expected-policy-sha256 POLICY_SHA \
  --training FOLD_TRAINING.json --expected-training-sha256 TRAINING_SHA \
  --output FOLD_BUNDLE.json

python3 -I -S -B dosei_prior.py merge \
  --primary-source ../ordinal-and-paired/dosei_score.py \
  --policy POLICY.json --expected-policy-sha256 POLICY_SHA \
  --fold-bundle FOLD_1.json --expected-bundle-sha256 FOLD_1_SHA \
  --fold-bundle FOLD_2.json --expected-bundle-sha256 FOLD_2_SHA \
  --output PRIOR_PREDICTIONS.json
```

Repeat the path/hash pair for **every** fold, not merely the two illustrative operands. Expected hashes must be independently frozen values. Files must be ordinary bounded inputs; final symlinks and FIFOs are refused by the original reader. Output creation is exclusive and never overwrites a prior result, although an interrupted write can leave a partial new file. The format limits are 4 MiB policy, 1 MiB training labels, 2 MiB per fold bundle and 2 MiB output; exceeding a limit refuses rather than truncates. These are format limits, not authentic runtime resource qualification. All fold bundles are materialized when merged.

The merged prediction file can be passed directly to the unchanged primary scorer and nested as one arm of the existing secondary/paired evaluator. Preserve the fit bundles, exact input/output hashes and full software version externally; the scorer schema intentionally does not embed this audit into participant predictions.

## Access and qualification

Direct observation, typed viewer, tool-assisted investigation and frozen prediction programs remain separate task conditions. This deterministic prior is a common no-EEG reference; it supplies neither a direct/viewer trial nor a participant transport. Its training evidence must be declared and matched across compared conditions. Computing an authentic prior would be a baseline run under the original protected data and resource protocol, not proof of unaided interpretation. No original source, full clinical labels, authentic prediction, waveform, trained model or participant data are distributed here.

The generated tests cover unequal assessment density, repeated-person weighting, hand-derived original RPS, exact decimal simplex rounding, complete slot retention, held-out label exclusion, missing training support, across-fold label influence, tampered/omitted bundle refusal, source/hash pins and CLI roundtrip. They establish software behavior only. Authentic person/assessment identity, causal 30-second two-channel 125 Hz EEG, rights, complete source census, clinical timing/QC, competent physiological references and all four participant access implementations remain unresolved.

Source interpretation is inherited from the preserved [primary component provenance](../ordinal-and-paired/PROVENANCE.json) and [current understanding contract](../../understanding.v1.json). No new external source was fetched or newly authenticated for this extension. This adds no benchmark ID or clinical performance claim.
