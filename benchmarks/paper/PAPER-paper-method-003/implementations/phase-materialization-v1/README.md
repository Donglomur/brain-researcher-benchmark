# Materialize the existing REVE development and test views

This trusted preparation command copies an existing complete participant packet
into the two physical data directories required by
[`development-boundary-v1`](../development-boundary-v1/README.md). It uses that
component's unchanged compiler and descriptors. It does not create another
participant runner, open targets, decode EEG arrays, execute a model, or qualify
a scientific result.

The full original panel remains **109 people, 654 recordings and 9,837 epochs**.
Development contains 534 signal files with all 6,300 training and 1,734 validation
epochs and their permitted labels. Test contains all 1,803 opaque single-epoch
files without labels, original person/run identity or original order. Each phase
directory contains only `view.json`, `positions.json` and its exact `signals/`
membership. Paper, official code, pretrained assets, private maps and the full
participant manifest are not copied into either data directory. Both paper
access conditions produce identical phase data for the same selected packet.

The input is the combined directory produced by the existing
[`candidate-materials-v1`](../candidate-materials-v1/README.md) exporter. That
authentic full export and the subsequent physical phase export remain unperformed
by this source construction. Existing assets or compiler tests alone do not prove
that either physical packet is available.

## Operator command

Use Python 3.11 or later on POSIX with a new output path under an existing
operator-owned private parent (mode 0700). Supply independently selected material
and panel identities and explicit preparation allowances:

```sh
python3 -I -B materialize.py \
  --source "$PARTICIPANT_PACKET" --output "$NEW_PRIVATE_OUTPUT" \
  --materials-identity "$SELECTED_MATERIALS_IDENTITY" \
  --panel-identity "$SELECTED_PANEL_IDENTITY" \
  --read-bytes "$ADMITTED_READ_BYTES" --write-bytes "$ADMITTED_WRITE_BYTES" \
  --wall-seconds "$ADMITTED_PREPARATION_SECONDS"
```

The operator chooses these finite preparation allowances; they do not define a
scientific training, GPU or agent budget. `plan()` reports exact logical copy
extents from authenticated metadata and observed signal sizes before any output
directory is created. The real input must have those complete source files.
For the generated full-census metadata with 128-byte NPY headers, copied bodies
are 4,029,653,794 bytes, including the geometry copy in each phase. Real sizes must
be measured; this illustration is not an authentic export measurement. Phase JSON
and the private receipt require additional writes. Manifest reads also consume
the read allowance. Source imports, directory metadata, runtime I/O and physical
filesystem amplification are explicitly outside the logical data counters.

The command streams selected bodies in 64 KiB chunks, checks their selected hash,
extent and file identity, rejects symlinks/hardlink aliases and refuses an existing
destination. It copies bytes without replacing the exporter’s original array
validation. Failed work retains partial outputs and cumulative logical attempted
read/write counts in the raised `MaterializationFailure.detail` or CLI error JSON.
This detail covers ordinary in-process exceptions. Keyboard interruption, process
termination and blocked-system-call accounting require the external supervisor.
Failed destinations cannot be resumed. No recursive source directory is copied;
unselected source files are neither opened nor transported.

Each completed phase is read-only (directories 0555, files 0444). A private
`MANIFEST.json`, published last, records the existing mount descriptors and view
identities. It stays outside both participant phase directories. There is one
trusted writer inside the new private output root; atomic final rename does not
protect against that operator deliberately racing or altering its own files.
This is not a hostile-host security boundary. The existing Provider must still
authenticate exact output membership and file bodies before use. The materializer
checks bytes during copying; it does not perform a second independent destination
readback. Wall checks are cooperative, not a hard timeout for a blocked syscall;
an admitted operator must retain external supervision for an authentic export.

## Focused construction controls and remaining work

```sh
python3 -I -B tests/test_materialize.py
```

The controls exercise complete 9,837-epoch metadata and exact phase/cost planning,
identical A/B data, source/identity/extent refusals, cumulative limits, path aliases,
mutation and hash failures, and tiny actual streamed copies/closed publication.
The full-census orchestration test replaces phase body staging with a recorder;
the separate tiny physical tests use the real unchanged copy/staging primitives.
They do not perform a 4 GB generated export or authenticate real EEG bytes.

Runtime and scientific qualification remain false. Genuine protected provider
deployment, physical authentic packet preparation, matched campaign budgets,
release-aware private outcome continuation and author calibration are still
required. Historical Table 12 preprocessing, downstream classifier/checkpoint and
seed/run/SD parity remain unresolved. The prospective full-test-context profile
still requires its separate outcome binding and cannot silently become the
current paper-win condition.
