# Complete worm-response participant transport

The initial evaluator exported original case, animal, acquisition and trial
identifiers and had no participant response collector. This component replaces
those administrative identifiers with keyed aliases, exports all permitted
samples, and collects a complete exact-grid answer into the existing scorer's
format. It preserves the retrospective source-to-receiver calcium target,
training-only references and equal-worm endpoint.

`participant_transport.py` uses the original evaluator at SHA-256
`4fde8b08dc090d6b0b3d79d8fb8e10b0e0145e78620c184c6880d83f9f6e0485`.
It refuses a changed predecessor until explicitly reviewed and repinned.
Canonical definitions and predecessor code remain unchanged.

## Operator use

Provision a secret random key of at least 32 bytes and an audited custody dataset
outside the participant directory. Parent directories must already exist. Output
paths must be new; none is overwritten. With existing Python 3:

```sh
python3 participant_transport.py export /operator/custody-data.json /operator/key.bin /delivery/public /operator/transport-custody.json
python3 participant_transport.py collect /delivery/public/packet.json /operator/transport-custody.json /incoming/answer.json /operator/custody-data.json /operator/predictions.json /operator/receipt.json --mode direct_observation --key-file /operator/key.bin
python3 ../initial-evaluator-v1/worm_evaluator.py score /operator/custody-data.json /operator/predictions.json /operator/score.json
```

Export creates `packet.json` and a response template for each of
`direct_observation`, `typed_viewer`, `tool_assisted`, and `frozen_program`.
All four use the same packet digest, case roster and time grid. The operator
assigns a condition; collection checks that assignment against the response.
Mode labels document the intended route. They do not enforce a tool prohibition,
launch a viewer, freeze or run a programme, authenticate a participant, or measure
performance. No visual route is required for using the numerical transport.

The response template contains null placeholders at **every** requested held
timestamp, independent of the private target mask. A participant replaces every
placeholder with a finite predicted fluorescence value in the stated units.
Collection rejects omissions, additions, duplicates, changed timestamps, wrong
units, wrong bundle/condition, unknown fields, booleans as numeric predictions,
nonfinite values and duplicate JSON keys. Response order may change; coverage may
not. The private mapping recovers original evaluator case IDs without exposing
target values. The collector authenticates the unchanged custody dataset before
creating scorer inputs; it never calculates a metric or returns score feedback.
Collection also requires the original export key and checks each public case
alias against its private original case ID. This rejects a swapped or changed
private case mapping even when the cases share timestamps and the source dataset
is unchanged. A dataset checksum alone cannot establish this correspondence.
Keep the key outside participant access; it is never copied into packets or
receipts. API callers pass it as `collect_response(..., key=key_bytes)`; the CLI
requires `--key-file` and refuses mismatches before creating scorer outputs.

Aliases use namespace-separated HMAC-SHA256 over typed identity tuples. Shared
worms/acquisitions/trials stay grouped, and locally repeated trial labels in
different acquisitions do not collide. Anatomical source/receiver identities,
condition, stimulus parameters, acquisition-relative onset, original irregular
timestamps, signal values and input missingness remain unchanged. Training
responses remain available only in the training packet. Held/development target
values, masks, quality flags, source locators and target-dependent custody hashes
are absent from public output. Changing hidden values/masks changes only the
private custody commitment, never the public packet or response template.

This removes direct administrative-ID lookup. It does not anonymize distinctive
public signals or establish an unexposed holdout. Retained biological identity,
condition, timing and signal measurements may support linkage to public data;
the task's exposure review remains necessary. File permissions reduce accidental
export, and are not execution isolation. An operator must keep custody, key,
source dataset, predictions and scores outside participant access.

## Source and qualification scope

This implementation consumes the existing normalized custody schema. It does
not download or extract authentic signals. The inherited immutable release is
[DANDI 001075/0.240930.1859](https://dandiarchive.org/dandiset/001075/0.240930.1859).
The prior source review pins the [official converter at
3544c9bb](https://github.com/catalystneuro/leifer_lab_to_nwb/tree/3544c9bb59f90d5630fa1871850d990db9cafc18)
and [author source at
1dbc5e0a](https://github.com/leiferlab/pumpprobe/tree/1dbc5e0a2b609d54bc9b1c90c73d4e3bf183d3c7).
See [the original numerical/source interface](../../docs/initial-evaluator-v1.md)
and [pinned source review](../initial-evaluator-v1/provenance.json).

Complete authentic trace extraction, independent worm/ROI/condition joins,
missing segmentation partners, original stimulus parameters, OSF scope,
exposure review and participant execution remain unresolved. No authentic data
preparation, model result or scientific qualification is claimed. Numerical
roundtrips test generated engineering fixtures only; none supplies a reference
biological result. Source input still extends through +30 seconds, so scores
remain conditional reconstruction rather than prestimulus forecasting or proof
of synaptic connectivity.

Run the generated checks through the shared bounded test pool:
`python3 -B -m unittest discover -s tests -v`.
