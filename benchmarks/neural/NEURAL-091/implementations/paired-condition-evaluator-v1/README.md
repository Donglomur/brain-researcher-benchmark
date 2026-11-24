# Paired declared-condition response assessment

This operator-side component compares a `restricted_observation` submission and
one `frozen_program` submission for NEURAL-091. Each must identify the same
**whole public calibration and query packet**, not only matching query IDs. It
addresses the missing paired assessment route; it does not deliver a participant
runner, freeze a program, enforce no-tools behavior, or authenticate observations.

Both submissions are admitted using public data before any protected target is
examined. In the CLI this includes admission before opening the private file.
Each submission must contain exactly:

```json
{
  "schema_version": "neural091-paired-submission/v1",
  "task_id": "NEURAL-091",
  "condition": "restricted_observation",
  "public_sha256": "<canonical digest of the entire public JSON packet>",
  "predictions": [{"key": ["session", "unit", "presentation"], "rate_hz": 1.5}]
}
```

The second envelope uses `condition: "frozen_program"`. The placeholder digest
above is illustrative; calculate the digest with the unchanged v1 `digest`
function (sorted compact JSON), not the raw file-byte digest. Every query key
must occur once in each envelope, with finite nonnegative rate Hz. Booleans,
negative/nonfinite rates, missing/duplicate keys, unknown fields and mismatched
public digests fail. Output row order is immaterial. Rates of zero are retained.
There is no automatic repair, candidate selection, or subset intersection.

From the repository root:

```sh
python3 -I -B benchmarks/neural/NEURAL-091/implementations/paired-condition-evaluator-v1/paired_conditions.py --public public.json --private private.json --restricted restricted.json --program program.json --output paired-score.json --bootstrap-seed 0 --bootstrap-replicates 1000
```

Keep protected source/export files inaccessible to participants. This command
runs only the scorer; it does not execute submitted programs. An operator must
separately freeze the candidate and training recipe, collect both complete
submissions before scoring, audit all actual information access, and prevent
feedback or cross-condition contamination. Identical packet hashes are a
**declared information binding**, not proof that each participant received or
used only that packet. A trained program may have additional pretraining,
training examples or state; neither those inputs nor the restricted condition's
history are represented or verified here. Compute and exposure are not matched.

## Preserved endpoint and paired difference

The preserved [complete-roster v2](../complete-roster-evaluator-v2/complete_roster.py)
checks all declared session/unit/presentation observations and exclusions, then
calls the unchanged [v1 scorer](../initial-evaluator-v1/evaluator.py). Each
condition retains its complete original report: mouse-macro held-out Poisson
bits per spike relative to train-only unit rate, family breakdowns, exposure-aware likelihood,
zero-rate behavior, mouse bootstrap and declared-roster counts. No units,
repeats, stimulus families or mice are selected based on predictions.

The additional contrast is **frozen program minus restricted observation** in
bits per spike, calculated within each mouse and then weighted equally across
mice. It is not a pooled spike/observation difference or the difference between
separately sampled confidence intervals. Its percentile interval resamples the
complete vector of paired mouse differences using one recorded seed; with fewer
than two mice or any nonfinite/undefined difference no interval is reported.
Each stimulus family is assessed with the same paired procedure. These intervals
are descriptive for the selected mice and do not establish population transfer.

The existing zero-spike or zero-training-rate-positive-target endpoint remains
undefined. A zero candidate rate at a positive target produces the existing
negative-infinity condition score. One finite score versus one negative-infinity
score yields a signed-infinity paired status; two negative-infinity scores yield
an undefined paired difference. Opposite signed infinities across mice also
leave the macro difference undefined. No undefined mouse is removed and no
numerical epsilon is introduced. All nonfinite results use explicit status
strings and JSON `null`, never nonstandard JSON `NaN`/`Infinity`.

## Qualification and source dependencies

The target is a held-out measured neural response for calibrated units. This
assessment is not direct interpretation of visible spikes: supplying query
spikes would reveal the target. Allowed stimulus input remains the registered
numeric/null attributes, without stimulus pixels. A competent stimulus-transfer
reference, authentic native export, native complete-cohort proof, enforced
access conditions and an executed scientific comparison remain absent.
`research_qualified`, `access_conditions_enforced`, and
`actual_information_access_verified` are always false in this component.

Dependencies, unchanged by this addition:

- v1 `evaluator.py`: SHA-256 `16606e98d575cce41cf18c0b8b20b3f6b313bccf1ec94bcfd52286c7d56153d4`.
- v2 `complete_roster.py`: SHA-256 `3fa62aaf3d85c4e377d8171fbcec172711fc775767c558ff4b4608b33f6dd8f9`.

The v1 source mapping retains AllenSDK commit
`a9b5c685396126d9748f1ccecf7c00f440569f69`; no source or historical pin changes.
The test suite uses tiny generated tables only. It covers a hand-calculated
unequally sized two-mouse cohort, preserved condition reports, calibrated-packet
mismatch, pre-private admission failures, roster omission, zero-rate and
undefined arithmetic, one-mouse uncertainty, and CLI ordering. It establishes
software behavior, not neural competence.

```sh
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-091/implementations/paired-condition-evaluator-v1 -p 'test_paired_conditions.py' -v
```
