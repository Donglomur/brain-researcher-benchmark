# PhysioP300 converter event-lineage audit

This operator utility turns captured converter metadata into a complete account
of intended export keys, dropped events and cross-recording key collisions. It
does not repair the converter, run MNE, read EEG, or decide paper reproduction.
It addresses one explicit blocker in `improvement.v1.json`: an epoch index
restarted in each recording cannot identify an event across recordings.

The pinned [author converter](https://github.com/BINE022/EEGPT/blob/ea7282f698c406cd423ccbedbe9960853761144c/datasets/downstream/prepare_PhysioNetP300.py)
epochs the full event array, skips descriptions beginning with `#` only after
epoch construction, and writes under a class directory using the retained
epoch ordinal and nominal subject token. Thus a retained metadata epoch affects
the filename ordinal even though that epoch is not exported. Removing rejected
epochs also changes ordinals. Reconstructing names from original annotation
indices would therefore give the wrong collision analysis. The converter visits
eight nominal subject tokens; the current paper task's probe roster includes
subject `1` as a ninth token. Both facts remain visible in every report.

## Inputs and use

Run only in operator custody; input and output include target labels:

```sh
python3 -B audit_export.py --inventory /operator/recording_inventory.json \
  --epoch-metadata /operator/epoch_metadata.json > /operator/lineage_audit.json
```

The inventory has schema `physiop300_recording_inventory_v1` and a `recordings`
list. Each item has `recording_id`, `subject_id`, `source_member`, `source_bytes`
and `source_sha256`. It must retain all nine nominal probe tokens
`1,2,3,4,5,6,7,9,11`, with unique recording and source-member identities.
These declarations do not prove that the recording list is complete or that
tokens identify distinct biological people.

The second document uses `physiop300_converter_epoch_metadata_v1`, the canonical
JSON `inventory_commitment` returned by `commitment(inventory)`, the pinned
`converter_source_sha256`, and a `recordings` list covering exactly the eight
converter tokens. Each recording contains:

- `recording_id` and the matching `source_sha256`;
- the complete `event_id` description-to-code mapping;
- the original MNE `events` rows `[sample, previous, code]` supplied to Epochs;
- `selection`, preserving original event indices after loading and rejection;
- the full original-event `drop_log`, with empty lists for retained events and
  nonempty reason lists for dropped events.

Capture this information before resetting, concatenating or reindexing epochs.
An actual collector and its MNE version must be independently qualified before
authentic use. The [MNE documentation](https://mne.tools/stable/generated/mne.Epochs.html)
defines the original-event index and drop-log relationship used here. Its
currently viewed version was1.13.2, not an authenticated version of the paper's
environment. The utility refuses inconsistent selections, ambiguous target
annotations, unknown event codes, changed source declarations and missing or
extra recording captures. It does not resolve the paper's environment.

## Interpretation

The [provider's protocol](https://physionet.org/content/erpbci/1.0.0/) describes
one matrix-speller character per recording and annotations for target identity
and flashed character sets. Its [README](https://physionet.org/content/erpbci/1.0.0/README)
documents the relationship between the EDF annotation channel and `.event`
companions. This utility accepts normalized metadata; it is not a decoder of
either binary format and does not authenticate their equivalence.

`intended_writes` preserves recording identity, original event index, sample,
retained ordinal, target class and legacy output key. Collision groups retain
all competing events. `displaced_writes_if_all_writes_completed` is conditional
arithmetic: it does not establish that any historical writes completed or
recover their order or surviving samples. In particular, `os.listdir` order
and preexisting output directories are unknown; the source's directory-creation
call does not itself ensure the class output directory exists.

No actual source metadata, arrays or model outputs are bundled or used in the
generated controls. The nine/eight-token conflict, original event completeness,
paper/converter epoch mismatch, reporting reduction, checkpoint exposure,
author/control calibration and protected evaluation remain unresolved. The
task's readiness and both outcome contracts are unchanged. This is a proposed
source component awaiting registry and CI enrollment, not an admitted runtime.

Run `python3 -B test_audit_export.py` for focused generated controls. In the
current construction environment, invoke it only through the existing shared
two-slot test pool. The CLI limits each JSON read to16MiB, but is not an
untrusted participant sandbox or a physical-memory enforcement boundary.
