# V1 author export bridge

This component connects V1 author inference artifacts to the existing frozen-panel
CER evaluator. It preserves presented-sentence scoring, biological-person alias
grouping, the original sentence-cluster condition and one neural argmax class per
keystroke. It does not load recordings, fit a model, run inference or establish a
paper result.

The author's export groups MEG `S<n>` recording IDs using its alias map. Its
`extract_subject` regex does not recognize the numeric participant token in the
registered EEG UID format and can collapse those rows into `unknown`. The
predecessor evaluator instead uses the panel's explicit EEG person map. EEG
conversion therefore preserves the registered scientific grouping, but exact
aggregation parity with the raw author EEG export remains unresolved. Accepting
an EEG capture does not certify source-exact EEG export reproduction.

The pinned author's `LogSentencePredictions` stores `true`, `typed`, `pred` and
`logits`, but omits keystroke identities and saves only rank zero. Its
`SentenceGroupedDistributedSampler` assigns whole sentences round-robin, then pads
shorter nonempty ranks by repeating sample indices. The callback appends these
repeated predictions. Consequently a rank-zero JSON can omit sentences, and simply
merging rank files can add characters. Existing source reviews had identified the
rank-zero omission; inspecting the sampler establishes the additional padding
problem. Sources and exact fingerprints appear in [PROVENANCE.json](PROVENANCE.json).

`RankCapture` records the same source-shaped callback content plus the actual
`button_UID` order from each observed `batch.segments` item. It refuses batch
length mismatch, inconsistent presented text, nonfinite logits and invalid class
indices. Repeated observations remain in the capture for detection. The collector
does not sort, drop, collapse or deduplicate outputs.

`convert_bytes` accepts every rank capture and an independently frozen panel. It
requires one capture for every rank from the same declared run, exact test-sentence
coverage, exact presented reference equality, exact ordered button coverage,
29 finite logits per keystroke and the source first-index argmax. Typed targets
are checked for structural consistency but never used as predictions or reference
text. A duplicate keystroke, including sampler padding, refuses conversion.

The resulting JSON is directly accepted by the unchanged predecessor evaluator.
No reference text, typed labels or logits are included in the converted submission.
It remains an operator artifact; case/keystroke IDs and predictions are not
automatically safe participant feedback. The separately printed receipt contains
only identities, hashes, counts and a `software_conversion_only` qualification.

## Capture integration

Import `bridge.py` by its file location in the operator's existing author execution
environment. At test epoch start create one collector per process using its actual
rank, world size and the frozen run-manifest digest. At each source test-batch
callback invoke:

```python
capture.add_batch(outputs, batch)
```

Use the identical `outputs` and `batch` given to the author's
`on_test_batch_end`. The collector reads `sentence_UID` and `button_UID` from the
actual trigger extras. It requires the post-transform `button_UID`, not the older
`button_unique_id`. At epoch end, the operator saves each rank's `document()` to a
new private artifact. `bundle_documents([...])` packs those captured documents for
offline conversion. An empty rank still supplies a document. Neither the capture
nor the model output defines the expected test population.

The collector is a small standard-library integration interface. It has been
tested using generated tensor/segment objects; actual Lightning hooks, distributed
execution and author inference have not been run. A preexisting callback file with
no actual observed-order trace cannot reconstruct lost keystroke identity. Do not
manufacture a trace from the expected panel or from array position.

`source_padding_audit(ordered_sentence_sizes, world_size)` calculates the pinned
unshuffled sampler's unique counts, repeated padding counts, empty ranks and
rank-zero sentence omissions without loading data. Input must reflect actual
first-seen dataset sentence order. This diagnostic neither recovers the paper split
nor repairs a padded capture. An unpadded complete execution is required; changing
distributed execution needs its own reviewed author-calibration protocol.

## Offline conversion

From the repository root, after the independent operator freezes the panel, run
manifest and completed capture bundle:

```sh
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-002/implementations/v1-author-export-bridge-v1/bridge.py \
  --panel /operator/panel.json --panel-sha256 "$TRUSTED_PANEL_SHA256" \
  --capture /operator/capture.json --capture-sha256 "$FROZEN_CAPTURE_SHA256" \
  --run-manifest-sha256 "$FROZEN_RUN_SHA256" \
  --output /operator/new-author-predictions.json \
  --max-json-bytes 16777216 --max-codepoints 1000000
```

The operator selects byte/codepoint limits for its complete panel. These example
limits are engineering bounds, not measured full-cohort requirements. Source and
output files are byte bounded; output is created exclusively and never overwritten.
Errors omit private paths, references and prediction contents. This is a trusted
operator tool, not a sandbox for an adversarial model process.

Score the generated `new-author-predictions.json` using the predecessor
[evaluator](../v1-transcript-evaluation-v1/README.md) and the same panel/digest.
Source CER aggregation and undefined-support behavior remain in that single
implementation. The bridge pins its exact source digest before importing it.

## Validation and qualification

Generated controls exercise the complete converter-to-evaluator path with a
hand-derived alias-weighted CER of 5/8, typed versus presented target separation,
all-rank coverage, repeated sampler padding, order permutations, source argmax
ties, invalid logits/classes, run/digest mismatch, batch truncation, duplicate JSON
keys, bounded reads and CLI overwrite refusal. These fixtures are invented
software inputs and are not observed neural results. Run the tests only under the
current shared lightweight test-pool protocol:

```sh
python3 -I -S -B -m unittest discover \
  -s benchmarks/paper/PAPER-ROOT-ADD-002/implementations/v1-author-export-bridge-v1/tests \
  -p test_bridge.py -v
```

No new data were acquired and no authentic targets, neural data, weights, training
or native inference were used. Original paper split/cohort authentication,
preprocessing/default reconciliation, the matching published neural-only baseline,
EEG export aggregation reconciliation, author competence, protected execution and
scientific uncertainty remain unresolved
as recorded in the task's unchanged improvement contract. A successful conversion
is not paper reproduction, improvement readiness or empirical superiority.
