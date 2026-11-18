"""Generated engineering controls with analytic, non-scientific oracles."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("find024_evaluator", ROOT / "evaluator.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def fixture(amplitudes=None):
    # At t=0, each context repeats [-1,0,1]. Context2 instead follows [1,0,-1]
    # at t=1. Thus CCC is 1 at lag0, undefined at .5, and -1 at lag1;
    # same-context reliability is1 at defined lags. This is hand-checkable.
    rates = [1 / np.sqrt(3), np.sqrt(3)]
    stimuli, epochs, cells, traces = [], [], [], []
    for rate_index, rate in enumerate(rates):
        cells.append({"story_id": "story", "speech_rate": rate, "segment_duration_sec": .1})
        for context in ["natural", "random"]:
            for segment, amplitude in enumerate([-1., 0., 1.] if amplitudes is None else amplitudes):
                stimulus = f"r{rate_index}-{context}-{segment}"
                stimuli.append(stimulus)
                sign = 1 if context == "natural" else -1
                traces.append([amplitude, sign * amplitude, sign * amplitude])
                epochs.append({"epoch_id": stimulus, "stimulus_id": stimulus,
                    "story_id": "story", "speech_rate": rate, "segment_duration_sec": .1,
                    "context_id": context, "segment_id": f"segment{segment}", "onset_sec": 0.})
    d = np.asarray(traces).T[:, :, None, None]
    d = np.repeat(d, 2, axis=3)
    p = {"participant_id": "p1", "electrode_ids": ["e1"], "stimulus_ids": stimuli,
        "repetition_ids": ["repeat1", "repeat2"], "stimulus_durations_sec": {s: 2. for s in stimuli}, "bad_stimuli": {}, "expected_cells": cells, "epochs": epochs}
    manifest = {"schema": e.SCHEMA, "input_role": "empirical_electrode_timecourses",
        "boundary_policy": "explicit_distinct_contexts", "alignment_policy": "linear_interpolation",
        "cohort_id": "generated-control", "eligibility_provenance": "all generated channels",
        "selection_uses_assessment_effects": False, "lags_sec": [0., 1.],
        "evaluation_mode": "unsplit_recomputation", "expected_participants": ["p1"],
        "story_splits": {"story": "analysis"}, "participants": [p]}
    return manifest, {"p1": {"D": d, "t": np.array([0., 1., 2.])}}


class CorrelationTests(unittest.TestCase):
    def test_extreme_finite_pearson_and_orthogonal_reference(self):
        self.assertAlmostEqual(e._pearson([1e308, 8e307, 6e307], [1e308, 8e307, 6e307]), 1.)
        self.assertAlmostEqual(e._pearson([-1, -1, 1, 1], [-1, 1, -1, 1]), 0.)
        self.assertAlmostEqual(e._pearson([-1, 0, 1], [-1, 1, 0]), .5)

    def test_duplicate_physical_context_rejected(self):
        m, a = fixture()
        p = m["participants"][0]
        p["epochs"].append(dict(p["epochs"][0], epoch_id="alias", context_id="fake"))
        with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_same_stimulus_cannot_cross_rates(self):
        m, a = fixture()
        p = m["participants"][0]
        # Physical offsets differ: condition identity binding must still reject.
        p["epochs"][6]["stimulus_id"] = p["epochs"][0]["stimulus_id"]
        p["epochs"][6]["onset_sec"] = .1
        with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_two_nearly_identical_slow_rates_cannot_replace_fast_rate(self):
        m, a = fixture()
        rate = 1 / np.sqrt(3) + 1e-12
        p = m["participants"][0]
        p["expected_cells"][1]["speech_rate"] = rate
        for epoch in p["epochs"][6:]: epoch["speech_rate"] = rate
        with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_near_equal_rates_are_canonicalized_and_cannot_duplicate_cells(self):
        m, a = fixture()
        p = m["participants"][0]
        p["expected_cells"][0]["speech_rate"] += 1e-12
        for epoch in p["epochs"][:6]: epoch["speech_rate"] += 2e-12
        r = e.evaluate(m, a)
        self.assertEqual(min(x["speech_rate"] for x in r["rows"]), 1 / np.sqrt(3))
        p["expected_cells"].append(dict(p["expected_cells"][0], speech_rate=1 / np.sqrt(3)))
        with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_independent_corrected_correlation_above_one_is_not_clipped(self):
        m, a = fixture([-1., -1., 1., 1.])
        signal = np.array([-1., -1., 1., 1.])
        noise = np.array([-1., 1., -1., 1.])
        p = m["participants"][0]
        for si, epoch in enumerate(p["epochs"]):
            index = int(epoch["segment_id"].replace("segment", ""))
            if epoch["context_id"] == "natural":
                a["p1"]["D"][:, si, 0, 0] = signal[index] + noise[index]
                a["p1"]["D"][:, si, 0, 1] = signal[index] - noise[index]
            else:
                a["p1"]["D"][:, si, 0, :] = signal[index]
        for row in e.evaluate(m, a)["rows"]:
            self.assertAlmostEqual(row["diff_context"], 1 / np.sqrt(2))
            self.assertAlmostEqual(row["same_context"], .5)
            self.assertAlmostEqual(row["normalized_ccc"], np.sqrt(2))

    def test_segment_cannot_be_in_recorded_poststimulus_padding(self):
        m, a = fixture()
        p = m["participants"][0]
        first = p["epochs"][0]
        p["stimulus_durations_sec"][first["stimulus_id"]] = .5
        first["onset_sec"] = .6
        # Extraction remains inside D's 0..2 s; actual sound ended at .5 s.
        with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_complex_inputs_are_not_silently_projected_to_real(self):
        for field in ["D", "t"]:
            m, a = fixture()
            a["p1"][field] = a["p1"][field].astype(complex) + 1j
            with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_subnormal_ceiling_preserves_raw_values_and_nulls_overflow(self):
        m, arrays = fixture([0., 0., 0., 0.])
        x, y = [-1., 0., 1., 0.], [0., 1., 1e-322, -1.]
        for si, epoch in enumerate(m["participants"][0]["epochs"]):
            index = int(epoch["segment_id"].replace("segment", ""))
            arrays["p1"]["D"][:, si, 0, 0] = x[index]
            arrays["p1"]["D"][:, si, 0, 1] = y[index]
        result = e.evaluate(m, arrays)
        for row in result["rows"]:
            self.assertAlmostEqual(row["diff_context"], .5)
            self.assertGreater(row["same_context"], 0.)
            self.assertLess(row["same_context"], 1e-320)
            self.assertIsNone(row["normalized_ccc"])
            self.assertEqual(row["status"], "nonfinite_normalization")
        json.dumps(result, allow_nan=False)

    def test_hand_derived_same_and_opposite_context(self):
        m, a = fixture()
        r = e.evaluate(m, a)
        self.assertEqual(len(r["rows"]), 4)
        for row in r["rows"]:
            self.assertEqual(row["same_context"], 1.)
            self.assertEqual(row["diff_context"], 1. if row["lag_sec"] == 0 else -1.)
            self.assertEqual(row["same_context_pair_count"], 2)
            self.assertEqual(row["different_context_pair_count"], 4)
        self.assertFalse(r["native_parity_verified"])
        self.assertEqual(r["scientific_qualification"], "unknown")

    def test_interpolation_exposes_zero_variance_without_dropping(self):
        m, a = fixture()
        m["lags_sec"] = [0., .5, 1.]
        r = e.evaluate(m, a)
        bad = [row for row in r["rows"] if row["lag_sec"] == .5]
        self.assertEqual(len(bad), 2)
        for row in bad:
            self.assertIsNone(row["same_context"])
            self.assertIsNone(row["diff_context"])
            self.assertIsNone(row["normalized_ccc"])
        self.assertTrue(all(x["status"] != "ok" for x in r["population_summary"] if x["lag_sec"] == .5))
        json.dumps(r, allow_nan=False)

    def test_no_silent_segment_intersection(self):
        m, a = fixture()
        m["participants"][0]["epochs"].pop()
        with self.assertRaises(e.ContractError):
            e.evaluate(m, a)

    def test_missing_participant_fails(self):
        m, a = fixture()
        m["expected_participants"].append("p2")
        with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_cached_input_role_fails(self):
        m, a = fixture()
        m["input_role"] = "precomputed_correlation"
        with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_missing_cell_after_bad_stimulus_exclusion_fails(self):
        m, a = fixture()
        p = m["participants"][0]
        p["bad_stimuli"] = {s: "absent recording" for s in p["stimulus_ids"] if s.startswith("r1")}
        with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_bad_stimulus_exclusion_is_audited(self):
        m, a = fixture()
        p = m["participants"][0]
        extra = dict(p["epochs"][0], epoch_id="bad-epoch", stimulus_id="bad-stim")
        p["stimulus_ids"].append("bad-stim")
        p["stimulus_durations_sec"]["bad-stim"] = 2.
        p["epochs"].append(extra)
        p["bad_stimuli"]["bad-stim"] = "prespecified missing recording"
        a["p1"]["D"] = np.concatenate([a["p1"]["D"], np.full((3, 1, 1, 2), np.nan)], axis=1)
        r = e.evaluate(m, a)
        self.assertEqual(r["participant_audit"][0]["excluded_epoch_count"], 1)

    def test_negative_ceiling_remains_unclipped_and_undefined_ratio(self):
        m, a = fixture()
        a["p1"]["D"][:, :, :, 1] *= -1
        r = e.evaluate(m, a)
        for row in r["rows"]:
            self.assertEqual(row["same_context"], -1.)
            self.assertIsNone(row["normalized_ccc"])

    def test_story_split_is_global_and_mode_explicit(self):
        m, a = fixture()
        m["evaluation_mode"] = "prospective_story_holdout"
        m["story_splits"] = {"story": "assessment"}
        with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_prospective_holdout_preserves_story_rows(self):
        m, a = fixture()
        p = m["participants"][0]
        m["evaluation_mode"] = "prospective_story_holdout"
        m["story_splits"] = {"story": "train", "heldout": "assessment"}
        p["expected_cells"] += [dict(c, story_id="heldout") for c in p["expected_cells"]]
        added = [dict(x, epoch_id=x["epoch_id"]+"h", stimulus_id=x["stimulus_id"]+"h", story_id="heldout") for x in p["epochs"]]
        p["stimulus_ids"] += [x["stimulus_id"] for x in added]
        p["stimulus_durations_sec"].update({x["stimulus_id"]: 2. for x in added})
        p["epochs"] += added
        a["p1"]["D"] = np.concatenate([a["p1"]["D"], a["p1"]["D"]], axis=1)
        r = e.evaluate(m, a)
        self.assertEqual({x["split"] for x in r["rows"]}, {"train", "assessment"})
        self.assertEqual(len(r["population_summary"]), 8)

    def test_no_out_of_bounds_or_nonfinite_or_assessment_selection(self):
        for mutation in ["out_of_bounds", "nonfinite", "selection"]:
            m, a = fixture()
            if mutation == "out_of_bounds": m["lags_sec"] = [-1., 0.]
            if mutation == "nonfinite": a["p1"]["D"][0, 0, 0, 0] = np.nan
            if mutation == "selection": m["selection_uses_assessment_effects"] = True
            with self.assertRaises(e.ContractError): e.evaluate(m, a)

    def test_summary_balances_participants_not_electrodes(self):
        common = dict(story_id="s", split="analysis", speech_rate=1., segment_duration_sec=.1, lag_sec=0., status="ok", same_context=1.)
        rows = [dict(common, participant_id="a", diff_context=1., normalized_ccc=1.)]
        rows += [dict(common, participant_id="b", diff_context=0., normalized_ccc=0.) for _ in range(9)]
        s = e.summarize(rows)[0]
        self.assertEqual(s["participant_balanced_ccc"], .5)
        self.assertEqual(s["n_electrodes"], 10)

    def test_ratio_of_means_is_not_mean_of_ratios(self):
        common = dict(story_id="s", split="analysis", speech_rate=1., segment_duration_sec=.1, lag_sec=0., status="ok", participant_id="a")
        rows = [dict(common, diff_context=.2, same_context=.2, normalized_ccc=1.),
                dict(common, diff_context=.2, same_context=.8, normalized_ccc=.25)]
        s = e.summarize(rows)[0]
        self.assertAlmostEqual(s["ratio_of_participant_balanced_means"], .4)
        self.assertAlmostEqual(s["participant_balanced_mean_of_ratios"], .625)

    def test_cli_pins_input_and_rejects_tampering(self):
        m, a = fixture()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            np.savez(root / "timecourses.npz", **a["p1"])
            digest = hashlib.sha256((root / "timecourses.npz").read_bytes()).hexdigest()
            m["participants"][0]["source"] = {"role": "empirical_electrode_timecourses", "npz_path": "timecourses.npz", "sha256": digest}
            (root / "manifest.json").write_text(json.dumps(m))
            subprocess.run([sys.executable, str(ROOT / "evaluator.py"), str(root / "manifest.json"), str(root / "result.json")], check=True, capture_output=True)
            r = json.loads((root / "result.json").read_text())
            self.assertEqual(r["input_receipts"][0]["sha256"], digest)
            m["participants"][0]["source"]["sha256"] = "0" * 64
            (root / "manifest.json").write_text(json.dumps(m))
            with self.assertRaises(e.ContractError): e.load_input(root / "manifest.json")


    def test_loaded_arrays_are_bound_to_captured_npz_after_path_replacement(self):
        m, arrays = fixture()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "timecourses.npz"
            np.savez(path, **arrays["p1"])
            original = path.read_bytes()
            m["participants"][0]["source"] = {"role": "empirical_electrode_timecourses",
                "npz_path": path.name, "sha256": hashlib.sha256(original).hexdigest()}
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(m))
            read_bytes = Path.read_bytes
            observed = []

            def capture_then_replace(selected):
                payload = read_bytes(selected)
                if selected == path:
                    observed.append(selected)
                    # A valid but different archive replaces the pathname after
                    # capture. The verified snapshot must still be consumed.
                    np.savez(path, D=arrays["p1"]["D"] + 100., t=arrays["p1"]["t"])
                return payload

            with mock.patch.object(Path, "read_bytes", capture_then_replace):
                _, loaded, receipts = e.load_input(manifest)
            self.assertEqual(observed, [path])
            np.testing.assert_array_equal(loaded["p1"]["D"], arrays["p1"]["D"])
            self.assertNotEqual(path.read_bytes(), original)
            self.assertEqual(receipts, [{"participant_id": "p1",
                "sha256": hashlib.sha256(original).hexdigest(), "bytes": len(original)}])

    def test_loaded_snapshot_survives_path_unlink_after_capture(self):
        m, arrays = fixture()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "timecourses.npz"
            np.savez(path, **arrays["p1"])
            original = path.read_bytes()
            m["participants"][0]["source"] = {"role": "empirical_electrode_timecourses",
                "npz_path": path.name, "sha256": hashlib.sha256(original).hexdigest()}
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps(m))
            read_bytes = Path.read_bytes

            def capture_then_unlink(selected):
                payload = read_bytes(selected)
                if selected == path:
                    path.unlink()
                return payload

            with mock.patch.object(Path, "read_bytes", capture_then_unlink):
                _, loaded, receipts = e.load_input(manifest)
            self.assertFalse(path.exists())
            np.testing.assert_array_equal(loaded["p1"]["t"], arrays["p1"]["t"])
            self.assertEqual(receipts[0]["bytes"], len(original))

    def test_cli_manifest_receipt_binds_evaluated_snapshot(self):
        m, arrays = fixture()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "timecourses.npz"
            np.savez(path, **arrays["p1"])
            m["participants"][0]["source"] = {"role": "empirical_electrode_timecourses",
                "npz_path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            manifest, output = root / "manifest.json", root / "result.json"
            payload = json.dumps(m).encode()
            manifest.write_bytes(payload)
            actual_evaluate = e.evaluate

            def evaluate_then_replace(selected_manifest, selected_arrays):
                result = actual_evaluate(selected_manifest, selected_arrays)
                # The output hash must still identify the manifest evaluated,
                # even if a concurrent writer changes or removes the pathname.
                manifest.unlink()
                return result

            with mock.patch.object(sys, "argv", ["evaluator.py", str(manifest), str(output)]):
                with mock.patch.object(e, "evaluate", evaluate_then_replace):
                    e.main()
            result = json.loads(output.read_text())
            self.assertFalse(manifest.exists())
            self.assertEqual(result["manifest_sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(result["cohort_id"], m["cohort_id"])
            self.assertEqual(len(result["rows"]), 4)

if __name__ == "__main__":
    unittest.main()
