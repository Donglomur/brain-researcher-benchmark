"""Tiny independent-checker fixtures only; no original EEG filtering/fitting."""
import importlib.util
import csv
import json
from pathlib import Path

import mne
import numpy as np
import pytest
from mne.decoding import CSP
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import cohen_kappa_score

spec = importlib.util.spec_from_file_location("motorimagery_independent", Path(__file__).with_name("check_independent.py"))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
mne.set_log_level("ERROR")


@pytest.mark.parametrize("rank", [8, 6])
def test_independent_csp_log_features_and_alternative_lda_match_pinned_library(rank):
    rng = np.random.RandomState(735)
    y = np.array([0]*11 + [1]*9)
    latent = rng.standard_normal((20, rank, 49))
    latent[y == 1, 0] *= 1.8
    latent[y == 0, 1] *= 1.6
    # Nonzero means distinguish uncentered empirical moments from demeaned covariance.
    latent[:, 2] += 0.8
    mixing = rng.standard_normal((8, rank))
    X = (mixing @ latent) * 1e-6
    library = CSP(n_components=4, reg=None, log=True, norm_trace=False, restr_type="restricting")
    oracle_features = library.fit_transform(X, y)
    filters, diagnostics = check.independent_csp(X, y)
    independent_features = check.log_power(X, filters)
    assert diagnostics["rank"] == rank
    np.testing.assert_allclose(independent_features, oracle_features, atol=2e-8, rtol=2e-7)
    original_lda = LinearDiscriminantAnalysis(solver="svd", tol=1e-4).fit(oracle_features, y)
    coef, intercept, _ = check.independent_lda(independent_features, y)
    np.testing.assert_allclose(independent_features @ coef + intercept,
                               original_lda.decision_function(oracle_features), atol=1e-7, rtol=1e-5)
    # Signs of spatial filters must not affect the reported feature comparison.
    np.testing.assert_allclose(check.log_power(X, -filters), independent_features, atol=0, rtol=0)


@pytest.mark.parametrize("degenerate", [False, True])
def test_pooled_covariance_lda_matches_svd_with_unequal_priors_and_rank_handling(degenerate):
    rng = np.random.RandomState(812)
    y = np.array([0]*13 + [1]*17)
    X = rng.standard_normal((30, 4))
    X[y == 1, 0] += 0.8
    if degenerate:
        X[:, 3] = X[:, 0] + 2*X[:, 1]
    model = LinearDiscriminantAnalysis(solver="svd", tol=1e-4).fit(X, y)
    coef, intercept, diagnostics = check.independent_lda(X, y)
    np.testing.assert_allclose(X @ coef + intercept, model.decision_function(X), atol=1e-10, rtol=1e-10)
    assert diagnostics["within_rank"] == (3 if degenerate else 4)


def test_csp_fails_insufficient_training_rank():
    rng = np.random.RandomState(3)
    data = rng.standard_normal((12, 3, 17))
    with pytest.raises(ValueError, match="rank"):
        check.independent_csp(data, np.array([0, 1]*6), n_components=4)


