# C4 biological-row and ensemble-weight integrity

The original endpoint remains classwise accuracy and retained fraction under
the original confidence conditions, using ten predictions for each left-out
unit and all 2,020 members for the original external transfer. The grouped
target-blind reference remains a separate extension. This repair changes no
probabilities, confidence thresholds, split, cohort or metric definition.

The predecessor scorer admitted a repeated biological identity if the caller
also repeated it in `expected_units`: conversion of targets to a set hid the
duplicate while the confusion matrix and denominators counted it twice. The
global capture route also admitted repeated model identities in separate
tensor columns. Equal-member averaging could therefore assign extra weight
to a repeated model. Both failures are testable with generated inputs through
the existing capture and scoring functions.

The repaired evaluation module requires a nonempty, unique, valid `UnitKey`
roster at capture admission, authenticated capture readback and direct scoring.
Model identity tokens normalize the existing tuple/list and `UnitKey`/JSON
dictionary representations before detecting duplicate members. This preserves
the serialization round trip and prevents changing representation to evade
the identity comparison. The original complete LOO mapping checks remain in
place. The grouped reference's single composite identity remains supported.

`tests/denominator_checks.py` exercises the actual NumPy writer and authenticated
readback, an invented 202-row/2,020-model LOO roster, an invented external
2,020-member tensor, duplicate-row/model failures, and the different `>` and
`>=` confidence conventions at exactly 2. These are software controls only.
The nine controls passed in the shared lightweight pool. The
`--predecessor /operator/preserved-evaluation.py` mode first verifies the
predecessor source hash, then documents both failures using the preserved
evaluator. Its pooled run confirmed that duplicate rows inflated a class
denominator and duplicate model identities passed capture and readback.

Uniqueness does not authenticate a roster's completeness or biological origin.
It does not prove that distinct model identities correspond to distinct fitted
states. The complete original panel, exact published baseline, original
preprocessing/exposure lineage, native execution and improvement decision
remain unqualified. No authentic data, targets, model run, acquisition or
scientific performance claim is introduced.
