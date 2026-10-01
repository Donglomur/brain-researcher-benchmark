"""Pooled OOF protocol prediction: no biological eye-state or fixed LOSO-gap gate."""
import csv
import json
import os
from pathlib import Path
import numpy as np
import proof_of_work as pw
from metric_contract import validate_subject_predictions

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def test_exact_subject_site_label_reference_required():
    path = Path(__file__).with_name("reference.npz")
    with np.load(path, allow_pickle=False) as archive:
        assert all(k in archive for k in ("ref_subject_ids", "ref_labels", "ref_sites")), "regenerate keyed subject reference before calibration"
        expected = {str(i): (str(site), int(label)) for i,site,label in zip(archive["ref_subject_ids"], archive["ref_sites"], archive["ref_labels"])}
    rows = list(csv.DictReader((OUT / "oof_predictions.csv").open()))
    assert len(rows) == len(expected) and {r["subject_id"] for r in rows} == set(expected)
    assert all((r["site"], int(r["label"])) == expected[r["subject_id"]] for r in rows)


def test_pooled_headlines_and_baselines_recompute():
    rows = list(csv.DictReader((OUT / "oof_predictions.csv").open()))
    metrics = validate_subject_predictions(rows)
    result = json.loads((OUT / "eye_decoding_results.json").read_text())
    assert result["n_subjects"] == len(rows)
    assert abs(result["cv_balanced_accuracy"] - metrics["prediction"]) <= .001
    assert abs(result["site_blocked_balanced_accuracy"] - metrics["prediction"]) <= .001
    assert abs(result["random_kfold_balanced_accuracy"] - metrics["random_prediction"]) <= .001
    assert abs(result["site_only_unseen_site_baseline"] - metrics["site_only_prediction"]) <= .001
    assert result["always_open_pooled_balanced_accuracy"] == .5
    assert result["always_closed_pooled_balanced_accuracy"] == .5
    for row in rows:
        training = [int(r["label"]) for r in rows if r["site"] != row["site"]]
        assert int(row["site_only_prediction"]) == int(sum(training)/len(training) >= .5)


def test_site_descriptive_scores_match_and_recompute():
    ref = pw.load_reference(Path(__file__).with_name("reference.npz"))
    sub = pw.load_submitted(OUT / "per_fold.csv")
    assert set(sub) == set(ref["ids"])
    st = ref["stats"]
    pw.check_folds_and_values(sub, ref, val_tol=st["VAL_TOL"], corr_min=st["CORR_MIN"], cover=1., match=st["MATCH"], eps=st["EPS"])
    rows = list(csv.DictReader((OUT / "oof_predictions.csv").open()))
    for site in sub:
        members = [r for r in rows if pw.canon_site(r["site"]) == site]
        labels = {int(r["label"]) for r in members}
        recall = sum(sum(int(r["prediction"])==label for r in members if int(r["label"])==label)/sum(int(r["label"])==label for r in members) for label in labels)/len(labels)
        assert abs(sub[site] - recall) <= 1e-6


def test_findings_present():
    assert (OUT / "findings.md").read_text().strip()
