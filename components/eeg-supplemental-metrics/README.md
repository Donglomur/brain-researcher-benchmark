# NEURAL-077 supplemental evaluator

This concrete evaluator adds tie-aware ROC AUC and balanced accuracy at the fixed
threshold 0.2 to the existing 400-row observed-input prediction interface. It uses
the unchanged canonical NPZ validator and canonical primary scorer. Every existing
primary key/value is preserved; the only addition is `supplemental_metrics`.
Canonical log loss, balanced accuracy at 0.5 and its confusion counts are unchanged.

`evaluate_submission` in `evaluator.py` accepts the already committed submission,
the existing two-person public IDs, the trusted hash/ID-joining private loader,
the exact saved six-arm reference scores and the canonical source directory.
The caller also supplies the submission byte/hash pin and explicitly selects
`condition="observed_signal"`. Other conditions are refused. The outer operator
must authenticate the observed-input producer receipt, freeze its output, verify
producer absence and run the private grader in its admitted isolated runtime.
Predictions alone cannot prove which inputs a producer used; the condition is
explicitly operator-declared provenance, not an inference made by the scorer.

The evaluator authenticates both canonical source bodies before executing their
verified bytes, validates the complete fixed NPZ, and rechecks the submission pin
before any private access. The canonical scorer runs first. A recording loader
copies each returned private vector while preserving its original dtype for the
canonical checks. Only after complete canonical success are those two copies used
for supplementary summaries. There are exactly two original private loads and no
additional private load. Invalid second-person data, missing classes or resource
failure aborts the complete operation; no partial or selected-person summary is
returned. No per-trial labels or predictions appear in the output report.

Production AUC counts positive-negative concordance using sorted exact-tie groups;
ties receive half credit. The test-only independent scalar oracle enumerates every
positive-negative pair. BA uses `p >= 0.2`, with no epsilon around the threshold.
Both metrics are reported per person and averaged with equal person weight. There
is no pooled-trial AUC, new primary endpoint, tuning, hypothesis test or population
confidence interval. The fixed cohort remains two exposed people and 400 trials.

`scalar_oracle.py` and `SCALAR_ANCHORS.json` were independently authored before the
oracle author saw production code. The source checks use generated examples only.
They test primary-score preservation against the exact canonical scalar scoring
source through a small generated validation shim; they do not import real NumPy,
open authentic inputs, fit models or qualify an isolated numeric/runtime image.

Run source controls with:

```text
python3 -I -S -B test_metrics.py
```

By default the test uses bundled canonical source when present, otherwise the
repository source; `NEURAL077_CANONICAL_DIR` can explicitly select an existing
canonical source directory, including a shallow standalone component location. This
reads source code only. The actual evaluator lazily imports the canonical NumPy
runtime only when an authentic operation is separately allocated and invoked.

There is no dataset payload, private target binding, communication, API key or
authentic example in this component. It is a public-safe source proposal pending
root publication review. No canonical file or old result is modified, no new
benchmark ID is added, and no empirical score is claimed.
