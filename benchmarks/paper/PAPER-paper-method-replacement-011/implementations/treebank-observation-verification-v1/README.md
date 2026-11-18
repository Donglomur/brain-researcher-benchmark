# Independent Figure 4 observation verification

This owner-only component checks whether the existing Treebank Figure 4
producer's recorded probabilities, split memberships and returned scores agree.
It fills a gap between observing an original source call and independently
verifying its numerical output. It does not fit or predict, modify the author
code, prepare recordings, score an AI, or qualify a benchmark.

The selected task remains the complete original Figure 4a–c sentence-onset versus
no-speech result. The existing producer, collector, canonical task and outcome
contracts are unchanged. The original anatomical grouping, projection and
display-interval gaps remain unresolved.

## What is checked

For every contact and window in the **supplied** preparation and source-window
tables, the verifier requires exactly one complete observed source call. It
joins the original positional train/test memberships to encoded labels, rejects
overlap or omissions, and checks all five training-only CV partitions. Each
training example must appear in exactly one CV validation fold. Both classes
must occur in every fit and validation partition.

Held-out ROC-AUC is independently recomputed from the observed test labels and
the actual second probability column. The implementation counts positive/negative
ranking pairs, assigning half credit to exact ties. It requires the observed
encoded class order `[0, 1]`, complete binary probability rows, and no NaN,
infinity or Boolean scores. The recorded final return must also agree exactly
with the saved source-score artifact.

The five observed training-CV AUC values are checked against their arithmetic
mean. This does **not** independently reconstruct each fold's AUC: the current
producer does not record its out-of-fold probability vectors. The verifier does
not pool predictions across folds or replace mean-fold AUC with pooled AUC.

The `1e-12` absolute tolerance concerns floating-point arithmetic agreement only.
It is not a paper-reproduction tolerance, minimum improvement, inferential
threshold, or clinical criterion. No aggregate score or success judgment is
created from the contact/window panel.

Lifecycle and count checks reject truncated, duplicate, interleaved or extra
window records. Source `SupportChecks` disagreements remain visible; arithmetic
can be verified even when same-case consistency across contacts is unavailable.
The result always leaves same-case admission, original-support authentication,
training-provenance authentication, paper reproduction and benchmark readiness
unqualified. No targets, probability vectors or example identifiers are emitted.

## Operator interface

Use only separately admitted, frozen owner/reference artifacts from
`treebank-figure4-producer-v2`. The observation stream contains private target and
prediction evidence and must never enter the paper-plus-data participant arm.
The command below specifies an interface, not evidence of native execution:

```sh
python -I -S -B verify.py \
  --prepared /owner/prepared/prepared.json \
  --windows /owner/replay/source_windows.json \
  --scores /owner/replay/source_scores.json \
  --observations /owner/replay/observations.jsonl.gz --gzip \
  --max-events OWNER_ADMITTED_EVENT_COUNT \
  --max-observation-bytes OWNER_ADMITTED_DECOMPRESSED_BYTES \
  --max-examples-per-window OWNER_ADMITTED_EXAMPLE_LIMIT \
  --output /owner/new-verification.json
```

The CLI accepts only complete JSONL records, rejects duplicate JSON object keys,
and bounds decompressed stream bytes and line length before JSON parsing. The
JSON event limit is the existing observer's 1 MiB default, plus one framing
newline byte. The total decompressed byte budget includes that newline. It retains one window's
observation records at a time, plus coverage identities and the supplied score
table. The caller must still qualify actual RAM, execution time and I/O. These
checks are not an OS sandbox or an immutable-file guarantee.

Input JSON byte hashes and a hash/count of the complete decompressed observation
stream are reported. These are observed identities, not evidence that a producer,
recording or fit is authentic. The gzip container itself is not authenticated by
the decompressed hash. The operator must independently qualify the producer's
completion receipt, post-run author-checkout check, source/data/runtime identities
and original support. A successful arithmetic check does not replace them.

Output creation is exclusive and occurs only after complete verification. An
existing output or input path is never overwritten. Importable `verify(...)`
supports already bounded dictionaries and a streaming event iterator; direct
callers own parsing and resource limits.

## Construction verification

`test_verify.py` contains 16 generated-only methods: an independent pairwise-AUC
definition with ties; polarity and class-order attacks; changed saved scores;
fold and train/test leakage; omitted, duplicate and foreign support; lifecycle
and budget failures; strict compressed JSONL; and a test consuming the maintained
producer's actual event emitter with its deliberately invalid generated fold
fixture. Source-hook success must not be mistaken for numerical qualification.

Construction attempt 1 passed 14 methods and exposed a tuple-mutation error in
one test fixture before that test reached the verifier. Only the corrected method
was rerun, and it passed. Independent review then found a framing-boundary
compatibility defect: the producer permits 1 MiB of JSON before adding a newline.
After correcting the line budget, one added boundary test passed using the real
1 MiB limit in memory; it accepts the final newline, rejects one extra JSON byte,
and confirms the total decompressed budget still applies. All 16 methods have passing evidence for the
final code; a second full-suite pass is not claimed. No authentic recordings,
scientific packages, trained models or author numerical functions were run.

Run necessary generated checks through the project's existing shared test pool;
the public test command is `python -I -S -B test_verify.py`. The test references
the sibling producer's maintained `observation.py` and `tests/test_observation.py`;
those files are pinned in `SOURCE.json` and are not vendored again in this package.
