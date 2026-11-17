# Complete-row private word-start preparation

This component closes a specific target-preparation gap in NEURAL-015: it reads
every word record from a frozen transcript CSV without excluding words because
unrelated linguistic, audio or video features are missing. The predecessor
accepted an already prepared onset list, so it could not detect that form of
population loss.

`extract_word_starts(bytes, expected_sha256)` checks the exact source bytes,
requires the source `start` column and retains every CSV data record. Missing,
nonfinite or negative starts, malformed rows, duplicate column names and empty
transcripts reject the whole extraction. Missing text, end times, sentence
positions or nuisance features do not exclude a row. Extra source columns are
allowed and their values are not copied to output. An empty index-column name
is permitted if it is unique. UTF-8 and an optional UTF-8 BOM are supported.

Word times use seconds in the movie clock. Sorting is stable, and repeated times
remain separate words. Each word retains its original one-based CSV data-record
number; quoted multiline text still counts as one record. The identity is the
pair `(transcript_sha256, source_record_number)`, not a possibly repeated source
word index. The digest binds the complete original bytes, including any BOM.
The expected digest must be frozen independently: computing it from an already
reduced input does not prove that the author's transcript is complete.

`prepare_unpaused_recording(bytes, specification)` additionally checks the
recording/movie join against the existing 26-record catalog and maps **all**
extracted starts through the predecessor's nearest-trigger, 2048-Hz conversion.
It uses the predecessor's ties-to-even rounding and residual checks. Every
trigger and resulting word index must lie in `[0, sample_count)`. A word outside
trigger coverage rejects the entire operation; no row is clipped or dropped.
The returned `word_onset_samples` can populate that field in the existing private
reference. The aligned row identities remain available for operator audit.

The alignment specification has exactly these fields:

```text
recording_id: one existing catalog ID
movie_id: exact catalog identity for that recording
sample_count: full native recording length in samples
transcript_sha256: independently frozen SHA-256 of the original CSV bytes
triggers: [{movie_time_seconds: seconds, neural_sample_index: integer}, ...]
max_clock_residual_samples: explicit finite nonnegative residual bound
```

This is an adapter for one operator-declared **unpaused** span covering the
entire transcript. Raw native timing CSVs are not accepted as normalized
triggers. Pauses, resumed or repeated movie spans and target words not shown in
a recording require a separately reviewed preparation policy. The adapter does
not infer that policy or certify completeness of the operator's trigger list.
Even a passing input always returns `native_alignment_validated: false`.

## Private operator interface

Python 3.9+ standard library only. The existing evaluator and catalog are
imported after checking their exact SHA-256 pins, preserving their numerical
implementation. No historical file or public query schema is changed.

```sh
python3 prepare.py extract /private/movie.csv --expected-sha256 FROZEN_SHA256 --output /private/word-starts.json
python3 prepare.py align /private/movie.csv --spec /private/unpaused-spec.json --output /private/aligned-onsets.json
```

Run from this implementation directory, or supply the full path to `prepare.py`.
Outputs contain private timing targets and must never be delivered to a
participant or committed to the repository. The CLI creates a new file with
owner-only permissions and refuses overwrite. It produces no output file on
validation failure. Source bytes and specifications remain operator inputs;
the package contains no source transcript values or neural data.

## Source and qualification scope

The preserved [source review](../initial-evaluator-v1/provenance.json) pins the
author repository at `c54ba38eab7814538bc03b1b6d29a3f50f034e12` and identifies
`data/trial_data.py` dropping rows for missing values across all transcript
features. The current task's recording contract records the inspected source
CSV header, including `start`/`end`. This implementation is original and uses
those previously reviewed interface facts; it does not copy author code or
claim a new source download. [Provenance](provenance.json) pins the exact local
contracts and predecessor files and distinguishes the unavailable raw source
SHA-256 from the recorded Git object IDs.

Tests use generated rows to check preserved nuisance-missing words, row identity,
coincident starts, malformed data, digest/identity/coverage failures, pause-clock
rejection, owner-only output and the actual predecessor scorer integration. Run
them only through the coordinator's reviewed shared lightweight test pool:

```sh
python3 -m unittest discover -s benchmarks/neural/NEURAL-015/implementations/transcript-preparation-v1/tests -v
```

This is a source preparation component with generated software controls. No
authentic CSV, HDF5 recording, native timing stream, model or media comparator
was executed. It does not establish complete native preparation for all 26
recordings, freeze the grid/tolerance, or supply neural observations. Direct,
viewer, tool-assisted and frozen-program conditions remain distinct and
undelivered; benchmark scientific qualification remains unknown.
