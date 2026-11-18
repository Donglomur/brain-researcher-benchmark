# Retained-epoch metadata bridge

This component supplies the missing connection between the source event tables,
a separately supplied MNE `Epochs.selection` export and the existing
[six-fold AUROC scorer](../oddball-auroc-v1/README.md). It projects metadata for
all twenty original sensor participants and the 158-run inventory. It reads no
MEG samples, fits no decoder and does not establish either scientific outcome.

The source [metadata producer](https://github.com/mathias-sm/AGeometricShapeRegularityEffectHumanBrain/blob/133669b577b5ae341cd0842dfb0e7f0af85c0020/MEG/add_metadata.py)
first concatenates run event tables, derives the shape/miniblock labels and only
then selects retained epochs. The bridge preserves that order. Removing rejected
events before labeling would incorrectly turn later trials into early trials.
The source counter resets when the shape changes or after index 29. It does
**not** explicitly reset at run boundaries; this behavior is preserved even when
a run begins with the same shape as the preceding run. These are source-code
semantics, not proof of the published preprocessing lineage.

Each returned `trials` row has exactly the five fields accepted by
`oddball_auroc.fold_plan`: `trial_id`, `run`, `shape`, `condition`, `is_early`.
Reference and outlier labels retain the scorer's original meaning. Stable IDs
hash the subject, original run, original run-row position and event-file hash.
They remain unchanged when retained epochs are reordered. A separate
`retained_epoch_lineage` table records the supplied selection position, full
concatenated event index, original run-row index and miniblock counter.

This is only the metadata subset needed by the selected oddball endpoint.
It does not recreate the source's symbolic-property columns or qualify the
separately retained biological/RSA finding family. It does not choose a time
window, scalarize the full AUROC family or infer a paper-win rule.

## Operator input

The command uses Python's standard library:

```sh
python3 epoch_lineage.py manifest.json INPUT_DIRECTORY lineage.json
```

The output is created exclusively. All referenced input files must be regular
files beneath `INPUT_DIRECTORY`, with canonical relative paths and no symlink
components. Each file is read once with a size bound and compared with its
declared SHA-256. The one-MiB manifest, eight-MiB per-file and 128-MiB aggregate
limits are explicit construction limits; an oversized input is rejected, never
truncated or silently reduced. Their adequacy for the authentic preparation has
not been measured. The confined reader is an operator utility, not an OS sandbox.

The manifest has exactly `schema`, `source_revision` and `subjects`:

```json
{
  "schema": "root010-epoch-lineage-input/v1",
  "source_revision": "133669b577b5ae341cd0842dfb0e7f0af85c0020",
  "subjects": [
    {
      "subject": "sub-01",
      "events": [{"run": 1, "file": {"path": "sub-01/run-01_events.tsv", "bytes": 123, "sha256": "..."}}],
      "selection": {"path": "sub-01/selection.json", "bytes": 123, "sha256": "..."}
    }
  ]
}
```

The shortened example is not executable. Supply every subject `sub-01` through
`sub-20`, and runs 1–8 for each, except runs 1–7 for `sub-10` and `sub-11`.
Missing, duplicate or extra identities fail before event-file reads. Each TSV
must contain all original rows in their source order and a unique `trial_type`
column. The accepted grammar is a nonempty prefix, one of the eleven source
shape names, `reference` or `outlier`, and an optional subtype 0–4. Unexpected
grammar fails; no event is silently reinterpreted as an outlier.

Each selection export has exactly:

```json
{
  "schema": "root010-mne-selection-export/v1",
  "subject": "sub-01",
  "selection": [6, 7, 10],
  "prepared_epochs": {"bytes": 123, "sha256": "..."}
}
```

The indices must be the complete, independently exported `Epochs.selection`
in prepared-epoch order. They must be unique integers within the concatenated
event table, and must not be rebuilt by counting retained rows. Reordered
selections are preserved. This utility does not open FIF, extract the selection,
check the declared prepared-FIF hash against a FIF file, or establish the
equivalence of MNE original epoch indices with the supplied full BIDS event
table. The output names this identity `prepared_epoch_identity_declared_unverified`
so a declaration cannot be mistaken for completed provenance verification.

All output is evaluator-owned: it contains conditions, run identities and
lineage. It is not a candidate input package. An independently qualified
preparation/participant protocol must enforce the file-level exposure boundary
and the six overlapping directional folds. Passing this bridge does not prove
training isolation or label secrecy.

## Qualification and checks

The original event bytes, actual retained-epoch export, final-paper/code
correspondence, epoch grid, scaling, smoothed producer, strongest author
baseline and complete author predictions remain unresolved. Matching supplied
pins proves only those supplied file bytes; it does not authenticate upstream
source identity. Both scientific outcomes remain unknown and the task remains
source-unresolved. No task contract or central authority changes are included.

The generated controls exercise pre-rejection labels, counter wrap and run
boundaries, selection order, all 20 participants/158 runs, exact compatibility
with the existing six-fold planner, file tampering, malformed metadata, path
containment and exclusive output. The tests use generated metadata only. In an
existing environment with NumPy for the unchanged scorer dependency:

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

The bridge itself needs no NumPy, MNE, installed service or network connection.
