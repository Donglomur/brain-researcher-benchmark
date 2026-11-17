"""Generated engineering controls, not authentic FAST or scientific validation."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

MODULE = Path(__file__).resolve().parents[1] / "evaluate.py"
spec = importlib.util.spec_from_file_location("fast_evaluator", MODULE)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        trace = np.array([10., 12., 10., 10., 20., 10., 11., 10.])
        self.clean = np.stack([trace, 2 * trace], axis=-1)[:, None, :]
        self.raw = self.clean + np.array([0, 0, 1, -1, 2, -1, 0, 1])[:, None, None]
        self.record = dict(id="r1", group_id="animal1", collection_id="fixture", split="test", kind="synthetic",
                           source_asset="generated-control-not-empirical", source_checksum="generated", export_provenance="test fixture",
                           roi_provenance="fixed disjoint masks", original_frame_count=8, frame_ids=list(range(8)),
                           frame_rate_hz=1000., exposure_ms=1., baseline_frames=[0, 1], event_windows=[[3, 6]], event_polarity=1,
                           raw=self.save("raw", self.raw), rois=self.save("roi", np.eye(2, dtype=np.uint8).reshape(2, 1, 2)),
                           clean=self.save("clean", self.clean), data_range=40.)
        self.panel = dict(task_id=e.TASK_ID, recipe="prospective-v1", freeze_provenance="generated fixture frozen independently", records=[self.record])
        self.submission = dict(task_id=e.TASK_ID, methods=[self.method("fast", "official_fast", self.clean), self.method("candidate", "candidate", self.raw)])

    def tearDown(self):
        self.temp.cleanup()

    def save(self, name, data):
        p = self.base / (name + ".npy")
        np.save(p, data)
        return dict(path=p.name, sha256=e.sha256(p))

    def timing(self):
        return dict(boundary=e.TIMING_BOUNDARY, hardware="generated CPU receipt", resource_budget_id="fixture-budget", measurement_provenance="generated",
                    clock="monotonic_seconds", start_s=0., end_s=.02, input_available_s=(np.arange(8)*.001).tolist(),
                    output_available_s=(np.arange(8)*.001+.002).tolist())

    def method(self, name, role, data):
        return dict(id=name, role=role, code_commit=e.SOURCE_COMMIT if role=="official_fast" else "fixture", implementation_provenance="generated fixture, not execution",
                    fit_provenance="generated frozen control", fit_group_ids=[], raw_test_adaptation=False, protected_reference_exposure=False,
                    temporal_window_frames=1, stride_frames=1, future_context_frames=0, predictions=[dict(record_id="r1", frame_ids=list(range(8)), output=self.save(name, data), timing=self.timing())])

    def evaluate(self):
        return e.evaluate(self.panel, self.submission, self.base, self.base)

    def test_analytic_image_error_and_temporal_controls(self):
        # Analytical error: each of two pixels receives the same scalar noise.
        report = self.evaluate()
        methods = report["records"][0]["methods"]
        expected = np.mean(np.array([0, 0, 1, -1, 2, -1, 0, 1]) ** 2)
        self.assertAlmostEqual(methods["raw"]["synthetic_image_error"]["mse"], expected)
        self.assertAlmostEqual(methods["raw"]["synthetic_image_error"]["psnr_db"], 10*np.log10(40**2/expected))
        self.assertEqual(methods["fast"]["synthetic_image_error"]["psnr_status"], "positive_infinity_exact_match")
        # Eight-frame float64 dot/norm arithmetic can round self-correlation below 1.
        # Allow 16 machine epsilons of absolute error, with no relative tolerance.
        perfect_r = methods["fast"]["traces"]["zero_lag_pearson_by_roi"]
        self.assertEqual(np.shape(perfect_r), (2,))
        np.testing.assert_allclose(perfect_r, [1., 1.],
                                   rtol=0., atol=16 * np.finfo(np.float64).eps)
        self.assertFalse(report["qualification"]["scientific"])
        json.dumps(report, allow_nan=False)
        a = np.array([0., 1., 0., -1.])
        self.assertAlmostEqual(e.correlation(a, a*2), 1.)
        self.assertAlmostEqual(e.correlation(a, np.roll(a, 1)), 0.)
        self.assertIsNone(e.correlation(a, np.zeros(4)))

    def test_extract_masks_and_frozen_baseline(self):
        traces = e.extract_traces(self.clean, np.ones((1,1,2),dtype=np.uint8))
        np.testing.assert_allclose(traces[:,0], self.clean.mean(axis=(1,2)))
        dff, baseline = e.delta_f_over_f(traces, [0,1])
        self.assertEqual(baseline[0], 16.5)
        self.assertAlmostEqual(dff[4,0], (30-16.5)/16.5)
        with self.assertRaises(e.ContractError):
            e.delta_f_over_f(np.zeros((4,1)), [0,1])
        with self.assertRaises(e.ContractError):
            e.extract_traces(self.clean, np.zeros((1,1,2)))
        with self.assertRaises(e.ContractError):
            e.extract_traces(self.clean, np.ones((2,1,2)))

    def test_real_data_never_get_clean_target_metrics(self):
        self.record["kind"] = "real_voltage"
        with self.assertRaisesRegex(e.ContractError, "clean-image"):
            self.evaluate()
        del self.record["clean"], self.record["data_range"]
        report = self.evaluate()
        self.assertEqual(report["records"][0]["reference_kind"], "none_no_clean_target")
        self.assertNotIn("synthetic_image_error", report["records"][0]["methods"]["raw"])
        self.record["electrophysiology"] = self.save("ephys", self.clean[:,0,:])
        self.record["synchronization_provenance"] = "generated already aligned frame mapping"
        self.record["reference_event_polarity"] = 1
        report = self.evaluate()
        self.assertEqual(report["records"][0]["reference_kind"], "synchronized_ephys_temporal_agreement_only")
        self.assertNotIn("synthetic_image_error", report["records"][0]["methods"]["fast"])

    def test_wrong_frame_order_shape_and_hash_rejected(self):
        pred = self.submission["methods"][1]["predictions"][0]
        pred["frame_ids"][0], pred["frame_ids"][1] = 1, 0
        with self.assertRaisesRegex(e.ContractError, "frame identities"):
            self.evaluate()
        pred["frame_ids"] = list(range(8))
        pred["output"] = self.save("cropped", self.raw[:-1])
        with self.assertRaisesRegex(e.ContractError, "every original"):
            self.evaluate()
        pred["output"]["sha256"] = "0"*64
        with self.assertRaisesRegex(e.ContractError, "SHA256"):
            self.evaluate()

    def test_split_and_population_mismatch_rejected(self):
        added = copy.deepcopy(self.record)
        added.update(id="r2", split="train")
        self.panel["records"].append(added)
        with self.assertRaisesRegex(e.ContractError, "crosses splits"):
            self.evaluate()
        added["group_id"] = "animal2"
        self.evaluate()
        added["split"] = "test"
        with self.assertRaisesRegex(e.ContractError, "all test"):
            self.evaluate()

    def test_timing_cannot_be_forward_only_partial_or_impossible(self):
        receipt = self.timing()
        m = e.timing_metrics(receipt, 8)
        self.assertEqual(m["throughput_fps"], 400.)
        self.assertAlmostEqual(m["frame_latency_ms_median"], 2.)
        for field, value in [("boundary", "forward"), ("output_available_s", [0]*8), ("output_available_s", [.01]*7)]:
            bad = copy.deepcopy(receipt)
            bad[field] = value
            with self.assertRaises(e.ContractError):
                e.timing_metrics(bad, 8)
        self.submission["methods"][1]["predictions"][0]["timing"]["hardware"] = "another GPU"
        with self.assertRaisesRegex(e.ContractError, "hardware"):
            self.evaluate()

    def test_constant_prediction_is_not_silently_dropped(self):
        self.submission["methods"][1] = self.method("candidate", "candidate", np.ones_like(self.raw)*10)
        report = self.evaluate()
        self.assertEqual(report["records"][0]["methods"]["candidate"]["traces"]["zero_lag_pearson_by_roi"], [None, None])
        aggregate = next(iter(report["grouped_temporal_agreement"]["candidate"].values()))
        self.assertIsNone(aggregate["equal_group_mean_pearson"])
        self.assertEqual(aggregate["group_count"], 1)

    def test_negative_spike_polarity(self):
        t = np.array([10.,12.,10.,10.,2.,10.,11.,10.])[:,None]
        self.record["event_polarity"] = -1
        m = e.trace_measurements(t, self.record, t)
        self.assertEqual(m["event_measurements"][0]["peak_frame"], [4])
        self.assertEqual(m["event_measurements"][0]["peak_time_error_ms"], [0.])

    def test_future_context_and_fit_declarations(self):
        with self.assertRaisesRegex(e.ContractError, "future context"):
            e.timing_metrics(self.timing(), 8, future_context_frames=4)
        self.submission["methods"][1]["fit_group_ids"] = ["animal1"]
        with self.assertRaisesRegex(e.ContractError, "fit groups"):
            self.evaluate()
        self.submission["methods"][1]["fit_group_ids"] = []
        self.submission["methods"][1]["raw_test_adaptation"] = True
        with self.assertRaisesRegex(e.ContractError, "held-out"):
            self.evaluate()

    def test_smoothing_cannot_hide_fast_event_loss(self):
        truth = np.ones((20,1))*10
        truth[10] = 20
        prediction = np.convolve(truth[:,0]-10, np.ones(5)/5, mode="same")[:,None]+10
        rec = dict(self.record, baseline_frames=[0,1], event_windows=[[8,13]], original_frame_count=20)
        ref, _ = e.delta_f_over_f(truth, rec["baseline_frames"])
        metrics = e.trace_measurements(prediction, rec, ref)
        self.assertLess(metrics["zero_lag_pearson_by_roi"][0], .5)
        self.assertAlmostEqual(metrics["event_measurements"][0]["peak_dff_error"][0], -.8)

    def test_synthetic_rejects_ephys_polarity_and_preserves_perfect_events(self):
        self.record["reference_event_polarity"] = -1
        with self.assertRaisesRegex(e.ContractError, "ephys-only"):
            self.evaluate()
        # Defense in depth: direct helper still uses the synthetic trace polarity.
        traces = e.extract_traces(self.clean, np.eye(2, dtype=np.uint8).reshape(2,1,2))
        ref, _ = e.delta_f_over_f(traces, self.record["baseline_frames"])
        m = e.trace_measurements(traces, self.record, ref)
        self.assertEqual(m["event_measurements"][0]["peak_time_error_ms"], [0., 0.])
        self.assertEqual(m["event_measurements"][0]["peak_dff_error"], [0., 0.])

    def test_cli_pins_and_report(self):
        p, s, out = [self.base / name for name in ["panel.json", "submission.json", "report.json"]]
        p.write_text(json.dumps(self.panel))
        s.write_text(json.dumps(self.submission))
        command = [sys.executable, "-B", str(MODULE), "--panel", str(p), "--panel-sha256", e.sha256(p), "--submissions", str(s), "--output", str(out)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(out.read_text())
        self.assertEqual(report["input_pins"]["panel_sha256"], e.sha256(p))
        command[command.index("--panel-sha256")+1] = "0"*64
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
