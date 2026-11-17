# Complete REVE participant materials

This operator command turns the existing complete PhysioNet preparation into a
physical participant directory. It supplies every declared signal epoch, training
and validation labels, the original paper, and the same electrode geometry in both
paper access conditions. Test labels and original test identities remain outside
the directory. The
code-assisted condition additionally receives the exact official source archive.

This closes a missing delivery step in the
[original PhysioNet route](../original-physionet/README.md). That route's `inputs/`
contains signals but no training labels; its `operator/targets.json` contains all
labels, including test labels, and must not be mounted into a participant process.
This exporter selects permitted labels and copies ordinary files; it creates no
links back to operator files and forwards no arbitrary source-manifest fields.

## Exact scope

The required source roster is all **109 people × six imagery runs = 654
recordings**, with original ordering retained privately. Participants 1–70 are training, 71–89 validation,
and 90–109 test. Every event declared by the authenticated input panel must be
present. Signals remain little-endian C-order float64 microvolts with 64 channels
and 800 samples. No normalization, filtering, epoch truncation or model is added.
The numerical source is only `released-06a7059-direct200`; it is not relabeled as
the paper's unresolved intermediate-128-Hz recipe.

The exporter requires an independently selected `--expected-panel-identity`.
The previously prepared authentic panel identity is
`7d67c330bbd111b393c7ab72a5008e0b6fb6b90e891045336f15d3c3437b3ee9`,
with 6,300 training, 1,734 validation and 1,803 test epochs. Source identity and
target commitments are checked before publication. Hash consistency does not
replace trusted operator custody or authenticate a newly supplied biological
dataset. If a separately prepared panel has a different observed epoch count,
the exported manifest retains that discrepancy. It does not force a count match
or qualify the different panel for the paper comparison.

Run identity narrows the possible imagery labels to left/right fist or both
fists/feet. The new participant view therefore supplies test observations as
**individual epochs in one persisted global shuffled order**, with opaque file
and event IDs. Test person/run metadata, run grouping and original within-run order
are absent from participant metadata and physical file-creation order. The private
mapping retains source record and row indices, exact original event IDs and source
hashes for evaluator restoration. Both access conditions must reuse that same
mapping. Training/validation labels and their original source metadata remain
available. No original panel file is rewritten.

Each test epoch is extracted by copying its exact float64 row bytes into a new
one-epoch NPY. This changes packaging and packet hashes, not signal values, samples,
labels, evaluation split or scientific metric. Source shards are authenticated
fully before extraction and checked for inode/size/time changes while rows are
copied. The reference also receives epoch signals and geometry without test-run
metadata. This is an explicit participant-view correction, not a claim that the
public source dataset became an unseen holdout.

Both conditions include the exact 543-position author bank. The manifest lists
the 64 electrode aliases in signal-channel order, including T3/T4/T5/T6 for
source T7/T8/P7/P8. Coordinates and their source convention remain unchanged.
The bank is data, so access to it does not depend on receiving author code.

## Export

Use Python 3.11 or later and the standard library. First reserve the full output
and temporary storage and admit the preparation operation through the enclosing
operator's resource controls. Inputs must already exist; the command performs no
downloads or dependency installation.

First create one private mapping, outside participant inputs. Keep the returned
mapping identity and reuse this file for both conditions:

```sh
python3 materials.py map \
  --panel "$PREPARED/inputs/panel.json" \
  --expected-panel-identity "$SELECTED_PANEL_IDENTITY" \
  --output "$PRIVATE_TEST_MAP"

python3 materials.py export \
  --panel "$PREPARED/inputs/panel.json" \
  --expected-panel-identity "$SELECTED_PANEL_IDENTITY" \
  --private-map "$PRIVATE_TEST_MAP" \
  --expected-mapping-identity "$SELECTED_MAPPING_IDENTITY" \
  --targets "$PREPARED/operator/targets.json" \
  --paper "$ORIGINAL_PROCEEDINGS_PDF" \
  --positions "$AUTHOR_SOURCE/hf/reve-positions/positions.json" \
  --condition paper_data \
  --output "$NEW_PARTICIPANT_DIRECTORY" \
  --max-bytes 5368709120
```

For `paper_data_code`, add `--code-archive "$PINNED_AUTHOR_TARBALL"`. Supplying
code to `paper_data`, or omitting it from `paper_data_code`, is rejected. The
published `data_identity` is identical across conditions for identical panel,
labels, geometry and private mapping. `materials_identity` also binds the access condition and
therefore differs. Neither identity counts as another scientific task or run.

The destination must not exist, and its parent must already exist and be owned by
the operator. It must be separate from the source signal tree. The exporter writes
to a private sibling temporary directory, verifies every byte/shape/finite-value
condition, and sets public files to 0444 and the signal directory to 0555. The root
stays 0700 through the rename, then becomes 0555 before a success receipt is returned.
This order also works on macOS, which rejected renaming the already0555 directory
in the first generated control. Failures remove only that invocation's directory
inode, including its published location if final permission-setting fails.
No existing output is intentionally overwritten. The operator must prevent
concurrent mutation of the destination parent; a pre-publication existence check
is not a general multi-writer filesystem transaction.

