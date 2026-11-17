# Helsinki original-source admission and lazy samples

This component connects the already published, exact Helsinki source intake to
the current `NEURAL-EXP-005` evaluator. It adds a bounded sample-major reader,
one-pass original-quality census, and current-protocol description projection.
It does not download EEG, run a model, fit a detector or qualify the benchmark.

The complete source is **79 EDF recordings and three corrected expert CSVs** from
[Zenodo version 4](https://zenodo.org/records/4940267). Existing authenticated source
profiles describe **402,825 exported record seconds** and **400,534 primary
cases**, after the fixed 29 leading seconds per infant. All recordings, all three
experts and every current-protocol case remain required.

## Exact existing intake

`source_loader.py` authenticates and loads the existing owner implementation at
`docs/provenance/registrations/expansion-20261113/helsinki-recorded-grid-construction-v1`.
Its source and profile files are byte-pinned; no historical body is edited or
copied into this directory. The module loader uses private names and a narrowly
bound source import, without changing `sys.path` or replacing a global
`helsinki_profile` import. The current sibling `protocol.py` is separately pinned.

The existing production `Corpus` authenticates all 82 complete input files against
the publisher's sizes and MD5s, records SHA-256 identities, verifies the exact
79 header profiles, and parses the exact corrected annotation layout. Required
annotations are `annotations_2017_A_fixed.csv`, `annotations_2017_B.csv` and
`annotations_2017_C.csv`. The first CSV record must be the ordered identifiers
1 through 79; the next record is annotation second zero. There are 15,416 data
rows, with binary values inside each recording's extent and empty cells only
outside it. No header guessing, dropped infant, two-rater fallback or invented
padding is admitted.

The publisher documents synchronized starts of EEG and annotations. Removing the
authenticated ordered identifier header is an explicit source-backed inference
about the CSV layout, not a quoted assertion that the paper specifies a physical
CSV row number. The corrected A file is never replaced by the older A file.

## Time coordinate and unchanged task

[coordinate-binding.json](coordinate-binding.json) records the reviewed current
interpretation: use the author's exported record/sample grid for native
sample-relative windows. One exported record has 256 samples and a declared
one-second duration. Annotation data row `k` aligns to exported record `k`.
Clinical clock continuity and reconstruction of EDF+ time-annotation lists remain
unknown. No clinically inferred gaps, extra zeros, interpolation or deleted
timestamps are introduced.

Only the exact source-profile exceptions for `eeg4`, `eeg29` and `eeg50` admit
their published EDF+C headers without an annotation channel. Full file and header
identities must match. This is not a blanket EDF+ relaxation or permission to edit
headers. The generic historical strict parser remains unchanged.

The current active protocol remains
`helsinki_full_timestamp_quality_flags_v1`. The older intake's protocol label,
`helsinki_recorded_grid_quality_flags_v2`, is retained as source lineage; its
controller, alternative folds and case identities are **not** imported. The new
description uses the current five-fold rule, development membership validation,
HMAC case identities, sample timing arithmetic and full participant-payload hashes.
The coordinate document and source identities enter the representation/admission
digests. This source decision conveys no earlier execution qualification.

The two existing probability endpoints remain distinct: primary infant-macro
soft-vote Brier loss against the three-expert fraction, and secondary Brier losses
against each expert separately. Mean expert Brier includes the additional
`q(1-q)` disagreement term. The adapter does not replace either endpoint with
event sensitivity or treat expert labels as independent infants.

## Lazy waveform and original flags

`SourceCorpus(source_root)` opens the complete authenticated input corpus.
`read_samples(recording_id, start, stop)` returns only the requested half-open
native-sample interval, in sample-major order, with the exact 18 bipolar channels.
Each electrode is calibrated from its own physical/digital range **before**
subtraction. Labels and electrode indices are joined through the authenticated
header mapping, including its reviewed `Ref` and `REF` spellings. ECG is excluded.

The interval may cross EDF record boundaries but cannot exceed 7,680 samples,
the original 30-record context. A 31-record cache handles unaligned bounded reads.
Cached samples remain bound to the original open file identity and header; source
mutation or replacement of the lookup descriptor refuses further reads. Returned
rows are immutable tuples, so a caller cannot corrupt the cache by editing them.
The corpus must stay in trusted owner storage and close after use. These Python
classes are not participant isolation.

`private_census()` reads each exported record once and retains both historical
flags: all bipolar values exactly zero, and any bipolar channel exactly constant
over that record. Their OR supplies the current Boolean flag. Zero-bipolar implies
flatline; both original flags remain in the private census. No cutoff is fitted,
no annotation informs these flags, and no flag deletes a case. This exact rule is
an unvalidated input-quality indicator, not a verified pause or missingness
detector. Its scientific calibration remains outstanding.

The private census includes all source identities, expert streams, sample extents,
quality flags and coverage counts. Do not give it, its source root or a corpus
object to a participant.

## Operator entry points

From the repository root, with all original inputs provisioned in protected owner
storage and authentic preparation separately admitted:

```sh
python3 benchmarks/neural/NEURAL-EXP-005/implementations/source-admission-v1/source_adapter.py \
  --source-root /absolute/private/helsinki-v4 \
  --output /absolute/private/new-census.json
```

To also project the current evaluator's private description, provide both
`--policy /absolute/private/policy.json` and
`--description-output /absolute/private/new-description.json`. The exact policy is:

```json
{
  "schema": "helsinki-source-preparation-policy-v1",
  "assessment_id": "prospectively-frozen-owner-assessment",
  "fold_seed": "prospectively-frozen-seed",
  "development_by_fold": {
    "0": ["owner-selected-nonheld-recording-IDs"],
    "1": ["owner-selected-nonheld-recording-IDs"],
    "2": ["owner-selected-nonheld-recording-IDs"],
    "3": ["owner-selected-nonheld-recording-IDs"],
    "4": ["owner-selected-nonheld-recording-IDs"]
  }
}
```

The strings above are illustrative, deliberately not a runnable split. The
operator freezes seed and real development membership before outcome-driven
selection. The current protocol checks every supplied ID, held/development
separation and nonempty fitting support. It is not replaced by the historical
controller's split. Output files must be new and are created with private mode
0600; existing outputs are never overwritten. If the second output fails, the
first private census may remain and is not a complete paired-output receipt.

The Python path is connected to the unchanged reference and packet functions:

```python
from source_adapter import SourceCorpus, current_description

with SourceCorpus(source_root) as corpus:
    census = corpus.private_census()
    description = current_description(census, frozen_policy)
    current = corpus.sources.current
    # Deliberate full-reference operation, separately budgeted by the operator:
    reference = current.prepare_reference(description, corpus.read_samples, private_case_key)
    # Owner-selected case only; participant receives the resulting packet:
    public_packet = current.packet(reference, "eeg1", 29, corpus.read_samples)
```

The full reference operation still hashes every complete overlapping packet. It
is **not** run by the census CLI. At this complete source scope it visits about
55.37 billion repeated waveform scalars; a lazy source reader avoids duplicated
stored windows but does not remove that computation or establish campaign/model
feasibility. No index-only substitute for the existing content hashes is used.

## Validation and remaining work

Generated tests exercise the real pinned source loader, actual EDF scalar
calibration, cross-record reads, mutation and bound refusals, quality flags,
current-coordinate projection and private output behavior. They contain no
authentic EEG or model trial. Fresh source review authenticated the live release
inventory, all three CSV files and selected header bytes; it did not read signal
samples or run complete preparation.

Run the generated controls from this directory with
`python3 -B -m unittest test_source_adapter -v` (subject to the operator's shared
resource controls). [SOURCE.json](SOURCE.json) freezes this component and its
review identities. The tests use invented waveforms and labels; full-coverage
bookkeeping controls reuse only the public duration roster.

Full authentic 82-file custody, complete preparation under the new adapter,
quality-detector calibration, train-only competent physiological references,
protected fresh participant execution and scientific qualification remain
outstanding. The target is expert-report fraction; it is not unique clinical
truth. All annotations are public, so local held-infant folds alone do not
establish an unseen-pretraining evaluation. This source component adds no task ID
and makes no readiness, native-understanding, improvement or SOTA claim.
