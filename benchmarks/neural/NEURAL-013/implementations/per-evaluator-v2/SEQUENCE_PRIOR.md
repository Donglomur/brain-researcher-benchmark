# Training-only unconditional phoneme control

`sequence_prior.py` implements the task's proposed no-neural sequence prior. It
chooses the most frequent complete phoneme sequence among retained **training**
trials. Equal frequencies are resolved by lexicographic token order. The entire
chosen sequence, including repeated phonemes and the `|` boundary symbol, is
returned for every retained query. This is a transparent nuisance control, not a
competent neural decoder or a language-model benchmark.

The fitter validates the allowed-label file against the public byte count and
SHA-256, requires every training/development case exactly once, and rejects query
or unknown label IDs. Development labels are validated as packet operands but
never affect the chosen sequence. Counts are pooled over training trials; no
session balancing, development tuning or duration-conditioned rule is inferred.

Run from this component directory in a trusted operator context:

```sh
python3 -B sequence_prior.py fit --public /operator/public/manifest.json \
  --labels /operator/public/training_labels.json --output /operator/prior.json
```

Record the resulting `model_id` before query execution. Then supply that exact
recorded identity to prediction:

```sh
python3 -B sequence_prior.py predict --public /operator/public/manifest.json \
  --model /operator/prior.json --expected-model-id RECORDED_MODEL_ID \
  --output /operator/new-submission.json
```

Prediction opens only the manifest and frozen model, never feature arrays,
allowed-label files, private targets or source HDF5 files. All nine query
sessions and every manifest query remain required by the existing evaluator.
Neither output may already exist. The resulting standard submission can be
scored alone with `score.py`, or supplied by the operator as
`--comparator-submission` alongside a candidate submission to produce a joint
comparison on one captured target packet. Both original grades and all nine
paired session PER differences remain private operator evidence, including the
target-content fingerprint; no query-time metric feedback is provided here.
The joint operation checks both complete operands before targets and preflights
the combined DP work under the unchanged 128-million-cell ceiling. This does not
authenticate the prior fit or establish a neural/native capability claim.

The model fingerprint binds supplied bytes. The operator must independently
establish the freeze chronology and authentic packet; self-consistent hashes do
not prove these facts or isolate a process. The public manifest includes query
metadata, but this prior never uses durations, feature content or query-session
identity to choose a sequence. A fully prepared packet does not yet exist under
the registered contract, so no authentic fit, performance, leakage-free source
preparation, neural understanding or readiness is claimed.

The original author repository describes both paper analyses and a modified
competition baseline. This control uses the benchmark's local chronological
27/9/9 protocol and session-macro PER; it does not reproduce the paper's online
word-error rate or the competition's partition. Remaining source holds include
the unreconciled trial inventory, feature-index notation, source normalization,
and a qualified neural reference. The pinned README and dataset loader were
viewed for this construction; no raw upstream checksum or payload inspection is
claimed.

Sources: the registered `task.json` and `split_policy.json`; the official
[dataset loader](https://raw.githubusercontent.com/Neuroprosthetics-Lab/nejm-brain-to-text/980a5b7e96392210edf976d76bdb5d15d2e0e62b/model_training/dataset.py),
[data description](https://raw.githubusercontent.com/Neuroprosthetics-Lab/nejm-brain-to-text/980a5b7e96392210edf976d76bdb5d15d2e0e62b/README.md),
and [training description](https://raw.githubusercontent.com/Neuroprosthetics-Lab/nejm-brain-to-text/980a5b7e96392210edf976d76bdb5d15d2e0e62b/model_training/README.md).

`test_sequence_prior.py` exercises generated 45-session metadata, train-only
selection, deterministic ties, malformed joins, pre-parse byte authentication,
frozen-model mutation, complete scoring, and prediction without feature/label
files. These controls are software checks, not experimental results.
