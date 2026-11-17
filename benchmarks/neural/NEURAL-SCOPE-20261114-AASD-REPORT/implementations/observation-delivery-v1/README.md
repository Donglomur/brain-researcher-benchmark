# AASD normalized observation delivery

This component fills the gap between the existing evaluator's case plan and numerical participant inputs. It extracts the exact common EEG slice, preserves the complete supplied stereo waveform, creates separate opaque request IDs for paired tool-assisted and frozen-program conditions, and joins complete responses back to the unchanged evaluator. It is newly written standard-library Python; no official MATLAB code is copied.

This is a tested construction path over generated normalized observations. It does not establish an authentic MAT adapter, native alignment, a trained decoder, an isolated participant runner, a direct-input condition, a typed viewer, or scientific qualification. The original task, history, initial evaluator, biological target, cohort denominator and modes remain unchanged. Programme performance would not establish direct neural interpretation.

## Run

From this directory, with Python 3.10 or later:

```sh
python3 aasd_delivery.py export INVENTORY.json OBSERVATION_MAP.json PUBLIC_ROOT PRIVATE_BINDING.json
python3 aasd_delivery.py join INVENTORY.json PRIVATE_BINDING.json frozen_program RESPONSES.json PREDICTIONS.json
python3 ../initial-evaluator-v1/aasd_evaluator.py score INVENTORY.json --predictions PREDICTIONS.json --output SCORES.json
```

Use `tool_assisted` for the other arm. There is no default mode that could mislabel a programme result as interpretation. Outputs must not exist. The private binding must be outside the public tree and is created with owner-only permissions. The exporter publishes the public directory only after successful preparation of both arms; a failed export removes its staging output. Existing files are never overwritten.

`INVENTORY.json` is the unchanged full 18-person, 1,260-slot `aasd-inventory-v1` interface documented in [the initial evaluator](../../docs/initial-evaluator-v1.md). `OBSERVATION_MAP.json` is an evaluator-only object mapping native-normalized `trial_id` values to observation JSON paths, resolved relative to that map. Both files contain protected metadata and must remain operator-owned. No authentic observations or targets are included here.

Each normalized observation has exactly these fields:

```json
{
  "schema": "aasd-normalized-observation-v1",
  "channels": ["C3", "C4"],
  "eeg_unit": "uV",
  "eeg_samples": [[0.0], [0.0]],
  "audio": {
    "sample_rate_hz": 48000,
    "sample_origin_ns": 0,
    "samples": [[0.0], [0.0]]
  }
}
```

The one-sample values illustrate field layout only and are not a valid trial. This example does not assert that the native recording has two EEG channels. EEG is channel-major, with every row exactly `sample_count` long on the inventory's fixed 128-Hz grid; units are explicitly `V` or `uV`. All used trials must share the identical cleaned electrode-name order and unit. A future native adapter must verify the retained channels and their meanings, rather than infer them from this interface.

Audio is the complete presented stereo waveform in channel-major normalized PCM, with finite values in `[-1,1]`. The declared integer rate and origin must cover the complete trial. The exporter does not resample, filter, align, change gain, derive envelopes, trim audio to one second, or infer left/right stimulus mappings. Its two streams preserve source ordering; identifying that ordering remains an operator obligation. Negative audio origins or trailing audio are retained identically for both arms. Exact rational coverage uses integer cross-products, avoiding rounded sample-clock decisions.

Only the common 256-sample EEG span chosen by the existing evaluator is emitted for each eligible target. The local EEG time begins at -500 ms relative to the one-second target; the full valid mask is 256 true values because the evaluator admits only completely valid contexts. Nonfinite values in a context fail export without deleting cases. Invalid values outside all admitted contexts do not create an additional exclusion. Eligibility and missing-class rules remain those of the original evaluator.

## Public and private artifacts

Each arm contains `index.json`, `packets/<opaque-request-id>.json` and `audio/<opaque-resource-id>.json`. Packet fields are explicitly constructed from the admitted observation; no prepared evaluator row is serialized. Participant, mixture, original trial, block/order, condition, key event, initial report, label, exclusion, guard stratum and source-path fields are absent. Index order is randomized through independently sampled IDs, and file modification times are normalized. The public index contains request IDs only. All participant/mixture-cell routing stays evaluator-only, including the grouping of requests that share a decoder.

Audio resources are stored once per distinct waveform per arm. Content hashes identify equality of already permitted waveform bytes; they are not anonymization claims. The packet includes the complete audio origin relative to the target so that the waveform and EEG can be aligned. This reveals the target's location within the admitted waveform, which is necessary for reconstruction; it does not reveal native trial order. Matching repeated speech from the waveform itself remains possible and is part of the stimulus-overlap and contamination problem, not solved by renaming files.

Every paired case has byte-equivalent numerical `observation` content and the same full-waveform digest. Request/resource names are independently random between arms. The private binding contains the evaluator case join, inventory digest, participant/fold routing and observation digest. It must remain inaccessible to participants. The arm response is a JSON list of exactly `{"request_id":"opaque ID","p_right":0.7}` rows. Response order may vary. Missing, duplicate, unexpected, cross-mode or malformed responses fail; dropping passive cases also fails. The binding is checked against the complete freshly prepared inventory before joining. An inventory change, including report-state changes, invalidates the join.

The binding and observation hashes support operator auditing; they are not signatures against a malicious operator or a sandbox. A protected runner must serve only one authorized case plus its audio resource at a time: exposing the entire export directory to a candidate would allow adjacent-window pooling beyond the common EEG context. It must verify immutable input artifacts, enforce model-to-cell assignments, isolate labels/private files, prevent cross-arm state transfer, supply permitted train-only fitted artifacts, and record execution provenance. This component supplies observations and joins, not that runner. Direct observation and typed viewer access remain undelivered; it would be inaccurate to relabel these numerical files as either mode.

The loader is called once per trial with eligible cases, and the writer retains one trial and one current packet at a time. Full audio deduplication limits repeated waveform storage. EEG is repeated where the required 2-second contexts overlap, intentionally preserving identical observations without permitting adjacent-case access through a shared full-trial EEG file. Native disk/RAM estimates must be frozen before authentic use; the generated tests do not qualify a full-corpus resource budget.

## Verification and source bounds

`tests/test_aasd_delivery.py` exercises exact independently indexed slices, stereo preservation, cross-arm equality, metadata allowlists, 18-person/54-cell routing, complete active/passive scoring through the original evaluator, missing/nonfinite/cross-mode responses, modified bindings, failed-export cleanup, private-path separation and common-channel mismatch. Run these generated controls through the project's approved lightweight test pool. No training, inference, native numerical preparation, network calls or private target access occurs in these tests.

The design follows the current `understanding.v1.json` and the retained source review of [the AASD paper](https://doi.org/10.1038/s41597-026-07244-w), [Zenodo 17413336](https://zenodo.org/records/17413336), and [official preprocessing commit 033856b3f4762b5fa33bc096b0de9f04bf0b5205](https://github.com/XXuefeii/AASD-Processing/tree/033856b3f4762b5fa33bc096b0de9f04bf0b5205). Cached pinned README/preprocessing text was inspected; no new source fetch was made. Trigger-coded filenames in that source motivate stripping native identifiers. The official preprocessing still does not resolve the complete passive census, channel identities, event indexing, EEG/audio alignment or connected stimulus family graph. Existing rights, source preprocessing and motor/report ambiguity limits remain in force.
