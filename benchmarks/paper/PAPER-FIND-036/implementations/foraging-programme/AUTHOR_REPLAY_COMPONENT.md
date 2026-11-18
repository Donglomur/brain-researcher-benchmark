# Source API reference for the Figure 6B endpoint

`program/author_replay.py` fills a specific reference gap: the existing operator
uses independent Bernoulli-naive-Bayes equations. Those equations do not establish
that the author's scikit-learn branch has been executed. This added callable
selects three unchanged statements from the exact retained author classifier:
construct `BernoulliNB(fit_prior=False)`, fit on the original training rows, and
write the held-out escape probabilities into their original positions. The
constructor's alpha, zero binarization and uniform prior are checked after fit.

Only the enclosing function and an estimator return are added. Top-level
argparse, hard-coded paths, MAT loading, unseeded shuffle and feature-importance
branches are never executed by this slice. The source-body SHA256 is checked
before parsing or compilation; a changed source is refused. This is an explicit
**source API endpoint replay**, not unchanged execution of the whole author
script, historical environment parity, or complete paper reproduction.

## Full-support integration

The public callable is `replay_prepared(prepared, author_source, budget,
output_numeric_capacity_bytes)`. It reuses the existing full40 preparation
validator and authenticated `array_io` loader. It requires all40 source members,
all released unit features and40 bins, unchanged[-1,+1]s windows and clipping,
and original source-order HW labels. It regenerates seed622 stratified fivefold
memberships and compares every train/test position with the protected preparation
before fitting that session. Participant presentation permutations do not alter
the author's training order or returned OOF positions.

On complete success it returns40 operator-only probability arrays and a metadata
report for200 real-label fits. Each session's balanced accuracy is computed from
all pooled OOF rows; the primary mean weights sessions equally. A fit/input error
raises `ReplayFailure` carrying attempted-fit and completed-session counts. No
partial panel is returned as success. The caller must preserve this failure and
all execution costs. The numerical-output capacity is only the returned arrays'
byte count; it is not a bound on workspace, metadata or process memory.

The adopted construction runtime remains NumPy2.2.6, SciPy1.15.3 and
scikit-learn1.6.1. The wrapper refuses other versions. These are existing project
choices, not authenticated historical versions; the paper reports Python3.9 but
does not bind the full historical stack. The callable performs no scientific
work on import and deliberately has no executable CLI or automatic invocation.
Fitted estimator objects are currently discarded after use. Complete model-artifact
capture is another required outer-integration step; this callable alone does not
satisfy the selected contract's model-audit obligations.

Before any real use, the operator still needs an admitted source closure,
authenticated complete archive/preparation, a measured finite CPU/RAM/time
profile, protected source/output custody and independent numerical comparison
against the separate equation implementation. The current archive and rat
mapping are still unadmitted. Existing runtime source manifests and
`paper_endpoint.py` are unchanged; their `author_replay` field is still null.
This new source is not silently enrolled into a previously qualified snapshot.

The returned report cannot award a reproduction or paper win. Complete source
shuffle companions remain a separate mandatory obligation. PFI, the predictive
time-window curve, SVC exploratory comparisons, same-task candidate scoring,
meaningful effect and rat-aware uncertainty are not implemented by this replay
slice. No authentic data, estimator fit, AI run or scientific score was produced
during construction.

## Maintained generated controls

`author-replay-controls/test_author_replay.py` uses generated40-session panels and
a spy estimator, not a trained statistical model. It exercises exact source
binding, source-only extraction, complete200-call coverage, training/query
separation, original-row folds, capacity, nonfinite/clipping/class constraints,
failed-attempt accounting, estimator semantics and the source0.5 tie rule.

Proposed component CI command:

```sh
python3 -B -m unittest discover -s benchmarks/paper/PAPER-FIND-036/implementations/foraging-programme/author-replay-controls -p 'test_*.py'
```

This new path needs explicit component enrollment by the shared integrator;
construction checks alone do not establish that public CI currently runs it.

## Evidence

- The exact author file is already retained under
  `program/author/PythonCode/EventClassification/HierarchicalEventClassifier.py`,
 8776 bytes, SHA256 `abfde10a70eec9a8f621909ec9fac37463efceb7bd5b5dbdb5eff37d6fcf4b63`,
 at author commit `2b74d2c2f8d6574b6a1b75c0feb99af5e18bb678`.
- The current [Dryad dataset page](https://datadryad.org/dataset/doi:10.5061/dryad.v9s4mw78c)
 still lists `EventClassificationData_4C.zip` and describes each MAT as one
 session with event-by-feature `X` and four-valued event labels `y`. This browser
 observation is not archive acquisition or authentication. No payload attempt
 was made for this construction.
- The [pinned author README](https://github.com/knowblesse/Lobster/blob/2b74d2c2f8d6574b6a1b75c0feb99af5e18bb678/README.md)
 points to the same Dryad data and supplies no alternate data mirror. No new
 data-access route or source-support closure is inferred.