def test_null_retains_original_pair_ids_and_fixed_surviving_members():
    event = np.tile([0, 1, 2, 4, 5, 14], 3)
    runs = np.repeat([6, 10, 14], 6)
    original = np.tile([0, 1, 0, 1, 0, 1], 3)
    labels = check.paired_labels(original, runs, event, 200)
    np.testing.assert_array_equal(labels[0], original)
    np.testing.assert_array_equal(labels[:, event == 2], np.zeros((201, 3), dtype=int))
    np.testing.assert_array_equal(labels[:, event == 14], np.ones((201, 3), dtype=int))
    for run in check.RUNS:
        for pair in (0, 2):
            members = (runs == run) & (event // 2 == pair)
            assert np.all(labels[:, members].sum(axis=1) == 1)
    # The first RandomState(0) permutation swaps the first original pair.
    np.testing.assert_array_equal(labels[1, :2], [1, 0])
    np.testing.assert_array_equal(check.paired_labels(original, runs, event, 200), labels)


def test_null_rng_resets_for_each_subject():
    y = np.tile([0, 1, 1], 3)
    events = np.tile([0, 1, 14], 3)
    runs = np.repeat(check.RUNS, 3)
    np.testing.assert_array_equal(check.paired_labels(y, runs, events, 5), check.paired_labels(y, runs, events, 5))


def test_holm_stable_ties_and_monotonic_adjustment():
    np.testing.assert_allclose(check.holm([0.01, 0.04, 0.01, 0.2]), [0.04, 0.08, 0.04, 0.2])


def test_identical_decimal_accuracies_have_undefined_group_test():
    rows = [dict(n_epochs=45, accuracy=0.1, kappa=0.0, perm_p=0.5, null_sd=0.04) for _ in range(10)]
    result = check.aggregate_statistics(rows, 200)
    assert result["group_t_vs_chance"] is None
    assert result["group_p_vs_chance"] is None


def test_statistics_use_pooled_counts_tie_inclusive_null_and_unrounded_values():
    target = np.tile([0, 0, 1, 1, 1], (4, 1))
    predicted = np.array([[0, 1, 1, 1, 1], [0, 0, 1, 1, 0], [0, 0, 1, 1, 1], [1, 1, 0, 0, 0]])
    result = check.subject_statistics(target, predicted)
    assert result["accuracy"] == 0.8
    assert result["n_null_ge_observed"] == 2
    assert result["perm_p"] == 0.75
    assert result["kappa"] == pytest.approx(cohen_kappa_score(target[0], predicted[0]))
    assert result["null_sd"] == pytest.approx(np.std([0.8, 1, 0], ddof=0))


def basic_header():
    return {"labels": [str(i) for i in range(64)], "sfreq": [160.0]*64,
            "units": ["uV"]*64, "n_samples": [1000]*64,
            "annotations": [(0, 0.5, "T0"), (0.505, 1, "T1"), (2, 1, "T2"), (5, 1, "T1")]}


def test_epoch_ledger_original_ordinal_rounded_sample_and_inclusive_window():
    ledger = check.epoch_ledger(basic_header(), 1, 6)
    assert [r["event_index"] for r in ledger] == [0, 1, 2]
    assert [r["event_sample"] for r in ledger] == [81, 320, 800]
    assert [r["source_class"] for r in ledger] == [0, 1, 0]
    assert [r["retained"] for r in ledger] == [1, 1, 0]
    assert ledger[2]["drop_reason"] == "out_of_bounds"


def test_bad_annotations_and_duplicate_samples_are_not_silently_accepted():
    header = basic_header()
    header["annotations"].append((1.6, 0.1, "BAD artifact"))
    assert check.epoch_ledger(header, 1, 6)[0]["drop_reason"] == "annotation"
    header["annotations"].insert(2, (0.505, 1, "T2"))
    with pytest.raises(ValueError, match="unique"):
        check.epoch_ledger(header, 1, 6)


def test_edf_parser_reads_header_and_original_tal_bytes(tmp_path):
    # A two-signal miniature format fixture, not a stand-in scientific recording.
    widths = [("0", 8), ("fixture", 80), ("fixture", 80), ("01.01.00", 8), ("00.00.00", 8),
              ("768", 8), ("EDF+C", 44), ("1", 8), ("1", 8), ("2", 4)]
    fixed = b"".join(value.encode().ljust(width) for value, width in widths)
    tal = b"+0\x14\x14\x00+0.25\x151.0\x14T1\x14\x00+0.5\x151.0\x14T2\x14\x00".ljust(80, b"\x00")
    fields = [(["Cz", "EDF Annotations"], 16), (["", ""], 80), (["uV", ""], 8),
              (["-10", "-1"], 8), (["10", "1"], 8), (["-10", "-1"], 8), (["10", "1"], 8),
              (["", ""], 80), (["160", "40"], 8), (["", ""], 32)]
    header = b"".join(value.encode().ljust(width) for values, width in fields for value in values)
    path = tmp_path / "fixture.edf"
    path.write_bytes(fixed + header + b"\x00"*320 + tal)
    parsed = check.edf_header_annotations(path)
    assert parsed["labels"] == ["Cz"]
    assert parsed["sfreq"] == [160.0]
    assert parsed["annotations"] == [(0.25, 1, "T1"), (0.5, 1, "T2")]


def write_rows(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def tiny_glue_fixture(tmp_path, monkeypatch):
    """12 random epochs, 18 tiny fits. Source loading is mocked, never original EEG."""
    output, data_dir = tmp_path / "output", tmp_path / "data"
    output.mkdir()
    data_dir.mkdir()
    manifest = json.loads((Path(__file__).parents[1] / "environment" / "data_manifest.json").read_text())
    (data_dir / "data_manifest.json").write_text(json.dumps(manifest))
    runs = np.repeat(check.RUNS, 4)
    events = np.tile(np.arange(4), 3)
    labels = np.tile([0, 1, 1, 0], 3)
    X = np.random.RandomState(817).standard_normal((12, 64, 161)) * 1e-6
    X[labels == 1, 0] *= 1.7
    targets = check.paired_labels(labels, runs, events, 5)
    predictions, scores = np.empty_like(targets), np.empty(targets.shape)
    ledger = [dict(subject=1, run=int(runs[i]), event_index=int(events[i]), event_sample=int(events[i]*500),
                   source_class=int(labels[i]), retained=1, drop_reason="") for i in range(12)]
    fold_rows, model_rows = [], []
    for replicate in range(6):
        for run in check.RUNS:
            train, test = runs != run, runs == run
            csp = CSP(n_components=4, reg=None, log=True, norm_trace=False).fit(X[train], targets[replicate, train])
            lda = LinearDiscriminantAnalysis(solver="svd", tol=1e-4).fit(csp.transform(X[train]), targets[replicate, train])
            scores[replicate, test] = lda.decision_function(csp.transform(X[test]))
            predictions[replicate, test] = (scores[replicate, test] > 0).astype(int)
            y = targets[replicate]
            fold_rows.append(dict(subject=1, replicate=replicate, test_run=run, n_train=int(train.sum()), n_test=int(test.sum()),
                n_train_class0=int(np.sum(y[train] == 0)), n_train_class1=int(np.sum(y[train] == 1)),
                n_test_class0=int(np.sum(y[test] == 0)), n_test_class1=int(np.sum(y[test] == 1)),
                accuracy=float(np.mean(predictions[replicate, test] == y[test]))))
            model_rows.append(dict(subject=1, replicate=replicate, test_run=run, csp_filters=csp.filters_[:4],
                csp_rank=len(csp.filters_), csp_eigenvalues=csp.evals_[:4], lda_coef=lda.coef_[0],
                lda_intercept=lda.intercept_[0], lda_classes=lda.classes_))
    channels = [f"fixture{i}" for i in range(64)]
    observations = [dict(subject=1, run=run, n_source_events=4, n_retained=4, n_dropped=0) for run in check.RUNS]
    metadata = dict(status="resource_pilot", pipeline_id=check.PIPELINE, source_manifest_sha256=check.MANIFEST_SHA256,
        source_sha256={r["path"]: r["sha256"] for r in manifest["files"]}, executed_subjects=[1], executed_permutations=5,
        channels=channels, sfreq=160, n_epochs_by_run=observations, n_subjects=1, n_epochs_total=12,
        n_source_events=12, n_dropped_epochs=0)
    arrays = dict(subjects=np.array([1]), n_permutations=np.array(5), pipeline_id=np.array(check.PIPELINE),
        subject=np.ones(12, dtype=int), run=runs, event_index=events, event_sample=events*500, source_class=labels,
        X=X.copy(), target_class=targets, predicted_class=predictions, decision_score=scores,
        metadata_json=np.array(json.dumps(metadata)), source_epochs_json=np.array(json.dumps(ledger)),
        run_observations_json=np.array(json.dumps(observations)))
    for key in ("subject", "replicate", "test_run"):
        arrays["fold_"+key] = np.array([r[key] for r in model_rows], dtype=int)
    for key in ("csp_filters", "csp_rank", "csp_eigenvalues", "lda_coef", "lda_intercept", "lda_classes"):
        arrays[key] = np.array([r[key] for r in model_rows])
    np.savez_compressed(output / "analysis_arrays.npz", **arrays)
    write_rows(output / "source_epochs.csv", ledger)
    write_rows(output / "fold_receipts.csv", fold_rows)
    oof = []
    for replicate in range(6):
        for index in range(12):
            row = {k: ledger[index][k] for k in ("subject", "run", "event_index", "event_sample", "source_class")}
            row.update(replicate=replicate, target_class=int(targets[replicate, index]),
                       predicted_class=int(predictions[replicate, index]), decision_score=float(scores[replicate, index]))
            oof.append(row)
    write_rows(output / "oof_predictions.csv", oof)
    summaries = [dict(subject=1, n_epochs=12, n_runs=3, **check.subject_statistics(targets, predictions))]
    group = check.aggregate_statistics(summaries, 5)
    write_rows(output / "per_subject.csv", summaries)
    (output / "decoding_results.json").write_text(json.dumps(dict(status="resource_pilot", pipeline_id=check.PIPELINE, **group)))
    (output / "run_metadata.json").write_text(json.dumps(metadata))
    monkeypatch.setattr(check, "source_epochs", lambda *args: (X.copy(), ledger, ledger, [{"channels": channels}]))
    return data_dir, output, arrays


def test_full_checker_glue_on_tiny_fixture_and_alternate_score_receipts(tiny_glue_fixture):
    data_dir, output, _ = tiny_glue_fixture
    report = {}
    alternate = check.check(data_dir, output, report, pilot=True)
    assert report["all_saved_fold_models_checked"] == 18
    assert report["independent_refit_folds"] == 6
    assert len(alternate["decision_score"]) == 24
    assert str(alternate["source_manifest_sha256"]) == check.MANIFEST_SHA256


@pytest.mark.parametrize("kind", ["epoch", "null", "score", "fractional_identity"])
def test_checker_rejects_corrupted_private_arrays(tiny_glue_fixture, kind):
    data_dir, output, arrays = tiny_glue_fixture
    if kind == "epoch": arrays["X"][0, 0, 0] += 1e-8
    elif kind == "null": arrays["target_class"][1, 0] = 1-arrays["target_class"][1, 0]
    elif kind == "score": arrays["decision_score"][0, 0] += 1
    else: arrays["event_index"] = arrays["event_index"].astype(float) + 0.25
    np.savez_compressed(output / "analysis_arrays.npz", **arrays)
    with pytest.raises(ValueError): check.check(data_dir, output, {}, pilot=True)
