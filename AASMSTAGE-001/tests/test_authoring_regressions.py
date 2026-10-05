"""Synthetic parser/arithmetic cases; no original-data or scientific evidence."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

import fixture_support as f
import metric_contract as q
import proof_of_work as p


@pytest.mark.parametrize("value,expected", [("1e0", 1), ("2.0000", 2), ("9007199254740993", 9007199254740993), (np.uint64(2**63+9), 2**63+9)])
def test_exact_integral_parser(value, expected):
    assert q.integer(value) == expected


@pytest.mark.parametrize("value", [True, np.bool_(False), "subject1", "1.5", "NaN", "Infinity", "-1", None])
def test_invalid_integer(value):
    with pytest.raises(AssertionError):
        q.integer(value)


@pytest.mark.parametrize("value", ["0", "1", "true", "FALSE"])
def test_boolean_tokens(value):
    assert isinstance(q.flag(value), bool)


@pytest.mark.parametrize("value", ["1e0", "0.0", "yes", "", 1, None])
def test_invalid_boolean_tokens(value):
    with pytest.raises(AssertionError):
        q.flag(value)


@pytest.mark.parametrize("value", ['{"x":NaN}', '{"x":Infinity}', '{"x":1e999}', '{"x":1,"x":2}'])
def test_bad_json(value):
    with pytest.raises(AssertionError):
        q.json_loads(value)


def test_exact_large_json_integer_and_boolean_separation():
    q.match(2**60+1, 2**60+1)
    with pytest.raises(AssertionError):
        q.match(float(2**60+1), 2**60+1)
    with pytest.raises(AssertionError):
        q.match(True, 1)


def test_sampling_rate_exact_but_time_rounding_allowed():
    q.match({"onset_s": .1+5e-10}, {"onset_s": .1})
    with pytest.raises(AssertionError):
        q.match({"sfreq_hz": 100+5e-10}, {"sfreq_hz": 100.0})


def test_distinct_balanced_and_overall_estimands():
    matrix = np.zeros((5, 5), dtype=int); matrix[:2, :2] = [[90, 10], [5, 5]]
    m = q.confusion_metrics(matrix)
    assert m["balanced"] == .7 and m["overall"] == 95/110
    assert m["n_supported"] == 2 and m["per_class"][2]["recall"] is None


def test_pooled_macro_and_mean_subject_macro_are_distinct_when_support_differs():
    matrices = {s: np.eye(5, dtype=int) for s in range(6)}
    matrices[0][:2, :2] = [[90, 10], [5, 5]]
    matrices[1][:2, :2] = [[1, 9], [45, 45]]
    expected = q.results_from_matrices(matrices)
    wrong = copy.deepcopy(expected)
    wrong["accuracy"] = wrong["balanced_accuracy"] = float(np.mean([q.confusion_metrics(m)["balanced"] for m in matrices.values()]))
    assert abs(wrong["accuracy"]-expected["accuracy"]) > .01  # Designed synthetic counterexample only.
    with pytest.raises(AssertionError):
        q.validate_results(wrong, expected)


def test_within_class_probability_swap_rejected_despite_unchanged_confusion(tmp_path):
    ref = f.toy_reference()
    ref["truth"][1] = 1
    ref["payload"]["epochs"][1]["stage_id"] = 1
    ref["payload"]["annotations"][1]["stage_id"] = 1
    f.emit_output(tmp_path, ref)
    before = (tmp_path/"confusion_counts.csv").read_bytes()
    swapped = ref["probabilities"].copy(); swapped[[0, 1]] = swapped[[1, 0]]
    f.emit_output(tmp_path, ref, probabilities=swapped)
    assert (tmp_path/"confusion_counts.csv").read_bytes() == before
    with pytest.raises(AssertionError, match="probabilities differ"):
        p.validate_output_directory(tmp_path, ref)


def test_identical_swap_is_logged_as_nondiscriminating_not_negative(tmp_path):
    from test_real_outputs import assess_control
    ref = f.toy_reference(); f.emit_output(tmp_path, ref)
    properties = {}
    with pytest.warns(UserWarning, match="control_not_discriminating"):
        assess_control(tmp_path, ref, True, "synthetic_identical_swap", properties.__setitem__)
    assert properties == {"control_name": "synthetic_identical_swap", "control_status": "control_not_discriminating"}


@pytest.mark.parametrize("control", ["uniform_class_swap", "identical_channel_swap", "identical_within_class_swap", "equal_weighting"])
def test_real_control_harness_handles_nondiscrimination_on_synthetic_inputs(tmp_path, control):
    import test_real_outputs as real
    ref = f.toy_reference(); properties = {}
    if control == "uniform_class_swap":
        ref["probabilities"][:] = .2
    elif control == "identical_channel_swap":
        ref["features"][:, 1::2] = ref["features"][:, ::2]
    elif control == "identical_within_class_swap":
        ref["truth"][1] = 1
        ref["payload"]["epochs"][1]["stage_id"] = 1
        ref["payload"]["annotations"][1]["stage_id"] = 1
        ref["probabilities"][1] = ref["probabilities"][0]
    f.emit_output(tmp_path, ref)
    with pytest.warns(UserWarning, match="control_not_discriminating"):
        if control == "uniform_class_swap":
            real.test_probability_binding_and_argmax(tmp_path, ref, "class_column_swap", properties.__setitem__)
        elif control == "identical_channel_swap":
            real.test_feature_and_physical_scale(tmp_path, ref, "wrong_channel", properties.__setitem__)
        elif control == "identical_within_class_swap":
            real.test_confusion_preserving_wrong_epoch_probabilities(tmp_path, ref, properties.__setitem__)
        else:
            real.test_reported_arithmetic(tmp_path, ref, "mean_subject_macro", properties.__setitem__)
    assert properties["control_status"] == "control_not_discriminating"


def test_probability_shift_is_not_a_noop_for_uniform_vectors(tmp_path):
    import test_real_outputs as real
    ref = f.toy_reference(); ref["probabilities"][:] = .2
    f.emit_output(tmp_path, ref)
    real.test_probability_binding_and_argmax(tmp_path, ref, "coherent_probability_shift", lambda *_: None)


def test_exact_degenerate_kappa_and_absent_recall():
    matrix = np.zeros((5, 5), dtype=int); matrix[0, 0] = 10
    m = q.confusion_metrics(matrix)
    assert m["kappa"] is None and m["kappa_status"] == "undefined_degenerate_marginals"
    assert m["balanced"] == 1 and m["per_class"][1]["recall_status"] == "undefined_no_true_epochs"


def test_negative_kappa_is_legitimate():
    matrix = np.zeros((5, 5), dtype=int); matrix[0, 1] = matrix[1, 0] = 2
    assert q.confusion_metrics(matrix)["kappa"] == -1


def test_probability_tie_smallest_class():
    assert q.own_predictions([[.5, .5, 0, 0, 0]]).tolist() == [1]


@pytest.mark.parametrize("row", [[.5, .6, 0, 0, 0], [1.00000000001, -.00000000001, 0, 0, 0], [np.nan, 1, 0, 0, 0]])
def test_invalid_probability(row):
    with pytest.raises(AssertionError):
        q.own_predictions([row])


def test_tiny_psd_values_are_checked_relatively(tmp_path):
    ref = f.toy_reference(); f.emit_output(tmp_path, ref, psd_sum=ref["psd_sum"]*1.01)
    with pytest.raises(AssertionError, match="PSD sums differ"):
        p.validate_output_directory(tmp_path, ref)


def test_feature_boundary_rounding_uses_declared_allowance():
    x = np.zeros((1, 10)); x[0, 8:] = 1/37+1e-12
    p.validate_features(x, np.ones((1, 2)))
    x[0, 8:] = 1/37+1e-7
    with pytest.raises(AssertionError):
        p.validate_features(x, np.ones((1, 2)))


def test_complete_constant_subject_scores_pass(tmp_path):
    ref = f.toy_reference(); f.emit_output(tmp_path, ref)
    p.validate_output_directory(tmp_path, ref)


def test_rounded_probability_tie_can_change_prediction_coherently(tmp_path):
    ref = f.toy_reference(); ref["probabilities"][0] = [.5, .5, 0, 0, 0]
    alternate = ref["probabilities"].copy(); alternate[0] = [.5-1e-11, .5+1e-11, 0, 0, 0]
    f.emit_output(tmp_path, ref, probabilities=alternate)
    p.validate_output_directory(tmp_path, ref)


def test_per_field_probability_bound_is_not_widened_at_ties(tmp_path):
    ref = f.toy_reference(); ref["probabilities"][0] = [.5, .5, 0, 0, 0]
    alternate = ref["probabilities"].copy(); alternate[0] = [.5-1e-5, .5+1e-5, 0, 0, 0]
    f.emit_output(tmp_path, ref, probabilities=alternate)
    with pytest.raises(AssertionError, match="probabilities differ"):
        p.validate_output_directory(tmp_path, ref)


def test_zero_status_omissions_and_metadata_order_are_fair(tmp_path):
    ref = f.toy_reference(); f.emit_output(tmp_path, ref)
    meta = copy.deepcopy(ref["payload"]["metadata"])
    meta["source_observed"]["subjects"].reverse()
    for row in meta["source_observed"]["subjects"]:
        row["epoch_status_counts"]["outside_recording"] = 0
    meta["software_versions"] = {"independent library": "different real version"}
    f.write_json(tmp_path/"run_metadata.json", meta)
    p.validate_output_directory(tmp_path, ref)


@pytest.mark.parametrize("mode", ["method_boolean", "extra_method", "extra_source", "failed_status", "unknown_status", "missing_null"])
def test_metadata_and_required_nulls_fail_closed(tmp_path, mode):
    ref = f.toy_reference(); f.emit_output(tmp_path, ref)
    meta = copy.deepcopy(ref["payload"]["metadata"])
    if mode == "method_boolean":
        meta["method_contract"]["classifier"]["parameters"]["n_jobs"] = True
    elif mode == "extra_method":
        meta["method_contract"]["undeclared_filter"] = True
    elif mode == "extra_source":
        meta["source_sha256"]["invented"] = "f"*64
    elif mode == "failed_status":
        meta["status"] = "resource_pilot"
    elif mode == "unknown_status":
        meta["source_observed"]["subjects"][0]["epoch_status_counts"]["quality_excluded"] = 0
    else:
        del meta["method_contract"]["classifier"]["parameters"]["max_depth"]
    f.write_json(tmp_path/"run_metadata.json", meta)
    with pytest.raises(AssertionError):
        p.validate_output_directory(tmp_path, ref)


def test_obsolete_bank_is_rejected_without_reading_historical_bank(tmp_path):
    path = tmp_path/"obsolete.npz"
    np.savez(path, group_balanced=np.array(.1))
    with pytest.raises(AssertionError, match="obsolete"):
        p.load_reference(path)


def test_grader_is_offline_python3_and_resets_reward_first():
    script = Path(__file__).with_name("test.sh")
    text = script.read_text()
    assert "python3 -m pytest" in text and "curl" not in text and "apt-get" not in text and "uvx" not in text
    assert text.index("echo 0") < text.index("python3")
    assert script.stat().st_mode & 0o111