The fixed per-shard limit is 64 MiB, JSON input/output limit 16 MiB, and total
output limit at most 8 GiB. Budget checks conservatively reserve maximum permitted
NPY-header and JSON overhead. The original 9,837-epoch signal payload alone is
4,029,235,200 bytes, plus NPY headers, manifests, paper and geometry. Exporting both
conditions produces two copies and must be budgeted accordingly. Reads and
copies stream; no entire EEG panel is loaded into RAM.

## Delivered interface

The directory contains:

- `materials.json`: input conditions, source identity, exact signal/event mapping,
  labels for training/validation only, source count discrepancies and limits.
- `signals/`: 534 unchanged training/validation source shards plus one NPY per
  test epoch, globally shuffled and given opaque names. The observed authentic
  panel would produce 1,803 test files, or 2,337 signal files total.
- `positions.json`: the same pinned complete geometry bank in both conditions.
- `paper.pdf`: exact final NeurIPS proceedings paper.
- `official-code.tar.gz`: code-assisted condition only; unchanged official source
  archive at commit `06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7`.

Each test entry has one opaque event ID and signal but **no `labels`, `participant`
or `run` member**. A candidate submission is a JSON object with schema
`reve-candidate-predictions-v1`, the exact `materials_identity`, and `predictions`:
one row for each opaque event, containing `event_id` and either an integer
`prediction` in 0–3 or four finite `scores` in the declared class order.

The evaluator restores the complete prediction set to original source event IDs
and ordering before using the unchanged original scorer:

```sh
python3 materials.py restore \
  --panel "$PREPARED/inputs/panel.json" \
  --expected-panel-identity "$SELECTED_PANEL_IDENTITY" \
  --private-map "$PRIVATE_TEST_MAP" \
  --expected-mapping-identity "$SELECTED_MAPPING_IDENTITY" \
  --materials "$PARTICIPANT_DIRECTORY/materials.json" \
  --expected-materials-identity "$SELECTED_MATERIALS_IDENTITY" \
  --predictions "$CANDIDATE_PREDICTIONS" \
  --output "$PRIVATE_RESTORED_PREDICTIONS"
```

Private maps and restored predictions are created with mode0600 and cannot
overwrite existing files. The map cannot be placed in the source signal tree;
restored predictions cannot be written into participant materials. Restoration
rejects incomplete, duplicate, extra, invalid-class or nonfinite predictions. It
reads no target labels and calculates no scientific score. The operator uses its
separate target manifest and `original-physionet/panel.py score` for evaluation.
The code archive contains its original MIT source license. Dataset and pretrained
weight terms remain separate; this repository redistributes none of these input
payloads.

The exporter is trusted preparation, not a sandbox. A separately qualified runner
must mount only the participant directory, enforce the declared tools/network and
resource boundaries, and collect the final submission. In particular, original
PhysioNet annotations are publicly available: withholding the local test-label
file does not make these historically exposed labels secret. Pretrained encoder
weights are not included in either condition. Equal permitted pretrained access
and its lineage must be separately provisioned and qualified before an experiment.

## Validation and remaining limitations

`python3 -I -B tests/test_materials.py` exercises complete roster and split
validation, physical streaming/copy behavior, permitted-label projection,
condition parity, geometry aliases, source hash failures, NPY dtype/shape/finite
checks, link refusal, private-umask publication, output collisions and cleanup.
Opaque-map controls verify complete inverse joins, and separate multi-row NPY
controls verify exact extraction of distinct epochs and source-mutation refusal.
Its positive integration fixture contains one generated epoch in each of the 654
recordings. Pinned document bytes are replaced with explicitly generated stand-ins
inside the test only. This is a complete source-shaped software control, not an
authentic 9,837-epoch export, a paper reproduction or a model result. The positive
fixture and exported copy require approximately 513 MiB temporary disk. Set
`REVE_FIXTURE_ROOT` to an admitted temporary location for local controls.

No authentic participant export, candidate execution, author refit or model
evaluation is established by these controls. The original Table 12 downstream
classifier, exact historical filtering and training-run/SD aggregation remain
unresolved. The existing strict author adapter still refuses encoder-only weights;
this exporter does not substitute a different comparator, change outcome
definitions, activate a canonical runtime or promote scientific readiness.

## Input provenance

The original operator route and its retained source reconciliation authenticate:

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| Final proceedings PDF | 2,717,915 | `83cbe94dc11b77ea7fd4f1fe46bc896cd25e71eba99b5e449325f794d7d63973` |
| Official source archive | 259,040 | `687d7c5d3d45f8351d524c9ace8a8fb970b04324fbece4fc97072f7495622ed7` |
| Author position-bank JSON | 59,729 | `f62ca8d7dd4b88e1422ea17348440a41ed0b73b9ff7d12c3b1229492c9b448a5` |

Primary sources: [final paper](https://proceedings.neurips.cc/paper_files/paper/2025/file/20a917f77773ac0fa8bea2bdd6606b66-Paper-Conference.pdf),
[official pinned source](https://github.com/elouayas/reve_eeg/tree/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7),
[task configuration](https://github.com/elouayas/reve_eeg/blob/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7/src/configs/task/physio.yaml),
and [original dataset](https://physionet.org/content/eegmmidb/1.0.0/).
