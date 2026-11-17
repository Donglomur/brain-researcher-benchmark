# Complete localization scorer and geometry-centroid negative control

This portable source component supports the existing registered task
`NEURAL-SCOPE-20261114-LOCALIZATION`. It preserves all **880 cases: 11 cells ×
16 degradation conditions × 5 realizations**, and every requested individual
spike and template. These are cases within one task, not 880 benchmarks or animals.

`neutral_contract.py` is the complete previously reviewed scorer and normalized
input projection, unchanged byte for byte. `centroid_control.py` implements the
registered geometry-centroid negative control. Its prediction is the arithmetic
mean of every probe contact's two ordered coordinates in µm. It reads no
waveform, template, observed-support mask, corruption mask or spatial-target body.
It is intentionally a negative control, **not a competent localization baseline**.

The existing scorer uses strict Euclidean error `<50 µm`, approximate
nearest-contact reference positions and full support. It reports spike and
template accuracy separately and balances cells within recordings, recordings
within animals, animals within conditions, then conditions. It also reports
template stability against the same cell and realization's undegraded estimate.
Zero apparent drift may coexist with substantial absolute localization error.

## Portable use

Only Python's standard library is required. The file reader uses Unix
`O_NOFOLLOW`/`O_NONBLOCK`; these interfaces are not claimed portable to Windows.
Keep every member named by [SOURCE.json](SOURCE.json) together. Its hashes bind
the exact package; the pinned CI step authenticates that manifest before import.
This is source delivery, not an installed data collection or qualified runtime.

The control's existing `--repo-root` argument now names **this component
directory**, containing its pinned `neutral_contract.py` dependency. It does not
need a private repository, an installed package or the working directory:

```text
python3 -B components/localization-centroid/centroid_control.py \
  --repo-root components/localization-centroid \
  --manifest OWNER_NORMALIZED.json --manifest-sha256 RAW_MANIFEST_SHA256 \
  --program-sha256 PUBLISHED_CENTROID_SOURCE_SHA256 \
  --participant-root PREPARED_INPUT_ROOT \
  --geometry-byte-budget COMPLETE_UNIQUE_GEOMETRY_BYTES \
  --output NEW_PREDICTIONS.json --receipt NEW_CONTROL_RECEIPT.json
```

This illustrates the interface; no authentic execution is selected by publication.
The owner supplies a complete source-qualified normalized manifest and selected
resource allowance. Geometry bodies are looked up only as
`PREPARED_INPUT_ROOT/inputs/<sha256>.npy`, authenticated in full, then decoded as
primitive NPY N×2 coordinates. Every contact contributes, independent of masks.
Any inconsistent fixed-cell contact mapping, missing case or insufficient whole
geometry allocation is refused. Ordered axes and units are never inferred.

The callable interface is:

```python
submission, control_receipt = centroid_control.produce(
    normalized_neural, geometry_loader,
    repo_root=component_directory,
    expected_manifest_sha256=canonical_neural_sha256,
    expected_program_sha256=published_centroid_source_sha256,
    geometry_byte_budget=complete_unique_geometry_bytes,
)
report = neutral_contract.score(
    normalized_neural, trusted_owner_reference, submission,
    frozen_program_sha256=published_centroid_source_sha256,
)
```

Import the modules from this component directory using ordinary Python import
configuration. The trusted owner must authenticate the reference before this
pure scoring call; the scorer is not a protected-file loader, candidate sandbox
or reference-custody mechanism. See [SPECIFICATION.md](SPECIFICATION.md) for the
complete normalized ABI and scientific scope. Program identity is part of the
submitted artifact and must agree with the separately frozen identity.

Outputs are exclusively created, but prediction and receipt writes are
sequential, not crash-atomic. A failed receipt write may leave predictions; an
external owner must preserve and reject incomplete outcomes. Input identities
are required before file access, with nonblocking regular-file admission and
final-symlink refusal. Parent-directory trust, effective isolation, arbitrary
callback behavior, runtime deadlines and aggregate memory enforcement remain
external. The producer's receipt describes its own requested roles only.

## Checks and limits

`test_centroid_control.py` carries the 13 generated scientific and input-boundary
checks. `test_relocation.py` adds three new checks for exact package closure,
full 880-case CLI/scorer use from an unrelated directory, and refusal of a changed
local dependency or program before geometry access. The public CI job explicitly
loads both suites and requires all 16 tests; it does not depend on recursive
test discovery. The relocation phase reruns only its three new checks locally.

All fixtures are invented. Prior independent controls distinguished the intended
hierarchical accuracy 13/24 from cell pooling 3/11 and spike pooling 5/21, while
every stability distance remained zero and absolute errors reached 200 µm.
These values describe software controls, not authentic biological or model results.

The original corpus/normalizer, exact geometry and gain, ordered channel/axis
mapping, condition labels, spatial proxy workbook/index convention, biological
recording/animal joins and competent native COM/MT/GC methods still need
qualification. The selected 11 paired cells do not represent all 43 original
recordings. Synthetic corruption is not biological electrode loss. There is no
new tolerance, reduced-support exception, readiness claim, model run or scientific
benchmark-count increase. No original arrays, private targets, signed URLs,
historical integration metadata or private source tree are included.
