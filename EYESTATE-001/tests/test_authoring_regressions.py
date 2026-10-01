import pytest
from metric_contract import pooled_balanced_accuracy, bind_keyed_predictions


def test_constant_predictions_have_pooled_half_chance():
    labels = [1]*6 + [0]*4
    assert pooled_balanced_accuracy(labels, [1]*10) == .5
    assert pooled_balanced_accuracy(labels, [0]*10) == .5
    assert sum([1]*6+[0]*4)/10 == .6  # Legacy equal-site one-class recall is different.


def test_keyed_reference_rejects_error_reassignment_with_unchanged_site_recall():
    reference = dict(ref_subject_ids=["a", "b", "c", "d"],
                     ref_sites=["X", "X", "Y", "Y"], ref_labels=[1, 1, 0, 0],
                     ref_predictions=[1, 0, 0, 1], ref_random_predictions=[1, 1, 0, 0],
                     ref_random_folds=[0, 1, 2, 3], ref_site_only_predictions=[0, 0, 1, 1],
                     ref_estimator_contract="ledoitwolf-correlation-losocv-v1")
    rows = [dict(subject_id=s, site=reference["ref_sites"][i],
                 fold_site=reference["ref_sites"][i], label=reference["ref_labels"][i],
                 prediction=reference["ref_predictions"][i],
                 random_prediction=reference["ref_random_predictions"][i],
                 random_fold=reference["ref_random_folds"][i],
                 site_only_prediction=reference["ref_site_only_predictions"][i])
            for i, s in enumerate(reference["ref_subject_ids"])]
    bind_keyed_predictions(rows, reference)
    original = pooled_balanced_accuracy([r["label"] for r in rows], [r["prediction"] for r in rows])
    rows[0]["prediction"], rows[1]["prediction"] = rows[1]["prediction"], rows[0]["prediction"]
    assert pooled_balanced_accuracy([r["label"] for r in rows], [r["prediction"] for r in rows]) == original
    with pytest.raises(AssertionError, match="keyed prediction"):
        bind_keyed_predictions(rows, reference)
    with pytest.raises(AssertionError, match="regenerate genuine"):
        bind_keyed_predictions(rows, {})
