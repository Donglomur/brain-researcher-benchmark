# Complete normalized CCEP observation transport

This component connects the existing validated complete-block envelopes to a
readable participant request and connects a four-compartment response back to an
existing scorer row. Original export works for every declared ready case,
including singleton or nonpermutable cases with no pairing control. Paired export
uses the existing exact target-free map and complete donor response, retaining
recipient times, units, masks and recording-location context. Both conditions
have the same public schema and numeric representation.

This is source-only normalized transport. It does not read native MEF, construct
anatomy labels, authenticate original clinical inputs, fit references, enforce
no-tools access, launch participants or establish scientific readiness. The
five-patient census, four classes, patient-macro loss, LOPO folds and existing
source identities are unchanged. A successful per-case export is not full-cohort
evaluation or evidence that a model understands a neural waveform.

## Exact dependencies

Keep this folder next to `clinical-ccep-pairing` and
`clinical-ccep-artifact-grading`. Standard-library Python 3.11+ on POSIX suffices.
The loader authenticates pairing.py (24,583 bytes,
`d3b0b2765d56904fb565099e876562d3f327df52a3489868aa774ac1a27b90a3`),
which authenticates score.py (14,609 bytes,
`2426ddc5585a113fb839e3b3dd78bf2c684d3f0d5fef2dac0b9af4ab1ebd6f32`).
No historical package, pin or scientific contract is rewritten.

## Export and response

The operator first supplies the existing frozen primary policy, control policy,
and complete normalized blocks. Their clinical authenticity, anatomical joins,
full-census completeness, target-free context and permissions remain separate
obligations. Paths, policies, maps, private bindings and collected rows stay
outside participant access. Use an opaque observation alias, never a patient,
contact or anatomical identifier. The exporter cannot recognize semantic leaks
inside an operator-supplied alias or recording-location descriptor.
Freeze a distinct opaque observation alias for each case and condition in a
delivery batch before participant outputs, then reuse the same exact request
bytes across compared arms. This stateless exporter cannot enforce batch-wide
alias uniqueness. Repeated aliases with identical payloads have identical
response tokens: the token checks payload identity, not a unique trial or
execution receipt.

For an original case, from a private operator directory with restrictive umask
and no-clobber output names:

```sh
python3 -I -S -B /absolute/path/to/observation.py export \
  --policy POLICY.json --policy-sha256 POLICY_SHA256 \
  --control CONTROL.json --control-sha256 CONTROL_SHA256 \
  --case-id PRIVATE_CASE_ID --packet COMPLETE_BLOCK.json \
  --observation-id observation-001 --max-public-bytes 100000 \
  --binding-output NEW_PRIVATE_BINDING.json > NEW_PUBLIC_OBSERVATION.json
```

The capacity is an operator-selected UTF-8 JSON byte limit, including the final
newline, no larger than the existing 8 MiB document ceiling. The example value
is not a claim of model context capacity. The complete observation either fits
or is refused before a binding is created; no repetitions, samples, nulls or
masks are dropped. Context overflow must remain in the complete task coverage
accounting. Byte capacity alone does not establish a model-specific token or
rendering limit. Exact decimal time strings are retained without resampling;
JSON numeric values are decoded without changing the original matrix.

For a paired case, add **all four** of `--map`, `--map-sha256`, `--transform-id`
and `--donor-packet`. The existing map and envelope validators admit the
transformation. No map is needed for original export. Unsupported null cases
still belong to original full-scope evaluation; do not replace an unavailable
paired case with its unchanged original input.

The public request contains only schema/task identity, opaque `observation_id`,
the fixed class order, complete `response` matrix, `relative_times_seconds`,
`units`, `missing` and `artifact` matrices, `recording_location`, response schema
name and a `response_token`. It contains no private case/patient/session/site/
contact IDs, map, donor identity, condition label, target hash or policy digest.
The token is the SHA256 of canonical request bytes before the token field is
added; participants copy it rather than compute a hash. The private binding
also records the hash of the complete emitted request bytes.

Ask the participant to return exactly these fields in JSON, copying the alias
and token from its request and using the displayed class order:

```json
{
  "schema": "ccep-observation-response-v1",
  "observation_id": "observation-001",
  "response_token": "<copy the request token>",
  "probabilities": [0.25, 0.25, 0.25, 0.25]
}
```

Freeze the operator-produced binding bytes and hash at export. Collect with
that externally trusted hash:

```sh
python3 -I -S -B /absolute/path/to/observation.py collect \
  --policy POLICY.json --policy-sha256 POLICY_SHA256 \
  --binding PRIVATE_BINDING.json --binding-sha256 BINDING_SHA256 \
  --response PARTICIPANT_RESPONSE.json > NEW_PRIVATE_COLLECTED_ROW.json
```

Collection checks the request alias/token and reuses the current scorer's exact
four-probability admission, without normalization or repair. It never opens
targets. It returns an evaluator-only wrapper identifying original or paired
condition and a `row` with private `case_id` and `probabilities`. Assemble all
original rows into the existing `ccep-predictions-v1` artifact, or paired rows
under their recorded transform in `ccep-paired-predictions-v1`; the existing
scorers enforce the exact full original census and exact supported null sets.
This component intentionally does not score a partial row collection or accept
participant-supplied policy, binding hashes or condition assignments.

Provide byte-identical request bytes, matched train-only evidence and the same
capacity policy to compared arms. Training references are not created here.
External process/filesystem isolation, direct/no-tools compliance, frozen versus
case-adaptive lifecycle, cost matching and full authentic evaluation remain
unimplemented obligations of a protected runner. Source transport is not that
runner.

Exit 0 is an admitted source operation; exit 2 is a generic refusal. A binding
file is created exclusively with mode 0600 and is never overwritten. Keep any
partial output from a failed filesystem write; successful binding creation
alone does not prove delivery of stdout to a participant.

## Generated controls

Run from any directory:

```sh
python3 -I -S -B /absolute/path/to/test_observation.py
```

The suite uses only the existing invented pairing fixture. It checks full
original delivery with no null support, paired donor/recipient conservation,
strict schema and response identity, source/current-scorer compatibility,
complete capacity refusal and malformed matrix/hash/mask/time rejection. No
clinical recordings, targets, model calls or biological results are included.
Code and generated controls are original project-MIT software; external clinical
source and data rights remain separate.
