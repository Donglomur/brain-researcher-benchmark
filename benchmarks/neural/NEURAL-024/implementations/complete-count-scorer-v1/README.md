# Complete count likelihood scorer

This implementation restores the numerical evaluator for NEURAL-024's existing
finite Indy 2016-10-05 → 2016-10-06 development episode. It implements the
mathematics specified in the current task and delivery contract; it is new code,
not a recovered copy of the historical scorer. Historical files and canonical
contracts remain unchanged.

`score.py` requires every sequence 0–22099 and every one of the 96 electrode
channels. Sequences 0–9 are validated warm-up and excluded from every metric;
sequences 10–22099 correspond to target bins 3010–25099. Expected values are
strictly positive finite **counts per 20 ms bin**, with no Hz conversion.
Observations are unsigned 32-bit integer counts. Sorted units are not inferred
or matched across days.

The scorer sums full Poisson log-likelihood, including `lgamma(count + 1)`, and
reports mean NLL, per-channel descriptive scores, and signed log-likelihood and
bits-per-spike contrasts against all six named references. Every contrast uses
the same complete support. The primary contrast is against `calibration_rate`.
Bits per spike uses total observed spikes, not mean channel-wise bits per spike.
Quiet channels remain in the likelihood; a zero spike denominator produces JSON
`null` and `undefined_zero_spikes`. Nonfinite arithmetic fails without a score.
Compensated sums and direct likelihood contrasts avoid unnecessary cancellation.

## Input and operator use

There are two separate JSONL streams. Every line is a JSON object terminated by
a newline; duplicate fields and extra fields are rejected. Candidate records
have exactly `sequence` (integer) and `means` (96 numbers). Operator records have
exactly `sequence`, `counts` (96 integers), and `reference_means` (a mapping of all
six names below to 96 positive finite numbers):

- `source_rate`
- `calibration_rate`
- `self_history_frozen`
- `self_history_adapted`
- `self_population_history_frozen`
- `self_population_history_adapted`

The operator must freeze the complete outcome/reference stream and its SHA-256
before evaluation and keep it outside participant mounts. The scorer never fits,
regenerates, clips or selects references. The six historical reference arrays
are not included or qualified by this component. Their procedural provenance
must be established separately; a hash alone cannot establish lawful fitting.
The CLI requires that externally trusted hash, reads the outcome stream once,
and releases a result only after all rows and the consumed-byte hash validate.

```sh
python score.py --predictions candidate.jsonl \
  --operator-outcomes /operator/episode.jsonl \
  --operator-sha256 OPERATOR_FROZEN_SHA256
```

The CLI prints a JSON result or exits 2 with `No score`. It does not print private
target paths in successful results. Use Python 3.10 or newer; standard library
only. Do not supply authentic private files until a separately frozen preparation
and scoring protocol is authorized. The example paths are placeholders.

## Boundaries and validation

This is an **offline numerical scorer**, not a participant controller or the
historical nonce-bound protocol parser. Its JSONL format is a scoring interchange,
not a claim of byte compatibility with a missing historical transcript format.
It cannot prove current-count concealment, durable commit-before-reveal, process
isolation, a stopped acknowledgment, or absence of prior NEURAL-023 exposure.
`causal_access_established` is always false. It must not be used as a replacement
for trusted causal transcript admission. Source presence, preparation, causal
execution, reference qualification and model performance remain separate.

The generated tests use two full 22,100-round, 96-channel episodes with analytic
answers: mixed quiet/active channels and a zero-spike episode. Other controls
exercise invalid values, missing support, identities, extras, line limits,
duplicate JSON fields, overflow and digest mismatch. They use no authentic data,
no target cache, fitting or model execution. Run through the wave's reviewed test
pool; test evidence belongs outside Git.

Remaining gaps are recovery/authentication of count and reference assets, exact
historical reference recipes, trusted causal runtime and protocol admission,
actual matched reference execution, and additional chronological day pairs.
One monkey/day pair does not establish stable neural mechanisms or population
generalization. No benchmark-ready, protected-test, new solver or scientific
performance claim follows from this component.
