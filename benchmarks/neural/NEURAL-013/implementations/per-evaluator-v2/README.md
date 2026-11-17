# NEURAL-013 complete-panel phoneme evaluator

This recovers the task-specific evaluator missing from the published manifest-only
delivery. It accepts the historical `neural013-public-v1`,
`neural013-predictions-v1`, and `neural013-targets-v1` formats, and enforces the
registered 45-session partition: sessions 001–027 training, 028–036 development,
and 037–045 query. It is an operator scoring component, not a prepared benchmark
or a candidate execution environment.

Run with Python 3's standard library:

```sh
python3 -B score.py --public /operator/public/manifest.json \
  --submission /operator/submission.json --private /operator/targets.json \
  --output /operator/new-score.json
```

The output must not exist. Exit codes are 0 for a complete score, 2 for invalid
candidate output or unsupported complexity, and 3 for an invalid operator packet.
The CLI reports invalid operator packets separately from candidate failures and
does not put private paths or target values in its error reports. Submitters do
not receive the private target file or query-time metric feedback.

The public manifest contains exactly `schema`, `packet_id`, `protocol_id`,
`sessions`, `cases`, and `training_labels`. Protocol is
`neural013-chronological-v1`; `packet_id` is the SHA-256 of canonical JSON without
that field (ASCII escaped, sorted keys, compact separators, no nonfinite values).
Each case has `case_id`, `session_id`, `role`, `n_time_steps`, and `features`.
Case IDs are opaque 64-character lowercase hex strings. The feature descriptor
has `path` equal to `features/CASE_ID.npy`, plus positive `bytes` and `sha256`.
`training_labels` is a descriptor with the path `training_labels.json`, `bytes`,
and `sha256`. At least one retained trial is required in each partition, and in
every query session. Earlier sessions may lose all trials under the frozen
sentence-overlap purge; the evaluator does not invent replacement trials.

A submission has exactly `schema`, `packet_id`, and `predictions`. Each prediction
has exactly `case_id` and `tokens`; every manifest query occurs exactly once and
no other case is admitted. Tokens may be a list or whitespace-separated string.
The operator target file has `schema`, `packet_id`, and `targets`, whose rows use
the same `case_id`/`tokens` form. Public manifest and complete predictions are
validated before the target loader is called. A target must be nonempty.

The 39 source phonemes and the `|` word-boundary symbol in `tokens.json` are scored.
CTC blank/padding is excluded; stress suffixes and unknown symbols are invalid.
Only ASCII case and whitespace are normalized. Repeated final sequence tokens
are preserved. Empty predictions are valid all-deletion outputs. Boundary tokens
contribute to both edit distance and the reference denominator.

The primary metric is `later_session_macro_phoneme_error_rate`: sum unit-cost
Levenshtein edits within each query session, divide by that session's total
reference tokens, then average the nine rates equally. It may exceed one.
Secondary outputs retain per-session and pooled edit counts, denominators,
sequence exact-match fractions, and pooled PER. Alignment ties prefer diagonal,
then deletion, then insertion; the total minimum edit distance is invariant, but
individual insertion/deletion/substitution counts need not be unique. There is
one biological participant, not nine independent participants.

Input JSON is limited to 64 MB, manifests to 50,000 cases, sequences to 2,048
tokens, and trials to 100,000 time steps. Complete-panel dynamic programming is
limited to 128 million cells. Exceeding this limit produces no partial score and
does not crop sequences or discard trials. These inherited bounds need checking
against a future authentic full packet; they are not measured source maxima.

`SOURCE_PINS.json` records exact hashes of recovered local source files. The
ordered vocabulary comes from the pinned official author revision
`980a5b7e96392210edf976d76bdb5d15d2e0e62b`; upstream bodies were inspected in the
preserved audit but no raw upstream checksum was retained. This recovery makes
no new upstream checksum claim. `split_policy.json` preserves the original local
chronological policy and exact normalized-sentence purge: latest partition wins,
retaining every query. Both policies differ from the official competition test.

The recovered scorer formerly admitted arbitrary shorter panels with all three
roles. This version rejects those panels and role changes, adds exact-sequence
summaries, exposes pooled counts, and distinguishes operator errors from invalid
submissions. The synthetic controls independently check edit distance and a
deliberately unequal-length/multiple-trial session example, plus missing IDs,
wrong splits, repeated tokens, boundary symbols, empty output, malformed targets,
bounded complexity, and private-read ordering.

No neural payloads or historical private targets were read; no model was run.
Passing these controls establishes software behavior only. The public source
panel still needs authenticated trial inventory and exclusions, feature-axis and
normalization verification, source-label compatibility, a matched neural
reference, language-only/zero-feature/shuffled controls, and independent complete
execution. A valid packet fingerprint binds supplied bytes; it cannot prove that
the supplied manifest represents every authentic retained source trial.

Direct observation, typed viewer, tool-assisted investigation, and frozen-program
conditions retain their current unqualified status. Any later condition may use
this same endpoint, but this scorer delivers none of their observation transports
or isolation guarantees. It establishes no paper WER, clinical outcome,
population result, or current-SOTA claim. Canonical registration and access-mode
changes remain separate integration proposals.
