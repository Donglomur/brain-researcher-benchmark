# CHB-MIT original-file admission

This operator-only component creates the existing NEURAL-009 evaluator's admission
and public-support artifacts from **all 686 original recordings and 23 biological
people**. It authenticates original release metadata and streams each complete EDF
through its publisher SHA-256 before deriving exact sample counts, recording
lengths, channel order, and reference intervals. It does not decode EEG samples,
filter/resample signals, fit models, or score a candidate. The original task,
10 Hz output grid, LOPO folds, event policy, scorer, and existing implementation
remain unchanged. `chb01` and `chb21` remain one held-out person.

The previous evaluator accepts normalized declarations. This producer supplies a
concrete original-file path into that evaluator, while requiring a separately
reviewed channel-role/clock/normalization/rights record. Merely creating that review
JSON does not establish the scientific correctness of its contents.

## Annotation policy and preserved source conflict

The selected event boundaries follow the exact summary-second interpretation in
[the pinned author loader](https://raw.githubusercontent.com/esl-epfl/epilepsy2bids/d3fb17526b8a483e292ae9ba2e51b02d5f9128ff/src/epilepsy2bids/load_annotations/chbmit.py).
The implementation uses exact integer 10 Hz ticks, rejects malformed or unpaired
annotations, and does not estimate duration from wall-clock strings.

The exact publisher release has 676 summary blocks: 141 positive and 535 explicitly
zero-event recordings, with 198 summary events. All 141 positive summary identities
match the complete `.edf.seizures` inventory in the pinned publisher checksum file.
Ten of the 22 `chb24` recordings lack summary blocks. They are specifically
`02, 05, 08, 10, 12, 16, 18, 19, 20, 22`; no other missing block is allowed.

These ten records are **inferred zero-event under the declared exhaustive-sidecar
source assumption**, using the publisher's statement that reported seizures have
companion annotations and the complete checksum inventory. They are not asserted
to have explicit human zero-event annotations. The operator review must explicitly
accept this source interpretation. Private evidence preserves each record's
category, the source hashes, and the inferred-negative identities. The existing
evaluator's `annotation_status="explicit_zero_events"` is used for the resulting
explicitly materialized empty interval list; that schema label must not be read as
proof of an original explicit-zero summary block. Candidate support omits all
annotation hashes, categories, and intervals.

There is also a real disagreement: `RECORDS-WITH-SEIZURES` lists `chb07_18.edf`
and omits `chb07_19.edf`. The summary declares 18 zero-event and 19 one event at
13688–13831 seconds; only 19 has a checksum-listed sidecar. The builder preserves
that exact discrepancy rather than using the positive list as ground truth. An
independent manual decode of the authenticated 54-byte 19 sidecar corroborates the
two summary boundaries. It is one-file corroboration, **not full binary-annotation
parity, clinical label correction, or a new benchmark result**. Any different
positive-list discrepancy or summary/sidecar set disagreement causes refusal.

The [publisher landing page](https://physionet.org/content/chbmit/1.0.0/) also retains
older prose counts. The exact `RECORDS` and `SHA256SUMS.txt` identities determine
this component's file population, rather than those historical counts. Source
metadata and inference conventions remain reviewable and are not silently repaired.

## Required local inputs

Use the original publisher directory layout under one operator-owned source root:

- `RECORDS`, `SHA256SUMS.txt`, and `RECORDS-WITH-SEIZURES` with their exact pinned bytes.
- All 24 `chbNN/chbNN-summary.txt` files, authenticated by that checksum inventory.
- For `build`, every indexed `chbNN/*.edf`, complete and matching its publisher hash.
- A separately reviewed source-review JSON and the existing evaluator resource limits.

`metadata` needs no EDF files. No command downloads files. No EEG payloads or
annotation bodies are redistributed here. Credit the CHB-MIT contributors and
PhysioNet and retain the dataset's
[ODC-By 1.0 terms](https://physionet.org/content/chbmit/view-license/1.0.0/).

The source review has exact fields:

```json
{
  "schema": "neural009_source_review_v1",
  "source_index_sha256": "<existing evaluator source-index digest>",
  "normalization_recipe_sha256": "<independently reviewed recipe digest>",
  "clock_review_sha256": "<independently reviewed clock evidence digest>",
  "rights_review_sha256": "<independently reviewed rights evidence digest>",
  "accept_annotation_source_assumptions": true,
  "records": [
    {
      "recording_id": "chb01/chb01_01.edf",
      "edf_header_sha256": "<reviewed complete EDF header digest>",
      "channels": [{"label": "<exact EDF label>", "role": "eeg"}],
      "predictor_channels": [0]
    }
  ]
}
```

The abbreviated example is **not runnable admission**: `records` must contain all
686 distinct identities with every header channel in original order. Roles are
`eeg`, `annotation`, or `other`; only reviewed EEG indices can be predictors.
Duplicate bipolar labels are retained. `EDF Annotations` always has its defined
non-EEG role, even if a supplied review says otherwise. ECG/VNS/other biological
channels and the three source unipolar exceptions need real domain review; labels
are not guessed into EEG roles. Selected channels need one common exact integer
native sample rate. Continuous classic EDF or EDF+C geometry is supported;
discontinuous EDF+D, unknown record counts, truncated/trailing sample bytes,
off-grid durations, and inconsistent event support are refused.

The byte-level native header digest includes its private source metadata. It is
operator-only provenance, not a participant observation. The public support
retains the evaluator's existing recording identifiers, timing support, biological
split and selected labels. Because these public original data/identities are
already exposed, this is not a newly secret test set.

## Commands

Use Python 3.11+, standard library only, for this admission producer. Its existing
scoring dependency needs NumPy when scientific scoring is subsequently invoked;
this component does not install anything. Run from this directory after the source
package and `SOURCE.json` have been independently authenticated.

```sh
python3 -I -S -B admission.py metadata \
  --source-root "$ORIGINAL_SOURCE_ROOT" \
  --output "$FRESH_PRIVATE_METADATA_DIRECTORY" \
  --max-json-bytes 2097152 --max-output-bytes 2097152

python3 -I -S -B admission.py build \
  --source-root "$ORIGINAL_SOURCE_ROOT" \
  --review "$REVIEW_JSON" --limits "$SCORER_LIMITS_JSON" \
  --max-edf-bytes "$PER_FILE_BYTE_BUDGET" \
  --max-total-edf-bytes "$TOTAL_ORIGINAL_EDF_BYTE_BUDGET" \
  --max-json-bytes "$JSON_BYTE_BUDGET" \
  --max-output-bytes "$OUTPUT_BYTE_BUDGET" \
  --output "$FRESH_PRIVATE_ADMISSION_DIRECTORY"
```

`build` authenticates the entire original cohort and refuses an insufficient total
byte budget. It never admits a reduced set to fit a resource cap. Whole EDF hashes
are streamed with bounded chunks; only headers and small metadata are retained.
Full-corpus data acquisition/storage and the cost of reading it remain an operator
requirement, not something these generated tests have measured.

The fresh output directory contains `admission.json`, `public-support.json`, and
`private-source-evidence.json`. All files are owner-only in an owner-only directory.
Only the public support artifact may be deliberately copied into a participant
workspace, together with the separately admitted signal representation. The
private evidence includes labels and must not be exposed as participant feedback.
The public projection alone does not deliver EEG observations or a participant
runner. The existing evaluator can consume the generated admission and support
without a schema rewrite; use its pinned `cli.py evaluate` route and existing
policy/complete candidate format.

Stable symlinks, hardlinked input files, FIFOs, changed input snapshots, source
hash mismatches, and repeated physical EDF identities are refused. These checks
assume a trusted operator-owned filesystem; they are not a hostile concurrent
filesystem sandbox. A failed output write may leave a partial new directory;
only a successful exit and all declared output hashes constitute completion.
Never reuse or silently overwrite that directory.

## Evidence and limits

Run the committed controls with:

```sh
python3 -I -S -B test_admission.py
```

They exercise exact EDF geometry and full-file identity, complete synthetic
686-record admission using the original identity roster, biological alias handling,
source coverage/disagreement refusal, complete public/private projection, annotation
channel exclusion, input failures and output protection. They do not read original
EDF payloads or establish authentic montage/clock/signal-normalization correctness.
Source authentication proves byte identity, not annotation validity.

Original source metadata has been independently reconciled, including the one
manual sidecar timing check described above. Authentic complete EDF preparation,
actual normalization, a competent signal-derived reference, timing/montage-only
controls, direct/viewer or frozen-program participant execution, patient-level
uncertainty, protected evaluation and scientific qualification remain unresolved.
The actual scoring endpoint remains tolerant retrospective event coverage, not
prompt onset detection or clinical deployment performance.
