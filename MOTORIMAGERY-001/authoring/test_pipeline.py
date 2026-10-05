"""Bounded equation/pipeline fixtures, never genuine-data performance evidence."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("motorimagery_oracle", TASK/"solution/compute.py")
ORACLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ORACLE)
REL = ORACLE._reliability if hasattr(ORACLE, "_reliability") else __import__("reliability")


def source_cues():
    return np.tile([0, 1]*7+[1], 3), np.repeat([6, 10, 14], 15), np.tile(np.arange(15), 3)


def test_pair_stream_exact_rng_order_and_subject_reset():
    labels, runs, indices = source_cues()
    actual = REL.permutation_targets(labels, runs, indices, 6)
    expected = np.tile(labels, (7, 1))
    rng = np.random.RandomState(0)
    for replicate in range(1, 7):
        for run in [6, 10, 14]:
            for pair in range(7):
                selected = np.flatnonzero((runs == run) & (indices//2 == pair))
                expected[replicate, selected] = rng.permutation(labels[selected])
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(actual, REL.permutation_targets(labels, runs, indices, 6))
    np.testing.assert_array_equal(actual[:, indices == 14], np.ones((7, 3)))
    assert np.any(actual[1:] != labels)
    for run in [6, 10, 14]:
        for pair in range(7):
            assert np.all(actual[:, (runs == run) & (indices//2 == pair)].sum(axis=1) == 1)


def test_original_pair_identity_survives_drops_and_no_rng_draw_for_orphans():
    labels, runs, indices = source_cues()
    keep = ~((runs == 6) & (indices == 1))
    labels, runs, indices = labels[keep], runs[keep], indices[keep]
    actual = REL.permutation_targets(labels, runs, indices, 3)
    survivor = (runs == 6) & (indices == 0)
    assert np.all(actual[:, survivor] == 0)
    rng = np.random.RandomState(0)
    first_complete = np.flatnonzero((runs == 6) & (indices//2 == 1))
    np.testing.assert_array_equal(actual[1, first_complete], rng.permutation(labels[first_complete]))
    assert actual.shape == (4, 44)


@pytest.mark.parametrize("case", ["duplicate", "fractional", "foreign", "class", "unbalanced_pair", "missing_run"])
def test_bad_source_pair_contract_fails(case):
    labels, runs, indices = source_cues()
    if case == "duplicate": indices[1] = indices[0]
    elif case == "fractional": indices = indices.astype(float); indices[0] = .1
    elif case == "foreign": indices[0] = 15
    elif case == "class": labels[0] = 2
    elif case == "unbalanced_pair": labels[1] = labels[0]
    elif case == "missing_run": runs[runs == 14] = 10
    with pytest.raises(ValueError): REL.permutation_targets(labels, runs, indices, 2)


def test_pooled_statistic_is_not_unweighted_fold_mean():
    # Deliberately unequal fold sizes distinguish the two statistics.
    runs = np.array([6, 6, 10, 10, 10, 10, 14, 14, 14, 14])
    y = np.array([0, 1]*5)
    prediction = y.copy(); prediction[:2] = 1-y[:2]
    targets = np.vstack([y, y, y])
    predictions = np.vstack([prediction, y, 1-y])
    row = REL.subject_statistics(1, runs, targets, predictions)
    assert row["accuracy"] == .8
    assert row["accuracy"] != np.mean([0, 1, 1])
    assert row["perm_p"] == pytest.approx(2/3)
    assert row["n_null_ge_observed"] == 1
    assert row["null_mean"] == .5 and row["null_sd"] == .5


def test_permutation_exceedances_include_ties_and_plus_one():
    y = np.array([0, 1, 0, 1])
    targets = np.tile(y, (4, 1))
    predictions = np.array([[0, 1, 1, 0], [0, 1, 1, 0], [0, 1, 0, 1], [1, 0, 1, 0]])
    row = REL.subject_statistics(1, [6, 6, 10, 14], targets, predictions)
    assert row["n_null_ge_observed"] == 2 and row["perm_p"] == .75


@pytest.mark.parametrize("predicted", [[0, 0, 0, 0], [1, 1, 1, 1], [0, 1, 0, 1], [1, 0, 1, 0]])
def test_kappa_matches_sklearn(predicted):
    from sklearn.metrics import cohen_kappa_score
    y = np.array([0, 1, 0, 1])
    _, value = REL.accuracy_kappa(y, predicted)
    assert value == pytest.approx(cohen_kappa_score(y, predicted))


def subject_row(subject, accuracy):
    return {"subject": subject, "n_epochs": 10, "n_runs": 3, "accuracy": accuracy,
            "kappa": 2*accuracy-1, "perm_p": .01*subject, "null_sd": .1}


@pytest.mark.parametrize("accuracies", [[.5], [.5, .5], [.75, .75], [.6]*10])
def test_undefined_group_t_is_json_null_without_quality_gate(accuracies):
    result = REL.group_statistics([subject_row(i+1, a) for i, a in enumerate(accuracies)], 200)
    assert result["group_t_vs_chance"] is None and result["group_p_vs_chance"] is None
    json.dumps(result, allow_nan=False)


def test_group_statistics_subject_weighted_and_holm_family_preserved():
    from scipy.stats import ttest_1samp
    rows = [subject_row(1, .8), subject_row(2, .4), subject_row(3, .6)]
    rows[0]["n_epochs"] = 100
    result = REL.group_statistics(rows, 200)
    assert result["accuracy"] == pytest.approx(.6)
    assert result["n_epochs_total"] == 120
    assert result["group_p_vs_chance"] == pytest.approx(ttest_1samp([.8, .4, .6], .5).pvalue)
    np.testing.assert_allclose([row["holm_p"] for row in rows], [.03, .04, .04])


@pytest.mark.parametrize("raw,expected", [([], ""), (["TOO_SHORT"], "out_of_bounds"),
    (["NO_DATA", "TOO_SHORT"], "out_of_bounds"), (["BAD_motion"], "annotation"),
    (["BAD_motion", "NO_DATA"], "annotation;out_of_bounds")])
def test_drop_reason_mapping(raw, expected):
    assert ORACLE.canonical_drop_reason(raw) == expected


def test_unrecognized_rejection_cannot_silently_remove_epochs():
    with pytest.raises(ValueError): ORACLE.canonical_drop_reason(["EEG001"])


def raw_fixture(bad_annotation=False, duplicate=False):
    import mne
    channels = ORACLE.CHANNELS
    rng = np.random.default_rng(853)
    data = rng.normal(scale=1e-6, size=(64, 8*160))
    raw = mne.io.RawArray(data, mne.create_info(channels, 160., "eeg"), verbose=False)
    onsets, durations, descriptions = [.5, 2.5, 7.], [.2, .2, .2], ["T1", "T2", "T1"]
    if bad_annotation:
        onsets.append(1.7); durations.append(.1); descriptions.append("BAD_fixture")
    if duplicate:
        onsets.append(.5); durations.append(.2); descriptions.append("T2")
    raw.set_annotations(mne.Annotations(onsets, durations, descriptions))
    return raw


@pytest.mark.parametrize("bad_annotation", [False, True])
def test_run_epoch_grid_preserves_boundary_and_annotation_ledger(bad_annotation):
    result = ORACLE.epoch_run(raw_fixture(bad_annotation), 1, 6)
    assert result["X"].shape == (1 if bad_annotation else 2, 64, 161)
    assert result["source_rows"][-1]["retained"] == 0
    assert result["source_rows"][-1]["drop_reason"] == "out_of_bounds"
    assert result["source_rows"][0]["event_sample"] == 80
    if bad_annotation:
        assert result["source_rows"][0]["drop_reason"] == "annotation"
        assert result["event_index"].tolist() == [1]  # Preserve original indexing after drops.


def test_duplicate_original_cue_samples_fail():
    with pytest.raises(ValueError, match="unique"):
        ORACLE.epoch_run(raw_fixture(duplicate=True), 1, 6)


def test_classifier_public_defaults_are_explicit():
    pipeline = ORACLE.csp_lda()
    for name, expected in (("csp", ORACLE.CSP_PARAMETERS), ("lda", ORACLE.LDA_PARAMETERS)):
        actual = pipeline.named_steps[name].get_params()
        assert all(actual[key] == value for key, value in expected.items())


def test_actual_small_fixture_refits_every_fold_and_retains_manual_score_algebra(monkeypatch):
    rng = np.random.default_rng(842)
    runs = np.repeat([6, 10, 14], 4)
    event_index = np.tile(np.arange(4), 3)
    labels = np.tile([0, 1, 0, 1], 3)
    x = rng.normal(scale=1e-6, size=(12, 8, 80))
    x[labels == 1, :2] *= 1.3
    epochs = {"X": x, "source_class": labels, "run": runs, "event_index": event_index}
    original, calls = ORACLE.csp_lda, []
    def count_pipeline():
        calls.append(1)
        return original()
    monkeypatch.setattr(ORACLE, "csp_lda", count_pipeline)
    fit = ORACLE.fit_subject(1, epochs, 2, progress=False)
    assert len(calls) == 9 and len(fit["fold_rows"]) == 9
    assert fit["decision_score"].shape == (3, 12)
    for row in fit["fold_private"]:
        selected = runs == row["test_run"]
        projected = np.einsum("kc,nct->nkt", row["csp_filters"], x[selected])
        features = np.log(np.mean(projected**2, axis=-1))
        decision = features @ row["lda_coef"] + row["lda_intercept"]
        np.testing.assert_allclose(decision, fit["decision_score"][row["replicate"], selected], atol=1e-12)
        np.testing.assert_array_equal((decision > 0).astype(int), fit["predicted_class"][row["replicate"], selected])


def test_contract_generation_never_requires_source_data_or_fit():
    manifest = json.loads((TASK/"environment/data_manifest.json").read_text())
    template = ORACLE.metadata_contract(manifest)
    assert template["pipeline_id"] == "eegbci-paired-null-held-run-csp-v3"
    assert len(template["source_sha256"]) == 30
    assert template["permutation"]["incomplete_pair"] == "surviving_label_fixed_and_no_RNG_draw"
    assert template["epochs"]["reject_by_annotation"] is True
    assert template["permutation"]["singleton_event14"] == "fixed"
    assert len(template["channels"]) == 64 and template["sfreq"] == 160.
    assert "accuracy" not in template
