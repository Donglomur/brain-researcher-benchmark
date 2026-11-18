# Opaque identities for word-boundary query collection

The existing NEURAL-015 query export includes recording IDs from its public
catalog. Those IDs provide a direct route to the source movie and transcript.
This optional operator-side codec replaces recording and fold IDs with keyed
aliases before response collection, then restores the original identities in
operator memory for the unchanged evaluator. It retains all 26 recordings, the
same complete grids, the same folds and the same probability vectors.

It supplies no neural observations or participant runtime. It is **not** an
access sandbox, an anonymization guarantee, or a delivered native-understanding
condition. Recording durations, fold-group sizes and eventual signal content
can still identify a source. Preventing external lookup and access to private
files remains an independent requirement. Existing scientific admission holds
remain in effect.

## Operator interface

Python 3.9+ standard library only. The module checks the existing evaluator and
catalog SHA-256 identities before importing them. It does not alter their code,
the canonical task, or the original public-query format.

`public_query(reference, secret)` validates the existing complete-cohort private
reference and returns the opaque query. The secret must be exactly 32 binary
bytes, generated securely and kept in operator-only storage. Use a fresh secret
for each run. A deterministic test key is present only in generated tests and
must never be used for benchmark collection. Length validation does not certify
entropy or secrecy; the deployment must provide both.

Aliases use HMAC-SHA256 with separate case and fold domains. Their context binds
the existing target-independent query, canonical complete train/test/unused
fold memberships, and declared neural-input hashes. A
change to the key, observation identity, grid, folds or protocol changes the
query binding. Onsets, transcript/alignment hashes and acoustic/visual control
probabilities do not determine aliases or ordering. These distinctions are
tested. Source hashes are checked as declared identities, not authenticated
against neural arrays by this codec.

The query contains exactly `task_id`, `delivery_profile`, `protocol_sha256` and
`recordings`. Each recording has only an opaque `case_id`, opaque `fold_id` and
the predecessor's four grid fields. Records are sorted by their keyed alias;
the original catalog order is not exported. Source IDs, movies, targets, private
input hashes and the secret are absent.

The response has exactly this structure:

```text
task_id: NEURAL-015
delivery_profile: opaque-word-onset-query/v1
query_sha256: canonical digest of the complete opaque query
predictions:
  - case_id: an exact alias from that query
    fold_id: its exact opaque fold
    neural: one finite probability in [0,1] for every grid point
```

The canonical digest uses the predecessor's `digest`: UTF-8 JSON with sorted
object keys, compact comma/colon separators and no nonfinite JSON values. Every
case must appear exactly once. Missing/extra/duplicate cases, wrong folds, stale
query bindings, malformed vectors, nonfinite values, booleans, out-of-range
probabilities and additional response fields reject the submission. Constant
predictions remain valid and are not treated as successful inference.

`restore_submission(reference, secret, submission)` returns the exact original
evaluator submission format. **That returned object contains original source
IDs and is operator-only.** `evaluate(...)` restores identities and delegates to
the unchanged evaluator. Its score object also contains operator diagnostics
and source IDs; it must not be used as entrant feedback. The wrapper explicitly
records false access-isolation and scientific-admission flags.

The CLI accepts a private reference and private key file:

```sh
python3 delivery.py query /private/reference.json --key-file /private/run-key.bin --output /private/opaque-query.json
python3 delivery.py score /private/reference.json --key-file /private/run-key.bin --submission /private/response.json --output /private/operator-score.json
```

Outputs are newly created with owner-only permissions and never overwrite an
existing file. The CLI creates no output on input validation failure. This is
not a defense against an entrant who can read the operator's filesystem; a
separate runner must enforce that boundary and bound untrusted input sizes.

## Validation and limits

Fifteen focused generated controls passed once for this revision. The earlier14-method
run is preserved; independent static review then identified omitted training/unused
fold membership in the alias context and repeated fixture vectors. Both were
corrected before the second necessary affected-suite run. They check exact allowlists,
complete cohort coverage, label-independent identities/order, changed-key and
observation binding, valid training-membership changes and stale-response rejection, source split gates, strict response restoration, invalid
outputs, constants, duplicate JSON keys, CLI output permissions and overwrite
refusal. Different prediction vectors for all 26 generated recordings restore
and score identically through the original evaluator. Generated data exercise
software behavior only.

For maintained CI, run this new module through the repository's component test
enrollment rather than assuming that an unrelated workflow discovers it:

```sh
python3 -I -S -B -m unittest discover -s benchmarks/neural/NEURAL-015/implementations/opaque-query-v1/tests -p test_delivery.py -v
```

No authentic recording, timing CSV, transcript, model or acoustic/visual
comparator was processed. Sampling calibration, clock/pause policy, channel
selection, full observation packets, protected evaluation, access enforcement
and a signal-derived reference remain outstanding. No reproduction,
improvement, model difficulty or native neural understanding is established.
