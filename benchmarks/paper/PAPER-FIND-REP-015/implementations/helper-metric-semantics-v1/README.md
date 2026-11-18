# S9 metric-definition diagnostic

The retained S9 point-metric component computes reward-class recall, precision
and F1. The observed [HappyML helper source](https://github.com/cnchi/HappyML/blob/master/performance.py)
uses class-macro definitions for those three quantities; its cross-validation
methods reduce their fold results to a scalar mean. **The historical HappyML
revision used for the paper is still unknown.** This mutable-branch observation
does not establish that those helpers produced the deposited MAT files.

`diagnose_counts` exposes the practical difference using one trusted confusion
matrix from the existing operator-side point-metric report. It reports the
reward-class definition and a separately named, fixed-two-class macro
definition. It changes no registered score, paper target, split or result.

For example, TP=8, TN=1, FP=9 and FN=2 give reward recall 0.8 but macro recall
0.45. Accuracy is 0.45 under either convention. Thus merely matching the saved
field name `Recall` does not establish metric equivalence. The diagnostic also
compares precision and F1 and records definition differences using exact
rational arithmetic before serializing numerical values.

This is not a second scientific scorer or an uncertainty procedure. It does
not aggregate units, infer mouse identities, choose the historical definition,
read targets or claim an improvement. Confusion matrices and any resulting
reports remain operator-private. Undefined terms propagate as null; no
unverified scikit-learn zero-division or inferred-label-set policy is supplied.
In particular, a one-class case must not be treated as authenticated parity
with the helper's implicit class-label behavior.

The useful next step is to authenticate the actual dependency revision and
compare the complete saved S9 decisions, metrics and helper outputs under that
revision. Until then, the binary-definition component is a paper-definition
calculation and its HappyML equivalence is unresolved. The original F2/F3
population timing and jitter questions remain separate and unresolved.

`test_diagnose.py` uses generated class-imbalance, label-exchange, missing-class
and integration controls. Its normal dependency is the sibling
`source-svm-v1/score.py`; a private construction check can set
`CEREBELLAR_EXISTING_SCORE_PATH` to that exact read-only source. These tests
establish diagnostic arithmetic, not source preparation or author execution.

This additive module needs a new explicit command in the existing
`benchmarks/integrity/parallel-source-controls.v1.json` enrollment before CI
coverage is claimed. No registry or central integrity file is changed here.
