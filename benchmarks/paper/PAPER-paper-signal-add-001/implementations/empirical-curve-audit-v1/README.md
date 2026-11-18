# Empirical Figure 6 prediction and curve audit

This operator component recomputes the empirical five-category accuracy curve
from submitted predictions on one frozen session/condition/removal selection.
It preserves all 500 decoding repetitions and every declared ensemble size,
including a maximum before the final size. The binary geometry example remains
a separate component. This addition does not implement a classifier, recover
the missing author decoder, or complete the selected paper benchmark.

The [original Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11078732/),
“Noise correlations and population category decoding,” specifies correct load-1
maintenance trials, category-balanced subsampling, linear one-versus-one decoding,
80/20 train/test partitions and 500 repeats. It describes adding one neuron at
a time through the entire session ensemble. Non-PAC removal uses another axis
of 500 random selections; it must not be confused with the decoding-repeat axis.
See the existing [source recovery](../../docs/decoder-source-recovery-v1.md)
and [selected endpoint](../../primary-endpoint-v1/selection.v1.json).

## Interface and trust boundary

`audit_curve(manifest, predictions, expected_manifest_sha256=...)` requires an
operator-supplied manifest with exact patient/session, noise condition, ablation
selection, five category IDs, all selected units, the nested ensemble sequence,
and training/testing trial identities and labels for all 500 repetitions.
`source_bindings` pins the observations, correct-load-1 selection, partition
policy, ensemble producer and condition transform. The expected manifest hash
must come from the operator's prior freeze. Candidate-supplied hashes cannot
establish that freeze or authenticate any source. The manifest and gold labels
are operator-only and must not be delivered to a participant.

Prediction records have exactly `repeat`, `step`, `trial` and `category`.
Their order is immaterial; every declared held trial at every repeat and step
must appear once. The auditor rejects missing steps/repeats/trials, duplicates,
training-trial substitutions, unknown labels, changed support, non-nested unit
sequences and unbalanced pooled category selection. A source trial's category
must remain identical across repeats, including when the trial moves between
training and testing. Selected membership may differ across repeated subsamples.
It reports per-repeat
correct/total counts, all accuracy values, and the arithmetic mean over repeats
for each step. It retains every exactly tied maximizing step; it invents no
tie-breaking rule. Accuracy is a fraction, not a percentage.

The source's exact integer rounding for an 80/20 split has not been recovered.
Accordingly, this component records the supplied train/test counts and pins the
partition policy; it does not validate that policy, create new splits, or infer
rounding. It also does not prove that the source ensemble was the best candidate
at each greedy step. Those are unresolved producer/admission obligations.

`compare_on_frozen_curve(manifest, author_predictions, candidate_predictions,
expected_manifest_sha256=...)` independently recomputes both submissions on the
same frozen cell support. It returns every paired repeat and step difference.
It imposes no scalar reduction, significance rule, biological uncertainty or
paper-win verdict. This narrow comparison holds the ensemble sequence fixed;
it does not adjudicate an alternative ensemble-selection algorithm. Such an
extension needs a separate same-task selection policy.

## Remaining complete-task obligations

The component audits one declared curve. It does not assert a complete roster
of the original 22 Figure 6d/e sessions, all 500 matched non-PAC removals, or
the distinct Figure 6c/g/h companions. Their identities and overlap cannot be
guessed from publication counts. No single curve or pooled average replaces
those mandatory supports. Authentic original recordings, PAC membership,
preprocessing, author predictions, selection dependence, exact empirical source
code, biological-unit uncertainty and full-panel comparison remain unresolved.
Paper+data and paper+data+author-code participant conditions remain uninstantiated.

The SHA-256 values establish identity only. No source data, private targets,
author MATLAB execution, fits or candidate scientific runs were used here.
Generated tests use explicit synthetic identifiers and cover mathematical
recomputation and failure cases only. There is no readiness or SOTA promotion.

## Generated controls

Run from this component directory with standard Python:

```sh
python -B -m unittest -v test_curve_audit.py
```

Project construction uses the existing shared generated-test pool. CI must
explicitly enroll this new component command; its presence alone is not a CI
admission. It needs no packages beyond the Python standard library.
