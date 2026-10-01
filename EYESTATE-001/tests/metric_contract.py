def pooled_balanced_accuracy(labels, predictions):
    assert len(labels) == len(predictions) and labels
    assert set(labels) == {0, 1} and set(predictions) <= {0, 1}
    recalls = [sum(pred == label for label,pred in zip(labels,predictions) if label==c)/sum(label==c for label in labels) for c in (0,1)]
    return sum(recalls)/2


def validate_subject_predictions(rows):
    assert len({r["subject_id"] for r in rows}) == len(rows), "duplicate subject"
    assert all(r["site"] == r["fold_site"] for r in rows), "site leaks across train/test folds"
    assert {int(r["random_fold"]) for r in rows} == set(range(10))
    labels = [int(r["label"]) for r in rows]
    return {k: pooled_balanced_accuracy(labels, [int(r[k]) for r in rows]) for k in
        ("prediction", "random_prediction", "site_only_prediction")}
