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


def bind_keyed_predictions(rows, reference):
    """Require actual independently generated per-subject OOF outputs, not site means."""
    fields = {"site": "ref_sites", "label": "ref_labels",
              "prediction": "ref_predictions", "random_prediction": "ref_random_predictions",
              "random_fold": "ref_random_folds", "site_only_prediction": "ref_site_only_predictions"}
    required = {"ref_subject_ids", "ref_estimator_contract", *fields.values()}
    assert required <= set(reference), "regenerate genuine keyed OOF prediction reference before calibration"
    assert str(reference["ref_estimator_contract"]) == "ledoitwolf-correlation-losocv-v1"
    ids = [str(i) for i in reference["ref_subject_ids"]]
    assert len(ids) == len(set(ids)), "reference subject IDs must be unique"
    assert all(len(reference[k]) == len(ids) for k in fields.values()), "invalid reference array dimensions"
    assert len(rows) == len(ids) and {r["subject_id"] for r in rows} == set(ids)
    assert len({r["subject_id"] for r in rows}) == len(rows)
    positions = {subject: i for i, subject in enumerate(ids)}
    for row in rows:
        i = positions[row["subject_id"]]
        for field, key in fields.items():
            expected = reference[key][i]
            if field == "site":
                assert row[field] == str(expected), f"wrong site for {row['subject_id']}"
            else:
                assert int(row[field]) == int(expected), f"wrong keyed {field} for {row['subject_id']}"
        assert row["fold_site"] == row["site"]
