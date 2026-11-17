"""Generated engineering controls, not AJILE12 observations or scientific evidence."""
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

HOME = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("neural050", HOME / "evaluator.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def packet():
    rows, pins = [], []
    for patient in range(3):
        for day in range(2):
            p, d, session = f"p{patient}", f"2020-01-{day+1:02}", f"session{day}"
            pins.append({"patient": p, "day": d, "session": session, "sha256": "0"*64})
            for i in range(12):
                gamma = float(i % 4)
                start = float(day * 86400 + i * 4)
                rows.append({"id": f"{p}/{d}/{i}", "patient": p, "day": d, "session": session,
                             "start_utc_s": start, "stop_utc_s": start+2, "local_seconds": 3600.0+i*4,
                             "state": "Eat", "gamma": gamma, "movement": 2+3*gamma})
    return {"schema": "neural050-features-v1", "data_scope": "public_development_only", "protocol": e.PROTOCOL,
            "rows": rows, "source_pins": pins, "input_kind": "generated_engineering_control", "raw_manifest_sha256": "0"*64, "source_dataset": {"dandiset": "000055", "version": "0.220127.0436"}}


def raw_manifest(tmp_path, amplitude=1.0, invalid=False):
    et = np.arange(0, 8, 1/500)
    pt = np.arange(241)/30
    ecog = amplitude*np.sin(2*np.pi*90*et)[:, None]
    valid = np.ones(len(et), dtype=bool)
    if invalid:
        valid[100] = False
    path = tmp_path / f"raw-{amplitude}-{invalid}.npz"
    np.savez(path, ecog=ecog, ecog_time_s=et, ecog_valid=valid,
             pose_xy=np.column_stack([3*pt, 4*pt]), pose_time_s=pt,
             pose_confidence=np.ones(len(pt)), pose_valid=np.ones(len(pt), dtype=bool))
    rec = {"patient": "p1", "day": "2020-01-01", "session": "s1", "path": str(path), "sha256": e.digest(path),
           "session_start_utc": "2020-01-01T00:00:00Z", "local_utc_offset_seconds": 0, "motor_channels": [0],
           "anatomy_evidence": "generated-control-only", "wrist_selection_evidence": "generated-control-only",
           "clock_evidence": "generated-control-only", "artifact_mask_evidence": "generated-control-only", "pose_units": "pixels", "source_asset_path": "generated_control.npz", "source_asset_id": "generated-control-only",
           "behavior_epochs": [{"start_s": 0, "stop_s": 8, "state": "Eat"}]}
    return {"schema": "neural050-raw-v1", "data_scope": "public_development_only", "protocol": e.PROTOCOL, "recordings": [rec], "input_kind": "generated_engineering_control", "source_dataset": {"dandiset": "000055", "version": "0.220127.0436"}}


def test_signal_features_have_analytic_scale(tmp_path):
    one = e.prepare(raw_manifest(tmp_path, 1.0))
    two = e.prepare(raw_manifest(tmp_path, 2.0))
    assert len(one["rows"]) == 4
    assert [r["movement"] for r in one["rows"]] == pytest.approx([5]*4)
    assert np.array([r["gamma"] for r in two["rows"]])-np.array([r["gamma"] for r in one["rows"]]) == pytest.approx([np.log(4)]*4)
    assert np.exp(one["rows"][0]["gamma"]) == pytest.approx(0.5, rel=1e-5)


def test_qc_rejects_zero_filled_or_masked_support(tmp_path):
    out = e.prepare(raw_manifest(tmp_path, invalid=True))
    assert len(out["rows"]) == 3
    assert out["excluded_windows"][0]["reasons"] == ["artifact_or_pose_QC"]


def test_overlap_behaviors_match_exact_label_sets(tmp_path):
    m = raw_manifest(tmp_path)
    m["recordings"][0]["behavior_epochs"].append({"start_s": 0, "stop_s": 4, "state": "Talk"})
    out = e.prepare(m)
    assert [r["state"] for r in out["rows"]] == ['["Eat","Talk"]']*2 + ['["Eat"]']*2


def test_provenance_and_clock_fail_closed(tmp_path):
    m = raw_manifest(tmp_path)
    m["recordings"][0]["sha256"] = "1"*64
    with pytest.raises(ValueError, match="SHA256"):
        e.prepare(m)
    m = raw_manifest(tmp_path)
    m["recordings"][0]["session_start_utc"] = "2020-01-01T00:00:00"
    with pytest.raises(ValueError, match="UTC"):
        e.prepare(m)
    with pytest.raises(ValueError, match="regular"):
        e.regular_clock([0, 1, 3], "test")


def test_exact_independent_prediction_arithmetic():
    rows = [{"id": str(i), "patient": "p", "day": "d", "movement": float(i)} for i in range(3)]
    result = e.score_predictions(rows, {str(i): 1.0 for i in range(3)}, {str(i): float(i) for i in range(3)})[0]
    assert result["delta_mse"] == pytest.approx(2/3)
    assert result["delta_r2"] == pytest.approx(1)


def test_macro_unit_is_patient_not_window():
    x = [{"patient": "a", "delta": 2/3}, {"patient": "b", "delta": -1/3}]
    assert e.patient_summary(x, "delta")["mean"] == pytest.approx(1/6)
    assert e.patient_summary([x[0]]*99+[x[1]], "delta")["mean"] == pytest.approx(1/6)
    rows = packet()["rows"]
    w = e.balanced_weights(rows)
    assert w.sum() == pytest.approx(1)
    for p in {r["patient"] for r in rows}:
        assert sum(weight for r, weight in zip(rows, w) if r["patient"] == p) == pytest.approx(1/3)


def test_constant_target_is_undefined_not_infinity():
    rows = [{"id": str(i), "patient": "p", "day": "d", "movement": 1.0} for i in range(4)]
    v = {str(i): 1.0 for i in range(4)}
    result = e.score_predictions(rows, v, v)[0]
    assert result["delta_r2"] is None and result["constant_target"]
    assert result["constant_gamma_prediction"]
    assert e.patient_summary([result], "delta_r2")["n_days_defined"] == 0


@pytest.mark.parametrize("alter", ["duplicate", "missing", "nan", "overlap", "pin"])
def test_bad_inputs_rejected(alter):
    p = packet()
    if alter == "duplicate":
        p["rows"][1]["id"] = p["rows"][0]["id"]
    elif alter == "missing":
        del p["rows"][0]["movement"]
    elif alter == "nan":
        p["rows"][0]["gamma"] = float("nan")
    elif alter == "overlap":
        p["rows"][1]["start_utc_s"] = 1
        p["rows"][1]["stop_utc_s"] = 3
    else:
        p["source_pins"] = p["source_pins"][1:]
    with pytest.raises(ValueError):
        e.evaluate(p)


def test_prediction_ids_and_nonfinite_rejected():
    rows = packet()["rows"][:4]
    v = {r["id"]: 0.0 for r in rows}
    with pytest.raises(ValueError, match="IDs"):
        e.score_predictions(rows, v, {})
    bad = dict(v); bad[rows[0]["id"]] = float("inf")
    with pytest.raises(ValueError, match="finite"):
        e.score_predictions(rows, v, bad)


def test_train_only_scaling_and_predictions_ignore_test_targets():
    _, train, test = next(e.folds(e.validate_features(packet()), "population_transfer"))
    pred, fit = e.fit_predict(train, test, True)
    changed = copy.deepcopy(test)
    for r in changed:
        r["movement"] += 1e9
    p2, f2 = e.fit_predict(train, changed, True)
    assert pred == pytest.approx(p2)
    assert fit == f2
    changed[0]["gamma"] += 1e8
    _, f3 = e.fit_predict(train, changed, True)
    assert fit == f3


def test_zero_gamma_matches_baseline():
    p = packet()
    for r in p["rows"]:
        r["gamma"] = 0.0
    result = e.evaluate(p)
    assert result["incremental_delta_r2"]["mean"] == pytest.approx(0, abs=1e-12)


def test_real_fitting_improves_generated_relation_and_freezes_units():
    result = e.evaluate(packet())
    assert result["incremental_delta_r2"]["mean"] > 0.65
    assert result["scientific_qualification"] == "unknown"
    assert len(result["fold_audit"]) == 3
    for f in result["fold_audit"]:
        assert {s.split('/')[0] for s in f["train_ids"]}.isdisjoint({s.split('/')[0] for s in f["test_ids"]})
    within = e.evaluate(packet(), "within_patient_days")
    assert len(within["fold_audit"]) == 6


def test_guard_rejects_day_labels_that_hide_adjacent_windows():
    p = packet()
    for r in p["rows"]:
        if r["day"] == "2020-01-02":
            r["start_utc_s"] -= 86400-46
            r["stop_utc_s"] -= 86400-46
    with pytest.raises(ValueError, match="guard"):
        list(e.folds(e.validate_features(p), "within_patient_days"))


def test_matched_pairs_exact_state_time_and_no_reuse():
    rows = packet()["rows"][:4]
    for row, movement, gamma in zip(rows, [10, 0, 11, 0], [3, 1, 7, 3]):
        row["movement"], row["gamma"] = movement, gamma
    pairs, unmatched = e.matched_contrasts(rows, 5)
    assert len(pairs) == 2 and unmatched == 0
    assert np.mean([r["gamma_difference"] for r in pairs]) == pytest.approx(3)
    assert len({p["low_id"] for p in pairs}) == 2
    rows[1]["state"] = "Talk"
    pairs, unmatched = e.matched_contrasts(rows, 5)
    assert len(pairs) == 1 and unmatched == 2


def test_day_shift_preserves_each_day_values():
    original = packet()["rows"]
    shifted = e.shifted_gamma(original)
    for patient, day in {(r["patient"], r["day"]) for r in original}:
        select = lambda rows: sorted(r["gamma"] for r in rows if (r["patient"], r["day"]) == (patient, day))
        assert select(original) == select(shifted)
    assert original == packet()["rows"]


def test_cli_and_json_duplicate_keys(tmp_path):
    inp, out = tmp_path / "input.json", tmp_path / "report.json"
    inp.write_text(json.dumps(packet()))
    run = subprocess.run([sys.executable, str(HOME / "evaluator.py"), "evaluate", str(inp), str(out)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert json.loads(out.read_text())["scientific_qualification"] == "unknown"
    inp.write_text('{"x":1,"x":2}')
    with pytest.raises(ValueError, match="duplicate"):
        e.read_json(inp)


def test_provenance_binds_clock_and_state_metadata(tmp_path):
    m = raw_manifest(tmp_path)
    first = e.prepare(m)
    m["recordings"][0]["local_utc_offset_seconds"] = 3600
    changed = e.prepare(m)
    assert first["source_pins"][0]["sha256"] == changed["source_pins"][0]["sha256"]
    assert first["raw_manifest_sha256"] != changed["raw_manifest_sha256"]
    assert changed["source_pins"][0]["extraction_manifest_record"]["local_utc_offset_seconds"] == 3600
    result = e.evaluate(packet())
    assert result["feature_packet_sha256"] == e.canonical_digest(packet())


def test_midnight_half_open_window_is_accepted(tmp_path):
    m = raw_manifest(tmp_path)
    m["recordings"][0]["session_start_utc"] = "2020-01-01T23:59:52Z"
    result = e.prepare(m)
    assert len(result["rows"]) == 4


def test_no_match_coverage_is_explicit():
    p = packet()
    for r in p["rows"]:
        r["movement"] = 1.0
    result = e.evaluate(p)
    assert result["matched_coverage"]["n_evaluated_patients"] == 3
    assert result["matched_coverage"]["n_matched_patients"] == 0
    assert result["matched_coverage"]["n_evaluated_days"] == 6
    assert result["matched_coverage"]["n_matched_days"] == 0
    assert result["matched_gamma_log_power_difference"]["mean"] is None


def test_binary_clock_selection_equals_independent_full_mask():
    for fs in (30, 500):
        for offset in (0.0, 0.017, 1.0):
            times = offset + np.arange(fs*10)/fs
            for left in (0.0, 2.0, 4.0, 8.0):
                for inclusive in (False, True):
                    right = left+2
                    mask = (times >= left-1e-8) & (times <= right+1e-8 if inclusive else times < right-1e-8)
                    assert np.array_equal(e.interval_indices(times, left, right, inclusive), np.flatnonzero(mask))
