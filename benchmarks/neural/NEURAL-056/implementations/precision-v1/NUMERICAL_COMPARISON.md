# Numerical revision comparison for NEURAL-056

`n056_precision.reconciliation.compare_versions` diagnoses the difference between the preserved Pearson kernel and the precision repair on the same complete study. The existing legacy reconciliation requires numerical equality within1e-12; the documented large-offset regression is an intentional arithmetic disagreement, so simply redirecting that legacy comparison to the repaired scorer would reject the new version.

The diagnostic first calls the existing immutable-product collector. All120 person/arm/role products must pass original process, protocol, method and file checks before any target callback. It then evaluates both declared kernels against identical measured arrays, preserves all200 images and1,700 cells, records raw/scoring definedness transitions and finite differences, and computes each version’s equal-person primary and paired controls. Odd/even reliability is reported separately and never corrects the primary score.

```python
from n056_precision.reconciliation import compare_versions, REVISION
comparison = compare_versions(panel, records, protocol, budget, numerical_revision=REVISION)
```

This is a source-level operator API. It requires the same preserved shared package and NumPy as `n056_precision.evaluation`; it does not accept participant-reported scores. It reports disagreements rather than declaring them numerically equivalent. It does not modify the historical reconciliation, execute its legacy collector, select a new programme version, activate a runtime, or establish dataset/checkpoint qualification. A later admitted integration must explicitly select a consistent development/final numerical version and retain both historical results and this diagnostic.

Six initial generated controls cover the full120-output comparison with a known one-cell arithmetic regression, full-primary undefinedness from a constant target, unknown-revision refusal, incomplete/duplicate rosters, corrupted final output before target access, and undefined-cell transitions. The successful local run used the real NPZ/custody admission path, took3.027s, and used one4,212-byte generated prediction artifact repeatedly across the roster. Generated completion records do not establish process isolation or biological results. One preceding attempt failed before tests at the macOS temporary-path symlink guard; resolving the generated temporary path fixed the fixture, and that failed attempt remains recorded.

No authentic EEG/image/weight arrays, model fitting, provider calls or scientific performance measurements were used. Full80-repeat targets and original exposed/transductive limitations remain unchanged. Image-to-EEG encoding still does not measure direct interpretation of a supplied neural observation or reproduce the paper’s random-half numerical endpoint.

Independent review identified that an overall-agreement label must include the separately reported reliability arrays. The corrected diagnostic exposes `observed_prediction_numerical_agreement` and `observed_reliability_numerical_agreement`, and requires both for `observed_numerical_agreement`. A seventh generated control uses ordinary prediction targets but a large-offset odd half: prediction agreement is true, reliability agreement is false, and overall agreement is false. Only this new affected control ran after the correction; it passed in1.351s. The six previously passing controls were not replayed. No scientific score or legacy gate changed.
