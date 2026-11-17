# Full-cohort protected scoring component

`score.py` fills the missing numerical evaluator described in the current
NEURAL-084 contract. It evaluates the existing `neural084_pool_v1`,
`neural084_gold_v1` and `neural084_scores_v1` interfaces without changing their
source representation or the historical programme. It uses Python's standard
library and the preserved `delivery-source/public/io_utils.py` transport.

The endpoint remains held-person overt-gaze target decoding for all 54 people,
both sessions and both acquisition phases. Each of 216 phase cells must contain
exactly 25 trials per source label. The source labels remain 1=up, 2=left,
3=right and 4=down, with nominal frequencies 60/[5,7,9,11] Hz. The prospective
400-sample half-open representation remains distinct from the original MATLAB
pipeline. Scoring does not inspect or transform EEG.

## Operator use

Keep the pool, gold and scorer in the protected operator environment. The
candidate receives none of them. Supply an independently authenticated pool
byte count and SHA-256, and four prediction directories. Each directory must
contain exactly `fold001.json` through `fold054.json` from the completed
candidate, CCA, constant and frequency-column permutation runs:

```text
python3 -I -B score.py --pool /protected/pool.json \
  --pool-bytes <verified-size> --pool-sha256 <verified-sha256> \
  --candidate /captured/candidate --cca /captured/cca \
  --constant /captured/constant --frequency-permuted /captured/frequency-permuted \
  --out /protected/new-report.json
```

Those paths illustrate an operator deployment; no such assets are included.
The JSON pool references sibling `gold.json` by exact size/hash and supplies the
same ordered source-phase identities used by the existing programme store.
The scorer requires complete disjoint identities, sorts the 400 queries for
each person exactly as the programme does, and validates all 216 submissions
before opening gold. It retains immutable predicted classes and input hashes;
candidate files are never reread after gold access. All predictions must have
exact generation, fold and ordered IDs, four finite nonboolean raw scores,
strict JSON without duplicate keys, and the existing 262,144-byte limit.

Gold is then checked against the source order, person, session, phase and every
ID, with complete class balance. Missing cases, changed mappings, unsupported
labels and incomplete output fail the whole evaluation. Files use the existing
bounded regular-file, no-symlink, no-hardlink, content-pin transport. This is an
operator API, not an operating-system sandbox; prediction/gold loader callbacks
are trusted code and must never be supplied by a participant.

## Output and interpretation

Argmax selects the earliest source class on ties; negative raw scores are
valid. There is no probability conversion or log loss. Each phase gets a 4×4
confusion matrix (rows=true class, columns=predicted class), class supports,
class recalls and their mean. Scores are averaged equally across phases,
sessions and people. Reports include 216 phase rows, 108 session rows, 54
person rows and the aggregate for each mode, plus per-frequency confusion and
recall and candidate-minus-comparator differences for all 54 people. Reports
omit query IDs, row-level predictions, target labels and private paths.

The scorer records the exact pool, gold and prediction hashes. It evaluates
the supplied modes; it does not certify that a mode was produced by the stated
method, or that fit/seal/infer isolation was maintained. Such provenance needs
the separate producer/runtime evidence. It supplies descriptive paired
differences, without confidence intervals or a population independence claim.
Programme scores do not establish direct, viewer or adaptive-agent ability.

## Software controls and remaining work

`test_score.py` exercises the complete 21,600-query panel using generated
software fixtures. A separate integer-count oracle checks variable accuracy
across people, sessions, phases and classes. Perfect reference, constant ties
and permuted columns have expected scores 1, 0.25 and 0. Compatibility checks
pass the same objects through the preserved programme's prediction validator
and source/gold metadata join. Negative controls cover late malformed reference
outputs before gold access, missing folds, class support, source order, wrong
identities and strict numeric/JSON policies. A full filesystem CLI round trip
and exclusive report creation exercise the actual entry point.

These controls establish software behavior only. No authentic arrays, private
historical targets, model outputs or new source downloads were used. Authentic
108-recording preparation, source array/schema authentication, input/gold
provenance and full programme execution remain unqualified. This directory is
an additive component, not a replacement of the frozen producer's source
binding: its `GRADE_HANDOFF.json` still requires integration to a reviewed
scorer identity. Canonical task/contract and registry changes remain with the
integration owner. No existing status is promoted by this addition.

Source basis: the current `understanding.v1.json`, preserved
`delivery-source/public/TASK.md`, `protocol.py` and `io_utils.py`, and
`sequential-programme/sequential-view-v2/program/{contracts,store,controller}.py`.
The source collection is [OpenBMI](https://doi.org/10.1093/gigascience/giz002);
this benchmark's split, representation and aggregation are specified by the
local contract, not claimed to reproduce the paper endpoint.
